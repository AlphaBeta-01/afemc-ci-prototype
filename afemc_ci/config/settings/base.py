"""Configuration commune (§ 5.3.3 du mémoire)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'cle-de-developpement-a-remplacer')
DEBUG = False
ALLOWED_HOSTS = [h for h in os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',') if h]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'anymail',
    # Applications du projet
    'apps.core',
    'apps.accounts',
    'apps.sections',
    'apps.membres',
    'apps.adhesions',
    'apps.cotisations',
    'apps.relances',
    'apps.notifications',
    'apps.dashboard',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # fichiers statiques, sans serveur dédié
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
            'apps.dashboard.context_processors.a_faire',
        ],
    },
}]

WSGI_APPLICATION = 'config.wsgi.application'

# ----- Base de données : PostgreSQL (§ 5.2.3) -----
if os.environ.get('USE_SQLITE') == '1':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('POSTGRES_DB', 'afemc_ci'),
            'USER': os.environ.get('POSTGRES_USER', 'afemc'),
            'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
            'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
            'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        }
    }

AUTH_USER_MODEL = 'accounts.Utilisateur'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Abidjan'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ----- Fichiers déposés par les candidates (pièces justificatives, § 5.5.4) -----
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'
TAILLE_MAX_PIECE_JUSTIFICATIVE = 5 * 1024 * 1024          # 5 Mo

# Cache adossé à la base (table créée par `createcachetable`, lancé au build) :
# compteurs des limites de fréquence (apps.core.limites) partagés entre les
# processus du serveur et préservés lors des redémarrages.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'afemc_cache',
    }
}

LOGIN_URL = 'accounts:connexion'
LOGIN_REDIRECT_URL = 'dashboard:accueil'
LOGOUT_REDIRECT_URL = 'accounts:connexion'

SESSION_COOKIE_AGE = 60 * 60 * 4
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Sans ceci, une exception non gérée (500) ne s'affiche nulle part une fois
# DEBUG=False : le handler « console » par défaut de Django est filtré par
# require_debug_true, et « mail_admins » ne fait rien tant qu'ADMINS est
# vide. Un handler console explicite, non filtré, garantit que le traceback
# atteint toujours stderr — donc les journaux de l'hébergeur (Render, etc.).
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'django.request': {'handlers': ['console'], 'level': 'ERROR', 'propagate': False},
    },
}

# ----- Paramètres fonctionnels de l'association -----
EMAIL_EXPEDITEUR = os.environ.get('EMAIL_EXPEDITEUR', 'gestion@afemc-ci.org')
COTISATION_MONTANT_DEFAUT = int(os.environ.get('COTISATION_MONTANT_DEFAUT', 25000))
MAX_TENTATIVES_CONNEXION = 5
MAX_TENTATIVES_NOTIFICATION = 3

# Base des liens absolus insérés dans les courriels (ex. activation de compte),
# construits hors du contexte d'une requête HTTP.
SITE_URL = os.environ.get('SITE_URL', 'http://127.0.0.1:8000').rstrip('/')

# Jeton attendu par apps.core.views.executer_taches_planifiees, appelée par un
# ordonnanceur externe (§ 7 du README) là où aucun worker Celery en arrière-plan
# n'est disponible (plan gratuit Render notamment). Vide par défaut : la vue
# refuse alors toute requête, y compris avec un jeton vide côté appelant.
CRON_SECRET = os.environ.get('CRON_SECRET', '')

# Identifiants du compte administrateur créé par apps.core.views.amorcer_administrateur
# (protégée par le même CRON_SECRET) — seul moyen de créer le premier compte
# sans accès Shell, indisponible sur le plan gratuit Render (§ 7 du README).
SUPERUSER_BOOTSTRAP_EMAIL = os.environ.get('SUPERUSER_BOOTSTRAP_EMAIL', '')
SUPERUSER_BOOTSTRAP_PASSWORD = os.environ.get('SUPERUSER_BOOTSTRAP_PASSWORD', '')

# ----- File de tâches asynchrones (Celery/Redis, § 5.6.1) -----
# Redis sert à la fois de courtier de messages et de stockage des résultats.
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Transport fichier (Kombu) : à activer explicitement (jamais par défaut) pour
# faire tourner un vrai worker/beat sans dépendre de Redis — utile en
# développement sur une machine où Redis n'est pas installable (ex. Windows
# sans WSL). Sans objet en production, où CELERY_BROKER_URL pointe Redis.
if CELERY_BROKER_URL.startswith('filesystem://'):
    # Un seul dossier partagé : ce que le producteur (beat) écrit dans
    # `data_folder_out` doit être exactement ce que le consommateur (worker)
    # lit dans `data_folder_in` — les deux doivent donc être identiques.
    _dossier_file_attente = BASE_DIR / 'var' / 'celery-filequeue'
    for _sous_dossier in ('file', 'traitees'):
        (_dossier_file_attente / _sous_dossier).mkdir(parents=True, exist_ok=True)
    CELERY_BROKER_TRANSPORT_OPTIONS = {
        'data_folder_in': str(_dossier_file_attente / 'file'),
        'data_folder_out': str(_dossier_file_attente / 'file'),
        'data_folder_processed': str(_dossier_file_attente / 'traitees'),
    }
    CELERY_RESULT_BACKEND = None  # résultats non nécessaires : effets observés en base
