import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'development-only-change-before-deployment')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DJANGO_DEBUG', 'true').lower() == 'true'
if not DEBUG and SECRET_KEY == 'development-only-change-before-deployment':
    raise RuntimeError('Set DJANGO_SECRET_KEY before running with DEBUG disabled.')

# ALLOWED_HOSTS = [host.strip() for host in os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if host.strip()]
ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'jazzmin',
    'config',
    'accounts',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'book_shop.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'book_shop.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]
AUTH_USER_MODEL = 'config.CustomUser'
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = 'login'


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True


USE_TZ = True


# Telegram Bot Settings
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_ADMIN_CHAT_ID = os.environ.get('TELEGRAM_ADMIN_CHAT_ID', '')



# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Presentation settings for the existing Jazzmin admin.
JAZZMIN_SETTINGS = {
    "site_title": "Comabooks — Управление",
    "site_header": "Comabooks",
    "site_brand": "comabooks",
    "welcome_sign": "Войдите в панель управления",
    "copyright": "Comabooks",
    "site_logo": "images/admin-mark.svg",
    "custom_css": "css/admin.css",
    "use_google_fonts_cdn": False,
    "show_ui_builder": False,
    "navigation_expanded": True,
    "search_model": ["config.Book", "config.CustomUser"],
    "topmenu_links": [
        {"name": "Открыть сайт", "url": "home", "new_window": True},
    ],
    "order_with_respect_to": ["config", "auth",
        "config.Book", "config.CustomUser", "config.BookPageAnswer",
        "config.BookPageQuestion", "config.BookDedication", "config.BookCover",
        "config.Review", "config.AISettings", "auth.Group",
    ],
    "icons": {
        "config.Book": "fas fa-book",
        "config.CustomUser": "fas fa-users",
        "config.BookPageAnswer": "fas fa-pen",
        "config.BookPageQuestion": "fas fa-question-circle",
        "config.BookDedication": "fas fa-heart",
        "config.BookCover": "fas fa-image",
        "config.Review": "fas fa-star",
        "config.AISettings": "fas fa-magic",
        "auth.Group": "fas fa-user-shield",
    },
    "changeform_format": "single",
}



# Millimetres. A full flat cover spread is generated only with a printer-approved spine.
BOOK_PRINT = {
    "width_mm": 148, "height_mm": 210,
    "inner_mm": 22, "outer_mm": 16, "top_mm": 18, "bottom_mm": 20,
    "bleed_mm": 3, "spine_mm": None,
}
