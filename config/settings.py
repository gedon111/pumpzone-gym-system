"""
Settings for the Pumpzone membership system.

Anything secret or machine-specific is read from environment variables,
so the same code runs on your laptop, a server, or (later) a Docker
container. Every variable has a safe default for LOCAL development only.
"""

import os
from pathlib import Path

# Folder that holds manage.py.
BASE_DIR = Path(__file__).resolve().parent.parent

# Where the database (and later, backups) live. Kept separate from the code
# so a Docker volume or a server folder can be mounted here later.
DATA_DIR = Path(os.environ.get("PUMPZONE_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# SECURITY: the default key is for local development only. On a real server,
# set PUMPZONE_SECRET_KEY to a long random string.
SECRET_KEY = os.environ.get(
    "PUMPZONE_SECRET_KEY", "dev-only-insecure-key-change-me-on-a-server"
)

# DEBUG shows detailed error pages. Never leave it on for a live server.
DEBUG = os.environ.get("PUMPZONE_DEBUG", "1") == "1"

# Host names this app answers to, comma separated.
ALLOWED_HOSTS = os.environ.get("PUMPZONE_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "gym",  # our app: members, memberships, payments
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Every page needs a login unless a view is explicitly marked public.
    # This is safer than remembering to protect each page one by one.
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "gym.context_processors.pumpzone",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# One SQLite file. Backing up = copying this file.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Login flow: where to send people who are not signed in, and where to go after.
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

# Philippine time. "Today" for expiry checks always means today in Manila.
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = DATA_DIR / "staticfiles"  # used later by `collectstatic` on a server

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Pumpzone business rules -------------------------------------------------
# Days before a membership end date that it counts as "expiring".
EXPIRING_WITHIN_DAYS = 7
# Days after a membership starts before an unpaid balance counts as "late".
GRACE_DAYS = int(os.environ.get("PUMPZONE_GRACE_DAYS", "3"))
