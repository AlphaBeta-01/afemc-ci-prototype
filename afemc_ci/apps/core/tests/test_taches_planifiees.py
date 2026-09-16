"""Point d'entrée pour l'ordonnanceur externe (§ 7 du README, GitHub Actions)."""
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import Utilisateur
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


@override_settings(CRON_SECRET='jeton-de-test',
                   SUPERUSER_BOOTSTRAP_EMAIL='admin@afemc-ci.org',
                   SUPERUSER_BOOTSTRAP_PASSWORD='MotDePasse2026!')
class TestAmorcageAdministrateur(TestCase):

    def _appeler(self, jeton='jeton-de-test'):
        entetes = {'HTTP_AUTHORIZATION': f'Bearer {jeton}'} if jeton is not None else {}
        return self.client.get(reverse('core:amorcer_administrateur'), **entetes)

    def test_refuse_sans_jeton(self):
        reponse = self._appeler(jeton=None)
        self.assertEqual(reponse.status_code, 403)
        self.assertFalse(Utilisateur.objects.filter(is_superuser=True).exists())

    def test_cree_le_compte_administrateur(self):
        reponse = self._appeler()
        self.assertEqual(reponse.status_code, 200)
        compte = Utilisateur.objects.get(email='admin@afemc-ci.org')
        self.assertTrue(compte.is_superuser)
        self.assertTrue(compte.is_staff)
        self.assertEqual(compte.role, Utilisateur.Role.ADMIN)
        self.assertTrue(compte.check_password('MotDePasse2026!'))

    def test_idempotente_si_un_administrateur_existe_deja(self):
        Utilisateur.objects.create_superuser(
            email='deja.la@afemc-ci.org', password='MotDePasse2026!',
            nom='TEST', prenoms='Deja')
        reponse = self._appeler()
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('existe déjà', reponse.json()['info'])
        self.assertFalse(Utilisateur.objects.filter(email='admin@afemc-ci.org').exists())

    @override_settings(SUPERUSER_BOOTSTRAP_EMAIL='', SUPERUSER_BOOTSTRAP_PASSWORD='')
    def test_refuse_si_non_configuree(self):
        reponse = self._appeler()
        self.assertEqual(reponse.status_code, 500)
