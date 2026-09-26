"""Compteur du bouton « À faire », présent dans la barre de navigation."""
from functools import cached_property


class ResumeAFaire:
    """Calculé seulement si un gabarit l'affiche, et une seule fois par page."""

    def __init__(self, utilisateur):
        self.utilisateur = utilisateur

    @cached_property
    def _taches(self):
        from .taches import taches_pour
        return taches_pour(self.utilisateur)

    @cached_property
    def nombre(self):
        from .taches import compteur
        return compteur(self._taches)

    @cached_property
    def urgent(self):
        from .taches import URGENT
        return any(t.priorite == URGENT for t in self._taches)


def a_faire(requete):
    utilisateur = getattr(requete, 'user', None)
    if utilisateur is None or not utilisateur.is_authenticated:
        return {}
    return {'a_faire': ResumeAFaire(utilisateur)}
