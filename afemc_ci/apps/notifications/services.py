"""Composition et acheminement des messages (§ 5.6.3)."""
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Notification


class ErreurEnvoi(Exception):
    """Échec d'acheminement d'une notification."""


def creer_notification(destinataire, type_notification, objet, gabarit, contexte,
                       membre=None, relance=None, canal=Notification.Canal.EMAIL):
    return Notification.objects.create(
        destinataire=destinataire, membre=membre, relance=relance,
        type=type_notification, canal=canal, objet=objet,
        gabarit=gabarit, contexte=contexte)


def rendre_gabarit(gabarit, contexte):
    return render_to_string(gabarit, contexte)


def envoyer_courriel(destinataire, objet, corps):
    try:
        envoyes = send_mail(objet, corps, settings.EMAIL_EXPEDITEUR,
                            [destinataire], fail_silently=False)
    except Exception as err:                # noqa: BLE001
        raise ErreurEnvoi(str(err)) from err
    if not envoyes:
        raise ErreurEnvoi('Aucun message accepté par le service de messagerie.')
    return envoyes


def acheminer_notifications_en_attente(taille_lot=100):
    """Achemine la file en attente ; réémission plafonnée (§ 5.6.3)."""
    maximum = settings.MAX_TENTATIVES_NOTIFICATION
    en_attente = (Notification.objects
                  .filter(statut=Notification.Statut.EN_ATTENTE,
                          tentatives__lt=maximum)
                  .order_by('cree_le')[:taille_lot])
    envoyees, echecs = 0, 0
    for notification in en_attente:
        try:
            corps = rendre_gabarit(notification.gabarit, notification.contexte)
            envoyer_courriel(notification.destinataire, notification.objet, corps)
            notification.statut = Notification.Statut.ENVOYEE
            notification.date_envoi = timezone.now()
            envoyees += 1
        except ErreurEnvoi as err:
            notification.tentatives += 1
            notification.derniere_erreur = str(err)[:255]
            if notification.tentatives >= maximum:
                notification.statut = Notification.Statut.ECHEC
            echecs += 1
        notification.save()
    return envoyees, echecs
