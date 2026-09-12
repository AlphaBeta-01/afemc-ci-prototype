from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.accounts.models import Utilisateur
from apps.core.models import JournalOperation
from apps.sections.models import Section


class TestAuthentification(TestCase):

    def setUp(self):
        self.section = Section.objects.create(code='ABJ', libelle='Section d\'Abidjan')
        self.utilisateur = Utilisateur.objects.create_user(
            email='resp@afemc-ci.org', password='MotDePasse2026!',
            nom='KOFFI', prenoms='Awa', role=Utilisateur.Role.RESP_ADMIN)

    def test_connexion_avec_identifiants_valides(self):
        reponse = self.client.post(reverse('accounts:connexion'),
                                   {'username': 'resp@afemc-ci.org',
                                    'password': 'MotDePasse2026!'})
        self.assertEqual(reponse.status_code, 302)

    def test_connexion_avec_mot_de_passe_errone_est_journalisee(self):
        self.client.post(reverse('accounts:connexion'),
                         {'username': 'resp@afemc-ci.org', 'password': 'mauvais'})
        self.assertTrue(JournalOperation.objects
                        .filter(type_operation='CONNEXION_ECHOUEE').exists())

    def test_page_interne_inaccessible_sans_authentification(self):
        reponse = self.client.get(reverse('membres:liste'))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn('connexion', reponse.url)

    def test_le_mot_de_passe_n_est_pas_stocke_en_clair(self):
        self.assertNotIn('MotDePasse2026!', self.utilisateur.password)
        self.assertTrue(self.utilisateur.check_password('MotDePasse2026!'))

    def test_role_par_defaut_est_membre(self):
        simple = Utilisateur.objects.create_user(
            email='membre@afemc-ci.org', password='MotDePasse2026!',
            nom='YAO', prenoms='Adjoua')
        self.assertEqual(simple.role, Utilisateur.Role.MEMBRE)

    def test_un_responsable_de_section_ne_voit_pas_toutes_les_sections(self):
        responsable = Utilisateur.objects.create_user(
            email='rs@afemc-ci.org', password='MotDePasse2026!',
            nom='BAMBA', prenoms='Fatou',
            role=Utilisateur.Role.RESP_SECTION, section=self.section)
        self.assertFalse(responsable.voit_toutes_les_sections)
        self.assertTrue(responsable.est_responsable)


class TestActivationCompte(TestCase):
    """Prise de mot de passe par un membre nouvellement admis (RG02)."""

    def setUp(self):
        self.compte = Utilisateur.objects.create_user(
            email='nouvelle.membre@exemple.org', password=None,
            nom='KOUAME', prenoms='Adjoua', role=Utilisateur.Role.MEMBRE,
            is_active=False)
        self.uidb64 = urlsafe_base64_encode(force_bytes(self.compte.pk))
        self.token = default_token_generator.make_token(self.compte)

    def test_connexion_impossible_avant_activation(self):
        reponse = self.client.post(reverse('accounts:connexion'),
                                   {'username': 'nouvelle.membre@exemple.org',
                                    'password': 'peu-importe'})
        self.assertEqual(reponse.status_code, 200)          # ré-affiche le formulaire
        self.assertFalse(self.client.session.get('_auth_user_id'))

    def test_lien_valide_permet_de_definir_le_mot_de_passe(self):
        url = reverse('accounts:activation', args=[self.uidb64, self.token])
        reponse_get = self.client.get(url, follow=True)
        self.assertTrue(reponse_get.context['validlink'])

        url_pose = reponse_get.redirect_chain[-1][0]
        reponse_post = self.client.post(url_pose,
                                        {'new_password1': 'NouveauMdp2026!',
                                         'new_password2': 'NouveauMdp2026!'})
        self.assertEqual(reponse_post.status_code, 302)

        self.compte.refresh_from_db()
        self.assertTrue(self.compte.is_active)
        self.assertTrue(self.compte.check_password('NouveauMdp2026!'))
        self.assertTrue(JournalOperation.objects
                        .filter(type_operation='ACTIVATION_COMPTE').exists())

    def test_lien_errone_est_rejete(self):
        url = reverse('accounts:activation', args=[self.uidb64, 'jeton-invalide'])
        reponse = self.client.get(url, follow=True)
        self.assertFalse(reponse.context['validlink'])
        self.compte.refresh_from_db()
        self.assertFalse(self.compte.is_active)


class TestMotDePasseOublie(TestCase):
    """Réinitialisation en libre-service d'un mot de passe oublié (RG02)."""

    def setUp(self):
        self.compte = Utilisateur.objects.create_user(
            email='responsable@afemc-ci.org', password='AncienMdp2026!', nom='KOUAME',
            prenoms='Adjoua', role=Utilisateur.Role.RESP_ADMIN, is_active=True)

    def _demander(self, email):
        return self.client.post(reverse('accounts:mot_de_passe_oublie'), {'email': email})

    def test_reponse_identique_que_le_compte_existe_ou_non(self):
        r1 = self._demander('responsable@afemc-ci.org')
        r2 = self._demander('personne@exemple.org')
        self.assertEqual(r1.status_code, r2.status_code)
        self.assertContains(r1, 'Vérifiez votre boîte de réception')
        self.assertContains(r2, 'Vérifiez votre boîte de réception')

    def test_un_lien_est_envoye_uniquement_si_le_compte_existe(self):
        from apps.notifications.models import Notification

        self._demander('responsable@afemc-ci.org')
        self.assertEqual(Notification.objects.filter(
            type='REINITIALISATION_MOT_DE_PASSE').count(), 1)

        self._demander('personne@exemple.org')
        self.assertEqual(Notification.objects.filter(
            type='REINITIALISATION_MOT_DE_PASSE').count(), 1)          # toujours 1

    def test_la_demande_est_toujours_journalisee(self):
        self._demander('personne@exemple.org')
        self.assertTrue(JournalOperation.objects.filter(
            type_operation='DEMANDE_REINITIALISATION_MOT_DE_PASSE',
            detail='personne@exemple.org').exists())

    def test_le_lien_permet_de_changer_le_mot_de_passe_sans_desactiver_le_compte(self):
        uidb64 = urlsafe_base64_encode(force_bytes(self.compte.pk))
        token = default_token_generator.make_token(self.compte)

        reponse_get = self.client.get(
            reverse('accounts:activation', args=[uidb64, token]), follow=True)
        url_pose = reponse_get.redirect_chain[-1][0]
        self.client.post(url_pose, {'new_password1': 'NouveauMdp2026!',
                                    'new_password2': 'NouveauMdp2026!'})

        self.compte.refresh_from_db()
        self.assertTrue(self.compte.is_active)          # toujours actif, pas "réactivé"
        self.assertTrue(self.compte.check_password('NouveauMdp2026!'))
        self.assertFalse(self.compte.check_password('AncienMdp2026!'))
        self.assertTrue(JournalOperation.objects.filter(
            type_operation='REINITIALISATION_MOT_DE_PASSE').exists())
        self.assertFalse(JournalOperation.objects.filter(
            type_operation='ACTIVATION_COMPTE').exists())

    def test_un_compte_jamais_active_peut_reobtenir_un_lien(self):
        """Sert aussi de renvoi de lien d'activation expiré (RG02)."""
        from apps.notifications.models import Notification

        inactif = Utilisateur.objects.create_user(
            email='nouvelle@exemple.org', password=None, nom='TRAORE',
            prenoms='Fatou', role=Utilisateur.Role.MEMBRE, is_active=False)
        self._demander('nouvelle@exemple.org')
        notification = Notification.objects.get(type='REINITIALISATION_MOT_DE_PASSE',
                                                 destinataire='nouvelle@exemple.org')
        self.assertIn('/comptes/activation/', notification.contexte['lien'])
        self.assertFalse(inactif.is_active)          # inchangé tant que le lien n'est pas suivi


class TestPerimetreResponsableSection(TestCase):
    """Le responsable de section : membres et sections seulement (RG08).

    Ni cotisations, ni adhésions, ni relances — ni dans le menu, ni en accès
    direct (le menu ne doit jamais proposer un lien qui aboutit à un 403).
    """

    def setUp(self):
        self.section = Section.objects.create(code='ABJ', libelle='Abidjan')
        self.autre_section = Section.objects.create(code='KRG', libelle='Korhogo')
        self.responsable = Utilisateur.objects.create_user(
            email='rs.abj@afemc-ci.org', password='MotDePasse2026!', nom='TRAORE',
            prenoms='Mariam', role=Utilisateur.Role.RESP_SECTION, section=self.section)
        self.client.force_login(self.responsable)

    def test_le_menu_ne_montre_que_membres_et_sections(self):
        reponse = self.client.get(reverse('membres:liste'))
        self.assertContains(reponse, reverse('membres:liste'))
        self.assertContains(reponse, reverse('sections:liste'))
        self.assertNotContains(reponse, reverse('cotisations:liste'))
        self.assertNotContains(reponse, reverse('adhesions:liste'))
        self.assertNotContains(reponse, reverse('relances:liste'))

    def test_acces_direct_bloque_cotisations_adhesions_relances(self):
        for url in (reverse('cotisations:liste'), reverse('adhesions:liste'),
                   reverse('relances:liste')):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_peut_ajouter_un_membre_dans_sa_propre_section(self):
        from apps.membres.models import Membre

        reponse = self.client.post(reverse('membres:creer'), {
            'nom': 'DIALLO', 'prenoms': 'Fatoumata', 'email': 'fatoumata@exemple.org',
            'section': self.section.pk, 'date_adhesion': '2026-01-01',
            'statut': 'ACTIF'})
        self.assertEqual(reponse.status_code, 302)
        membre = Membre.objects.get(email='fatoumata@exemple.org')
        self.assertEqual(membre.section, self.section)

    def test_ne_peut_pas_ajouter_un_membre_dans_une_autre_section(self):
        from apps.membres.models import Membre

        reponse = self.client.post(reverse('membres:creer'), {
            'nom': 'DIALLO', 'prenoms': 'Fatoumata', 'email': 'fatoumata@exemple.org',
            'section': self.autre_section.pk, 'date_adhesion': '2026-01-01',
            'statut': 'ACTIF'})
        self.assertEqual(reponse.status_code, 200)          # formulaire réaffiché, erreur
        self.assertFalse(Membre.objects.filter(email='fatoumata@exemple.org').exists())

    def test_peut_modifier_un_membre_de_sa_propre_section(self):
        from apps.membres.models import Membre

        membre = Membre.objects.create(nom='KOUAME', prenoms='Akissi',
                                       email='kouame@exemple.org', section=self.section)
        reponse = self.client.post(reverse('membres:modifier', args=[membre.pk]), {
            'nom': 'KOUAME', 'prenoms': 'Akissi Marie', 'email': 'kouame@exemple.org',
            'section': self.section.pk, 'date_adhesion': '2026-01-01',
            'statut': 'ACTIF'})
        self.assertEqual(reponse.status_code, 302)
        membre.refresh_from_db()
        self.assertEqual(membre.prenoms, 'Akissi Marie')

    def test_ne_peut_pas_modifier_un_membre_hors_de_sa_section(self):
        from apps.membres.models import Membre

        membre = Membre.objects.create(nom='BAMBA', prenoms='Fatou',
                                       email='bamba@exemple.org',
                                       section=self.autre_section)
        reponse = self.client.get(reverse('membres:modifier', args=[membre.pk]))
        self.assertEqual(reponse.status_code, 404)

    def test_ne_peut_pas_deplacer_un_membre_vers_une_autre_section(self):
        from apps.membres.models import Membre

        membre = Membre.objects.create(nom='KOUAME', prenoms='Akissi',
                                       email='kouame@exemple.org', section=self.section)
        self.client.post(reverse('membres:modifier', args=[membre.pk]), {
            'nom': 'KOUAME', 'prenoms': 'Akissi', 'email': 'kouame@exemple.org',
            'section': self.autre_section.pk, 'date_adhesion': '2026-01-01',
            'statut': 'ACTIF'})
        membre.refresh_from_db()
        self.assertEqual(membre.section, self.section)          # inchangé

    def test_ne_voit_ni_cotisations_ni_relances_sur_la_fiche_membre(self):
        from apps.membres.models import Membre

        membre = Membre.objects.create(nom='KOUAME', prenoms='Akissi',
                                       email='kouame@exemple.org', section=self.section)
        reponse = self.client.get(reverse('membres:detail', args=[membre.pk]))
        self.assertEqual(reponse.status_code, 200)
        self.assertNotIn('cotisations', reponse.context)
        self.assertNotIn('relances', reponse.context)
        self.assertNotContains(reponse, 'Historique des cotisations')
        self.assertNotContains(reponse, 'Relances reçues')


class TestGestionComptesResponsables(TestCase):
    """Création des comptes responsables, réservée à l'Administrateur (RG08)."""

    def setUp(self):
        self.section = Section.objects.create(code='ABJ', libelle='Abidjan')
        self.admin = Utilisateur.objects.create_user(
            email='admin@afemc-ci.org', password='MotDePasse2026!', nom='KOUADIO',
            prenoms='Jean', role=Utilisateur.Role.ADMIN, is_staff=True, is_superuser=True)

    def test_un_non_administrateur_est_refuse(self):
        responsable = Utilisateur.objects.create_user(
            email='administratif@afemc-ci.org', password='MotDePasse2026!',
            nom='KONE', prenoms='Aya', role=Utilisateur.Role.RESP_ADMIN)
        self.client.force_login(responsable)
        self.assertEqual(self.client.get(reverse('accounts:comptes_liste')).status_code, 403)
        self.assertEqual(self.client.get(reverse('accounts:comptes_creer')).status_code, 403)

    def test_le_lien_comptes_n_apparait_que_pour_l_administrateur(self):
        self.client.force_login(self.admin)
        reponse = self.client.get(reverse('sections:liste'))
        self.assertContains(reponse, reverse('accounts:comptes_liste'))

        responsable = Utilisateur.objects.create_user(
            email='administratif@afemc-ci.org', password='MotDePasse2026!',
            nom='KONE', prenoms='Aya', role=Utilisateur.Role.RESP_ADMIN)
        self.client.force_login(responsable)
        reponse = self.client.get(reverse('sections:liste'))
        self.assertNotContains(reponse, reverse('accounts:comptes_liste'))

    def test_creation_d_un_responsable_de_section(self):
        self.client.force_login(self.admin)
        reponse = self.client.post(reverse('accounts:comptes_creer'), {
            'nom': 'TRAORE', 'prenoms': 'Mariam', 'email': 'mariam@afemc-ci.org',
            'role': Utilisateur.Role.RESP_SECTION, 'section': self.section.pk})
        self.assertEqual(reponse.status_code, 302)

        compte = Utilisateur.objects.get(email='mariam@afemc-ci.org')
        self.assertEqual(compte.role, Utilisateur.Role.RESP_SECTION)
        self.assertEqual(compte.section, self.section)
        self.assertFalse(compte.is_active)
        self.assertFalse(compte.has_usable_password())
        self.assertTrue(JournalOperation.objects
                        .filter(type_operation='CREATION_COMPTE_RESPONSABLE').exists())

        from apps.notifications.models import Notification
        notification = Notification.objects.get(type='CREATION_COMPTE_RESPONSABLE')
        self.assertEqual(notification.destinataire, 'mariam@afemc-ci.org')
        self.assertIn('/comptes/activation/', notification.contexte['lien'])

    def test_une_section_est_exigee_pour_un_responsable_de_section(self):
        self.client.force_login(self.admin)
        reponse = self.client.post(reverse('accounts:comptes_creer'), {
            'nom': 'TRAORE', 'prenoms': 'Mariam', 'email': 'mariam@afemc-ci.org',
            'role': Utilisateur.Role.RESP_SECTION})
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Utilisateur.objects.filter(email='mariam@afemc-ci.org').exists())

    def test_impossible_de_creer_un_administrateur_via_cet_ecran(self):
        self.client.force_login(self.admin)
        reponse = self.client.post(reverse('accounts:comptes_creer'), {
            'nom': 'TRAORE', 'prenoms': 'Mariam', 'email': 'mariam@afemc-ci.org',
            'role': Utilisateur.Role.ADMIN})
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Utilisateur.objects.filter(email='mariam@afemc-ci.org').exists())

    def test_activation_du_compte_permet_la_connexion(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('accounts:comptes_creer'), {
            'nom': 'TRAORE', 'prenoms': 'Mariam', 'email': 'mariam@afemc-ci.org',
            'role': Utilisateur.Role.RESP_FINANCIER})
        compte = Utilisateur.objects.get(email='mariam@afemc-ci.org')

        c2 = self.client_class()
        uidb64 = urlsafe_base64_encode(force_bytes(compte.pk))
        token = default_token_generator.make_token(compte)
        r = c2.get(reverse('accounts:activation', args=[uidb64, token]), follow=True)
        url_pose = r.redirect_chain[-1][0]
        c2.post(url_pose, {'new_password1': 'Nouveau2026!', 'new_password2': 'Nouveau2026!'})

        compte.refresh_from_db()
        self.assertTrue(compte.is_active)
        self.assertTrue(c2.login(email='mariam@afemc-ci.org', password='Nouveau2026!'))

    def test_basculer_desactive_puis_reactive_un_compte(self):
        self.client.force_login(self.admin)
        compte = Utilisateur.objects.create_user(
            email='mariam@afemc-ci.org', password='MotDePasse2026!', nom='TRAORE',
            prenoms='Mariam', role=Utilisateur.Role.RESP_FINANCIER)

        url = reverse('accounts:compte_basculer_actif', args=[compte.pk])
        self.client.post(url)
        compte.refresh_from_db()
        self.assertFalse(compte.is_active)

        self.client.post(url)
        compte.refresh_from_db()
        self.assertTrue(compte.is_active)

    def test_ne_peut_pas_desactiver_son_propre_compte(self):
        self.client.force_login(self.admin)
        url = reverse('accounts:compte_basculer_actif', args=[self.admin.pk])
        self.client.post(url)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
