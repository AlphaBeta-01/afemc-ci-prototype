"""Présentation de la Présidente et mise à jour des chiffres et réalisations.

Rédigé uniquement à partir d'articles de presse vérifiés (27/09/2026) :
- Fraternité Matin, 9 août 2022 : « Recherche scientifique : Pr Céline Nobah
  succède à Pr Rita Kacou à la tête de l'Afemc-CI » ;
- Fraternité Matin, 20 mai 2026 : « Femmes chercheures : Professeure Céline
  Nobah Kacou plébiscitée pour un second mandat » ;
- KOACI, 21 mai 2026 : « la prof Céline Nobah Kacou-Wodjè rempile pour un
  nouveau mandat ».
Le mot de bienvenue, qui doit être écrit par la Présidente elle-même, reste
vide. Sans effet si le contenu a déjà été validé (`contenu_verifie`).
"""
from django.db import migrations

NOM = "Professeure NOBAH Céline Sidonie Koco épouse KACOU-WODJE"
TITRE = "Présidente de l'AFEMC-CI · Enseignante-chercheure à l'École normale supérieure d'Abidjan"
PRESENTATION = (
    "Enseignante-chercheure à l'École normale supérieure (ENS) d'Abidjan, où elle a dirigé "
    "la section des Sciences de la vie et de la Terre, la Professeure Céline Nobah "
    "Kacou-Wodjè est spécialiste d'hydrobiologie (aquaculture) et d'écotoxicologie, et "
    "reconnue pour ses travaux en aquaponie. Elle a été chercheure associée à l'Institut "
    "français de l'Éducation (ENS de Lyon).\n\n"
    "Élue présidente de l'AFEMC-CI le 26 mars 2022, elle succède à la Professeure Rita "
    "Caroline Kacou. Sous son premier mandat, l'association est passée de 3 à 22 sections, "
    "plusieurs dizaines de membres ont été admises aux concours du CAMES, et un coaching "
    "personnalisé des mastérantes a été mis en place.\n\n"
    "Le 16 mai 2026, l'assemblée générale l'a réélue à l'unanimité pour un second mandat "
    "de trois ans.")

SOURCE_2022 = 'Fraternité Matin, 9 août 2022'
SOURCE_2026 = 'Fraternité Matin, 20 mai 2026 ; KOACI, 21 mai 2026'


def appliquer(apps, schema_editor):
    PageAccueil = apps.get_model('vitrine', 'PageAccueil')
    ChiffreCle = apps.get_model('vitrine', 'ChiffreCle')
    Realisation = apps.get_model('vitrine', 'Realisation')

    page = PageAccueil.objects.first()
    if page is None or page.contenu_verifie:
        return                          # contenu déjà relu : on n'y touche pas
    if not page.presidente_nom:
        page.presidente_nom = NOM
        page.presidente_titre = TITRE
        page.presidente_presentation = PRESENTATION
        page.save()

    # 22 sections en 2026 remplace le chiffre de 2024 (17, selon l'UVCI).
    ChiffreCle.objects.filter(valeur='17', libelle='sections').update(
        valeur='22', precision='en 2026, contre 3 en 2022 (Fraternité Matin)')

    Realisation.objects.filter(annee=2026, titre='Bilan triennal et renouvellement du Bureau').update(
        titre='Bilan du premier mandat et réélection de la Présidente',
        description="Assemblée générale du 16 mai 2026 à l'UVCI (Cocody) : bilan du premier "
                    "mandat — sections passées de 3 à 22, plusieurs dizaines de membres admises "
                    "aux concours du CAMES, coaching des mastérantes — et réélection à "
                    "l'unanimité de la Présidente pour trois ans.",
        source=SOURCE_2026)
    if not Realisation.objects.filter(annee=2022).exists():
        Realisation.objects.create(
            annee=2022, periode='mars', titre="Élection d'une nouvelle Présidente",
            description="La Professeure Céline Nobah Kacou-Wodjè est élue présidente de "
                        "l'AFEMC-CI le 26 mars 2022, succédant à la Professeure Rita Caroline "
                        "Kacou ; son investiture a lieu en août 2022.",
            source=SOURCE_2022)


class Migration(migrations.Migration):

    dependencies = [('vitrine', '0003_mot_de_la_presidente')]

    operations = [migrations.RunPython(appliquer, migrations.RunPython.noop)]
