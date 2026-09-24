from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import role_requis
from apps.core.services import journaliser
from apps.core.utils import paginer

from .forms import FormulaireMembre
from .models import Membre

RESPONSABLES = ('ADMIN', 'RESP_ADMIN', 'RESP_SECTION', 'RESP_FINANCIER')


def appliquer_filtres(selection, parametres):
    recherche = parametres.get('q', '').strip()
    if recherche:
        selection = selection.filter(
            Q(nom__icontains=recherche) | Q(prenoms__icontains=recherche)
            | Q(matricule__icontains=recherche) | Q(email__icontains=recherche))
    if parametres.get('section'):
        selection = selection.filter(section_id=parametres['section'])
    if parametres.get('statut'):
        selection = selection.filter(statut=parametres['statut'])
    return selection


@login_required
@role_requis(*RESPONSABLES)
def liste(requete):
    from apps.sections.models import Section
    membres = (Membre.objects.visibles_par(requete.user)
               .select_related('section').order_by('nom', 'prenoms'))
    membres = appliquer_filtres(membres, requete.GET)
    return render(requete, 'membres/liste.html', {
        'page': paginer(membres, requete),
        'sections': Section.objects.all(),
        'parametres': requete.GET,
        'total': membres.count(),
    })


@login_required
def detail(requete, pk):
    from apps.relances.models import Relance
    membre = get_object_or_404(
        Membre.objects.visibles_par(requete.user).select_related('section'), pk=pk)
    contexte = {'membre': membre}
    if requete.user.role != 'RESP_SECTION' or membre.utilisateur_id == requete.user.pk:
        # Cotisations et relances sont hors périmètre du responsable de
        # section (RG08) : ni interrogées, ni affichées pour ce rôle — sauf
        # sur sa propre fiche, puisqu'elle est aussi une membre cotisante (RG13).
        contexte['voir_cotisations'] = True
        contexte['cotisations'] = membre.cotisations.order_by('-exercice')
        contexte['relances'] = (Relance.objects.filter(cotisation__membre=membre)
                                .select_related('regle', 'cotisation')
                                .order_by('-date_emission'))
    return render(requete, 'membres/detail.html', contexte)


@login_required
@role_requis('ADMIN', 'RESP_ADMIN', 'RESP_SECTION')
def creer(requete):
    formulaire = FormulaireMembre(requete.POST or None, utilisateur=requete.user)
    if requete.method == 'POST' and formulaire.is_valid():
        membre = formulaire.save()
        journaliser(requete.user, 'CREATION_MEMBRE',
                    f'{membre.matricule} — {membre.nom_complet()}', requete)
        messages.success(requete, f'Membre créé. Matricule attribué : {membre.matricule}.')
        return redirect('membres:detail', pk=membre.pk)
    return render(requete, 'membres/formulaire.html',
                  {'formulaire': formulaire, 'titre': 'Nouveau membre'})


@login_required
@role_requis('ADMIN', 'RESP_ADMIN', 'RESP_SECTION')
def modifier(requete, pk):
    # `visibles_par` cantonne un responsable de section à sa propre section
    # (RG08) : une fiche hors périmètre renvoie 404, comme pour `detail`.
    membre = get_object_or_404(Membre.objects.visibles_par(requete.user), pk=pk)
    formulaire = FormulaireMembre(requete.POST or None, instance=membre,
                                  utilisateur=requete.user)
    if requete.method == 'POST' and formulaire.is_valid():
        formulaire.save()
        journaliser(requete.user, 'MODIFICATION_MEMBRE', membre.matricule, requete)
        messages.success(requete, 'Fiche mise à jour.')
        return redirect('membres:detail', pk=membre.pk)
    return render(requete, 'membres/formulaire.html',
                  {'formulaire': formulaire, 'titre': f'Modifier {membre.nom_complet()}'})
