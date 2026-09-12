"""Organisation territoriale de l'association (§ 5.5.3)."""
from django.db import models


class Section(models.Model):
    code = models.CharField(max_length=10, unique=True)
    libelle = models.CharField(max_length=100)
    ville = models.CharField(max_length=80, blank=True)
    etablissement = models.CharField(max_length=150, blank=True)
    date_creation = models.DateField(auto_now_add=True)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'section'
        verbose_name_plural = 'sections'
        ordering = ['libelle']

    def __str__(self):
        return self.libelle

    def effectif_actif(self):
        return self.membres.filter(statut='ACTIF').count()
