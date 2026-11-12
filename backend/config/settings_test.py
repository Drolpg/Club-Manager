"""Configuração dos testes: roda sem depender do ambiente, contra o PostgreSQL do compose local.

No CI, o DATABASE_URL vem do ambiente. Na máquina de desenvolvimento, a senha do banco é lida do .env da raiz,
que é o mesmo que o compose usa.
"""

import os
from pathlib import Path


def _dotenv() -> dict[str, str]:
    path = Path(__file__).resolve().parents[2] / ".env"
    if not path.exists():
        return {}
    pairs = (line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines() if "=" in line)
    return {key.strip(): value.strip() for key, value in pairs if not key.lstrip().startswith("#")}


_env = _dotenv()
_db_url = "postgres://{user}:{password}@127.0.0.1:5433/{name}".format(
    user=_env.get("POSTGRES_USER", "clubmanager"),
    password=_env.get("POSTGRES_PASSWORD", "clubmanager"),
    name=_env.get("POSTGRES_DB", "clubmanager"),
)

os.environ.setdefault("DATABASE_URL", _db_url)
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6380/0")
# Fixos de propósito: os testes não usam os segredos do .env.
os.environ["DJANGO_SECRET_KEY"] = "so-para-testes"
os.environ["DJANGO_DEBUG"] = "0"
os.environ["DJANGO_ALLOWED_HOSTS"] = "testserver,localhost"

from config.settings import *

# As tarefas rodam na hora, dentro do teste, sem worker nem Redis.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
# Os testes não servem arquivos estáticos.
MIDDLEWARE = [item for item in MIDDLEWARE if "whitenoise" not in item]
