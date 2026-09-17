"""Tests des traitements planifiés et des commandes d'administration (§ 5.6.1)."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.core.tests import fabrique


class TestTachesPlanifiees(TestCase):

    def setUp(self):
        call_command('charger_regles', verbosity=0)
        self.section = fabrique.section()

    def test_la_tache_de_detection_execute_le_moteur(self):
        from apps.relances.models import Relance
        from apps.relances.tasks import executer_detection

        fabrique.cotisation(jours_ecart=20)
        resultat = executer_detection()
        self.assertGreaterEqual(resultat['relances'], 1)
        self.assertEqual(Relance.objects.count(), 1)

    def test_la_tache_d_acheminement_vide_la_file(self):
        """`creer_notification` envoie déjà instantanément (§ 5.6.3) : la
        tâche planifiée est le filet de sécurité, sans rien à faire ici."""
        from apps.notifications.models import Notification
        from apps.notifications.services import creer_notification
        from apps.notifications.tasks import acheminer

        creer_notification('membre@exemple.org', 'TEST', 'Objet',
                           'notifications/synthese.txt',
                           {'responsable': 'KONE Aya', 'exercice': 2026,
                            'effectif': 12, 'retards': 3, 'taux': '80,0',
                            'reste': '15000'})
        self.assertEqual(Notification.objects.first().statut,
                         Notification.Statut.ENVOYEE)
        resultat = acheminer()
        self.assertEqual(resultat['envoyees'], 0)

    def test_la_synthese_hebdomadaire_vise_les_responsables(self):
        from apps.dashboard.tasks import envoyer_synthese
        from apps.notifications.models import Notification

        fabrique.utilisateur('RESP_ADMIN')
        fabrique.utilisateur('RESP_FINANCIER')
        nombre = envoyer_synthese()
        self.assertEqual(nombre, 2)
        self.assertEqual(
            Notification.objects.filter(type='SYNTHESE_HEBDO').count(), 2)

    def test_la_commande_d_acheminement_rend_compte(self):
        from unittest.mock import patch

        from apps.notifications.services import ErreurEnvoi, creer_notification

        with patch('apps.notifications.services.envoyer_courriel',
                   side_effect=ErreurEnvoi('temporaire')):
            creer_notification('membre@exemple.org', 'TEST', 'Objet',
                               'notifications/synthese.txt',
                               {'responsable': 'KONE Aya', 'exercice': 2026,
                                'effectif': 12, 'retards': 3, 'taux': '80,0',
                                'reste': '15000'})
        sortie = StringIO()
        call_command('acheminer_notifications', stdout=sortie)
        self.assertIn('1 notification', sortie.getvalue())

    def test_la_commande_de_chargement_des_regles_est_idempotente(self):
        from apps.relances.models import RegleRelance

        call_command('charger_regles', verbosity=0)
        call_command('charger_regles', verbosity=0)
        self.assertEqual(RegleRelance.objects.count(), 6)
