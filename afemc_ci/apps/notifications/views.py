"""Écran de suivi de la file de notifications, réservé à la Présidente."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import role_requis
from apps.core.services import journaliser
from apps.core.utils import paginer

from .models import Notification


@login_required
@role_requis('ADMIN')
def liste(requete):
    notifications = Notification.objects.select_related('membre', 'relance')
    if requete.GET.get('statut'):
        notifications = notifications.filter(statut=requete.GET['statut'])
    if requete.GET.get('type'):
        notifications = notifications.filter(type=requete.GET['type'])

    types = (Notification.objects.order_by('type')
            .values_list('type', flat=True).distinct())

    return render(requete, 'notifications/liste.html', {
        'page': paginer(notifications, requete),
        'statuts': Notification.Statut.choices,
        'types': types,
        'parametres': requete.GET,
        'nb_en_attente': Notification.objects.filter(
            statut=Notification.Statut.EN_ATTENTE).count(),
        'nb_echec': Notification.objects.filter(
            statut=Notification.Statut.ECHEC).count(),
    })


@require_POST
@login_required
@role_requis('ADMIN')
def renvoyer(requete, pk):
    """Remet une notification en échec dans la file (RG09).

    Ne l'envoie jamais elle-même — cohérent avec le reste de l'application,
    l'acheminement effectif reste la responsabilité de la tâche périodique
    ou de la commande `acheminer_notifications`.
    """
    notification = get_object_or_404(Notification, pk=pk)
    if notification.statut != Notification.Statut.ECHEC:
        messages.error(requete, "Seule une notification en échec peut être remise en file.")
        return redirect('notifications:liste')

    notification.statut = Notification.Statut.EN_ATTENTE
    notification.tentatives = 0
    notification.derniere_erreur = ''
    notification.save(update_fields=['statut', 'tentatives', 'derniere_erreur'])
    journaliser(requete.user, 'NOTIFICATION_REMISE_EN_FILE',
               f'{notification.destinataire} — {notification.objet}', requete)
    messages.success(
        requete,
        "Notification remise en file d'attente ; elle sera acheminée au prochain passage.")
    return redirect('notifications:liste')
