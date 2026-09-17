"""Composition et acheminement des messages (§ 5.6.3)."""
import time

from django.conf import settings
from django.core.mail import send_mail
from django.template import Context, Template
from django.template.loader import get_template
from django.utils import timezone

from .models import Notification


class ErreurEnvoi(Exception):
    """Échec d'acheminement d'une notification."""


def creer_notification(destinataire, type_notification, objet, gabarit, contexte,
                       membre=None, relance=None, canal=Notification.Canal.EMAIL):
    """Persiste la notification puis tente aussitôt de l'envoyer (§ 5.6.3).

    L'échec de cette tentative immédiate — panne du fournisseur, gabarit
    invalide, etc. — est toujours absorbé par `_tenter_envoi`, jamais
    propagé : la personne qui vient de soumettre une demande d'adhésion ou
    de créer un compte ne doit jamais voir sa page échouer à cause d'un
    problème d'envoi de courriel. `acheminer_notifications_en_attente` reste
    le filet de sécurité qui réessaiera ce qui n'est pas parti du premier
    coup (§ 7 du README, cron toutes les 15 min).
    """
    notification = Notification.objects.create(
        destinataire=destinataire, membre=membre, relance=relance,
        type=type_notification, canal=canal, objet=objet,
        gabarit=gabarit, contexte=contexte)
    _tenter_envoi(notification)
    return notification


def rendre_gabarit(gabarit, contexte):
    """Rend un gabarit de courriel en texte brut.

    Django échappe le HTML par défaut même dans un fichier `.txt` (via
    `render_to_string`) : une simple apostrophe dans un nom de section
    devenait « &#x27; » dans le corps du message. Sans objet pour un
    courriel en texte brut — l'échappement est donc désactivé ici, une fois
    pour tous les gabarits, plutôt que dans chacun d'eux.
    """
    source = get_template(gabarit).template.source
    return Template('{% autoescape off %}' + source + '{% endautoescape %}').render(
        Context(contexte))


def envoyer_courriel(destinataire, objet, corps):
    try:
        envoyes = send_mail(objet, corps, settings.EMAIL_EXPEDITEUR,
                            [destinataire], fail_silently=False)
    except Exception as err:                # noqa: BLE001
        raise ErreurEnvoi(str(err)) from err
    if not envoyes:
        raise ErreurEnvoi('Aucun message accepté par le service de messagerie.')
    return envoyes


def _tenter_envoi(notification):
    """Une tentative d'envoi ; met à jour et sauvegarde la notification.

    Capture largement (pas seulement `ErreurEnvoi`) : un gabarit invalide
    (`rendre_gabarit`) ne doit pas plus faire échouer l'appelant qu'une
    panne du fournisseur de messagerie — les deux sont un échec d'envoi du
    point de vue de cette notification, à comptabiliser et à réessayer.
    """
    maximum = settings.MAX_TENTATIVES_NOTIFICATION
    try:
        corps = rendre_gabarit(notification.gabarit, notification.contexte)
        envoyer_courriel(notification.destinataire, notification.objet, corps)
    except Exception as err:                # noqa: BLE001
        notification.tentatives += 1
        notification.derniere_erreur = str(err)[:255]
        if notification.tentatives >= maximum:
            notification.statut = Notification.Statut.ECHEC
        notification.save()
        return False
    notification.statut = Notification.Statut.ENVOYEE
    notification.date_envoi = timezone.now()
    notification.save()
    return True


def acheminer_notifications_en_attente(taille_lot=100, budget_secondes=60):
    """Rattrape ce que l'envoi immédiat de `creer_notification` n'a pas pu
    délivrer (panne passagère, notification créée avant ce mécanisme…).
    Filet de sécurité plutôt que voie normale — voir § 5.6.3 et le README § 7.

    `budget_secondes` borne le temps total, pas seulement `taille_lot` le
    nombre d'éléments : un grand nombre de notifications en échec (chacune
    pouvant consommer jusqu'à REQUESTS_TIMEOUT secondes côté fournisseur)
    cumulerait sinon un temps largement supérieur au délai du serveur
    d'application (--timeout de gunicorn, voir render.yaml), faisant
    planter la requête HTTP qui a déclenché cet acheminement (§ 7 du
    README). Le reliquat non traité reste EN_ATTENTE et sera repris au
    passage suivant (toutes les 15 min), sans rien perdre.
    """
    maximum = settings.MAX_TENTATIVES_NOTIFICATION
    en_attente = (Notification.objects
                  .filter(statut=Notification.Statut.EN_ATTENTE,
                          tentatives__lt=maximum)
                  .order_by('cree_le')[:taille_lot])
    debut = time.monotonic()
    envoyees, echecs = 0, 0
    for notification in en_attente:
        if time.monotonic() - debut > budget_secondes:
            break
        if _tenter_envoi(notification):
            envoyees += 1
        else:
            echecs += 1
    return envoyees, echecs
