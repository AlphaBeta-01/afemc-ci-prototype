"""Contenu de la page d'accueil publique, modifiable par le Bureau.

Rien n'y est codé en dur : la Présidente et la Responsable à l'organisation
rédigent présentation, chiffres clés et réalisations depuis l'application,
sans intervention d'un développeur. Le contenu initial a été rédigé à
partir des seules sources publiques citées dans le mémoire ; il reste
signalé « à relire » dans l'« À faire » de la Présidente tant qu'elle ne
l'a pas validé.
"""
from django.conf import settings
from django.db import models


class PageAccueil(models.Model):
    """Textes de la page d'accueil (un seul enregistrement)."""

    accroche = models.CharField(max_length=160)
    sous_titre = models.CharField('sous-titre', max_length=250, blank=True)
    presentation = models.TextField('qui sommes-nous')
    mission = models.TextField('nos missions', blank=True,
                               help_text='Une mission par ligne.')
    # Mot de la Présidente. La photo est stockée en base plutôt que dans
    # MEDIA_ROOT : sur Render, le disque est effacé à chaque redéploiement, et
    # MEDIA_ROOT n'est volontairement jamais servi (pièces d'identité).
    presidente_nom = models.CharField('nom de la Présidente', max_length=120, blank=True)
    presidente_titre = models.CharField(
        'titre affiché', max_length=150, blank=True, default="Présidente de l'AFEMC-CI",
        help_text="Ex. « Présidente de l'AFEMC-CI, Professeure titulaire ».")
    presidente_presentation = models.TextField(
        'présentation de la Présidente', blank=True,
        help_text='Parcours et mandat, à la troisième personne, à partir de sources vérifiables.')
    presidente_message = models.TextField(
        'mot de la Présidente', blank=True,
        help_text='Quelques lignes de bienvenue, rédigées ou validées par la Présidente.')
    presidente_photo = models.BinaryField('photo', null=True, blank=True, editable=False)
    presidente_photo_maj = models.DateTimeField(null=True, blank=True, editable=False)
    email_contact = models.EmailField('adresse de contact', blank=True)
    site_institutionnel = models.URLField(blank=True)
    contenu_verifie = models.BooleanField(
        'contenu relu et validé', default=False,
        help_text="À cocher par la Présidente une fois les textes et les chiffres vérifiés.")
    modifiee_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='+')
    modifiee_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "page d'accueil"
        verbose_name_plural = "page d'accueil"

    def __str__(self):
        return "Page d'accueil"

    @classmethod
    def courante(cls):
        page = cls.objects.first()
        return page or cls(accroche="Association des Femmes Enseignantes Chercheures "
                                    "de Côte d'Ivoire", presentation='')

    @property
    def a_une_photo(self):
        return bool(self.presidente_photo)

    @property
    def montre_la_presidente(self):
        return (self.a_une_photo or bool(self.presidente_nom) or bool(self.presidente_message)
                or bool(self.presidente_presentation))

    @property
    def missions(self):
        return [ligne.strip(' -•\t') for ligne in self.mission.splitlines() if ligne.strip()]


class ChiffreCle(models.Model):
    valeur = models.CharField(max_length=20, help_text='Ex. « 1 000 », « 17 », « 3ᵉ ».')
    libelle = models.CharField('libellé', max_length=60, help_text='Ex. « membres ».')
    precision = models.CharField('précision / source', max_length=120, blank=True,
                                 help_text='Ex. « en 2024, selon l\'UVCI ».')
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'chiffre clé'
        verbose_name_plural = 'chiffres clés'
        ordering = ['ordre', 'pk']

    def __str__(self):
        return f'{self.valeur} {self.libelle}'


class Realisation(models.Model):
    """Une œuvre ou un temps fort de l'association, présenté au public."""

    annee = models.PositiveSmallIntegerField('année')
    periode = models.CharField('période', max_length=40, blank=True,
                               help_text='Facultatif, ex. « octobre », « mai ».')
    titre = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    source = models.CharField(max_length=150, blank=True,
                              help_text="D'où vient l'information (article, publication…).")
    publiee = models.BooleanField('affichée sur la page', default=True)

    class Meta:
        verbose_name = 'réalisation'
        verbose_name_plural = 'réalisations'
        ordering = ['-annee', '-pk']

    def __str__(self):
        return f'{self.annee} — {self.titre}'


class PhotoGalerie(models.Model):
    """Photo de la section « En images » de la page d'accueil.

    Stockée en base, comme la photo de la Présidente : le disque de Render est
    effacé à chaque redéploiement et MEDIA_ROOT n'est jamais servi.
    """

    image = models.BinaryField(editable=False)
    largeur = models.PositiveIntegerField(editable=False, default=0)
    hauteur = models.PositiveIntegerField(editable=False, default=0)
    legende = models.CharField('légende', max_length=200, blank=True,
                               help_text="Ce que montre la photo : événement, lieu, date. "
                                         "Ne nommer que des personnes qui ont donné leur accord.")
    ordre = models.PositiveSmallIntegerField(default=0)
    publiee = models.BooleanField('affichée sur la page', default=True)
    ajoutee_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'photo de la galerie'
        verbose_name_plural = 'galerie de photos'
        ordering = ['ordre', '-ajoutee_le']

    def __str__(self):
        return self.legende or f'Photo {self.pk}'

    @property
    def paysage(self):
        return self.largeur > self.hauteur
