"""Configuration de développement."""
import os

from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']

# Console par défaut (sûr, aucun risque d'envoi accidentel). Bascule sur un
# envoi SMTP réel dès que des identifiants sont fournis par l'environnement —
# pratique pour vérifier l'expérience complète sans dupliquer prod.py, dont
# les réglages HTTPS (SECURE_SSL_REDIRECT, cookies sécurisés...) casseraient
# le serveur de développement, servi en HTTP simple.
if os.environ.get('EMAIL_HOST_USER'):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
    EMAIL_USE_TLS = True
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
