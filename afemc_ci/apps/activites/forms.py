from django import forms
from django.db.models.functions import Lower

from apps.core.utils import ordre_alphabetique

from .models import Activite

CLASSE = {'class': 'form-control'}
FORMAT_DATE_HEURE = '%Y-%m-%dT%H:%M'


class ChampDateHeure(forms.DateTimeField):
    widget = forms.DateTimeInput(attrs={**CLASSE, 'type': 'datetime-local'},
                                 format=FORMAT_DATE_HEURE)
    input_formats = [FORMAT_DATE_HEURE]


class FormulaireActivite(forms.ModelForm):
    """Fiche d'une activité. Le statut n'y figure pas : publier, clôturer ou
    annuler sont des décisions distinctes, réservées à la Responsable."""

    date_debut = ChampDateHeure(label='Début')
    date_fin = ChampDateHeure(label='Fin', required=False)

    class Meta:
        model = Activite
        fields = ['titre', 'type', 'date_debut', 'date_fin', 'lieu', 'section', 'places',
                  'description']
        labels = {'section': 'Section concernée'}
        widgets = {
            'titre': forms.TextInput(attrs=CLASSE),
            'type': forms.Select(attrs={'class': 'form-select'}),
            'lieu': forms.TextInput(attrs=CLASSE),
            'section': forms.Select(attrs={'class': 'form-select'}),
            'places': forms.NumberInput(attrs={**CLASSE, 'min': 1}),
            'description': forms.Textarea(attrs={**CLASSE, 'rows': 5}),
        }

    def __init__(self, *args, **kwargs):
        from apps.sections.models import Section
        super().__init__(*args, **kwargs)
        self.fields['section'].queryset = Section.objects.filter(active=True).order_by(
            Lower('libelle'))
        self.fields['section'].empty_label = 'Nationale — toutes les sections'

    def clean(self):
        cleaned = super().clean()
        debut, fin = cleaned.get('date_debut'), cleaned.get('date_fin')
        if debut and fin and fin < debut:
            self.add_error('date_fin', 'La fin ne peut pas précéder le début.')
        places = cleaned.get('places')
        if (places is not None and self.instance.pk
                and places < self.instance.inscriptions.count()):
            self.add_error('places', f'{self.instance.inscriptions.count()} membres sont déjà '
                                     'inscrites : le nombre de places ne peut pas être inférieur.')
        return cleaned


class ChoixMembre(forms.ModelChoiceField):
    def label_from_instance(self, membre):
        return f'{membre.nom} {membre.prenoms} — {membre.section.libelle}'


class FormulaireComite(forms.Form):
    membre = ChoixMembre(queryset=None, label='Membre',
                         widget=forms.Select(attrs={'class': 'form-select'}))
    mission = forms.CharField(label='Mission (facultatif)', required=False, max_length=80,
                              widget=forms.TextInput(attrs={
                                  **CLASSE, 'placeholder': 'Logistique, communication…'}))

    def __init__(self, *args, activite=None, **kwargs):
        from apps.membres.models import Membre
        super().__init__(*args, **kwargs)
        membres = Membre.objects.filter(statut=Membre.Statut.ACTIF)
        if activite is not None:
            membres = membres.exclude(comites__activite=activite)
        self.fields['membre'].queryset = (membres.select_related('section')
                                          .order_by(*ordre_alphabetique()))
