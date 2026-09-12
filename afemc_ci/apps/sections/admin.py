from django.contrib import admin

from .models import Section


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('code', 'libelle', 'ville', 'etablissement', 'active')
    list_filter = ('active',)
    search_fields = ('code', 'libelle', 'ville')
