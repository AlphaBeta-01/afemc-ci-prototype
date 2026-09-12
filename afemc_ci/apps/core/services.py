"""Services transversaux."""
from .models import JournalOperation


def extraire_ip(requete):
    if requete is None:
        return None
    transmise = requete.META.get('HTTP_X_FORWARDED_FOR')
    if transmise:
        return transmise.split(',')[0].strip()
    return requete.META.get('REMOTE_ADDR')


def journaliser(utilisateur, type_operation, detail='', requete=None):
    """Enregistre une opération sensible (RG09).

    Les entrées du journal ne peuvent être ni modifiées ni supprimées
    depuis l'application.
    """
    return JournalOperation.objects.create(
        utilisateur=utilisateur if (utilisateur and utilisateur.is_authenticated) else None,
        type_operation=type_operation[:40],
        detail=detail,
        adresse_ip=extraire_ip(requete),
    )
