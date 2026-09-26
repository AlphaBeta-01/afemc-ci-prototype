"""Activités de l'association, comités d'organisation et inscriptions.

Met en œuvre les classes Événement et Inscription du modèle conçu au
chapitre 4 (figure 3), laissées jusqu'ici hors du prototype.
"""
from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class Activite(models.Model):

    class Type(models.TextChoices):
        CONFERENCE = 'CONFERENCE', 'Conférence'
        FORMATION = 'FORMATION', 'Formation'
        JOURNEE_SCIENTIFIQUE = 'JOURNEE_SCIENTIFIQUE', 'Journée scientifique'
        ASSEMBLEE_GENERALE = 'ASSEMBLEE_GENERALE', 'Assemblée générale'
        REUNION = 'REUNION', 'Réunion'
        AUTRE = 'AUTRE', 'Autre'

    class Statut(models.TextChoices):
        EN_PREPARATION = 'EN_PREPARATION', 'En préparation'
        PUBLIEE = 'PUBLIEE', 'Publiée'
        TERMINEE = 'TERMINEE', 'Terminée'
        ANNULEE = 'ANNULEE', 'Annulée'

    titre = models.CharField(max_length=150)
    type = models.CharField(max_length=25, choices=Type.choices)
    description = models.TextField(blank=True)
    date_debut = models.DateTimeField('début')
    date_fin = models.DateTimeField('fin', null=True, blank=True)
    lieu = models.CharField(max_length=150)
    section = models.ForeignKey(
        'sections.Section', null=True, blank=True, on_delete=models.PROTECT,
        related_name='activites',
        help_text="Laisser vide pour une activité nationale, ouverte à toutes les membres.")
    places = models.PositiveIntegerField(
        'nombre de places', null=True, blank=True,
        help_text='Laisser vide si le nombre de participantes n\'est pas limité.')
    statut = models.CharField(max_length=15, choices=Statut.choices,
                              default=Statut.EN_PREPARATION)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='activites_creees')
    cree_le = models.DateTimeField(auto_now_add=True)
    modifiee_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'activité'
        verbose_name_plural = 'activités'
        ordering = ['date_debut']
        constraints = [
            models.CheckConstraint(condition=Q(date_fin__isnull=True)
                                   | Q(date_fin__gte=F('date_debut')),
                                   name='activite_fin_apres_debut'),
        ]
        indexes = [models.Index(fields=['statut', 'date_debut'])]

    def __str__(self):
        return f'{self.titre} ({self.date_debut:%d/%m/%Y})'

    @property
    def est_nationale(self):
        return self.section_id is None

    @property
    def est_a_venir(self):
        return self.date_debut > timezone.now()

    @property
    def nombre_inscrites(self):
        return self.inscriptions.count()

    @property
    def places_restantes(self):
        if self.places is None:
            return None
        return max(0, self.places - self.nombre_inscrites)

    @property
    def inscriptions_ouvertes(self):
        return (self.statut == self.Statut.PUBLIEE and self.est_a_venir
                and self.places_restantes != 0)


class MembreComite(models.Model):
    """Membre à qui la Responsable à l'organisation délègue la gestion d'une activité."""

    activite = models.ForeignKey(Activite, on_delete=models.CASCADE, related_name='comite')
    membre = models.ForeignKey('membres.Membre', on_delete=models.PROTECT,
                               related_name='comites')
    mission = models.CharField(max_length=80, blank=True,
                               help_text='Facultatif : logistique, communication, programme…')
    ajoutee_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='+')
    ajoutee_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "membre du comité d'organisation"
        verbose_name_plural = "comité d'organisation"
        constraints = [models.UniqueConstraint(fields=['activite', 'membre'],
                                               name='unicite_membre_comite')]

    def __str__(self):
        return f'{self.membre.nom_complet()} — {self.activite.titre}'


class Inscription(models.Model):
    activite = models.ForeignKey(Activite, on_delete=models.CASCADE,
                                 related_name='inscriptions')
    membre = models.ForeignKey('membres.Membre', on_delete=models.PROTECT,
                               related_name='inscriptions')
    inscrite_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'inscription'
        verbose_name_plural = 'inscriptions'
        constraints = [models.UniqueConstraint(fields=['activite', 'membre'],
                                               name='unicite_inscription')]

    def __str__(self):
        return f'{self.membre.nom_complet()} — {self.activite.titre}'
