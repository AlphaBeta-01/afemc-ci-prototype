from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.core.decorators import role_requis
from apps.core.services import journaliser

from .forms import (FormsetChiffres, FormsetGalerie, FormsetRealisations,
                    FormulaireAjoutPhotos, FormulairePageAccueil)
from .models import ChiffreCle, PageAccueil, PhotoGalerie, Realisation

EDITRICES = ('ADMIN', 'RESP_ORGA')


def accueil(requete):
    """Page d'accueil publique : aucune donnée personnelle, rien que du contenu
    choisi par le Bureau et les activités qu'il a décidé d'annoncer."""
    from apps.activites.models import Activite

    annoncees = (Activite.objects
                 .filter(annoncee=True, statut=Activite.Statut.PUBLIEE,
                         date_debut__gte=timezone.now())
                 .select_related('section').order_by('date_debut')[:4])
    realisations = Realisation.objects.filter(publiee=True)
    return render(requete, 'vitrine/accueil.html', {
        'page': PageAccueil.courante(),
        'chiffres': ChiffreCle.objects.all(),
        'realisations': realisations,
        'galerie': PhotoGalerie.objects.filter(publiee=True).defer('image'),
        'activites': annoncees,
        'peut_modifier': requete.user.is_authenticated and requete.user.role in EDITRICES,
    })


@login_required
@role_requis(*EDITRICES)
def modifier(requete):
    page = PageAccueil.objects.first() or PageAccueil(
        accroche=PageAccueil.courante().accroche)
    peut_valider = requete.user.role == 'ADMIN'
    donnees = requete.POST or None
    formulaire = FormulairePageAccueil(donnees, requete.FILES or None, instance=page,
                                       peut_valider=peut_valider)
    chiffres = FormsetChiffres(donnees, queryset=ChiffreCle.objects.all(), prefix='chiffres')
    realisations = FormsetRealisations(donnees, queryset=Realisation.objects.all(),
                                       prefix='realisations')
    galerie = FormsetGalerie(donnees, queryset=PhotoGalerie.objects.defer('image'),
                             prefix='galerie')
    ajout = FormulaireAjoutPhotos(donnees, requete.FILES or None)
    formulaires = (formulaire, chiffres, realisations, galerie, ajout)
    if requete.method == 'POST' and all(f.is_valid() for f in formulaires):
        with transaction.atomic():
            page = formulaire.save(commit=False)
            page.modifiee_par = requete.user
            page.save()
            chiffres.save()
            realisations.save()
            galerie.save()
            ajoutees = ajout.enregistrer()
        journaliser(requete.user, 'MODIFICATION_PAGE_ACCUEIL',
                    f'{ajoutees} photo(s) ajoutée(s)' if ajoutees else '', requete)
        if ajoutees:
            messages.success(requete, f'{ajoutees} photo(s) ajoutée(s) : donnez-leur une légende.')
            return redirect(f"{requete.path}#galerie")
        messages.success(requete, "Page d'accueil mise à jour.")
        return redirect('vitrine:accueil')
    return render(requete, 'vitrine/modifier.html', {
        'formulaire': formulaire, 'chiffres': chiffres, 'realisations': realisations,
        'galerie': galerie, 'ajout': ajout,
        'peut_valider': peut_valider})


def photo_presidente(requete):
    """Sert la photo stockée en base. L'adresse porte ?v=<date de mise à jour> :
    elle change à chaque nouvelle photo, d'où une mise en cache longue possible."""
    page = PageAccueil.objects.first()
    if page is None or not page.presidente_photo:
        raise Http404
    reponse = HttpResponse(bytes(page.presidente_photo), content_type='image/jpeg')
    reponse['Cache-Control'] = 'public, max-age=604800'
    return reponse


def photo_galerie(requete, pk):
    photo = PhotoGalerie.objects.filter(pk=pk).only('image', 'publiee').first()
    if photo is None:
        raise Http404
    if not photo.publiee and not (requete.user.is_authenticated
                                  and requete.user.role in EDITRICES):
        raise Http404
    reponse = HttpResponse(bytes(photo.image), content_type='image/jpeg')
    reponse['Cache-Control'] = 'public, max-age=604800'
    return reponse
