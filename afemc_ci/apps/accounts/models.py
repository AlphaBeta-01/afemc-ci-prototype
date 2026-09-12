"""Authentification, rôles et permissions (§ 5.5.1)."""
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


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
        RESP_ADMIN = 'RESP_ADMIN', 'Responsable administratif'
        RESP_SECTION = 'RESP_SECTION', 'Responsable de section'
        RESP_FINANCIER = 'RESP_FINANCIER', 'Responsable financier'
        ADMIN = 'ADMIN', 'Administrateur'

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
