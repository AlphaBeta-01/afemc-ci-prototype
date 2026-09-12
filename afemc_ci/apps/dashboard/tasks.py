try:
    from celery import shared_task
except ImportError:
    def shared_task(fonction):
        return fonction


@shared_task
def envoyer_synthese():
    """Synthèse hebdomadaire adressée aux responsables (§ 5.6.1)."""
    from django.utils import timezone

    from apps.accounts.models import Utilisateur
    from apps.notifications.services import creer_notification

    from .services import indicateurs_globaux

    exercice = timezone.localdate().year
    indicateurs = indicateurs_globaux(exercice)
    destinataires = Utilisateur.objects.filter(
        role__in=[Utilisateur.Role.ADMIN, Utilisateur.Role.RESP_ADMIN,
                  Utilisateur.Role.RESP_FINANCIER], is_active=True)
    for responsable in destinataires:
        creer_notification(
            destinataire=responsable.email,
            type_notification='SYNTHESE_HEBDO',
            objet=f'Synthèse hebdomadaire — exercice {exercice}',
            gabarit='notifications/synthese.txt',
            contexte={'responsable': responsable.nom_complet(),
                      'exercice': exercice,
                      'effectif': indicateurs['effectif_total'],
                      'retards': indicateurs['nb_retard'],
                      'taux': f"{indicateurs['taux_recouvrement']:.1f}",
                      'reste': str(indicateurs['reste_a_recouvrer'])})
    return destinataires.count()
