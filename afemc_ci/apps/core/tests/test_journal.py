from django.test import TestCase

from apps.accounts.models import Utilisateur
from apps.core.models import JournalOperation
from apps.core.services import journaliser


class TestJournalisation(TestCase):

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            email='resp@afemc-ci.org', password='MotDePasse2026!',
            nom='KOFFI', prenoms='Awa', role=Utilisateur.Role.RESP_ADMIN)

    def test_une_operation_est_enregistree(self):
        journaliser(self.utilisateur, 'TEST_OPERATION', 'détail de test')
        self.assertEqual(JournalOperation.objects.count(), 1)

    def test_l_auteur_est_conserve(self):
        journaliser(self.utilisateur, 'TEST_OPERATION')
        self.assertEqual(JournalOperation.objects.first().utilisateur, self.utilisateur)

    def test_le_type_est_tronque_a_quarante_caracteres(self):
        journaliser(self.utilisateur, 'T' * 60)
        self.assertEqual(len(JournalOperation.objects.first().type_operation), 40)

    def test_une_operation_systeme_sans_utilisateur(self):
        journaliser(None, 'EXECUTION_MOTEUR_RELANCE', '0 relance')
        self.assertIsNone(JournalOperation.objects.first().utilisateur)
