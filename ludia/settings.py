from pathlib import Path

from django.utils.translation import gettext_noop
from environs import Env

env = Env()
env.read_env()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 3600

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # 1st party
    "ludia.users",
    "ludia.styles",
    "ludia.contacts",
    # 3rd party
    "django_probes",
    "debug_toolbar",
    "widget_tweaks",
    "django_tables2",
    "django_cleanup.apps.CleanupConfig",
    "mozilla_django_oidc",
]

MIDDLEWARE = [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "mozilla_django_oidc.middleware.SessionRefresh",
    "django.middleware.locale.LocaleMiddleware",
]

ROOT_URLCONF = "ludia.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "ludia.wsgi.application"

DATABASES = {
    "default": env.dj_db_url("DATABASE_URL", default="sqlite://:memory:"),
}

AUTH_USER_MODEL = "users.User"
AUTH_PASSWORD_VALIDATORS = []
AUTHENTICATION_BACKENDS = [
    "ludia.users.auth.OIDC",
    "django.contrib.auth.backends.ModelBackend",
]
LOGIN_URL = "oidc_authentication_init"
OIDC_OP_JWKS_ENDPOINT = "https://bridz.sluzby.fmph.uniba.sk/keys"
OIDC_OP_AUTHORIZATION_ENDPOINT = "https://bridz.sluzby.fmph.uniba.sk/authorize"
OIDC_OP_USER_ENDPOINT = "https://bridz.sluzby.fmph.uniba.sk/userinfo"
OIDC_OP_TOKEN_ENDPOINT = "https://bridz.sluzby.fmph.uniba.sk/token"
OIDC_RP_SCOPES = "openid email profile"
OIDC_RP_SIGN_ALGO = "RS256"
OIDC_RP_CLIENT_ID = env("OIDC_RP_CLIENT_ID", default="")
OIDC_RP_CLIENT_SECRET = env("OIDC_RP_CLIENT_SECRET", default="")
OIDC_OP_LOGOUT_URL_METHOD = "ludia.users.auth.logout_url"
OIDC_RENEW_ID_TOKEN_EXPIRY_SECONDS = 3600  # 1-hour
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

LANGUAGE_CODE = "sk"
LANGUAGES = [
    ("en", gettext_noop("English")),
    ("sk", gettext_noop("Slovak")),
]
TIME_ZONE = "Europe/Bratislava"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "static"
MEDIA_URL = "uploads/"
MEDIA_ROOT = BASE_DIR / "uploads"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

email = env.dj_email_url("EMAIL_URL", default="consolemail://")
vars().update(email)
DEFAULT_FROM_EMAIL = env("EMAIL_FROM", default="Django <django@localhost>")


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "log_format": {
            "format": "[%(levelname)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "log_format",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "ludia": {
            "handlers": ["console"],
            "level": "INFO",
        },
    },
}

DJANGO_TABLES2_TABLE_ATTRS = {
    "class": "table",
}
DJANGO_TABLES2_TEMPLATE = "tables/jds.html"

CIT_API_USERNAME = env("CIT_API_USERNAME", default="")
CIT_API_PASSWORD = env("CIT_API_PASSWORD", default="")

if DEBUG:
    import socket

    # add Docker IPs to INTERNAL_IPS (for DjDT)
    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS = [ip[:-1] + "1" for ip in ips] + ["127.0.0.1"]
