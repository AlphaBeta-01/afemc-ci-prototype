import json
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.adhesions.models import DemandeAdhesion
from apps.core.utils import trier_par_nom
from apps.membres.models import Membre

from .services import (evolution_mensuelle, indicateurs_globaux,
                       repartition_par_section, situations_a_examiner)


class EncodeurDecimal(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


@login_required
def accueil(requete):
    """Tableau de bord décisionnel (§ 5.7) : réservé aux responsables (RG08).

    Un simple membre y arrive naturellement (page d'accueil par défaut) mais
    n'a pas vocation à voir les indicateurs de gouvernance de sa section ;
    il est redirigé vers sa propre fiche.
    """
    if not requete.user.est_responsable:
        fiche = getattr(requete.user, 'fiche_membre', None)
        if fiche:
            return redirect('membres:detail', pk=fiche.pk)
        return render(requete, 'dashboard/aucun_acces.html')

    if requete.user.role == 'RESP_SECTION':
        return _tableau_de_bord_section(requete)

    exercice = int(requete.GET.get('exercice', timezone.localdate().year))

    section = None
    if not requete.user.voit_toutes_les_sections and requete.user.section_id:
        section = requete.user.section          # cloisonnement automatique

    indicateurs = indicateurs_globaux(exercice, section, requete.user)
    sections = repartition_par_section(exercice)
    evolution = evolution_mensuelle(exercice)

    donnees_sections = {
        'libelles': [s.libelle for s in sections],
        'effectifs': [s.effectif for s in sections],
    }
    donnees_evolution = {
        'libelles': [p['mois'].strftime('%m/%Y') for p in evolution if p['mois']],
        'montants': [float(p['total']) for p in evolution if p['mois']],
    }
    donnees_statuts = {
        'libelles': ['Payées', 'Partielles', 'En retard', 'En attente'],
        'valeurs': [indicateurs['nb_payees'], indicateurs['nb_partiel'],
                    indicateurs['nb_retard'],
                    indicateurs['nb_total'] - indicateurs['nb_payees']
                    - indicateurs['nb_partiel'] - indicateurs['nb_retard']],
    }

    return render(requete, 'dashboard/accueil.html', {
        'indicateurs': indicateurs,
        'exercice': exercice,
        'exercices': range(timezone.localdate().year - 3, timezone.localdate().year + 2),
        'section': section,
        'sections': sections,
        # Sélection par urgence (retards les plus anciens), affichage de A à Z.
        'retards': trier_par_nom(situations_a_examiner(exercice, section),
                                 personne=lambda c: c.membre),
        'demandes': trier_par_nom(DemandeAdhesion.objects.filter(
            statut__in=[DemandeAdhesion.Statut.EN_ATTENTE,
                        DemandeAdhesion.Statut.EN_EXAMEN]).select_related('section')[:5]),
        'donnees_sections': json.dumps(donnees_sections, cls=EncodeurDecimal),
        'donnees_evolution': json.dumps(donnees_evolution, cls=EncodeurDecimal),
        'donnees_statuts': json.dumps(donnees_statuts, cls=EncodeurDecimal),
    })


def _tableau_de_bord_section(requete):
    """Vue restreinte du responsable de section : rien que sa section (RG08).

    Ni cotisations, ni adhésions, ni relances — uniquement l'effectif dont il
    a la charge, cohérent avec l'absence de ces menus pour ce rôle.
    """
    section = requete.user.section
    if not section:
        return render(requete, 'dashboard/aucun_acces.html', {
            'message': "Votre compte n'est rattaché à aucune section. "
                      "Contactez l'administrateur."})

    membres = Membre.objects.filter(section=section)
    return render(requete, 'dashboard/section.html', {
        'section': section,
        'effectif_actif': membres.filter(statut=Membre.Statut.ACTIF).count(),
        'effectif_inactif': membres.filter(statut=Membre.Statut.INACTIF).count(),
        'effectif_suspendu': membres.filter(statut=Membre.Statut.SUSPENDU).count(),
        # Les 10 dernières inscrites, affichées de A à Z.
        'membres_recents': trier_par_nom(membres.order_by('-cree_le')[:10]),
    })
