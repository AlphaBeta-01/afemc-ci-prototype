from django import forms

from apps.accounts.models import Utilisateur
from apps.sections.models import Section

from .models import Membre

CLASSE = {'class': 'form-control'}


class FormulaireMembre(forms.ModelForm):
    class Meta:
        model = Membre
        fields = ['nom', 'prenoms', 'email', 'telephone', 'date_naissance',
                  'grade', 'etablissement', 'section', 'date_adhesion', 'statut']
        labels = {
            'nom': 'Nom', 'prenoms': 'Prénoms', 'email': 'Adresse électronique',
            'telephone': 'Téléphone', 'date_naissance': 'Date de naissance',
            'grade': 'Grade', 'etablissement': 'Établissement', 'section': 'Section',
            'date_adhesion': "Date d'adhésion", 'statut': 'Statut',
        }
        widgets = {
            'nom': forms.TextInput(attrs=CLASSE),
            'prenoms': forms.TextInput(attrs=CLASSE),
            'email': forms.EmailInput(attrs=CLASSE),
            'telephone': forms.TextInput(attrs=CLASSE),
            'date_naissance': forms.DateInput(attrs={**CLASSE, 'type': 'date'}),
            'grade': forms.TextInput(attrs=CLASSE),
            'etablissement': forms.TextInput(attrs=CLASSE),
            'section': forms.Select(attrs={'class': 'form-select'}),
            'date_adhesion': forms.DateInput(attrs={**CLASSE, 'type': 'date'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, utilisateur=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Un responsable de section n'ajoute des membres que dans sa propre
        # section (RG08) : le choix est restreint, pas seulement masqué, pour
        # rejeter toute valeur soumise directement dans la requête.
        if (utilisateur and utilisateur.role == 'RESP_SECTION'
                and utilisateur.section_id):
            self.fields['section'].queryset = Section.objects.filter(
                pk=utilisateur.section_id)
            self.fields['section'].initial = utilisateur.section_id

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        existant = Membre.objects.filter(email=email)
        if self.instance.pk:
            existant = existant.exclude(pk=self.instance.pk)
        if existant.exists():
            raise forms.ValidationError(
                "Cette adresse électronique est déjà associée à un autre membre.")
        return email

    def save(self, commit=True):
        membre = super().save(commit=False)
        # La Présidente, la Secrétaire générale, la Trésorière et les
        # Coordinatrices de section paient elles aussi leur cotisation : leur
        # compte de connexion (créé sans fiche membre, cf. creer_compte_responsable)
        # est rattaché automatiquement s'il existe déjà avec la même adresse —
        # jamais créé ici, seulement relié, pour ne pas dupliquer l'identité.
        if not membre.utilisateur_id:
            compte = Utilisateur.objects.filter(email__iexact=membre.email).first()
            if compte:
                membre.utilisateur = compte
        if commit:
            membre.save()
        return membre
