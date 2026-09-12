"""Fabrique d'objets pour les campagnes de test."""
from datetime import date, timedelta
from decimal import Decimal

from apps.accounts.models import Utilisateur
from apps.cotisations.models import Cotisation
from apps.membres.models import Membre
from apps.sections.models import Section

MOT_DE_PASSE = 'MotDePasse2026!'


def section(code='ABJ', libelle="Section d'Abidjan"):
    obj, _ = Section.objects.get_or_create(code=code, defaults={'libelle': libelle})
    return obj


def utilisateur(role, email=None, section_liee=None):
    email = email or f'{role.lower()}@afemc-ci.org'
    return Utilisateur.objects.create_user(
        email=email, password=MOT_DE_PASSE, nom='TEST', prenoms=role.title(),
        role=role, section=section_liee)


def membre(nom='KOUAME', sect=None, statut=Membre.Statut.ACTIF, email=None):
    sect = sect or section()
    indice = Membre.objects.count() + 1
    return Membre.objects.create(
        nom=nom, prenoms='Akissi', email=email or f'{nom.lower()}{indice}@exemple.org',
        section=sect, statut=statut, grade='Maître-Assistante')


def cotisation(membre_lie=None, exercice=2026, du='25000', paye='0', jours_ecart=-30,
               statut=None):
    """jours_ecart > 0 : retard ; < 0 : échéance à venir."""
    membre_lie = membre_lie or membre()
    obj = Cotisation.objects.create(
        membre=membre_lie, exercice=exercice, montant_du=Decimal(du),
        montant_paye=Decimal(paye),
        date_echeance=date.today() - timedelta(days=jours_ecart))
    if statut:
        obj.statut = statut
        obj.save(update_fields=['statut'])
    return obj
