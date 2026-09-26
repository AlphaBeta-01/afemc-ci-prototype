"""Corrige les codes de section saisis avec la lettre O au lieu du chiffre 0.

Deux sections avaient été créées avec « OO » (lettres) là où les autres ont
« 00 » (chiffres) : BKE-OO-257 et COD-OO-353, contre UVC-00-787, UJL-00-367…
Le code de section entrant dans le n° d'adhérente (RG01), les numéros des
membres de ces sections suivaient le même format erroné.

La migration corrige le code des sections concernées puis le n° d'adhérente
de leurs membres, et inscrit chaque changement au journal des opérations
(RG09) : l'ancien numéro reste retrouvable, notamment pour les reçus déjà
envoyés qui le portent. Elle ne touche qu'au segment central composé
exactement de deux lettres O, et s'arrête sans rien modifier si le code
corrigé est déjà pris par une autre section.
"""
import re

from django.db import migrations

MOTIF = re.compile(r'^(?P<avant>[A-Z]+)-OO-(?P<apres>\d+)$')


def _corriger(apps, sens):
    Section = apps.get_model('sections', 'Section')
    Membre = apps.get_model('membres', 'Membre')
    JournalOperation = apps.get_model('core', 'JournalOperation')

    for section in Section.objects.all():
        if sens == 'avant':
            trouve = MOTIF.match(section.code)
            if not trouve:
                continue
            nouveau = f"{trouve['avant']}-00-{trouve['apres']}"
        else:   # retour arrière : seulement les codes corrigés par cette migration
            if not JournalOperation.objects.filter(
                    type_operation='CORRECTION_CODE_SECTION',
                    detail__startswith=f'{section.code.replace("-00-", "-OO-")} -> {section.code}'
            ).exists():
                continue
            nouveau = section.code.replace('-00-', '-OO-', 1)

        if Section.objects.filter(code=nouveau).exclude(pk=section.pk).exists():
            raise RuntimeError(f'Le code {nouveau} existe déjà : correction de '
                               f'{section.code} abandonnée, rien n\'a été modifié.')

        ancien = section.code
        section.code = nouveau
        section.save(update_fields=['code'])
        JournalOperation.objects.create(
            type_operation='CORRECTION_CODE_SECTION',
            detail=f'{ancien} -> {nouveau} ({section.libelle})')

        for membre in Membre.objects.filter(matricule__startswith=f'{ancien}-'):
            ancien_numero = membre.matricule
            membre.matricule = nouveau + ancien_numero[len(ancien):]
            membre.save(update_fields=['matricule'])
            JournalOperation.objects.create(
                type_operation='CORRECTION_NUMERO_ADHERENTE',
                detail=f'{ancien_numero} -> {membre.matricule} '
                       f'({membre.nom} {membre.prenoms})')


def corriger(apps, schema_editor):
    _corriger(apps, 'avant')


def annuler(apps, schema_editor):
    _corriger(apps, 'arriere')


class Migration(migrations.Migration):
    atomic = True

    dependencies = [
        ('membres', '0002_libelle_numero_adherente'),
        ('sections', '0001_initial'),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(corriger, annuler),
    ]
