from django.contrib import admin

from apps.core.utils import ordre_alphabetique

from .models import Cotisation, Paiement


@admin.register(Cotisation)
class CotisationAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenoms', 'exercice', 'montant_du', 'montant_paye',
                    'date_echeance', 'statut')
    list_filter = ('exercice', 'statut', 'membre__section')
    search_fields = ('membre__nom', 'membre__prenoms', 'membre__matricule')
    ordering = (*ordre_alphabetique('membre__'), '-exercice')
    list_select_related = ('membre',)

    @admin.display(description='nom', ordering='membre__nom')
    def nom(self, cotisation):
        return cotisation.membre.nom

    @admin.display(description='prénoms', ordering='membre__prenoms')
    def prenoms(self, cotisation):
        return cotisation.membre.prenoms


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenoms', 'exercice', 'montant', 'mode', 'date_paiement',
                    'enregistre_par')
    list_filter = ('mode',)
    ordering = (*ordre_alphabetique('cotisation__membre__'), '-date_paiement')
    list_select_related = ('cotisation__membre', 'enregistre_par')

    @admin.display(description='nom', ordering='cotisation__membre__nom')
    def nom(self, paiement):
        return paiement.cotisation.membre.nom

    @admin.display(description='prénoms', ordering='cotisation__membre__prenoms')
    def prenoms(self, paiement):
        return paiement.cotisation.membre.prenoms

    @admin.display(description='exercice', ordering='cotisation__exercice')
    def exercice(self, paiement):
        return paiement.cotisation.exercice
