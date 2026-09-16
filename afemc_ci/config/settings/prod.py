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

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = True
# Sans ceci, smtplib bloque indéfiniment si la connexion TCP sortante
# n'aboutit pas (observé sur Render : le worker gunicorn se fait tuer par
# son propre timeout pendant que smtplib attend encore). Un échec rapide
# retombe proprement dans le circuit ECHEC/réessai existant plutôt que de
# faire planter tout le worker. smtp-relay.brevo.com résout vers plusieurs
# IP essayées une à une (§ startCommand dans render.yaml) : 8 s par adresse
# laisse une marge confortable sous le --timeout 90 de gunicorn même si
# plusieurs adresses échouent avant qu'une ne réponde.
EMAIL_TIMEOUT = 8

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
