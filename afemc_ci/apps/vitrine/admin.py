from django.contrib import admin

from .models import ChiffreCle, PageAccueil, Realisation


@admin.register(PageAccueil)
class PageAccueilAdmin(admin.ModelAdmin):
    list_display = ('accroche', 'contenu_verifie', 'modifiee_le')


@admin.register(ChiffreCle)
class ChiffreCleAdmin(admin.ModelAdmin):
    list_display = ('valeur', 'libelle', 'precision', 'ordre')


@admin.register(Realisation)
class RealisationAdmin(admin.ModelAdmin):
    list_display = ('annee', 'titre', 'source', 'publiee')
    list_filter = ('publiee', 'annee')
