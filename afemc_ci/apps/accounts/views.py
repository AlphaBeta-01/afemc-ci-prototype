from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from apps.core.decorators import role_requis
from apps.core.services import journaliser

from .forms import FormulaireActivation, FormulaireCompteResponsable, FormulaireConnexion
from .models import Utilisateur
from .services import creer_compte_responsable


class VueConnexion(auth_views.LoginView):
    template_name = 'accounts/connexion.html'
    authentication_form = FormulaireConnexion
    redirect_authenticated_user = True

    def form_valid(self, form):
        reponse = super().form_valid(form)
        journaliser(self.request.user, 'CONNEXION_REUSSIE', '', self.request)
        return reponse

    def form_invalid(self, form):
        journaliser(None, 'CONNEXION_ECHOUEE',
                    f"identifiant : {form.data.get('username', '')[:80]}", self.request)
        return super().form_invalid(form)


class VueDeconnexion(auth_views.LogoutView):
    next_page = reverse_lazy('accounts:connexion')


class VueActivation(auth_views.PasswordResetConfirmView):
    """Définition du mot de passe par le membre, à partir du lien reçu (RG02).

    Le compte est créé inactif lors de la validation de la demande d'adhésion
    (`apps.adhesions.services.creer_compte_acces`) : cette vue est le seul
    moyen de le rendre exploitable.
    """
    template_name = 'accounts/activation.html'
    form_class = FormulaireActivation
    success_url = reverse_lazy('accounts:connexion')
    post_reset_login = False

    def form_valid(self, form):
        reponse = super().form_valid(form)
        self.user.is_active = True
        self.user.save(update_fields=['is_active'])
        journaliser(self.user, 'ACTIVATION_COMPTE', '', self.request)
        messages.success(self.request,
                          'Compte activé : vous pouvez à présent vous connecter.')
        return reponse


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
