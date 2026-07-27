"""Backend de acceso a /docs/ para la landing de Restolibra -- config sobre
libra_web_kit.docs_auth (extraído 2026-07-26, ver
wiki/analyses/auditoria-duplicacion-familia-libra.md)."""
from libra_web_kit.docs_auth import build_docs_login_app, DocsLoginTheme

app = build_docs_login_app(
    product_name="Restolibra",
    apex_domain_default="restolibra.com.ar",
    secret_key_env="SECRET_KEY",
    secret_key_default="restolibra-docs-secret-change-me",
    verify_path="/api/auth/verify",
    slug_placeholder="tu-restaurante",
    theme=DocsLoginTheme(
        accent="#ea580c", accent_hover="#c2410c",
        bg="#fbf9f6", fg="#292019", border="#e7e0d8",
        muted_fg="#78716c", muted_bg="#f5f0e8",
    ),
)
