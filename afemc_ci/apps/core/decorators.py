"""Contrôle d'accès par rôle (RG08, § 5.5.1)."""
from functools import wraps

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .services import journaliser


def role_requis(*roles):
    """Restreint l'accès d'une vue aux rôles indiqués (RG08)."""

    def decorateur(vue):
        @wraps(vue)
        def _verifier(requete, *args, **kwargs):
            if not requete.user.is_authenticated:
                return redirect('accounts:connexion')
            if requete.user.role not in roles:
                journaliser(requete.user, 'ACCES_REFUSE', requete.path, requete)
                raise PermissionDenied("Accès non autorisé pour ce profil.")
            return vue(requete, *args, **kwargs)

        return _verifier

    return decorateur
