from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('destinataire', 'type', 'objet', 'statut', 'tentatives', 'cree_le')
    list_filter = ('statut', 'type', 'canal')
    search_fields = ('destinataire', 'objet')
