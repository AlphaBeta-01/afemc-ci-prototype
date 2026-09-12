from django.contrib import admin

from .models import Membre


@admin.register(Membre)
class MembreAdmin(admin.ModelAdmin):
    list_display = ('matricule', 'nom', 'prenoms', 'section', 'statut', 'date_adhesion')
    list_filter = ('statut', 'section')
    search_fields = ('matricule', 'nom', 'prenoms', 'email')
    readonly_fields = ('matricule', 'cree_le')
