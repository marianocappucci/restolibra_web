"""
Backend de acceso a /docs/ para la landing de Restolibra.

No guarda usuarios propios: cada login se valida en tiempo real contra la
instancia real del cliente (POST https://{subdominio}.restolibra.com.ar/api/auth/verify),
reutilizando el auth que ya existe en cada contenedor. El usuario escribe
directamente su subdominio (el mismo que usa para entrar al sistema) en vez
de elegirlo de un <select> poblado por el backoffice -- mismo patrón que
gestiolibra_web/medlibra_web/ventalibra_web, normalizado acá el 2026-07-26
para que los cinco productos de la familia usen el mismo mecanismo de login
de documentación.

Server-to-server: la llamada usa el secreto compartido DOCS_AUTH_SECRET.
"""
import os
import re

import httpx
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

DOCS_AUTH_SECRET = os.environ.get("DOCS_AUTH_SECRET", "")
SECRET_KEY       = os.environ.get("SECRET_KEY", "restolibra-docs-secret-change-me")
APEX_DOMAIN      = os.environ.get("APEX_DOMAIN", "restolibra.com.ar")

COOKIE_NAME  = "docs_session"
MAX_AGE      = 86400 * 7  # 7 dias
SLUG_RE      = re.compile(r"^[a-z0-9-]{1,63}$")

_signer = URLSafeTimedSerializer(SECRET_KEY)

app = FastAPI(title="Restolibra Docs Auth", docs_url=None, redoc_url=None)


def _render_login(error: str = "", slug: str = "", username: str = "") -> str:
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
  .domain-row {{ display:flex; align-items:stretch; border:1px solid #e7e0d8; border-radius:8px; overflow:hidden; }}
  .domain-row input {{ border:none; flex:1; min-width:0; }}
  .domain-row span {{ background:#f5f0e8; color:#78716c; padding:.6rem .6rem; font-size:.85rem;
                       white-space:nowrap; display:flex; align-items:center; }}
  input {{ width:100%; padding:.6rem .75rem; border:1px solid #e7e0d8; border-radius:8px;
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
      <label for="slug">Tu subdominio</label>
      <div class="domain-row">
        <input type="text" name="slug" id="slug" required autocomplete="off"
               placeholder="tu-restaurante" value="{slug}">
        <span>.{APEX_DOMAIN}</span>
      </div>
      <label for="username">Usuario</label>
      <input type="text" name="username" id="username" required autocomplete="username" value="{username}">
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
    return _render_login()


@app.post("/login-docs", response_class=HTMLResponse)
async def login_submit(slug: str = Form(...), username: str = Form(...), password: str = Form(...)):
    slug = slug.strip().lower()
    if not SLUG_RE.match(slug):
        return HTMLResponse(_render_login("Subdominio inválido.", slug, username), status_code=400)

    domain = f"{slug}.{APEX_DOMAIN}"
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.post(
                f"https://{domain}/api/auth/verify",
                headers={"X-Internal-Auth": DOCS_AUTH_SECRET},
                json={"username": username, "password": password},
            )
        data = r.json() if r.status_code == 200 else {"valid": False}
    except httpx.HTTPError:
        return HTMLResponse(
            _render_login("No se pudo contactar a tu instancia. Revisá el subdominio e intentá de nuevo.", slug, username),
            status_code=502,
        )

    if not data.get("valid"):
        return HTMLResponse(_render_login("Subdominio, usuario o contraseña incorrectos.", slug, username), status_code=401)

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
