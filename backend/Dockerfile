# A mesma imagem serve a API (gunicorn) e o worker (celery), em desenvolvimento e em produção (RNF-03).
FROM python:3.14-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/opt/venv/bin:$PATH"

RUN useradd --create-home --uid 10001 app
COPY --from=build /opt/venv /opt/venv

WORKDIR /app
COPY --chown=app:app . .

# Os arquivos estáticos (documentação da API) são coletados na imagem; a chave e o banco aqui são só para o comando rodar.
RUN DJANGO_SECRET_KEY=build DATABASE_URL=postgres://build:build@localhost/build SITE_URL=http://build \
    python manage.py collectstatic --noinput && chown -R app:app /app/staticfiles

USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]
