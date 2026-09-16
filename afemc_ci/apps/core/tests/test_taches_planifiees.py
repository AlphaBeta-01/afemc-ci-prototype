"""Point d'entrée pour l'ordonnanceur externe (§ 7 du README, GitHub Actions)."""
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.core.tests import fabrique
from apps.notifications.models import Notification


@override_settings(CRON_SECRET='jeton-de-test')
class TestExecutionTachesPlanifiees(TestCase):

    def setUp(self):
        call_command('charger_regles', verbosity=0)
        self.section = fabrique.section()

    def _appeler(self, jeton='jeton-de-test', **params):
        entetes = {'HTTP_AUTHORIZATION': f'Bearer {jeton}'} if jeton is not None else {}
        return self.client.get(reverse('core:executer_taches'), params, **entetes)

    def test_refuse_sans_jeton(self):
        reponse = self._appeler(jeton=None)
        self.assertEqual(reponse.status_code, 403)

    def test_refuse_avec_un_mauvais_jeton(self):
        reponse = self._appeler(jeton='incorrect')
        self.assertEqual(reponse.status_code, 403)

    @override_settings(CRON_SECRET='')
    def test_refuse_si_aucun_jeton_configure(self):
        """Un CRON_SECRET vide ne doit jamais être « acceptant par défaut »."""
        reponse = self._appeler(jeton='')
        self.assertEqual(reponse.status_code, 403)

    def test_execute_la_detection_et_l_acheminement_avec_le_bon_jeton(self):
        fabrique.cotisation(membre_lie=fabrique.membre(sect=self.section), jours_ecart=5)
        reponse = self._appeler()
        self.assertEqual(reponse.status_code, 200)
        corps = reponse.json()
        self.assertIn('detection', corps)
        self.assertIn('notifications_envoyees', corps)
        self.assertTrue(Notification.objects.filter(type='RELANCE_COTISATION').exists())

    def test_refuse_en_methode_post(self):
        reponse = self.client.post(reverse('core:executer_taches'),
                                   HTTP_AUTHORIZATION='Bearer jeton-de-test')
        self.assertEqual(reponse.status_code, 405)
