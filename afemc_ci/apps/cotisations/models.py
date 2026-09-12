"""Cotisations, paiements et exemptions (§ 5.4.3, § 5.5.5)."""
from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Cotisation(models.Model):

    class Statut(models.TextChoices):
        EN_ATTENTE = 'EN_ATTENTE', 'En attente'
        PARTIEL = 'PARTIEL', 'Partiellement payée'
        PAYEE = 'PAYEE', 'Payée'
        EN_RETARD = 'EN_RETARD', 'En retard'
        EXEMPTEE = 'EXEMPTEE', 'Exemptée'

    membre = models.ForeignKey('membres.Membre', on_delete=models.PROTECT,
                               related_name='cotisations')
    exercice = models.PositiveIntegerField()
    montant_du = models.DecimalField(max_digits=10, decimal_places=2)
    montant_paye = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date_emission = models.DateField(auto_now_add=True)
    date_echeance = models.DateField()
    statut = models.CharField(max_length=12, choices=Statut.choices,
                              default=Statut.EN_ATTENTE)

    class Meta:
        verbose_name = 'cotisation'
        verbose_name_plural = 'cotisations'
        ordering = ['-exercice', 'membre__nom']
        constraints = [
            models.UniqueConstraint(fields=['membre', 'exercice'],
                                    name='unicite_cotisation_membre_exercice'),
            models.CheckConstraint(check=Q(montant_du__gt=0),
                                   name='montant_du_positif'),
            models.CheckConstraint(check=Q(montant_paye__gte=0),
                                   name='montant_paye_non_negatif'),
            models.CheckConstraint(check=Q(montant_paye__lte=F('montant_du')),
                                   name='paye_inferieur_ou_egal_au_du'),
        ]
        indexes = [
            models.Index(fields=['statut', 'date_echeance']),
            models.Index(fields=['exercice']),
        ]

    def __str__(self):
        return f'{self.membre.nom_complet()} — exercice {self.exercice}'

    @property
    def reste_a_payer(self):
        return self.montant_du - self.montant_paye

    @property
    def est_exemptee(self):
        return Exemption.objects.filter(membre_id=self.membre_id,
                                        exercice=self.exercice).exists()


class Paiement(models.Model):

    class Mode(models.TextChoices):
        ESPECES = 'ESPECES', 'Espèces'
        VIREMENT = 'VIREMENT', 'Virement bancaire'
        MOBILE_MONEY = 'MOBILE_MONEY', 'Monnaie électronique mobile'
        CHEQUE = 'CHEQUE', 'Chèque'

    cotisation = models.ForeignKey(Cotisation, on_delete=models.PROTECT,
                                   related_name='paiements')
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    mode = models.CharField(max_length=20, choices=Mode.choices)
    reference = models.CharField(max_length=60, blank=True)
    date_paiement = models.DateTimeField()
    enregistre_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                       on_delete=models.SET_NULL,
                                       related_name='paiements_saisis')

    class Meta:
        verbose_name = 'paiement'
        verbose_name_plural = 'paiements'
        ordering = ['-date_paiement']
        constraints = [
            models.CheckConstraint(check=Q(montant__gt=0), name='montant_paiement_positif'),
        ]

    def __str__(self):
        return f'{self.montant} FCFA — {self.get_mode_display()}'


class Exemption(models.Model):
    membre = models.ForeignKey('membres.Membre', on_delete=models.PROTECT,
                               related_name='exemptions')
    exercice = models.PositiveIntegerField()
    motif = models.CharField(max_length=200)
    accordee_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL)
    date_decision = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = 'exemption'
        verbose_name_plural = 'exemptions'
        constraints = [
            models.UniqueConstraint(fields=['membre', 'exercice'],
                                    name='unicite_exemption_membre_exercice'),
        ]

    def __str__(self):
        return f'{self.membre.nom_complet()} — exercice {self.exercice}'
