"""Crée le premier compte d'administration au déploiement, s'il n'existe pas.

Lancée à chaque build Render (render.yaml), sans accès Shell — celui-ci
exige un plan payant. Elle ne fait rien si un compte d'administration
existe déjà, ou si les variables SUPERUSER_BOOTSTRAP_EMAIL /
SUPERUSER_BOOTSTRAP_PASSWORD ne sont pas renseignées : une fois le compte
créé, ces variables peuvent et doivent être supprimées de Render, pour ne
pas laisser un mot de passe en clair dans la configuration.

Remplace l'ancien point d'entrée HTTP /taches/amorcer-admin/ : plus
aucune adresse publique ne permet de créer un compte d'administration.
"""
import os

from django.core.management.base import BaseCommand

from apps.accounts.models import Utilisateur
from apps.core.services import journaliser


class Command(BaseCommand):
    help = "Crée le compte de la Présidente au premier déploiement (sans effet ensuite)."

    def handle(self, *args, **options):
        if Utilisateur.objects.filter(is_superuser=True).exists():
            self.stdout.write("Compte d'administration déjà présent : rien à faire.")
            return
        email = os.environ.get('SUPERUSER_BOOTSTRAP_EMAIL', '').strip()
        mot_de_passe = os.environ.get('SUPERUSER_BOOTSTRAP_PASSWORD', '')
        if not (email and mot_de_passe):
            self.stdout.write(self.style.WARNING(
                "Aucun compte d'administration et SUPERUSER_BOOTSTRAP_EMAIL / "
                "SUPERUSER_BOOTSTRAP_PASSWORD non renseignés : rien n'a été créé."))
            return
        compte = Utilisateur.objects.create_superuser(
            email=email, password=mot_de_passe, nom='Présidente', prenoms='Principale')
        journaliser(None, 'CREATION_COMPTE_ADMINISTRATION', compte.email)
        self.stdout.write(self.style.SUCCESS(
            f"Compte d'administration créé : {compte.email}. Supprimez maintenant "
            "SUPERUSER_BOOTSTRAP_PASSWORD de la configuration Render."))
