from django.contrib import admin

from apps.core.utils import ordre_alphabetique

from .models import Relance, RegleRelance


@admin.register(RegleRelance)
class RegleRelanceAdmin(admin.ModelAdmin):
    list_display = ('code', 'libelle', 'decalage_jours', 'niveau',
                    'destinataires', 'active')
    list_filter = ('active', 'niveau')

    def save_model(self, request, obj, form, change):
        obj.modifiee_par = request.user
        super().save_model(request, obj, form, change)


@admin.register(Relance)
class RelanceAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenoms', 'exercice', 'regle', 'jours_ecart', 'date_emission')
    list_filter = ('regle',)
    ordering = (*ordre_alphabetique('cotisation__membre__'), '-date_emission')
    list_select_related = ('cotisation__membre', 'regle')

    @admin.display(description='nom', ordering='cotisation__membre__nom')
    def nom(self, relance):
        return relance.cotisation.membre.nom

    @admin.display(description='prénoms', ordering='cotisation__membre__prenoms')
    def prenoms(self, relance):
        return relance.cotisation.membre.prenoms

    @admin.display(description='exercice', ordering='cotisation__exercice')
    def exercice(self, relance):
        return relance.cotisation.exercice
