"""Configuration de production (§ 5.10.2)."""
from .base import *  # noqa

DEBUG = False

# Manifeste strict (échoue si un fichier référencé n'a pas été collecté) —
# volontairement réservé à la production : en dev/tests, `collectstatic`
# n'a jamais tourné, et cette variante lèverait une erreur sur chaque
# `{% static %}`. Le build Render exécute `collectstatic` avant chaque
# démarrage (voir README), donc le manifeste existe toujours ici.
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

# Envoi via l'API HTTP de Brevo (port 443), pas en SMTP : le SMTP sortant
# (port 587) s'est révélé peu fiable depuis le réseau gratuit de Render —
# connexions qui restaient bloquées en `socket.connect()` jusqu'à ce que
# gunicorn tue le worker (timeout), avant même qu'une erreur propre ne
# remonte. Le HTTPS standard n'a pas ce problème.
EMAIL_BACKEND = 'anymail.backends.brevo.EmailBackend'
ANYMAIL = {'BREVO_API_KEY': os.environ.get('BREVO_API_KEY', '')}

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Render (et la plupart des PaaS) placent l'application derrière un proxy qui
# termine le HTTPS et transmet en HTTP en interne : sans cet en-tête, Django
# ne reconnaît jamais la requête comme sécurisée et SECURE_SSL_REDIRECT
# provoque une boucle de redirection infinie.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Render fournit automatiquement le nom d'hôte attribué (ex. afemc-ci.onrender.com)
# via cette variable — inutile de le connaître à l'avance pour le premier déploiement.
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS = [f'https://{RENDER_EXTERNAL_HOSTNAME}']
    # Sert de secours si SITE_URL n'a pas été renseigné explicitement — les
    # liens d'activation (RG11) doivent pointer vers le vrai domaine, jamais
    # vers 127.0.0.1 (valeur par défaut de base.py, pensée pour le dev local).
    if not os.environ.get('SITE_URL'):
        SITE_URL = f'https://{RENDER_EXTERNAL_HOSTNAME}'
