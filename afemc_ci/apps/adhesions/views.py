from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import role_requis
from apps.core.utils import paginer

from .forms import FormsetPiecesJustificatives, FormulaireDemande
from .models import DemandeAdhesion, PieceJustificative
from .services import TransitionInterdite, changer_statut


def soumettre(requete):
    """Formulaire public : accessible sans authentification.

    Au moins une pièce justificative (carte professionnelle, attestation
    d'exercice ou diplôme) est exigée pour prouver la qualité d'enseignante
    chercheure — vérifiée par le responsable administratif au traitement.
    """
    formulaire = FormulaireDemande(requete.POST or None)
    formset = FormsetPiecesJustificatives(requete.POST or None, requete.FILES or None,
                                          prefix='pieces')
    if requete.method == 'POST' and formulaire.is_valid() and formset.is_valid():
        demande = formulaire.save()
        for piece in formset:
            fichier = piece.cleaned_data.get('fichier')
            if fichier:
                PieceJustificative.objects.create(
                    demande=demande, type_piece=piece.cleaned_data['type_piece'],
                    fichier=fichier)
        return render(requete, 'adhesions/confirmation.html')
    return render(requete, 'adhesions/soumettre.html',
                  {'formulaire': formulaire, 'formset': formset})


@login_required
@role_requis('ADMIN', 'RESP_ADMIN')          # pas RESP_SECTION
def liste(requete):
    demandes = DemandeAdhesion.objects.select_related('section')
    if not requete.user.voit_toutes_les_sections and requete.user.section_id:
        demandes = demandes.filter(section_id=requete.user.section_id)
    if requete.GET.get('statut'):
        demandes = demandes.filter(statut=requete.GET['statut'])
    return render(requete, 'adhesions/liste.html', {
        'page': paginer(demandes, requete),
        'statuts': DemandeAdhesion.Statut.choices,
        'parametres': requete.GET,
    })


@login_required
@role_requis('ADMIN', 'RESP_ADMIN')
def traiter(requete, pk):
    demande = get_object_or_404(DemandeAdhesion, pk=pk)
    if requete.method == 'POST':
        try:
            changer_statut(demande, requete.POST.get('statut'), requete.user,
                           requete.POST.get('motif', ''))
        except (TransitionInterdite, KeyError) as err:
            messages.error(requete, str(err))
        else:
            messages.success(requete, 'Demande mise à jour.')
            return redirect('adhesions:liste')
    from .services import TRANSITIONS
    return render(requete, 'adhesions/traiter.html', {
        'demande': demande,
        'transitions': sorted(TRANSITIONS[demande.statut]),
    })
