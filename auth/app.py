"""
Backend de acceso a /docs/ para la landing de Restolibra.

No guarda usuarios propios: cada login se valida en tiempo real contra la
instancia real del cliente (POST {dominio}/api/auth/verify), reutilizando el
auth que ya existe en cada contenedor. La lista de empresas para el <select>
se pide al backoffice (admin.restolibra.com.ar/api/clientes-publicos).

Server-to-server: ambas llamadas usan el secreto compartido DOCS_AUTH_SECRET.
"""
import os
import re
import time

import httpx
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

DOCS_AUTH_SECRET = os.environ.get("DOCS_AUTH_SECRET", "")
SECRET_KEY       = os.environ.get("SECRET_KEY", "restolibra-docs-secret-change-me")
ADMIN_API_URL    = os.environ.get("ADMIN_API_URL", "https://admin.restolibra.com.ar")

COOKIE_NAME  = "docs_session"
MAX_AGE      = 86400 * 7  # 7 días, igual que la sesión de la app
DOMAIN_RE    = re.compile(r"^[a-z0-9-]+\.restolibra\.com\.ar$")

_signer = URLSafeTimedSerializer(SECRET_KEY)

app = FastAPI(title="Restolibra Docs Auth", docs_url=None, redoc_url=None)

_clientes_cache: dict = {"data": [], "ts": 0}
_CACHE_TTL = 300  # 5 min


async def get_clientes() -> list[dict]:
    now = time.time()
    if now - _clientes_cache["ts"] < _CACHE_TTL and _clientes_cache["data"]:
        return _clientes_cache["data"]
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                f"{ADMIN_API_URL}/api/clientes-publicos",
                headers={"X-Internal-Auth": DOCS_AUTH_SECRET},
            )
        r.raise_for_status()
        clientes = r.json().get("clientes", [])
        _clientes_cache["data"] = clientes
        _clientes_cache["ts"] = now
        return clientes
    except httpx.HTTPError:
        # Si el backoffice no responde, se sigue sirviendo la última lista conocida.
        return _clientes_cache["data"]


def _render_login(error: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Acceso a Documentación · Restolibra</title>
<meta name="robots" content="noindex">
<style>
  body {{ font-family: 'Inter', system-ui, sans-serif; background:#fbf9f6; color:#292019;
         display:flex; align-items:center; justify-content:center; min-height:100vh; margin:0; }}
  .card {{ background:#fff; border:1px solid #e7e0d8; border-radius:12px; padding:2rem;
           box-shadow:0 4px 24px rgba(0,0,0,.08); width:100%; max-width:380px; }}
  h1 {{ font-size:1.25rem; margin:0 0 1.25rem; }}
  label {{ display:block; font-size:.85rem; margin:.75rem 0 .25rem; color:#78716c; }}
  select, input {{ width:100%; padding:.6rem .75rem; border:1px solid #e7e0d8; border-radius:8px;
                   font-size:1rem; box-sizing:border-box; }}
  button {{ width:100%; margin-top:1.25rem; padding:.7rem; background:#ea580c; color:#fff;
            border:none; border-radius:8px; font-size:1rem; cursor:pointer; }}
  button:hover {{ background:#c2410c; }}
  .error {{ background:#fef2f2; color:#b91c1c; padding:.6rem .75rem; border-radius:8px;
            font-size:.85rem; margin-bottom:1rem; }}
  a {{ color:#ea580c; text-decoration:none; font-size:.85rem; }}
</style>
</head>
<body>
  <div class="card">
    <h1>Documentación del sistema</h1>
    {'<div class="error">' + error + '</div>' if error else ''}
    <form method="post" action="/login-docs">
      <label for="slug">Tu restaurante</label>
      <select name="slug" id="slug" required>
        <option value="">Seleccioná tu restaurante…</option>
        {''.join(f'<option value="{c["slug"]}">{c["nombre"]}</option>' for c in _clientes_cache["data"])}
      </select>
      <label for="username">Usuario</label>
      <input type="text" name="username" id="username" required autocomplete="username">
      <label for="password">Contraseña</label>
      <input type="password" name="password" id="password" required autocomplete="current-password">
      <button type="submit">Ingresar</button>
    </form>
    <p style="margin-top:1rem"><a href="/">&larr; Volver al sitio</a></p>
  </div>
</body>
</html>"""


@app.get("/login-docs", response_class=HTMLResponse)
async def login_form():
    await get_clientes()
    return _render_login()


@app.post("/login-docs", response_class=HTMLResponse)
async def login_submit(slug: str = Form(...), username: str = Form(...), password: str = Form(...)):
    clientes = await get_clientes()
    cliente = next((c for c in clientes if c["slug"] == slug), None)
    if not cliente:
        return HTMLResponse(_render_login("Restaurante no encontrado. Volvé a intentarlo."), status_code=400)

    domain = cliente.get("domain", "")
    if not DOMAIN_RE.match(domain):
        return HTMLResponse(_render_login("Configuración de restaurante inválida."), status_code=400)

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.post(
                f"https://{domain}/api/auth/verify",
                headers={"X-Internal-Auth": DOCS_AUTH_SECRET},
                json={"username": username, "password": password},
            )
        data = r.json() if r.status_code == 200 else {"valid": False}
    except httpx.HTTPError:
        return HTMLResponse(_render_login("No se pudo contactar al sistema. Probá de nuevo en unos minutos."), status_code=502)

    if not data.get("valid"):
        return HTMLResponse(_render_login("Usuario o contraseña incorrectos."), status_code=401)

    token = _signer.dumps({"slug": slug, "username": username})
    resp = RedirectResponse("/docs/", status_code=303)
    resp.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", max_age=MAX_AGE)
    return resp


@app.get("/logout-docs")
async def logout():
    resp = RedirectResponse("/login-docs", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp


@app.get("/check", include_in_schema=False)
async def check(request: Request):
    """Endpoint interno para el auth_request de nginx: 200 si la cookie es válida, 401 si no."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return Response(status_code=401)
    try:
        _signer.loads(token, max_age=MAX_AGE)
    except (BadSignature, SignatureExpired):
        return Response(status_code=401)
    return Response(status_code=200)
