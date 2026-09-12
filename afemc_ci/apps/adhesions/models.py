"""Demandes d'adhésion et cycle de validation (§ 5.5.4)."""
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models

EXTENSIONS_AUTORISEES = ['pdf', 'jpg', 'jpeg', 'png']


class DemandeAdhesion(models.Model):

    class Statut(models.TextChoices):
        EN_ATTENTE = 'EN_ATTENTE', 'En attente'
        EN_EXAMEN = 'EN_EXAMEN', 'En examen'
        INFOS_REQUISES = 'INFOS_REQUISES', 'Informations requises'
        VALIDEE = 'VALIDEE', 'Validée'
        REJETEE = 'REJETEE', 'Rejetée'

    nom = models.CharField(max_length=100)
    prenoms = models.CharField(max_length=150)
    email = models.EmailField()
    telephone = models.CharField(max_length=20)
    grade = models.CharField(max_length=80)
    etablissement = models.CharField(max_length=150)
    section = models.ForeignKey('sections.Section', on_delete=models.PROTECT,
                                related_name='demandes')
    motivation = models.TextField()
    statut = models.CharField(max_length=15, choices=Statut.choices,
                              default=Statut.EN_ATTENTE)
    motif = models.TextField(blank=True)          # renseigné par le traitement, pas la candidate
    date_soumission = models.DateTimeField(auto_now_add=True)
    date_traitement = models.DateTimeField(null=True, blank=True)
    traitee_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL)
    membre = models.ForeignKey('membres.Membre', null=True, blank=True,
                               on_delete=models.SET_NULL, related_name='demandes')

    class Meta:
        verbose_name = "demande d'adhésion"
        verbose_name_plural = "demandes d'adhésion"
        ordering = ['-date_soumission']
        indexes = [models.Index(fields=['statut', 'date_soumission'])]

    def __str__(self):
        return f'{self.nom} {self.prenoms} — {self.get_statut_display()}'

    def nom_complet(self):
        return f'{self.nom} {self.prenoms}'


def chemin_piece(instance, nom_fichier):
    return f'adhesions/pieces/{instance.demande_id}/{nom_fichier}'


class PieceJustificative(models.Model):
    """Document attestant de la qualité d'enseignante chercheure (§ 5.5.4)."""

    class TypePiece(models.TextChoices):
        CARTE_PROFESSIONNELLE = 'CARTE_PROFESSIONNELLE', 'Carte professionnelle'
        ATTESTATION_EMPLOI = 'ATTESTATION_EMPLOI', "Attestation d'exercice ou d'emploi"
        DIPLOME = 'DIPLOME', 'Diplôme'
        AUTRE = 'AUTRE', 'Autre document'

    demande = models.ForeignKey(DemandeAdhesion, on_delete=models.CASCADE,
                                related_name='pieces')
    type_piece = models.CharField(max_length=25, choices=TypePiece.choices)
    fichier = models.FileField(
        upload_to=chemin_piece,
        validators=[FileExtensionValidator(EXTENSIONS_AUTORISEES)])
    depose_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'pièce justificative'
        verbose_name_plural = 'pièces justificatives'
        ordering = ['depose_le']

    def __str__(self):
        return f'{self.get_type_piece_display()} — {self.demande.nom_complet()}'
