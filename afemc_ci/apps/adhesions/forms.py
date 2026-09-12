from django import forms
from django.conf import settings
from django.core.validators import FileExtensionValidator

from .models import EXTENSIONS_AUTORISEES, DemandeAdhesion, PieceJustificative

CLASSE = {'class': 'form-control'}


class FormulaireDemande(forms.ModelForm):
    class Meta:
        model = DemandeAdhesion
        fields = ['nom', 'prenoms', 'email', 'telephone', 'grade',
                  'etablissement', 'section', 'motivation']
        widgets = {
            'nom': forms.TextInput(attrs=CLASSE),
            'prenoms': forms.TextInput(attrs=CLASSE),
            'email': forms.EmailInput(attrs=CLASSE),
            'telephone': forms.TextInput(attrs=CLASSE),
            'grade': forms.TextInput(attrs=CLASSE),
            'etablissement': forms.TextInput(attrs=CLASSE),
            'section': forms.Select(attrs={'class': 'form-select'}),
            'motivation': forms.Textarea(attrs={**CLASSE, 'rows': 4}),
        }


class FormulairePieceJustificative(forms.Form):
    """Une ligne du formulaire de dépôt : type de document + fichier.

    Les deux champs sont facultatifs à l'échelle d'UNE ligne — la règle
    « au moins un document » est vérifiée globalement par le formset
    (`ExigerAuMoinsUnePiece`), pour permettre de laisser un emplacement vide.
    """
    type_piece = forms.ChoiceField(
        label='Type de document', choices=PieceJustificative.TypePiece.choices,
        required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    fichier = forms.FileField(
        label='Fichier', required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
        validators=[FileExtensionValidator(EXTENSIONS_AUTORISEES)])

    def clean(self):
        cleaned = super().clean()
        fichier = cleaned.get('fichier')
        if fichier and not cleaned.get('type_piece'):
            self.add_error('type_piece', 'Précisez le type de ce document.')
        if fichier and fichier.size > settings.TAILLE_MAX_PIECE_JUSTIFICATIVE:
            self.add_error('fichier', 'Le fichier dépasse la taille maximale autorisée (5 Mo).')
        return cleaned


class ExigerAuMoinsUnePiece(forms.BaseFormSet):

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        if not any(f.cleaned_data.get('fichier') for f in self.forms if f.cleaned_data):
            raise forms.ValidationError(
                "Joignez au moins un document justifiant votre statut "
                "d'enseignante chercheure (carte professionnelle, attestation "
                "d'exercice ou diplôme).")


FormsetPiecesJustificatives = forms.formset_factory(
    FormulairePieceJustificative, formset=ExigerAuMoinsUnePiece, extra=2)
