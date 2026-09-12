"""Détection des échéances et génération des relances (§ 5.6.1, § 5.6.2)."""
import time
from datetime import date

from django.db import transaction

from apps.core.services import journaliser
from apps.cotisations.models import Cotisation
from apps.cotisations.services import calculer_statut
from apps.membres.models import Membre
from apps.notifications.services import creer_notification

from .models import Relance, RegleRelance


def relance_deja_emise(cotisation, regle):
    return Relance.objects.filter(cotisation=cotisation, regle=regle).exists()


def resoudre_destinataires(regle, cotisation):
    """Détermine les adresses visées par la règle."""
    from apps.accounts.models import Utilisateur

    D = RegleRelance.Destinataires
    adresses = []
    if regle.destinataires in (D.MEMBRE, D.MEMBRE_SECTION, D.MEMBRE_FINANCIER):
        adresses.append(cotisation.membre.email)
    if regle.destinataires in (D.MEMBRE_SECTION, D.RESPONSABLES):
        adresses += list(Utilisateur.objects
                         .filter(role=Utilisateur.Role.RESP_SECTION,
                                 section_id=cotisation.membre.section_id,
                                 is_active=True)
                         .values_list('email', flat=True))
    if regle.destinataires in (D.MEMBRE_FINANCIER, D.RESPONSABLES):
        adresses += list(Utilisateur.objects
                         .filter(role=Utilisateur.Role.RESP_FINANCIER, is_active=True)
                         .values_list('email', flat=True))
    return list(dict.fromkeys(adresses))


@transaction.atomic
def creer_relance(cotisation, regle, aujourdhui=None):
    """Crée une relance et les notifications correspondantes (RG07)."""
    aujourdhui = aujourdhui or date.today()
    ecart = (aujourdhui - cotisation.date_echeance).days

    relance = Relance.objects.create(cotisation=cotisation, regle=regle,
                                     jours_ecart=ecart)

    contexte = {
        'membre': cotisation.membre.nom_complet(),
        'exercice': cotisation.exercice,
        'montant_du': str(cotisation.montant_du),
        'reste': str(cotisation.reste_a_payer),
        'echeance': cotisation.date_echeance.strftime('%d/%m/%Y'),
        'jours': abs(ecart),
        'section': cotisation.membre.section.libelle,
        'niveau': regle.get_niveau_display(),
    }

    for destinataire in resoudre_destinataires(regle, cotisation):
        creer_notification(
            destinataire=destinataire,
            type_notification='RELANCE_COTISATION',
            objet=f'Cotisation {cotisation.exercice} — {regle.libelle}',
            gabarit=regle.gabarit_message,
            contexte=contexte,
            membre=cotisation.membre,
            relance=relance)

    return relance


def executer_detection(simulation=False, aujourdhui=None):
    """Moteur de détection des échéances et des retards (§ 5.6.1)."""
    aujourdhui = aujourdhui or date.today()
    debut = time.monotonic()

    # 1. Sélection des cotisations à examiner
    candidates = (Cotisation.objects
                  .select_related('membre', 'membre__section')
                  .filter(statut__in=[Cotisation.Statut.EN_ATTENTE,
                                      Cotisation.Statut.PARTIEL,
                                      Cotisation.Statut.EN_RETARD])
                  .exclude(membre__statut=Membre.Statut.SUSPENDU))

    basculees, relances = 0, 0
    for cotisation in candidates.iterator(chunk_size=500):
        # 2. Comparaison échéance / date courante (RG06)
        ecart = (cotisation.date_echeance - aujourdhui).days
        nouveau = calculer_statut(cotisation, aujourdhui)

        if nouveau != cotisation.statut:
            if not simulation:
                cotisation.statut = nouveau
                cotisation.save(update_fields=['statut'])
            basculees += 1

        # 3. Application des règles de relance (RG07)
        regle = RegleRelance.applicable(ecart, cotisation)
        if regle and not relance_deja_emise(cotisation, regle):
            if not simulation:
                creer_relance(cotisation, regle, aujourdhui)
            relances += 1

    duree = time.monotonic() - debut
    journaliser(None, 'EXECUTION_MOTEUR_RELANCE',
                f'{basculees} statuts modifiés, {relances} relances, '
                f'{duree:.2f} s, simulation={simulation}')
    return {'basculees': basculees, 'relances': relances, 'duree': duree}
