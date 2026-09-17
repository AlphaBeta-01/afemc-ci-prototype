from django import forms
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm

from .models import Utilisateur
from .services import ROLES_ATTRIBUABLES


class FormulaireConnexion(AuthenticationForm):
    username = forms.EmailField(
        label='Adresse électronique',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'autofocus': True,
                                       'placeholder': 'prenom.nom@exemple.org'}))
    password = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    error_messages = {
        'invalid_login': "Adresse électronique ou mot de passe incorrect.",
        'inactive': "Ce compte est désactivé.",
    }

    def confirm_login_allowed(self, user):
        if user.est_verrouille:
            raise forms.ValidationError(
                "Compte temporairement verrouillé après plusieurs tentatives "
                "de connexion échouées. Réessayez dans quelques minutes ou "
                "utilisez « Mot de passe oublié ».",
                code='verrouille')
        super().confirm_login_allowed(user)


class FormulaireActivation(SetPasswordForm):
    """Définition du mot de passe lors de l'activation d'un compte (RG11)."""

    new_password1 = forms.CharField(
        label='Nouveau mot de passe', strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autofocus': True}))
    new_password2 = forms.CharField(
        label='Confirmation du mot de passe', strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}))


class FormulaireMotDePasseOublie(forms.Form):
    """Demande de lien de réinitialisation (RG11)."""

    email = forms.EmailField(
        label='Adresse électronique',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'autofocus': True,
                                       'placeholder': 'prenom.nom@exemple.org'}))


class FormulaireCompteResponsable(forms.ModelForm):
    """Création d'un compte responsable (RG08), réservée à la Présidente.

    N'appelle jamais `.save()` : la création passe par
    `apps.accounts.services.creer_compte_responsable`, seule à savoir fixer
    un mot de passe inutilisable en toute sécurité (cf. ce module).
    """

    class Meta:
        model = Utilisateur
        fields = ['nom', 'prenoms', 'email', 'role', 'section']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'prenoms': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'section': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = [
            (valeur, libelle) for valeur, libelle in Utilisateur.Role.choices
            if valeur in ROLES_ATTRIBUABLES]
        self.fields['section'].required = False
        self.fields['section'].help_text = 'Requise uniquement pour un responsable de section.'

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get('role')
        if role == Utilisateur.Role.RESP_SECTION and not cleaned.get('section'):
            self.add_error('section', 'Une section est requise pour ce rôle.')
        elif role != Utilisateur.Role.RESP_SECTION:
            cleaned['section'] = None
        return cleaned
