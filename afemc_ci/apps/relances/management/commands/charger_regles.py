"""Charge les six règles de relance du tableau 15.

Ne crée que les règles absentes, sans jamais toucher à celles déjà en base :
la commande est rappelée à chaque déploiement (render.yaml), et une règle
ajustée depuis l'administration (délai, destinataires, désactivation) ne
doit pas être silencieusement réinitialisée par un simple `git push` — ce
qui contredirait le principe même de RegleRelance, modifiable sans
intervention d'un développeur.
"""
from django.core.management.base import BaseCommand

from apps.relances.models import RegleRelance

REGLES = [
    ('R01', 'Rappel préventif — échéance dans 15 jours', -15, 'INFORMATION', 'MEMBRE'),
    ('R02', 'Rappel — échéance dans 3 jours', -3, 'RAPPEL', 'MEMBRE'),
    ('R03', 'Notification de retard', 1, 'RETARD', 'MEMBRE'),
    ('R04', 'Relance 1 — retard de 15 jours', 15, 'RELANCE_1', 'MEMBRE_SECTION'),
    ('R05', 'Relance 2 — retard de 45 jours', 45, 'RELANCE_2', 'MEMBRE_FINANCIER'),
    ('R06', 'Alerte — retard de 90 jours', 90, 'ALERTE', 'RESPONSABLES'),
]


class Command(BaseCommand):
    help = "Charge les règles de relance par défaut."

    def handle(self, *args, **options):
        creees = 0
        for code, libelle, decalage, niveau, destinataires in REGLES:
            _, creee = RegleRelance.objects.get_or_create(
                code=code,
                defaults={'libelle': libelle, 'decalage_jours': decalage,
                          'niveau': niveau, 'destinataires': destinataires,
                          'active': True})
            creees += creee
        if options.get('verbosity', 1):
            self.stdout.write(self.style.SUCCESS(
                f'{creees} règle(s) créée(s), {len(REGLES) - creees} déjà présente(s) '
                f'laissée(s) intacte(s).'))
