"""Jeu de données de démonstration reproductible (§ 5.4.5, annexe D)."""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Utilisateur
from apps.adhesions.models import DemandeAdhesion
from apps.cotisations.models import Cotisation, Exemption, Paiement
from apps.cotisations.services import calculer_statut
from apps.membres.models import Membre
from apps.sections.models import Section

SECTIONS = [
    ('ABJ', 'Section d\'Abidjan', 'Abidjan', 'Université Félix Houphouët-Boigny'),
    ('COC', 'Section de Cocody', 'Abidjan', 'Université Félix Houphouët-Boigny'),
    ('ABO', 'Section d\'Abobo-Adjamé', 'Abidjan', 'Université Nangui Abrogoua'),
    ('BKE', 'Section de Bouaké', 'Bouaké', 'Université Alassane Ouattara'),
    ('KRG', 'Section de Korhogo', 'Korhogo', 'Université Peleforo Gon Coulibaly'),
    ('DAL', 'Section de Daloa', 'Daloa', 'Université Jean Lorougnon Guédé'),
    ('SPD', 'Section de San-Pédro', 'San-Pédro', 'Antenne universitaire'),
    ('UVC', 'Section de l\'UVCI', 'Abidjan', 'Université Virtuelle de Côte d\'Ivoire'),
]

NOMS = ['KOUASSI', 'KOUAME', 'YAO', 'KONE', 'TRAORE', 'BAMBA', 'DIABATE', 'OUATTARA',
        'COULIBALY', 'DIALLO', 'TOURE', 'CISSE', 'FOFANA', 'SANOGO', 'N\'GUESSAN',
        'ADJOUMANI', 'AKA', 'ASSI', 'BROU', 'DJEDJE', 'EHUI', 'GNAGNE', 'KOFFI',
        'KOUADIO', 'LOBA', 'MEITE', 'SILUE', 'TANOH', 'ZAGBAYOU', 'ANOH']

PRENOMS = ['Akissi', 'Adjoua', 'Aya', 'Affoue', 'Amenan', 'Ahou', 'Awa', 'Mariam',
           'Fatoumata', 'Salimata', 'Aminata', 'Kadiatou', 'Rosine', 'Chantal',
           'Solange', 'Béatrice', 'Clarisse', 'Estelle', 'Micheline', 'Nadège']

GRADES = ['Maître-Assistante', 'Maître de Conférences', 'Professeure Titulaire',
          'Assistante', 'Chargée de Recherche', 'Directrice de Recherche']

MOTIFS_EXEMPTION = ['Congé de maternité', 'Membre fondatrice honoraire',
                    'Détachement à l\'étranger', 'Décision du bureau']


class Command(BaseCommand):
    help = "Charge un jeu de données de démonstration reproductible."

    def add_arguments(self, parser):
        parser.add_argument('--exercices', nargs='+', type=int,
                            default=[2024, 2025, 2026])
        parser.add_argument('--membres', type=int, default=420)
        parser.add_argument('--sections', type=int, default=8)
        parser.add_argument('--graine', type=int, default=20260101)
        parser.add_argument('--reinitialiser', action='store_true',
                            help='Vide les tables avant le chargement')

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(options['graine'])
        self.aujourdhui = date.today()

        if options['reinitialiser']:
            self._vider()

        call_command('charger_regles', verbosity=0)
        sections = self._creer_sections(options['sections'])
        self._creer_utilisateurs(sections)
        membres = self._creer_membres(options['membres'], sections)
        self._creer_demandes(sections)
        self._creer_exemptions(membres)
        self._creer_cotisations(membres, options['exercices'])

        self.stdout.write(self.style.SUCCESS(
            f"Jeu de données chargé : {Section.objects.count()} sections, "
            f"{Membre.objects.count()} membres, "
            f"{Cotisation.objects.count()} cotisations, "
            f"{Paiement.objects.count()} paiements, "
            f"{DemandeAdhesion.objects.count()} demandes."))
        self.stdout.write(
            "Comptes de démonstration (mot de passe : Afemc2026!Demo) :\n"
            "  admin@afemc-ci.org           — Administrateur\n"
            "  administratif@afemc-ci.org   — Responsable administratif\n"
            "  financier@afemc-ci.org       — Responsable financier\n"
            "  section.abj@afemc-ci.org     — Responsable de section (Abidjan)")

    # ------------------------------------------------------------------
    def _vider(self):
        """Vide les tables en respectant l'ordre des dépendances protégées."""
        from apps.notifications.models import Notification
        from apps.relances.models import Relance

        Notification.objects.all().delete()
        Relance.objects.all().delete()
        Paiement.objects.all().delete()
        DemandeAdhesion.objects.all().delete()
        Cotisation.objects.all().delete()
        Exemption.objects.all().delete()
        Membre.objects.all().delete()
        Utilisateur.objects.all().update(section=None)
        Utilisateur.objects.filter(is_superuser=False).delete()
        Section.objects.all().delete()

    def _creer_sections(self, nombre):
        sections = []
        for code, libelle, ville, etablissement in SECTIONS[:nombre]:
            section, _ = Section.objects.get_or_create(
                code=code, defaults={'libelle': libelle, 'ville': ville,
                                     'etablissement': etablissement})
            sections.append(section)
        return sections

    def _creer_utilisateurs(self, sections):
        comptes = [
            ('admin@afemc-ci.org', 'KOUADIO', 'Jean Marc', Utilisateur.Role.ADMIN, None),
            ('administratif@afemc-ci.org', 'KONE', 'Aya', Utilisateur.Role.RESP_ADMIN, None),
            ('financier@afemc-ci.org', 'TRAORE', 'Mariam', Utilisateur.Role.RESP_FINANCIER, None),
        ]
        for section in sections[:5]:
            comptes.append((f'section.{section.code.lower()}@afemc-ci.org',
                            random.choice(NOMS), random.choice(PRENOMS),
                            Utilisateur.Role.RESP_SECTION, section))
        for email, nom, prenoms, role, section in comptes:
            if not Utilisateur.objects.filter(email=email).exists():
                utilisateur = Utilisateur.objects.create_user(
                    email=email, password='Afemc2026!Demo', nom=nom,
                    prenoms=prenoms, role=role, section=section)
                if role == Utilisateur.Role.ADMIN:
                    utilisateur.is_staff = True
                    utilisateur.is_superuser = True
                    utilisateur.save()

    def _creer_membres(self, nombre, sections):
        membres = []
        for i in range(nombre):
            nom = random.choice(NOMS)
            prenoms = f'{random.choice(PRENOMS)} {random.choice(PRENOMS)}'
            rang = random.random()
            statut = (Membre.Statut.INACTIF if rang < 0.11
                      else Membre.Statut.SUSPENDU if rang < 0.14
                      else Membre.Statut.ACTIF)
            identifiant = nom.lower().replace("'", "")
            membres.append(Membre.objects.create(
                nom=nom, prenoms=prenoms,
                email=f'{identifiant}.{i}@exemple.org',
                telephone=f'+225 07 {random.randint(10, 99)} {random.randint(10, 99)} '
                          f'{random.randint(10, 99)} {random.randint(10, 99)}',
                grade=random.choice(GRADES),
                etablissement=random.choice(sections).etablissement,
                section=random.choice(sections),
                date_adhesion=self.aujourdhui - timedelta(days=random.randint(30, 2500)),
                statut=statut))
        return membres

    def _creer_demandes(self, sections):
        repartition = ([DemandeAdhesion.Statut.VALIDEE] * 38
                       + [DemandeAdhesion.Statut.EN_ATTENTE] * 14
                       + [DemandeAdhesion.Statut.EN_EXAMEN] * 8
                       + [DemandeAdhesion.Statut.REJETEE] * 15)
        for i, statut in enumerate(repartition):
            nom = random.choice(NOMS)
            DemandeAdhesion.objects.create(
                nom=nom, prenoms=random.choice(PRENOMS),
                email=f'candidate.{i}@exemple.org',
                telephone=f'+225 05 {random.randint(10, 99)} {random.randint(10, 99)} 00 00',
                grade=random.choice(GRADES),
                etablissement=random.choice(sections).etablissement,
                section=random.choice(sections),
                motivation="Je souhaite rejoindre l'association afin de participer "
                           "à ses activités scientifiques.",
                statut=statut,
                date_traitement=(timezone.now() - timedelta(days=random.randint(1, 200))
                                 if statut in (DemandeAdhesion.Statut.VALIDEE,
                                               DemandeAdhesion.Statut.REJETEE) else None))

    def _creer_exemptions(self, membres):
        for membre in random.sample(membres, min(18, len(membres))):
            Exemption.objects.get_or_create(
                membre=membre, exercice=self.aujourdhui.year,
                defaults={'motif': random.choice(MOTIFS_EXEMPTION)})

    def _creer_cotisations(self, membres, exercices):
        montant = Decimal('25000')
        exercice_courant = max(exercices)
        for exercice in exercices:
            for membre in membres:
                if membre.statut == Membre.Statut.INACTIF and exercice == exercice_courant:
                    continue
                if membre.date_adhesion.year > exercice:
                    continue

                echeance = self._echeance(exercice, exercice_courant)
                cotisation = Cotisation.objects.create(
                    membre=membre, exercice=exercice, montant_du=montant,
                    date_echeance=echeance)

                self._regler(cotisation, exercice, exercice_courant, montant)

    def _echeance(self, exercice, courant):
        if exercice < courant:
            return date(exercice, 3, 31)
        # Exercice courant : échéances réparties autour de la date du jour
        tirage = random.random()
        if tirage < 0.05:
            return self.aujourdhui                       # échéance du jour (SC03)
        if tirage < 0.45:
            return self.aujourdhui + timedelta(days=random.randint(1, 120))
        return self.aujourdhui - timedelta(days=random.randint(1, 150))

    def _regler(self, cotisation, exercice, courant, montant):
        tirage = random.random()
        ancien = exercice < courant
        seuil_integral = 0.88 if ancien else 0.52
        seuil_partiel = seuil_integral + (0.05 if ancien else 0.14)

        if tirage < seuil_integral:
            self._payer(cotisation, montant)
        elif tirage < seuil_partiel:
            self._payer(cotisation, Decimal(random.choice([5000, 10000, 15000, 20000])))

        cotisation.statut = calculer_statut(cotisation, self.aujourdhui)
        cotisation.save(update_fields=['montant_paye', 'statut'])

    def _payer(self, cotisation, montant):
        jours = max((self.aujourdhui - cotisation.date_echeance).days, 0)
        quand = timezone.now() - timedelta(days=random.randint(1, max(jours + 60, 61)))
        Paiement.objects.create(
            cotisation=cotisation, montant=montant,
            mode=random.choice(['ESPECES', 'VIREMENT', 'MOBILE_MONEY', 'CHEQUE']),
            reference=f'REC-{random.randint(10000, 99999)}',
            date_paiement=quand)
        cotisation.montant_paye += montant
