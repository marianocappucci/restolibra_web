FROM python:3.12-slim
WORKDIR /app

# requirements.txt referencia libra-web-kit (backend de login compartido
# por las 5 landings, extraido 2026-07-26 -- ver
# wiki/analyses/auditoria-duplicacion-familia-libra.md) via git+https, asi
# funciona tambien el dev local en WSL sin identidad SSH propia. El build
# en el VPS reescribe la URL a git+ssh (--mount=type=ssh, deploy key de
# solo lectura dedicada -- GitHub no permite reusar una deploy key entre
# repos) y la descarta con la imagen: ninguna clave queda en ninguna capa.
RUN apt-get update && apt-get install -y --no-install-recommends git openssh-client && rm -rf /var/lib/apt/lists/*
RUN mkdir -p -m 0700 /root/.ssh \
    && ssh-keyscan github.com >> /root/.ssh/known_hosts 2>/dev/null \
    && printf 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINZ2l1pBBHhFIgKFpoW1485sEtImpuF3jyc1msT4n88f deploy-key-libra-web-kit-readonly\n' > /root/.ssh/id_libra_web_kit.pub \
    && printf 'Host github-libra-web-kit\n  HostName github.com\n  User git\n  HostKeyAlias github.com\n  IdentityFile /root/.ssh/id_libra_web_kit.pub\n  IdentitiesOnly yes\n' > /root/.ssh/config \
    && chmod 600 /root/.ssh/config /root/.ssh/id_libra_web_kit.pub
COPY requirements.txt .
RUN --mount=type=ssh \
    git config --global url."ssh://git@github-libra-web-kit/marianocappucci/libra-web-kit.git".insteadOf "https://github.com/marianocappucci/libra-web-kit.git" \
    && pip install --no-cache-dir -r requirements.txt \
    && git config --global --unset url."ssh://git@github-libra-web-kit/marianocappucci/libra-web-kit.git".insteadOf
COPY app.py .
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
