from django.contrib import admin

from .models import Cotisation, Exemption, Paiement


@admin.register(Cotisation)
class CotisationAdmin(admin.ModelAdmin):
    list_display = ('membre', 'exercice', 'montant_du', 'montant_paye',
                    'date_echeance', 'statut')
    list_filter = ('exercice', 'statut', 'membre__section')
    search_fields = ('membre__nom', 'membre__matricule')


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ('cotisation', 'montant', 'mode', 'date_paiement', 'enregistre_par')
    list_filter = ('mode',)


@admin.register(Exemption)
class ExemptionAdmin(admin.ModelAdmin):
    list_display = ('membre', 'exercice', 'motif', 'date_decision')
    list_filter = ('exercice',)
