"""File de notifications persistée (§ 5.6.3)."""
from django.db import models


class Notification(models.Model):

    class Statut(models.TextChoices):
        EN_ATTENTE = 'EN_ATTENTE', 'En attente'
        ENVOYEE = 'ENVOYEE', 'Envoyée'
        ECHEC = 'ECHEC', 'Échec'

    class Canal(models.TextChoices):
        EMAIL = 'EMAIL', 'Courriel'
        INTERNE = 'INTERNE', 'Notification interne'

    destinataire = models.CharField(max_length=150)
    membre = models.ForeignKey('membres.Membre', null=True, blank=True,
                               on_delete=models.SET_NULL, related_name='notifications')
    relance = models.ForeignKey('relances.Relance', null=True, blank=True,
                                on_delete=models.SET_NULL, related_name='notifications')
    type = models.CharField(max_length=40)
    canal = models.CharField(max_length=15, choices=Canal.choices, default=Canal.EMAIL)
    objet = models.CharField(max_length=200)
    gabarit = models.CharField(max_length=80)
    contexte = models.JSONField(default=dict, blank=True)
    piece_jointe_generateur = models.CharField(
        max_length=200, blank=True,
        help_text="Chemin Python pointillé (ex. apps.cotisations.services.generer_recu_pdf) "
                  "d'une fonction qui reçoit `contexte` et retourne (nom_fichier, contenu, "
                  "type_mime) — régénérée à chaque tentative d'envoi plutôt que stockée, "
                  "comme le corps du courriel lui-même (voir rendre_gabarit).")
    statut = models.CharField(max_length=12, choices=Statut.choices,
                              default=Statut.EN_ATTENTE)
    tentatives = models.PositiveSmallIntegerField(default=0)
    derniere_erreur = models.CharField(max_length=255, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    date_envoi = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'notification'
        verbose_name_plural = 'notifications'
        ordering = ['-cree_le']
        indexes = [models.Index(fields=['statut', 'cree_le'])]

    def __str__(self):
        return f'{self.destinataire} — {self.objet[:40]}'
