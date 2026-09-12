from django.contrib import admin

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
    list_display = ('cotisation', 'regle', 'jours_ecart', 'date_emission')
    list_filter = ('regle',)
