from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.decorators.http import require_POST

from apps.core.decorators import role_requis
from apps.core.services import journaliser

from .forms import (FormulaireActivation, FormulaireCompteResponsable, FormulaireConnexion,
                    FormulaireMotDePasseOublie)
from .models import Utilisateur
from .services import creer_compte_responsable, demander_reinitialisation_mot_de_passe


class VueConnexion(auth_views.LoginView):
    template_name = 'accounts/connexion.html'
    authentication_form = FormulaireConnexion
    redirect_authenticated_user = True

    def form_valid(self, form):
        reponse = super().form_valid(form)
        self.request.user.reinitialiser_tentatives_connexion()
        journaliser(self.request.user, 'CONNEXION_REUSSIE', '', self.request)
        return reponse

    def form_invalid(self, form):
        identifiant = form.data.get('username', '')[:80]
        # Comptabilisé seulement si l'adresse correspond à un compte existant
        # (RG10) : impossible de verrouiller un compte qui n'existe pas, et
        # ça n'indique rien à l'appelant sur l'existence ou non de l'adresse
        # — le message d'erreur reste identique dans les deux cas.
        utilisateur = Utilisateur.objects.filter(email__iexact=identifiant).first()
        if utilisateur is not None:
            utilisateur.enregistrer_echec_connexion()
            if utilisateur.est_verrouille:
                journaliser(None, 'COMPTE_VERROUILLE', identifiant, self.request)
        journaliser(None, 'CONNEXION_ECHOUEE', f"identifiant : {identifiant}", self.request)
        return super().form_invalid(form)


class VueDeconnexion(auth_views.LogoutView):
    next_page = reverse_lazy('accounts:connexion')


class VueActivation(auth_views.PasswordResetConfirmView):
    """Définition du mot de passe à partir du lien reçu (RG11).

    Un seul mécanisme pour deux usages : l'activation d'un compte tout juste
    créé (inactif, cf. `creer_compte_acces`/`creer_compte_responsable`) et la
    réinitialisation d'un mot de passe oublié sur un compte déjà actif — le
    lien et l'écran sont identiques, seul le message final diffère.
    """
    template_name = 'accounts/activation.html'
    form_class = FormulaireActivation
    success_url = reverse_lazy('accounts:connexion')
    post_reset_login = False

    def form_valid(self, form):
        premiere_activation = not self.user.is_active
        reponse = super().form_valid(form)
        self.user.is_active = True
        self.user.save(update_fields=['is_active'])
        if premiere_activation:
            journaliser(self.user, 'ACTIVATION_COMPTE', '', self.request)
            messages.success(self.request,
                             'Compte activé : vous pouvez à présent vous connecter.')
        else:
            journaliser(self.user, 'REINITIALISATION_MOT_DE_PASSE', '', self.request)
            messages.success(self.request,
                             'Mot de passe modifié : vous pouvez à présent vous connecter.')
        return reponse


class VueMotDePasseOublie(View):
    """Demande de lien de réinitialisation, sans révéler si l'adresse existe."""
    template_name = 'accounts/mot_de_passe_oublie.html'

    def get(self, requete):
        return render(requete, self.template_name, {'formulaire': FormulaireMotDePasseOublie()})

    def post(self, requete):
        formulaire = FormulaireMotDePasseOublie(requete.POST)
        if formulaire.is_valid():
            demander_reinitialisation_mot_de_passe(formulaire.cleaned_data['email'], requete)
            return render(requete, 'accounts/mot_de_passe_oublie_envoye.html')
        return render(requete, self.template_name, {'formulaire': formulaire})


@login_required
def profil(requete):
    return render(requete, 'accounts/profil.html', {'utilisateur': requete.user})


@login_required
@role_requis('ADMIN')
def comptes_liste(requete):
    comptes = (Utilisateur.objects.exclude(role=Utilisateur.Role.MEMBRE)
              .select_related('section').order_by('nom', 'prenoms'))
    return render(requete, 'accounts/comptes_liste.html', {'comptes': comptes})


@login_required
@role_requis('ADMIN')
def comptes_creer(requete):
    formulaire = FormulaireCompteResponsable(requete.POST or None)
    if requete.method == 'POST' and formulaire.is_valid():
        donnees = formulaire.cleaned_data
        compte = creer_compte_responsable(
            nom=donnees['nom'], prenoms=donnees['prenoms'], email=donnees['email'],
            role=donnees['role'], section=donnees.get('section'), cree_par=requete.user)
        messages.success(
            requete,
            f"Compte créé pour {compte.nom_complet()}. Un lien d'activation lui a été envoyé.")
        return redirect('accounts:comptes_liste')
    return render(requete, 'accounts/comptes_creer.html', {'formulaire': formulaire})


@require_POST
@login_required
@role_requis('ADMIN')
def compte_basculer_actif(requete, pk):
    compte = get_object_or_404(Utilisateur, pk=pk)
    if compte == requete.user:
        messages.error(requete, 'Vous ne pouvez pas désactiver votre propre compte.')
        return redirect('accounts:comptes_liste')

    compte.is_active = not compte.is_active
    compte.save(update_fields=['is_active'])
    journaliser(requete.user,
               'REACTIVATION_COMPTE_RESPONSABLE' if compte.is_active
               else 'DESACTIVATION_COMPTE_RESPONSABLE',
               compte.email, requete)
    messages.success(requete,
                     f"Compte {'réactivé' if compte.is_active else 'désactivé'}.")
    return redirect('accounts:comptes_liste')
