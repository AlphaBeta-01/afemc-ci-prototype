from django.contrib import admin

from .models import JournalOperation


@admin.register(JournalOperation)
class JournalOperationAdmin(admin.ModelAdmin):
    list_display = ('horodatage', 'utilisateur', 'type_operation', 'detail')
    list_filter = ('type_operation',)
    search_fields = ('detail',)
    readonly_fields = ('utilisateur', 'type_operation', 'detail', 'adresse_ip', 'horodatage')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
