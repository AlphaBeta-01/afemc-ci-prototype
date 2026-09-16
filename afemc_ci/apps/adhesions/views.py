from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.decorators import role_requis
from apps.core.services import journaliser
from apps.core.utils import paginer

from .forms import FormsetPiecesJustificatives, FormulaireDemande
from .models import DemandeAdhesion, PieceJustificative
from .services import MembreExistant, TransitionInterdite, changer_statut, notifier_nouvelle_demande


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
        notifier_nouvelle_demande(demande)
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
        except (TransitionInterdite, KeyError, MembreExistant) as err:
            messages.error(requete, str(err))
        else:
            messages.success(requete, 'Demande mise à jour.')
            return redirect('adhesions:liste')
    from .services import TRANSITIONS
    return render(requete, 'adhesions/traiter.html', {
        'demande': demande,
        'transitions': sorted(TRANSITIONS[demande.statut]),
    })


@login_required
@role_requis('ADMIN', 'RESP_ADMIN')
def telecharger_piece(requete, pk):
    """Sert une pièce justificative (revue de sécurité) : le fichier déposé
    par une candidate ne doit jamais être accessible par un lien direct vers
    `MEDIA_URL`, seulement via cette vue authentifiée et journalisée."""
    piece = get_object_or_404(PieceJustificative, pk=pk)
    journaliser(requete.user, 'CONSULTATION_PIECE_JUSTIFICATIVE',
               f'{piece.demande.nom_complet()} — {piece.get_type_piece_display()}', requete)
    return FileResponse(piece.fichier.open('rb'),
                        filename=piece.fichier.name.rsplit('/', 1)[-1])
