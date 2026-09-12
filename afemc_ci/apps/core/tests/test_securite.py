"""Tests de sécurité TS01 à TS10 (§ 6.6.2 du mémoire)."""
from django.test import TestCase
from django.urls import reverse

from apps.core.models import JournalOperation
from apps.core.tests import fabrique


class TestSecurite(TestCase):

    def setUp(self):
        self.abidjan = fabrique.section('ABJ', "Section d'Abidjan")
        self.korhogo = fabrique.section('KRG', 'Section de Korhogo')
        self.admin = fabrique.utilisateur('ADMIN')
        self.resp_abidjan = fabrique.utilisateur('RESP_SECTION',
                                                 email='rs.abj@afemc-ci.org',
                                                 section_liee=self.abidjan)
        self.membre_krg = fabrique.membre(nom='BAMBA', sect=self.korhogo)

    def test_ts01_acces_sans_authentification(self):
        reponse = self.client.get(reverse('membres:liste'))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn('connexion', reponse.url)

    def test_ts02_acces_direct_a_une_fiche_non_habilitee(self):
        simple = fabrique.utilisateur('MEMBRE', email='simple@afemc-ci.org')
        self.client.login(username=simple.email, password=fabrique.MOT_DE_PASSE)
        reponse = self.client.get(reverse('membres:detail', args=[self.membre_krg.pk]))
        self.assertIn(reponse.status_code, (403, 404))

    def test_ts03_cloisonnement_maintenu_par_modification_d_url(self):
        self.client.login(username=self.resp_abidjan.email,
                          password=fabrique.MOT_DE_PASSE)
        reponse = self.client.get(reverse('sections:detail', args=[self.korhogo.pk]))
        self.assertEqual(reponse.status_code, 403)

    def test_ts04_injection_sql_dans_la_recherche(self):
        from apps.membres.models import Membre

        self.client.login(username=self.admin.email, password=fabrique.MOT_DE_PASSE)
        reponse = self.client.get(reverse('membres:liste'),
                                  {'q': "'; DROP TABLE membres_membre; --"})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(Membre.objects.count(), 1)   # la table existe toujours

    def test_ts05_injection_de_balises_html(self):
        from apps.membres.models import Membre

        Membre.objects.create(nom='<script>alert(1)</script>', prenoms='Test',
                              email='xss@exemple.org', section=self.abidjan)
        self.client.login(username=self.admin.email, password=fabrique.MOT_DE_PASSE)
        reponse = self.client.get(reverse('membres:liste'))
        self.assertNotContains(reponse, '<script>alert(1)</script>')
        self.assertContains(reponse, '&lt;script&gt;')

    def test_ts06_formulaire_sans_jeton_anti_csrf(self):
        client = self.client_class(enforce_csrf_checks=True)
        reponse = client.post(reverse('accounts:connexion'),
                              {'username': self.admin.email,
                               'password': fabrique.MOT_DE_PASSE})
        self.assertEqual(reponse.status_code, 403)

    def test_ts07_tentatives_repetees_journalisees(self):
        for _ in range(5):
            self.client.post(reverse('accounts:connexion'),
                             {'username': self.admin.email, 'password': 'faux'})
        self.assertEqual(
            JournalOperation.objects.filter(type_operation='CONNEXION_ECHOUEE').count(), 5)

    def test_ts08_les_mots_de_passe_sont_haches(self):
        self.assertTrue(self.admin.password.startswith(('pbkdf2_', 'argon2', 'md5$')))
        self.assertNotIn(fabrique.MOT_DE_PASSE, self.admin.password)

    def test_ts09_session_invalidee_apres_deconnexion(self):
        self.client.login(username=self.admin.email, password=fabrique.MOT_DE_PASSE)
        self.client.post(reverse('accounts:deconnexion'))
        reponse = self.client.get(reverse('membres:liste'))
        self.assertEqual(reponse.status_code, 302)

    def test_ts10_le_journal_n_est_pas_modifiable_depuis_l_administration(self):
        from django.contrib import admin as django_admin

        from apps.core.models import JournalOperation as Journal

        outil = django_admin.site._registry[Journal]
        self.assertFalse(outil.has_add_permission(None))
        self.assertFalse(outil.has_change_permission(None))
        self.assertFalse(outil.has_delete_permission(None))
