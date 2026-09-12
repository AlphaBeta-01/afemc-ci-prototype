"""Configuration des campagnes de test (§ 6.1.3)."""
import tempfile

from .base import *  # noqa

DEBUG = False
ALLOWED_HOSTS = ['*']
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']  # accélère les tests

# Répertoire jetable : les pièces jointes déposées pendant les tests ne
# doivent pas s'accumuler dans le vrai dossier media/ du projet.
MEDIA_ROOT = tempfile.mkdtemp(prefix='afemc_ci_media_test_')
