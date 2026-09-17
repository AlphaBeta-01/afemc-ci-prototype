from django import forms

from .models import Paiement

CLASSE = {'class': 'form-control'}


class FormulairePaiement(forms.Form):
    montant = forms.DecimalField(max_digits=10, decimal_places=2, min_value=1,
                                 label='Montant versé (FCFA)',
                                 widget=forms.NumberInput(attrs=CLASSE))
    mode = forms.ChoiceField(choices=Paiement.Mode.choices, label='Mode de règlement',
                             widget=forms.Select(attrs={'class': 'form-select'}))
    reference = forms.CharField(required=False, max_length=60, label='Référence du reçu',
                                widget=forms.TextInput(attrs=CLASSE))


class FormulaireEmission(forms.Form):
    exercice = forms.IntegerField(label='Exercice', widget=forms.NumberInput(attrs=CLASSE))
    montant = forms.DecimalField(max_digits=10, decimal_places=2, min_value=1,
                                 label='Montant de la cotisation (FCFA)',
                                 widget=forms.NumberInput(attrs=CLASSE))
    date_echeance = forms.DateField(label="Date d'échéance",
                                    widget=forms.DateInput(attrs={**CLASSE, 'type': 'date'}))


class FormulaireExemption(forms.Form):
    exercice = forms.IntegerField(label='Exercice', widget=forms.NumberInput(attrs=CLASSE))
    motif = forms.CharField(label='Motif', max_length=200,
                            widget=forms.TextInput(attrs=CLASSE))
