# Imagen base compartida con Contalibra/Gestiolibra/MedLibra/VentaLibra
# (nginx.conf era identico salvo el upstream de auth, extraido 2026-07-26 --
# ver wiki/analyses/auditoria-duplicacion-familia-libra.md, P3 continuacion).
# AUTH_UPSTREAM se setea via docker-compose.yml.
FROM ghcr.io/marianocappucci/libra-nginx-web:v0.2.0
COPY public/ /usr/share/nginx/html/
EXPOSE 80
