from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import role_requis
from apps.core.services import journaliser
from apps.core.utils import ordre_alphabetique

from . import services
from .forms import FormulaireActivite, FormulaireComite
from .models import Activite, MembreComite


def _activite_visible(requete, pk):
    """404 plutôt que 403 : une activité en préparation n'a pas à être révélée."""
    activite = get_object_or_404(Activite.objects.select_related('section'), pk=pk)
    if not services.peut_voir(requete.user, activite):
        raise Http404
    return activite


@login_required
def liste(requete):
    maintenant = timezone.now()
    activites = services.activites_visibles(requete.user).select_related('section')
    fiche = getattr(requete.user, 'fiche_membre', None)
    inscrites = set(fiche.inscriptions.values_list('activite_id', flat=True)) if fiche else set()
    comites = set(fiche.comites.values_list('activite_id', flat=True)) if fiche else set()
    return render(requete, 'activites/liste.html', {
        'a_venir': activites.filter(date_debut__gte=maintenant).order_by('date_debut'),
        'passees': activites.filter(date_debut__lt=maintenant).order_by('-date_debut')[:30],
        'gere': services.gere_les_activites(requete.user),
        'inscrites': inscrites,
        'comites': comites,
    })


@login_required
def detail(requete, pk):
    activite = _activite_visible(requete, pk)
    peut_modifier = services.peut_modifier(requete.user, activite)
    gere = services.gere_les_activites(requete.user)
    fiche = getattr(requete.user, 'fiche_membre', None)
    contexte = {
        'activite': activite,
        'gere': gere,
        'peut_modifier': peut_modifier,
        'comite': activite.comite.select_related('membre', 'membre__section')
                  .order_by(*ordre_alphabetique('membre__')),
        'est_inscrite': bool(fiche and activite.inscriptions.filter(membre=fiche).exists()),
        'peut_s_inscrire': services.peut_s_inscrire(requete.user, activite),
    }
    if peut_modifier:
        # La liste des inscrites n'est montrée qu'à celles qui organisent.
        contexte['inscriptions'] = (activite.inscriptions.select_related('membre__section')
                                    .order_by(*ordre_alphabetique('membre__')))
    if gere:
        contexte['formulaire_comite'] = FormulaireComite(activite=activite)
        contexte['statuts_possibles'] = _statuts_possibles(activite)
    return render(requete, 'activites/detail.html', contexte)


def _statuts_possibles(activite):
    S = Activite.Statut
    libelles = {S.PUBLIEE: 'Publier', S.TERMINEE: 'Clôturer', S.ANNULEE: 'Annuler',
                S.EN_PREPARATION: 'Repasser en préparation'}
    suite = {S.EN_PREPARATION: [S.PUBLIEE, S.ANNULEE],
             S.PUBLIEE: [S.TERMINEE, S.EN_PREPARATION, S.ANNULEE],
             S.TERMINEE: [], S.ANNULEE: [S.EN_PREPARATION]}[activite.statut]
    return [(s, libelles[s]) for s in suite]


@login_required
@role_requis(*services.ROLES_GESTION)
def creer(requete):
    formulaire = FormulaireActivite(requete.POST or None)
    if requete.method == 'POST' and formulaire.is_valid():
        activite = formulaire.save(commit=False)
        activite.cree_par = requete.user
        activite.save()
        journaliser(requete.user, 'CREATION_ACTIVITE', activite.titre, requete)
        messages.success(requete, "Activité créée, en préparation : elle n'est visible des "
                                  "membres qu'une fois publiée.")
        return redirect('activites:detail', pk=activite.pk)
    return render(requete, 'activites/formulaire.html',
                  {'formulaire': formulaire, 'titre': 'Nouvelle activité'})


@login_required
def modifier(requete, pk):
    activite = _activite_visible(requete, pk)
    if not services.peut_modifier(requete.user, activite):
        raise PermissionDenied("Vous ne faites pas partie de l'organisation de cette activité.")
    formulaire = FormulaireActivite(requete.POST or None, instance=activite)
    if requete.method == 'POST' and formulaire.is_valid():
        formulaire.save()
        journaliser(requete.user, 'MODIFICATION_ACTIVITE', activite.titre, requete)
        messages.success(requete, 'Activité mise à jour.')
        return redirect('activites:detail', pk=activite.pk)
    return render(requete, 'activites/formulaire.html', {
        'formulaire': formulaire, 'activite': activite, 'titre': f'Modifier « {activite.titre} »'})


@require_POST
@login_required
@role_requis(*services.ROLES_GESTION)
def statut(requete, pk):
    activite = get_object_or_404(Activite, pk=pk)
    try:
        services.changer_statut(activite, requete.POST.get('statut'), requete.user, requete)
        messages.success(requete, f'Activité {activite.get_statut_display().lower()}.')
    except (services.OperationImpossible, ValueError) as erreur:
        messages.error(requete, str(erreur))
    return redirect('activites:detail', pk=activite.pk)


@require_POST
@login_required
@role_requis(*services.ROLES_GESTION)
def comite_ajouter(requete, pk):
    activite = get_object_or_404(Activite, pk=pk)
    formulaire = FormulaireComite(requete.POST, activite=activite)
    if formulaire.is_valid():
        membre = formulaire.cleaned_data['membre']
        try:
            services.ajouter_au_comite(activite, membre, formulaire.cleaned_data['mission'],
                                       requete.user, requete)
            messages.success(requete, f"{membre.nom_complet()} rejoint le comité "
                                      "d'organisation ; elle en est prévenue par courriel.")
        except services.OperationImpossible as erreur:
            messages.error(requete, str(erreur))
    else:
        messages.error(requete, 'Choisissez une membre active.')
    return redirect('activites:detail', pk=activite.pk)


@require_POST
@login_required
@role_requis(*services.ROLES_GESTION)
def comite_retirer(requete, pk, comite_pk):
    membre_comite = get_object_or_404(MembreComite, pk=comite_pk, activite_id=pk)
    services.retirer_du_comite(membre_comite, requete.user, requete)
    messages.success(requete, f"{membre_comite.membre.nom_complet()} ne fait plus partie "
                              "du comité.")
    return redirect('activites:detail', pk=pk)


@require_POST
@login_required
def inscription(requete, pk):
    activite = _activite_visible(requete, pk)
    try:
        if requete.POST.get('action') == 'annuler':
            services.desinscrire(activite, requete.user, requete)
            messages.success(requete, 'Votre inscription est annulée.')
        else:
            services.inscrire(activite, requete.user, requete)
            messages.success(requete, 'Vous êtes inscrite. À bientôt !')
    except services.OperationImpossible as erreur:
        messages.error(requete, str(erreur))
    return redirect('activites:detail', pk=activite.pk)
