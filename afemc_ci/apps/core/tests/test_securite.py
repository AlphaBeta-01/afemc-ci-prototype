"""Tests de sécurité TS01 à TS14 (§ 6.6.2 du mémoire).

TS11-TS12 formalisent les deux failles trouvées et corrigées lors de la
revue de sécurité menée après la rédaction initiale du chapitre 6.
TS13 vérifie le retrait immédiat des droits à la fin d'un mandat (RG13),
TS14 que la connexion à l'administration est soumise au verrouillage (RG10).
"""
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

    def test_ts11_detail_de_section_inaccessible_a_un_simple_membre(self):
        membre_actif = fabrique.utilisateur('MEMBRE', email='membre.actif@afemc-ci.org',
                                            section_liee=self.abidjan)
        self.client.login(username=membre_actif.email, password=fabrique.MOT_DE_PASSE)
        reponse = self.client.get(reverse('sections:detail', args=[self.abidjan.pk]))
        self.assertEqual(reponse.status_code, 403)

    def test_ts12_piece_justificative_non_accessible_par_lien_direct(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from apps.adhesions.models import DemandeAdhesion, PieceJustificative

        demande = DemandeAdhesion.objects.create(
            nom='DIABATE', prenoms='Salimata', email='salimata@exemple.org',
            section=self.abidjan)
        piece = PieceJustificative.objects.create(
            demande=demande, type_piece=PieceJustificative.TypePiece.DIPLOME,
            fichier=SimpleUploadedFile('diplome.pdf', b'%PDF-1.4',
                                       content_type='application/pdf'))
        url = reverse('adhesions:telecharger_piece', args=[piece.pk])

        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 302)          # sans authentification

        self.client.login(username=self.resp_abidjan.email, password=fabrique.MOT_DE_PASSE)
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 403)          # rôle non habilité
        self.client.logout()

        self.client.login(username=self.admin.email, password=fabrique.MOT_DE_PASSE)
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 200)          # rôle habilité

    def test_ts13_droits_retires_immediatement_en_fin_de_fonctions(self):
        """Une session ouverte pendant le mandat ne conserve aucun droit après :
        le rôle est relu en base à chaque requête."""
        from apps.accounts.services import mettre_fin_aux_fonctions

        fiche = fabrique.membre(nom='COULIBALY', sect=self.abidjan,
                                email=self.resp_abidjan.email)
        fiche.utilisateur = self.resp_abidjan
        fiche.save()
        self.client.login(username=self.resp_abidjan.email, password=fabrique.MOT_DE_PASSE)
        self.assertEqual(self.client.get(reverse('membres:liste')).status_code, 200)

        mettre_fin_aux_fonctions(self.resp_abidjan, par=self.admin)   # session toujours ouverte

        self.assertEqual(self.client.get(reverse('membres:liste')).status_code, 403)
        self.assertEqual(self.client.get(reverse('sections:detail',
                                                 args=[self.abidjan.pk])).status_code, 403)

    def test_ts14_connexion_admin_soumise_au_verrouillage(self):
        """La page de connexion de l'administration ne permet plus d'essayer
        des mots de passe sans limite : elle renvoie vers celle de
        l'application, qui compte les échecs et verrouille le compte."""
        reponse = self.client.get('/admin/login/?next=/admin/')
        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(reponse.url, reverse('accounts:connexion') + '?next=/admin/')

        # Un envoi direct de mot de passe n'y est plus traité du tout.
        self.admin.is_staff = True
        self.admin.save()
        self.client.post('/admin/login/', {'username': self.admin.email,
                                           'password': fabrique.MOT_DE_PASSE})
        self.assertEqual(self.client.get('/admin/').status_code, 302)   # toujours déconnecté

        # Par la page de l'application, l'accès à l'administration fonctionne.
        self.client.post(reverse('accounts:connexion') + '?next=/admin/',
                         {'username': self.admin.email, 'password': fabrique.MOT_DE_PASSE})
        self.assertEqual(self.client.get('/admin/').status_code, 200)
