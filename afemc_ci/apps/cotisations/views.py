from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.decorators import role_requis
from apps.core.utils import ordre_alphabetique, paginer
from apps.membres.models import Membre

from .forms import FormulaireEmission, FormulairePaiement
from .models import Cotisation
from .services import emettre_cotisations_exercice, enregistrer_paiement, indicateurs_exercice

RESPONSABLES = ('ADMIN', 'RESP_ADMIN', 'RESP_FINANCIER')          # pas RESP_SECTION


@login_required
@role_requis(*RESPONSABLES)
def liste(requete):
    exercice = int(requete.GET.get('exercice', timezone.localdate().year))
    membres_visibles = Membre.objects.visibles_par(requete.user)
    cotisations = (Cotisation.objects
                   .filter(exercice=exercice, membre__in=membres_visibles)
                   .select_related('membre', 'membre__section'))
    if requete.GET.get('statut'):
        cotisations = cotisations.filter(statut=requete.GET['statut'])
    return render(requete, 'cotisations/liste.html', {
        'page': paginer(cotisations.order_by(*ordre_alphabetique('membre__')), requete),
        'exercice': exercice,
        'statuts': Cotisation.Statut.choices,
        'parametres': requete.GET,
        'indicateurs': indicateurs_exercice(exercice),
    })


@login_required
@role_requis('RESP_FINANCIER')          # seule la Trésorière enregistre un paiement ;
def saisir_paiement(requete, pk):        # la Présidente garde la vue globale, pas la saisie
    cotisation = get_object_or_404(Cotisation.objects.select_related('membre'), pk=pk)
    formulaire = FormulairePaiement(requete.POST or None)
    if requete.method == 'POST' and formulaire.is_valid():
        try:
            enregistrer_paiement(cotisation,
                                 formulaire.cleaned_data['montant'],
                                 formulaire.cleaned_data['mode'],
                                 formulaire.cleaned_data['reference'],
                                 requete.user)
        except ValidationError as err:
            formulaire.add_error('montant', err.messages[0])
        else:
            messages.success(requete, 'Paiement enregistré.')
            return redirect('cotisations:liste')
    return render(requete, 'cotisations/paiement.html',
                  {'formulaire': formulaire, 'cotisation': cotisation})


@login_required
@role_requis('ADMIN', 'RESP_FINANCIER')
def emettre(requete):
    formulaire = FormulaireEmission(requete.POST or None)
    if requete.method == 'POST' and formulaire.is_valid():
        creees, ignorees = emettre_cotisations_exercice(
            formulaire.cleaned_data['exercice'],
            formulaire.cleaned_data['montant'],
            formulaire.cleaned_data['date_echeance'],
            requete.user)
        messages.success(
            requete,
            f'{len(creees)} cotisation(s) émise(s), {ignorees} déjà existante(s).')
        return redirect('cotisations:liste')
    return render(requete, 'cotisations/emission.html', {'formulaire': formulaire})


@login_required
@role_requis(*RESPONSABLES)
def exporter_csv(requete):
    import csv
    exercice = int(requete.GET.get('exercice', timezone.localdate().year))
    reponse = HttpResponse(content_type='text/csv; charset=utf-8')
    reponse['Content-Disposition'] = f'attachment; filename="cotisations_{exercice}.csv"'
    plume = csv.writer(reponse, delimiter=';')
    plume.writerow(['Matricule', 'Nom', 'Prénoms', 'Section', 'Exercice',
                    'Montant dû', 'Montant payé', 'Reste', 'Échéance', 'Statut'])
    for c in (Cotisation.objects
              .filter(exercice=exercice,
                      membre__in=Membre.objects.visibles_par(requete.user))
              .select_related('membre', 'membre__section')
              .order_by(*ordre_alphabetique('membre__'))):
        plume.writerow([c.membre.matricule, c.membre.nom, c.membre.prenoms,
                        c.membre.section.libelle, c.exercice, c.montant_du,
                        c.montant_paye, c.reste_a_payer, c.date_echeance,
                        c.get_statut_display()])
    return reponse
