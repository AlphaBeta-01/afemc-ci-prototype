"""Calcul des indicateurs de pilotage (§ 5.7)."""
from datetime import date

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth

from apps.adhesions.models import DemandeAdhesion
from apps.cotisations.models import Cotisation, Paiement
from apps.cotisations.services import indicateurs_exercice
from apps.membres.models import Membre
from apps.relances.models import Relance
from apps.sections.models import Section


def repartition_par_section(exercice):
    return (Section.objects
            .annotate(
                effectif=Count('membres', filter=Q(membres__statut='ACTIF')),
                du=Sum('membres__cotisations__montant_du',
                       filter=Q(membres__cotisations__exercice=exercice)),
                paye=Sum('membres__cotisations__montant_paye',
                         filter=Q(membres__cotisations__exercice=exercice)))
            .order_by('-effectif'))


def evolution_mensuelle(exercice):
    return list(Paiement.objects
                .filter(cotisation__exercice=exercice)
                .annotate(mois=TruncMonth('date_paiement'))
                .values('mois')
                .annotate(total=Sum('montant'), nombre=Count('id'))
                .order_by('mois'))


def indicateurs_globaux(exercice, section=None, utilisateur=None):
    membres = Membre.objects.all()
    demandes = DemandeAdhesion.objects.all()
    relances = Relance.objects.filter(cotisation__exercice=exercice)
    if section:
        membres = membres.filter(section=section)
        demandes = demandes.filter(section=section)
        relances = relances.filter(cotisation__membre__section=section)

    financier = indicateurs_exercice(exercice, section=section)

    return {
        'exercice': exercice,
        'effectif_total': membres.filter(statut=Membre.Statut.ACTIF).count(),
        'effectif_inactif': membres.filter(statut=Membre.Statut.INACTIF).count(),
        'effectif_suspendu': membres.filter(statut=Membre.Statut.SUSPENDU).count(),
        'demandes_en_attente': demandes.filter(
            statut__in=[DemandeAdhesion.Statut.EN_ATTENTE,
                        DemandeAdhesion.Statut.EN_EXAMEN]).count(),
        'nouvelles_adhesions': demandes.filter(
            statut=DemandeAdhesion.Statut.VALIDEE,
            date_traitement__year=exercice).count(),
        'relances_emises': relances.count(),
        'relances_par_niveau': list(relances.values('regle__niveau')
                                    .annotate(nombre=Count('id'))
                                    .order_by('-nombre')),
        **financier,
    }


def situations_a_examiner(exercice, section=None, limite=10):
    retards = (Cotisation.objects
               .filter(exercice=exercice, statut=Cotisation.Statut.EN_RETARD)
               .select_related('membre', 'membre__section')
               .order_by('date_echeance'))
    if section:
        retards = retards.filter(membre__section=section)
    return retards[:limite]
