"""Configuration de développement."""
import os

from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']

# Console par défaut (sûr, aucun risque d'envoi accidentel). Bascule sur un
# envoi réel via l'API HTTP de Brevo dès qu'une clé API est fournie par
# l'environnement — pratique pour vérifier l'expérience complète sans
# dupliquer prod.py, dont les réglages HTTPS (SECURE_SSL_REDIRECT, cookies
# sécurisés...) casseraient le serveur de développement, servi en HTTP simple.
if os.environ.get('BREVO_API_KEY'):
    EMAIL_BACKEND = 'anymail.backends.brevo.EmailBackend'
    ANYMAIL = {'BREVO_API_KEY': os.environ['BREVO_API_KEY'], 'REQUESTS_TIMEOUT': 10}
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
