"""Configuração do Django. Tudo que varia por ambiente vem de variável de ambiente."""

import os
from pathlib import Path
from urllib.parse import ParseResult, parse_qs, unquote, urlparse

from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, "1" if default else "0").strip().lower() in ("1", "true", "yes")


def _env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def _database_from_url(url: str) -> dict[str, object]:
    parsed = urlparse(url)
    if parsed.scheme not in ("postgres", "postgresql"):
        raise ImproperlyConfigured("DATABASE_URL precisa ser postgres://usuario:senha@host:porta/banco")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or 5432),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }


DEBUG = _env_bool("DJANGO_DEBUG")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured("Defina DJANGO_SECRET_KEY. Não existe chave padrão.")

ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS")

# Endereço público do site, usado nos links de convite e nos e-mails.
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")
if not SITE_URL:
    raise ImproperlyConfigured("Defina SITE_URL com o endereço público do site.")

if "DATABASE_URL" not in os.environ:
    raise ImproperlyConfigured("Defina DATABASE_URL.")
DATABASES = {"default": _database_from_url(os.environ["DATABASE_URL"])}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Um módulo por bounded context (docs/domain/strategic-design.md).
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "kernel",
    "auditoria",
    "acesso",
    "permissoes",
    "notificacoes",
    "marca",
    "aprovacoes",
    "comunicacao",
    "financeiro",
    "eventos",
    "relatorios",
]

MIDDLEWARE = [
    "kernel.logging.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    }
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Identidade e sessão (ADR-008).
AUTH_USER_MODEL = "acesso.Usuario"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.Argon2PasswordHasher"]
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        "OPTIONS": {"user_attributes": ("nome_de_usuario", "email", "nome")},
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
# Sessão no banco: 7 dias sem uso, renovados a cada requisição.
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 7 * 24 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_FAILURE_VIEW = "kernel.errors.csrf_failure"
# Login com o Google: sem o ID de cliente, as rotas do Google recusam tudo e o site esconde o botão.
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_VERIFIER = "acesso.google.VerificadorGoogleReal"
# Link de recuperação de senha: 1 hora.
PASSWORD_RESET_TIMEOUT = 60 * 60

# Contadores de tentativas (kernel.rate_limit) ficam no Redis que já serve de fila.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    }
}

# Segurança de transporte: ligada sempre que não for depuração local.
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

REST_FRAMEWORK = {
    # Sessão no servidor (ADR-008). A permissão padrão nega tudo: cada rota aberta declara isso
    # explicitamente.
    "DEFAULT_AUTHENTICATION_CLASSES": ["kernel.http.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "kernel.errors.exception_handler",
    "COERCE_DECIMAL_TO_STRING": True,
    # A API só fala JSON; o cliente de teste do DRF segue o mesmo padrão.
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Club Manager API",
    "DESCRIPTION": "API única do Club Manager, usada pelo site e, depois, pelo aplicativo.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Os arquivos da página de documentação vêm da própria imagem, não de uma CDN.
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "SCHEMA_PATH_PREFIX": "/api/v1",
}

# Fila e agendador (ADR-006).
CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = None
CELERY_TASK_IGNORE_RESULT = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 200
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True


def _starttls_da_url(parsed: ParseResult) -> bool:
    """`?tls=0` desliga a criptografia, só para o servidor de e-mail de desenvolvimento (Mailpit).

    Só vale em `smtp://`, e é a única opção aceita na consulta: um erro de digitação não pode virar um
    servidor sem criptografia por engano.
    """
    if not parsed.query:
        return True
    if parsed.scheme != "smtp" or parse_qs(parsed.query, keep_blank_values=True) != {"tls": ["0"]}:
        raise ImproperlyConfigured("EMAIL_URL só aceita ?tls=0 na consulta, e só em smtp://")
    return False


def _mailer_from_url(url: str) -> dict[str, object]:
    """`smtp://usuario:senha@host:porta` (STARTTLS) ou `smtps://…` (TLS direto)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("smtp", "smtps"):
        raise ImproperlyConfigured("EMAIL_URL precisa ser smtp://usuario:senha@host:porta ou smtps://…")
    starttls = _starttls_da_url(parsed)
    return {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {
            "host": parsed.hostname or "",
            "port": parsed.port or (465 if parsed.scheme == "smtps" else 587),
            "username": unquote(parsed.username or ""),
            "password": unquote(parsed.password or ""),
            "use_ssl": parsed.scheme == "smtps",
            "use_tls": parsed.scheme == "smtp" and starttls,
            "timeout": 10,
        },
    }


# E-mail: SMTP genérico por variável de ambiente (AD-012). Sem EMAIL_URL, os e-mails saem no log.
MAILERS = {
    "default": _mailer_from_url(os.environ["EMAIL_URL"])
    if os.environ.get("EMAIL_URL")
    else {"BACKEND": "django.core.mail.backends.console.EmailBackend"}
}
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Club Manager <nao-responda@localhost>")

CELERY_BEAT_SCHEDULE = {
    "acesso.descartar_cadastros_vencidos": {
        "task": "acesso.descartar_cadastros_vencidos",
        "schedule": 60 * 60,
    },
    # Uma vez por dia, de manhã (adendo 1 da spec do motor, A10).
    "aprovacoes.lembrar_solicitacoes_paradas": {
        "task": "aprovacoes.lembrar_solicitacoes_paradas",
        "schedule": crontab(minute=0, hour=8),
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "kernel.logging.JsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}
