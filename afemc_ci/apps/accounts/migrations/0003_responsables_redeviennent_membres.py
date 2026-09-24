"""Tous les comptes responsables existants redeviennent des comptes Membre (RG13).

Passage au modèle « une responsable est une membre nommée à une fonction » :
les comptes Secrétaire générale, Trésorière et Coordinatrice de section
créés jusqu'ici l'ont été à part, souvent sans fiche membre. Plutôt que de
tenter une fusion automatique (risquée : doublons d'adresses, fiches
manquantes), ils redeviennent tous de simples comptes Membre ; la
Présidente les nomme ensuite depuis leur fiche, avec « Nommer une
responsable ». Le compte de la Présidente (ADMIN) n'est pas concerné.

Chaque changement est inscrit au journal des opérations (RG09), pour
garder la trace des fonctions occupées avant cette migration.

Non réversible : l'ancienne fonction n'est conservée que dans le journal.
"""
from django.db import migrations

ROLES_RESPONSABLES = ('RESP_ADMIN', 'RESP_SECTION', 'RESP_FINANCIER')
LIBELLES = {'RESP_ADMIN': 'Secrétaire générale', 'RESP_SECTION': 'Coordinatrice de section',
            'RESP_FINANCIER': 'Trésorière'}


def ramener_au_role_membre(apps, schema_editor):
    Utilisateur = apps.get_model('accounts', 'Utilisateur')
    Membre = apps.get_model('membres', 'Membre')
    JournalOperation = apps.get_model('core', 'JournalOperation')
    Section = apps.get_model('sections', 'Section')

    for compte in Utilisateur.objects.filter(role__in=ROLES_RESPONSABLES):
        fiche = Membre.objects.filter(utilisateur_id=compte.pk).first()
        section = Section.objects.filter(pk=compte.section_id).first()
        ancienne = LIBELLES[compte.role] + (f' — {section.libelle}' if section else '')
        compte.role = 'MEMBRE'
        compte.section_id = fiche.section_id if fiche else None
        compte.save(update_fields=['role', 'section'])
        JournalOperation.objects.create(
            utilisateur=None, type_operation='FIN_FONCTIONS_MIGRATION',
            detail=f'{compte.email} : {ancienne} -> Membre '
                   f'({"fiche " + fiche.matricule if fiche else "sans fiche membre"})')


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_alter_utilisateur_role'),
        ('membres', '0001_initial'),
        ('core', '0001_initial'),
        ('sections', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(ramener_au_role_membre, migrations.RunPython.noop),
    ]
