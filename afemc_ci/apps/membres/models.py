"""Registre des membres (§ 5.4.2, § 5.5.2)."""
from datetime import date

from django.conf import settings
from django.db import models


def generer_matricule(section):
    """Produit un matricule unique : <CODE SECTION>-<ANNÉE>-<RANG> (RG01)."""
    annee = date.today().year
    prefixe = f'{section.code}-{annee}-'
    dernier = (Membre.objects.filter(matricule__startswith=prefixe)
               .order_by('-matricule').first())
    rang = int(dernier.matricule.rsplit('-', 1)[1]) + 1 if dernier else 1
    return f'{prefixe}{rang:04d}'


class MembreQuerySet(models.QuerySet):

    def visibles_par(self, utilisateur):
        """Restreint la sélection au périmètre autorisé (RG08, § 5.5.1)."""
        from apps.accounts.models import Utilisateur
        R = Utilisateur.Role
        if utilisateur.role in (R.ADMIN, R.RESP_ADMIN, R.RESP_FINANCIER):
            return self
        if utilisateur.role == R.RESP_SECTION and utilisateur.section_id:
            return self.filter(section_id=utilisateur.section_id)
        return self.filter(utilisateur=utilisateur)

    def actifs(self):
        return self.filter(statut=Membre.Statut.ACTIF)


class Membre(models.Model):

    class Statut(models.TextChoices):
        ACTIF = 'ACTIF', 'Actif'
        INACTIF = 'INACTIF', 'Inactif'
        SUSPENDU = 'SUSPENDU', 'Suspendu'

    # Identifiant interne à l'association (RG01), affiché « N° d'adhérente » :
    # attribué automatiquement, à ne pas confondre avec le matricule de
    # fonctionnaire délivré par l'État, que toutes les membres n'ont pas.
    matricule = models.CharField("n° d'adhérente", max_length=20, unique=True, editable=False)
    nom = models.CharField(max_length=100)
    prenoms = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    telephone = models.CharField(max_length=20, blank=True)
    date_naissance = models.DateField(null=True, blank=True)
    grade = models.CharField(max_length=80, blank=True)
    etablissement = models.CharField(max_length=150, blank=True)
    section = models.ForeignKey('sections.Section', on_delete=models.PROTECT,
                                related_name='membres')
    utilisateur = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True,
                                       on_delete=models.SET_NULL, related_name='fiche_membre')
    date_adhesion = models.DateField(default=date.today)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.ACTIF)
    cree_le = models.DateTimeField(auto_now_add=True)

    objects = MembreQuerySet.as_manager()

    class Meta:
        verbose_name = 'membre'
        verbose_name_plural = 'membres'
        ordering = ['nom', 'prenoms']
        indexes = [
            models.Index(fields=['section', 'statut']),
            models.Index(fields=['nom', 'prenoms']),
        ]

    def __str__(self):
        return f'{self.nom} {self.prenoms} ({self.matricule})'

    def save(self, *args, **kwargs):
        if not self.matricule:                      # RG01 : unicité du membre
            self.matricule = generer_matricule(self.section)
        super().save(*args, **kwargs)

    def nom_complet(self):
        return f'{self.nom} {self.prenoms}'

    def est_a_jour(self, exercice=None):
        exercice = exercice or date.today().year
        return not self.cotisations.filter(exercice=exercice,
                                           statut='EN_RETARD').exists()
