"""Moteur de règles de relance (§ 5.6.2)."""
from django.conf import settings
from django.db import models


class RegleRelance(models.Model):
    """Règle enregistrée en base : modifiable sans intervention d'un développeur."""

    class Niveau(models.TextChoices):
        INFORMATION = 'INFORMATION', 'Information'
        RAPPEL = 'RAPPEL', 'Rappel'
        RETARD = 'RETARD', 'Retard'
        RELANCE_1 = 'RELANCE_1', 'Relance 1'
        RELANCE_2 = 'RELANCE_2', 'Relance 2'
        ALERTE = 'ALERTE', 'Alerte'

    class Destinataires(models.TextChoices):
        MEMBRE = 'MEMBRE', 'Membre'
        MEMBRE_SECTION = 'MEMBRE_SECTION', 'Membre et responsable de section'
        MEMBRE_FINANCIER = 'MEMBRE_FINANCIER', 'Membre et responsable financier'
        RESPONSABLES = 'RESPONSABLES', 'Responsables uniquement'

    code = models.CharField(max_length=10, unique=True)
    libelle = models.CharField(max_length=120)
    decalage_jours = models.IntegerField(
        help_text="Négatif : avant l'échéance. Positif : après l'échéance.")
    niveau = models.CharField(max_length=20, choices=Niveau.choices)
    destinataires = models.CharField(max_length=20, choices=Destinataires.choices,
                                     default=Destinataires.MEMBRE)
    gabarit_message = models.CharField(max_length=80,
                                       default='notifications/relance.txt')
    active = models.BooleanField(default=True)
    modifiee_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL)
    modifiee_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'règle de relance'
        verbose_name_plural = 'règles de relance'
        ordering = ['decalage_jours']

    def __str__(self):
        return f'{self.code} — {self.libelle}'

    @classmethod
    def applicable(cls, ecart_jours, cotisation):
        """Retourne la règle correspondant à l'écart constaté, s'il en existe une.

        ecart_jours = date_echeance - date du jour
            valeur positive : échéance à venir
            valeur négative : échéance dépassée
        """
        from apps.cotisations.models import Cotisation
        from apps.membres.models import Membre

        if cotisation.statut in (Cotisation.Statut.PAYEE, Cotisation.Statut.EXEMPTEE):
            return None
        if cotisation.membre.statut == Membre.Statut.SUSPENDU:
            return None        # aucune relance adressée à un membre suspendu

        decalage = -ecart_jours     # normalisation : positif = retard
        return (cls.objects
                .filter(active=True, decalage_jours__lte=decalage)
                .order_by('-decalage_jours')
                .first())


class Relance(models.Model):
    cotisation = models.ForeignKey('cotisations.Cotisation', on_delete=models.PROTECT,
                                   related_name='relances')
    regle = models.ForeignKey(RegleRelance, on_delete=models.PROTECT,
                              related_name='relances')
    date_emission = models.DateTimeField(auto_now_add=True)
    jours_ecart = models.IntegerField()

    class Meta:
        verbose_name = 'relance'
        verbose_name_plural = 'relances'
        ordering = ['-date_emission']
        constraints = [
            models.UniqueConstraint(fields=['cotisation', 'regle'],
                                    name='unicite_relance_cotisation_regle'),
        ]

    def __str__(self):
        return f'{self.regle.code} — {self.cotisation}'
