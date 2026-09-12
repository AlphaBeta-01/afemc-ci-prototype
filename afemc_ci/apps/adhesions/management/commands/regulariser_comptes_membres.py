"""Rattrapage des comptes d'accès manquants pour des membres déjà admis (RG02)."""
from django.core.management.base import BaseCommand

from apps.adhesions.services import regulariser_comptes_membres


class Command(BaseCommand):
    help = ("Crée le compte d'accès et envoie le lien d'activation pour tout "
            "membre dont la demande a été validée mais qui n'a pas encore de "
            "compte (ex. déploiement de la fonctionnalité en cours d'exploitation).")

    def add_arguments(self, parser):
        parser.add_argument('--simulation', action='store_true',
                            help="Liste les cas concernés sans rien créer ni envoyer")

    def handle(self, *args, **options):
        membres = regulariser_comptes_membres(simulation=options['simulation'])

        if not membres:
            self.stdout.write(self.style.SUCCESS('Aucun compte manquant.'))
            return

        for membre in membres:
            self.stdout.write(f'  {membre.matricule} — {membre.nom_complet()} '
                              f'({membre.email})')

        entete = 'SIMULATION — ' if options['simulation'] else ''
        self.stdout.write(self.style.SUCCESS(
            f"{entete}{len(membres)} compte(s) régularisé(s)."))
