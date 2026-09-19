"""Logique métier des cotisations (§ 5.5.5, § 5.7.2)."""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.core.services import journaliser
from apps.membres.models import Membre
from apps.notifications.services import creer_notification

from .models import Cotisation, Paiement


def calculer_statut(cotisation, aujourdhui=None):
    """Détermine le statut d'une cotisation (RG04, RG06).

    Fonction pure : elle ne dépend que de l'état de la cotisation et de la date.
    """
    aujourdhui = aujourdhui or date.today()
    if cotisation.montant_paye >= cotisation.montant_du:
        return Cotisation.Statut.PAYEE
    if cotisation.date_echeance < aujourdhui:
        return Cotisation.Statut.EN_RETARD
    if cotisation.montant_paye > 0:
        return Cotisation.Statut.PARTIEL
    return Cotisation.Statut.EN_ATTENTE


@transaction.atomic
def emettre_cotisations_exercice(exercice, montant, date_echeance, utilisateur=None):
    """Émet les appels de cotisation d'un exercice (RG04)."""
    membres = Membre.objects.actifs()
    creees, ignorees = [], 0
    for membre in membres:
        cotisation, cree = Cotisation.objects.get_or_create(
            membre=membre, exercice=exercice,
            defaults={'montant_du': montant,
                      'date_echeance': date_echeance,
                      'statut': Cotisation.Statut.EN_ATTENTE})
        if cree:
            creees.append(cotisation)
        else:
            ignorees += 1          # contrainte d'unicité respectée
    journaliser(utilisateur, 'EMISSION_COTISATIONS',
                f'exercice {exercice} : {len(creees)} créées, {ignorees} ignorées')
    return creees, ignorees


@transaction.atomic
def enregistrer_paiement(cotisation, montant, mode, reference='', utilisateur=None):
    """Enregistre un paiement rattaché à une cotisation existante (RG05)."""
    montant = Decimal(montant)
    if montant <= 0:
        raise ValidationError("Le montant doit être strictement positif.")

    # Reverrouille la ligne au tout début de la transaction plutôt que de
    # se fier à l'objet passé par l'appelant, potentiellement chargé avant
    # que la transaction ne commence : sans ce verrou, deux saisies
    # simultanées sur la même cotisation peuvent lire le même reste à
    # payer, passer toutes deux la validation, puis s'écraser l'une
    # l'autre à l'enregistrement — le paiement resterait tracé dans
    # Paiement, mais montant_paye/statut de la cotisation perdrait l'une
    # des deux mises à jour.
    cotisation = Cotisation.objects.select_for_update().get(pk=cotisation.pk)

    reste = cotisation.montant_du - cotisation.montant_paye
    if montant > reste:
        raise ValidationError(
            f"Montant supérieur au reste à payer ({reste} FCFA).")

    paiement = Paiement.objects.create(
        cotisation=cotisation, montant=montant, mode=mode,
        reference=reference, enregistre_par=utilisateur,
        date_paiement=timezone.now())

    cotisation.montant_paye += montant
    cotisation.statut = calculer_statut(cotisation)
    cotisation.save(update_fields=['montant_paye', 'statut'])

    journaliser(utilisateur, 'ENREGISTREMENT_PAIEMENT',
                f'cotisation {cotisation.pk} : +{montant} FCFA')
    notifier_recu_paiement(paiement, cotisation)
    return paiement


def notifier_recu_paiement(paiement, cotisation):
    """Envoie au membre un reçu du versement qu'il vient d'effectuer (RG05)."""
    creer_notification(
        destinataire=cotisation.membre.email,
        type_notification='RECU_PAIEMENT',
        objet=f"Reçu de cotisation {cotisation.exercice} — AFEMC-CI",
        gabarit='notifications/recu_paiement.txt',
        contexte={
            'membre': cotisation.membre.nom_complet(),
            'matricule': cotisation.membre.matricule,
            'exercice': cotisation.exercice,
            'montant_verse': str(paiement.montant),
            'mode': paiement.get_mode_display(),
            'reference': paiement.reference or '—',
            'date_paiement': paiement.date_paiement.strftime('%d/%m/%Y'),
            'montant_du': str(cotisation.montant_du),
            'montant_paye_cumule': str(cotisation.montant_paye),
            'reste': str(cotisation.reste_a_payer),
            'statut': cotisation.get_statut_display(),
        },
        membre=cotisation.membre)


def indicateurs_exercice(exercice, section=None):
    """Agrégats financiers de l'exercice, en une seule requête (§ 5.7.2)."""
    cotisations = Cotisation.objects.filter(exercice=exercice)
    if section:
        cotisations = cotisations.filter(membre__section=section)

    agr = cotisations.aggregate(
        total_du=Sum('montant_du'),
        total_paye=Sum('montant_paye'),
        nb_total=Count('id'),
        nb_payees=Count('id', filter=Q(statut=Cotisation.Statut.PAYEE)),
        nb_retard=Count('id', filter=Q(statut=Cotisation.Statut.EN_RETARD)),
        nb_partiel=Count('id', filter=Q(statut=Cotisation.Statut.PARTIEL)),
    )
    total_du = agr['total_du'] or Decimal('0')
    total_paye = agr['total_paye'] or Decimal('0')

    return {
        **agr,
        'total_du': total_du,
        'total_paye': total_paye,
        'reste_a_recouvrer': total_du - total_paye,
        'taux_recouvrement': (total_paye / total_du * 100) if total_du else Decimal('0'),
    }
