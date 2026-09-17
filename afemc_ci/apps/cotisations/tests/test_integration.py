"""Tests d'intégration TI01 à TI12 (§ 6.3 du mémoire)."""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.db.models import Sum
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from apps.adhesions.models import DemandeAdhesion
from apps.adhesions.services import changer_statut
from apps.core.tests import fabrique
from apps.cotisations.models import Cotisation, Exemption
from apps.cotisations.services import (accorder_exemption, emettre_cotisations_exercice,
                                       enregistrer_paiement)
from apps.dashboard.services import indicateurs_globaux
from apps.membres.models import Membre
from apps.notifications.models import Notification
from apps.notifications.services import ErreurEnvoi, acheminer_notifications_en_attente
from apps.relances.models import Relance
from apps.relances.services import executer_detection

S = DemandeAdhesion.Statut


class TestProcessusComplets(TestCase):
    """Chaque test correspond à une ligne du tableau 21."""

    def setUp(self):
        call_command('charger_regles', verbosity=0)
        self.section = fabrique.section()
        self.responsable = fabrique.utilisateur('RESP_ADMIN')

    # ---------------- TI01 / TI02 : adhésion ----------------
    def test_ti01_validation_d_une_demande_d_adhesion(self):
        demande = DemandeAdhesion.objects.create(
            nom='DIABATE', prenoms='Salimata', email='salimata@exemple.org',
            section=self.section)
        changer_statut(demande, S.EN_EXAMEN, self.responsable)
        changer_statut(demande, S.VALIDEE, self.responsable)

        self.assertEqual(Membre.objects.count(), 1)
        self.assertEqual(Cotisation.objects.count(), 1)
        self.assertTrue(Notification.objects.filter(
            destinataire='salimata@exemple.org').exists())

    def test_ti02_rejet_d_une_demande_d_adhesion(self):
        demande = DemandeAdhesion.objects.create(
            nom='TOURE', prenoms='Awa', email='awa@exemple.org', section=self.section)
        changer_statut(demande, S.REJETEE, self.responsable, motif='Dossier incomplet')

        self.assertEqual(Membre.objects.count(), 0)
        self.assertEqual(Cotisation.objects.count(), 0)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, S.REJETEE)
        self.assertEqual(demande.motif, 'Dossier incomplet')

    # ---------------- TI03 : émission collective ----------------
    def test_ti03_emission_collective_sans_doublon(self):
        for i in range(6):
            fabrique.membre(nom=f'NOM{i}')
        creees, _ = emettre_cotisations_exercice(2026, Decimal('25000'),
                                                 date(2026, 12, 31), self.responsable)
        creees2, ignorees = emettre_cotisations_exercice(2026, Decimal('25000'),
                                                         date(2026, 12, 31))
        self.assertEqual(len(creees), 6)
        self.assertEqual(len(creees2), 0)
        self.assertEqual(ignorees, 6)
        self.assertEqual(Cotisation.objects.count(), 6)

    # ---------------- TI04 / TI05 : paiements ----------------
    def test_ti04_paiement_integral(self):
        cot = fabrique.cotisation(jours_ecart=-60)
        enregistrer_paiement(cot, Decimal('25000'), 'ESPECES', 'REC-1', self.responsable)
        cot.refresh_from_db()
        self.assertEqual(cot.statut, Cotisation.Statut.PAYEE)
        self.assertEqual(cot.reste_a_payer, Decimal('0'))

    def test_ti05_deux_paiements_partiels(self):
        cot = fabrique.cotisation(jours_ecart=-60)
        enregistrer_paiement(cot, Decimal('10000'), 'ESPECES')
        cot.refresh_from_db()
        self.assertEqual(cot.statut, Cotisation.Statut.PARTIEL)
        enregistrer_paiement(cot, Decimal('15000'), 'MOBILE_MONEY')
        cot.refresh_from_db()
        self.assertEqual(cot.statut, Cotisation.Statut.PAYEE)
        self.assertEqual(cot.paiements.count(), 2)
        self.assertEqual(cot.paiements.aggregate(t=Sum('montant'))['t'], Decimal('25000'))

    # ---------------- TI06 : passage d'échéance ----------------
    def test_ti06_passage_d_echeance_sans_paiement(self):
        cot = fabrique.cotisation(jours_ecart=1)
        executer_detection()
        cot.refresh_from_db()
        self.assertEqual(cot.statut, Cotisation.Statut.EN_RETARD)
        self.assertTrue(cot.relances.filter(regle__code='R03').exists())
        self.assertTrue(Notification.objects.filter(membre=cot.membre).exists())

    # ---------------- TI07 / TI08 : exécutions répétées et simulation ----------------
    def test_ti07_executions_repetees_sans_doublon(self):
        cot = fabrique.cotisation(jours_ecart=20)
        executer_detection()
        executer_detection()
        executer_detection()
        self.assertEqual(cot.relances.count(), 1)

    def test_ti08_mode_simulation_n_ecrit_rien(self):
        cot = fabrique.cotisation(jours_ecart=20)
        resultat = executer_detection(simulation=True)
        cot.refresh_from_db()
        self.assertEqual(cot.statut, Cotisation.Statut.EN_ATTENTE)
        self.assertEqual(Relance.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)
        self.assertGreaterEqual(resultat['relances'], 1)

    # ---------------- TI09 : exemption tardive ----------------
    def test_ti09_exemption_enregistree_apres_emission(self):
        membre = fabrique.membre()
        cot = fabrique.cotisation(membre_lie=membre, jours_ecart=20)
        executer_detection()
        nombre = cot.relances.count()
        self.assertGreaterEqual(nombre, 1)

        accorder_exemption(membre, 2026, 'Congé de maternité', self.responsable)
        cot.refresh_from_db()
        self.assertEqual(cot.statut, Cotisation.Statut.EXEMPTEE)

        executer_detection()
        self.assertEqual(cot.relances.count(), nombre)

    # ---------------- TI10 : indisponibilité du service de messagerie ----------------
    @patch('apps.notifications.services.envoyer_courriel',
           side_effect=ErreurEnvoi('service indisponible'))
    def test_ti10_les_notifications_ne_sont_pas_perdues(self, _):
        fabrique.cotisation(jours_ecart=20)
        executer_detection()             # tentative immédiate (échoue, service patché)
        notification = Notification.objects.first()
        self.assertEqual(notification.statut, Notification.Statut.EN_ATTENTE)
        self.assertEqual(notification.tentatives, 1)

        # le service est rétabli : la notification part à la tentative suivante
        with patch('apps.notifications.services.envoyer_courriel', return_value=1):
            envoyees, echecs = acheminer_notifications_en_attente()
        self.assertGreaterEqual(envoyees, 1)
        notification.refresh_from_db()
        self.assertEqual(notification.statut, Notification.Statut.ENVOYEE)

    # ---------------- TI11 : protection des données ----------------
    def test_ti11_suppression_d_une_section_peuplee_refusee(self):
        fabrique.membre(sect=self.section)
        with self.assertRaises(ProtectedError):
            self.section.delete()
        self.assertEqual(Membre.objects.count(), 1)

    def test_ti11b_suppression_d_un_membre_avec_cotisation_refusee(self):
        cot = fabrique.cotisation(jours_ecart=-10)
        with self.assertRaises(ProtectedError):
            cot.membre.delete()

    # ---------------- TI12 : cohérence du tableau de bord ----------------
    def test_ti12_les_indicateurs_egalent_le_calcul_direct(self):
        for i in range(12):
            membre = fabrique.membre(nom=f'NOM{i}')
            fabrique.cotisation(membre_lie=membre, jours_ecart=-10,
                                paye='25000' if i < 7 else '0',
                                statut=Cotisation.Statut.PAYEE if i < 7 else None)

        indicateurs = indicateurs_globaux(2026)
        direct = Cotisation.objects.filter(exercice=2026).aggregate(
            du=Sum('montant_du'), paye=Sum('montant_paye'))

        self.assertEqual(indicateurs['total_du'], direct['du'])
        self.assertEqual(indicateurs['total_paye'], direct['paye'])
        self.assertEqual(indicateurs['reste_a_recouvrer'], direct['du'] - direct['paye'])
        self.assertEqual(indicateurs['nb_payees'], 7)
