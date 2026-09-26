from django.contrib import admin

from apps.core.utils import ordre_alphabetique

from .models import DemandeAdhesion, PieceJustificative


class PieceJustificativeInline(admin.TabularInline):
    model = PieceJustificative
    extra = 0
    readonly_fields = ('depose_le',)


@admin.register(DemandeAdhesion)
class DemandeAdhesionAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenoms', 'section', 'statut', 'date_soumission')
    list_filter = ('statut', 'section')
    search_fields = ('nom', 'prenoms', 'email')
    ordering = (*ordre_alphabetique(), '-date_soumission')
    inlines = [PieceJustificativeInline]
