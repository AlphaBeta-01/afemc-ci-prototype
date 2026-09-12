"""Commande du moteur de détection (§ 5.6.1)."""
from datetime import datetime

from django.core.management.base import BaseCommand

from apps.relances.services import executer_detection


class Command(BaseCommand):
    help = "Détecte les échéances proches et les cotisations en retard."

    def add_arguments(self, parser):
        parser.add_argument('--simulation', action='store_true',
                            help="Analyse sans écriture ni envoi")
        parser.add_argument('--date', type=str, default=None,
                            help="Date d'analyse au format AAAA-MM-JJ (essais)")

    def handle(self, *args, **options):
        aujourdhui = None
        if options['date']:
            aujourdhui = datetime.strptime(options['date'], '%Y-%m-%d').date()

        resultat = executer_detection(simulation=options['simulation'],
                                      aujourdhui=aujourdhui)

        entete = 'SIMULATION — ' if options['simulation'] else ''
        self.stdout.write(self.style.SUCCESS(
            f"{entete}{resultat['basculees']} statut(s) modifié(s), "
            f"{resultat['relances']} relance(s), "
            f"exécution en {resultat['duree']:.2f} s."))
