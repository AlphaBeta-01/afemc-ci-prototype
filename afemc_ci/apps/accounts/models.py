"""Authentification, rôles et permissions (§ 5.5.1)."""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class GestionnaireUtilisateur(BaseUserManager):
    use_in_migrations = True

    def _creer(self, email, password, **extra):
        if not email:
            raise ValueError("L'adresse électronique est obligatoire.")
        email = self.normalize_email(email)
        utilisateur = self.model(email=email, **extra)
        utilisateur.set_password(password)
        utilisateur.save(using=self._db)
        return utilisateur

    def create_user(self, email, password=None, **extra):
        extra.setdefault('is_staff', False)
        extra.setdefault('is_superuser', False)
        return self._creer(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        extra.setdefault('role', Utilisateur.Role.ADMIN)
        return self._creer(email, password, **extra)


class Utilisateur(AbstractUser):
    """Compte d'accès au système. Les six profils du chapitre 3 y sont portés."""

    class Role(models.TextChoices):
        MEMBRE = 'MEMBRE', 'Membre'
        RESP_ADMIN = 'RESP_ADMIN', 'Secrétaire générale'
        RESP_SECTION = 'RESP_SECTION', 'Coordinatrice de section'
        RESP_FINANCIER = 'RESP_FINANCIER', 'Trésorière'
        RESP_ORGA = 'RESP_ORGA', "Responsable à l'organisation"
        ADMIN = 'ADMIN', 'Présidente'

    username = None
    email = models.EmailField('adresse électronique', unique=True)
    nom = models.CharField(max_length=100)
    prenoms = models.CharField(max_length=150)
    role = models.CharField(max_length=15, choices=Role.choices, default=Role.MEMBRE)
    section = models.ForeignKey('sections.Section', null=True, blank=True,
                                on_delete=models.SET_NULL, related_name='responsables')
    tentatives_echouees = models.PositiveSmallIntegerField(default=0)
    verrouille_jusqua = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nom', 'prenoms']

    objects = GestionnaireUtilisateur()

    class Meta:
        verbose_name = 'utilisateur'
        verbose_name_plural = 'utilisateurs'
        ordering = ['nom', 'prenoms']

    def __str__(self):
        return f'{self.nom} {self.prenoms}'

    def nom_complet(self):
        return f'{self.nom} {self.prenoms}'

    @property
    def est_responsable(self):
        return self.role in (self.Role.ADMIN, self.Role.RESP_ADMIN,
                             self.Role.RESP_SECTION, self.Role.RESP_FINANCIER)

    @property
    def voit_toutes_les_sections(self):
        return self.role in (self.Role.ADMIN, self.Role.RESP_ADMIN, self.Role.RESP_FINANCIER)

    @property
    def est_verrouille(self):
        return bool(self.verrouille_jusqua and self.verrouille_jusqua > timezone.now())

    def enregistrer_echec_connexion(self):
        """Comptabilise une tentative échouée ; verrouille au-delà du seuil (RG10).

        `MAX_TENTATIVES_CONNEXION` était déclaré dans les réglages et
        `tentatives_echouees`/`verrouille_jusqua` sur ce modèle, mais rien ne
        les reliait jusqu'ici : un mot de passe pouvait être deviné sans
        limite. Verrouillage de 15 minutes, glissant à chaque nouvel échec
        pendant la fenêtre de verrouillage — une tentative continue pendant
        le blocage ne raccourcit jamais la durée restante.
        """
        self.tentatives_echouees += 1
        if self.tentatives_echouees >= settings.MAX_TENTATIVES_CONNEXION:
            self.verrouille_jusqua = timezone.now() + timedelta(minutes=15)
        self.save(update_fields=['tentatives_echouees', 'verrouille_jusqua'])

    def reinitialiser_tentatives_connexion(self):
        if self.tentatives_echouees or self.verrouille_jusqua:
            self.tentatives_echouees = 0
            self.verrouille_jusqua = None
            self.save(update_fields=['tentatives_echouees', 'verrouille_jusqua'])
