"""Contenu initial de la page d'accueil, à relire par la Présidente.

Rédigé uniquement à partir des sources publiques citées dans le mémoire
(§ 1.2 et références) : aucun chiffre ni événement n'y est inventé, et
chaque réalisation indique sa source. Le champ `contenu_verifie` reste à
False : l'« À faire » de la Présidente lui demande de relire et compléter.
"""
from django.db import migrations

PRESENTATION = (
    "L'Association des Femmes Enseignantes Chercheures de Côte d'Ivoire (AFEMC-CI) "
    "rassemble des femmes évoluant dans l'enseignement supérieur et la recherche.\n\n"
    "Organisée en sections implantées dans les universités et grandes écoles du pays, "
    "elle mène des activités scientifiques, de formation et de sensibilisation, et "
    "contribue à donner plus de visibilité aux femmes dans le milieu académique et "
    "scientifique.")

MISSIONS = "\n".join([
    "Rassembler les femmes enseignantes et chercheures de Côte d'Ivoire",
    "Donner plus de visibilité aux femmes dans le milieu académique et scientifique",
    "Développer des activités scientifiques et de formation communes",
    "Accompagner le développement professionnel de ses membres",
])

CHIFFRES = [
    ('1 000', 'membres', "en 2024, selon l'Université Virtuelle de Côte d'Ivoire"),
    ('17', 'sections', "en 2024, selon l'Université Virtuelle de Côte d'Ivoire"),
    ('3ᵉ', 'édition des JSIFEC', 'Journées Scientifiques Internationales de la Femme Chercheure, 2024'),
]

REALISATIONS = [
    (2024, '', "3ᵉ édition des Journées Scientifiques Internationales de la Femme Chercheure (JSIFEC)",
     "Journées scientifiques consacrées aux travaux des femmes chercheures, organisées "
     "avec l'Université Virtuelle de Côte d'Ivoire.",
     "Université Virtuelle de Côte d'Ivoire (2024)"),
    (2024, 'décembre', "Conférences de sensibilisation de la section de Korhogo",
     "Conférences de sensibilisation organisées par la section AFEMC-CI de Korhogo.",
     'Agence Ivoirienne de Presse, décembre 2024'),
    (2026, 'mai', "Bilan triennal et renouvellement du Bureau",
     "Présentation du bilan des trois années écoulées et renouvellement du Bureau exécutif.",
     'Fraternité Matin, mai 2026'),
]


def creer(apps, schema_editor):
    PageAccueil = apps.get_model('vitrine', 'PageAccueil')
    ChiffreCle = apps.get_model('vitrine', 'ChiffreCle')
    Realisation = apps.get_model('vitrine', 'Realisation')
    if PageAccueil.objects.exists():
        return
    PageAccueil.objects.create(
        accroche="Association des Femmes Enseignantes Chercheures de Côte d'Ivoire",
        sous_titre="Rassembler, valoriser et accompagner les femmes de l'enseignement "
                   "supérieur et de la recherche.",
        presentation=PRESENTATION, mission=MISSIONS,
        site_institutionnel='https://www.afemc-ci.org', contenu_verifie=False)
    for ordre, (valeur, libelle, precision) in enumerate(CHIFFRES):
        ChiffreCle.objects.create(valeur=valeur, libelle=libelle, precision=precision,
                                  ordre=ordre)
    for annee, periode, titre, description, source in REALISATIONS:
        Realisation.objects.create(annee=annee, periode=periode, titre=titre,
                                   description=description, source=source)


class Migration(migrations.Migration):

    dependencies = [('vitrine', '0001_initial')]

    operations = [migrations.RunPython(creer, migrations.RunPython.noop)]
