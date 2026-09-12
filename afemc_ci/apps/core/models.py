"""Entités transversales : journal des opérations (RG09)."""
from django.conf import settings
from django.db import models


class JournalOperation(models.Model):
    """Trace non modifiable des opérations sensibles (§ 5.6.4)."""

    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL,
                                    related_name='operations')
    type_operation = models.CharField(max_length=40)
    detail = models.TextField(blank=True)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    horodatage = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "opération journalisée"
        verbose_name_plural = "journal des opérations"
        ordering = ['-horodatage']
        indexes = [
            models.Index(fields=['-horodatage']),
            models.Index(fields=['type_operation']),
        ]

    def __str__(self):
        auteur = self.utilisateur or 'système'
        return f'{self.horodatage:%d/%m/%Y %H:%M} — {auteur} — {self.type_operation}'
