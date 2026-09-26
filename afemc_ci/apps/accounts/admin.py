from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.core.utils import ordre_alphabetique

from .models import Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display = ('email', 'nom', 'prenoms', 'role', 'section', 'is_active')
    list_filter = ('role', 'section', 'is_active')
    search_fields = ('email', 'nom', 'prenoms')
    ordering = ordre_alphabetique()
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Identité', {'fields': ('nom', 'prenoms')}),
        ('Rôle', {'fields': ('role', 'section')}),
        ('Droits', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
    )
    add_fieldsets = (
        (None, {'classes': ('wide',),
                'fields': ('email', 'nom', 'prenoms', 'role', 'section',
                           'password1', 'password2')}),
    )
