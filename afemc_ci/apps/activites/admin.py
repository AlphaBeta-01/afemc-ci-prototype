from django.contrib import admin

from .models import Activite, Inscription, MembreComite


class MembreComiteInline(admin.TabularInline):
    model = MembreComite
    extra = 0
    autocomplete_fields = ()
    readonly_fields = ('ajoutee_par', 'ajoutee_le')


@admin.register(Activite)
class ActiviteAdmin(admin.ModelAdmin):
    list_display = ('titre', 'type', 'date_debut', 'lieu', 'section', 'statut')
    list_filter = ('statut', 'type', 'section')
    search_fields = ('titre', 'lieu')
    inlines = [MembreComiteInline]


@admin.register(Inscription)
class InscriptionAdmin(admin.ModelAdmin):
    list_display = ('activite', 'membre', 'inscrite_le')
    list_filter = ('activite',)
