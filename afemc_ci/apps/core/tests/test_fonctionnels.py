"""Tests fonctionnels TF01 à TF32 (§ 6.4 du mémoire).

Chaque test rejoue un cas d'utilisation depuis l'interface, pour un profil donné.
TF26-TF30 couvrent les fonctionnalités ajoutées après la rédaction initiale du
chapitre 6 (activation de compte, mot de passe oublié, gestion des comptes
responsables, périmètre resserré du responsable de section, pièces
justificatives) — à raccorder au texte du mémoire si celui-ci doit en rendre compte.
TF31-TF32 couvrent la nomination d'une membre à une fonction et la fin de
fonctions (RG13) ; TF28 porte désormais sur le compte externe, l'exception.
"""
from datetime import date
from decimal import Decimal
from urllib.parse import urlparse

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.adhesions.models import DemandeAdhesion
from apps.core.models import JournalOperation
from apps.core.tests import fabrique
from apps.cotisations.models import Cotisation, Paiement
from apps.membres.models import Membre
from apps.sections.models import Section


class BaseFonctionnelle(TestCase):

    def setUp(self):
        call_command('charger_regles', verbosity=0)
        self.abidjan = fabrique.section('ABJ', "Section d'Abidjan")
        self.korhogo = fabrique.section('KRG', 'Section de Korhogo')

        self.admin = fabrique.utilisateur('ADMIN')
        self.administratif = fabrique.utilisateur('RESP_ADMIN')
        self.financier = fabrique.utilisateur('RESP_FINANCIER')
        self.resp_abidjan = fabrique.utilisateur('RESP_SECTION',
                                                 email='rs.abj@afemc-ci.org',
                                                 section_liee=self.abidjan)

        self.membre_abj = fabrique.membre(nom='KOUAME', sect=self.abidjan)
        self.membre_krg = fabrique.membre(nom='BAMBA', sect=self.korhogo)
        self.cotisation = fabrique.cotisation(membre_lie=self.membre_abj, jours_ecart=-30)

    def connecter(self, utilisateur):
        self.assertTrue(self.client.login(username=utilisateur.email,
                                          password=fabrique.MOT_DE_PASSE))


class TestAuthentificationEtAcces(BaseFonctionnelle):

    def test_tf01_connexion_avec_identifiants_valides(self):
        reponse = self.client.post(reverse('accounts:connexion'),
                                   {'username': self.admin.email,
                                    'password': fabrique.MOT_DE_PASSE})
        self.assertEqual(reponse.status_code, 302)
        self.assertTrue(JournalOperation.objects
                        .filter(type_operation='CONNEXION_REUSSIE').exists())

    def test_tf02_connexion_avec_mot_de_passe_errone(self):
        reponse = self.client.post(reverse('accounts:connexion'),
                                   {'username': self.admin.email,
                                    'password': 'mauvais-mot-de-passe'})
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(JournalOperation.objects
                        .filter(type_operation='CONNEXION_ECHOUEE').exists())

    def test_tf03_un_membre_n_accede_pas_aux_pages_financieres(self):
        simple = fabrique.utilisateur('MEMBRE', email='membre@afemc-ci.org')
        self.connecter(simple)
        reponse = self.client.get(reverse('cotisations:liste'))
        self.assertEqual(reponse.status_code, 403)
        self.assertTrue(JournalOperation.objects
                        .filter(type_operation='ACCES_REFUSE').exists())

    def test_tf04_un_responsable_de_section_ne_voit_que_sa_section(self):
        self.connecter(self.resp_abidjan)
        reponse = self.client.get(reverse('membres:liste'))
        self.assertEqual(reponse.status_code, 200)
        noms = [m.nom for m in reponse.context['page']]
        self.assertIn('KOUAME', noms)
        self.assertNotIn('BAMBA', noms)

    def test_tf04b_acces_direct_a_une_fiche_hors_perimetre(self):
        self.connecter(self.resp_abidjan)
        reponse = self.client.get(reverse('membres:detail', args=[self.membre_krg.pk]))
        self.assertEqual(reponse.status_code, 404)


class TestGestionDesMembres(BaseFonctionnelle):

    def test_tf05_creation_d_un_membre_avec_matricule_automatique(self):
        self.connecter(self.administratif)
        reponse = self.client.post(reverse('membres:creer'), {
            'nom': 'DIALLO', 'prenoms': 'Fatoumata',
            'email': 'fatoumata@exemple.org', 'telephone': '+225 07 00 00 00 00',
            'grade': 'Assistante', 'etablissement': 'UFHB',
            'section': self.abidjan.pk, 'date_adhesion': date.today().isoformat(),
            'statut': 'ACTIF'})
        self.assertEqual(reponse.status_code, 302)
        membre = Membre.objects.get(email='fatoumata@exemple.org')
        self.assertTrue(membre.matricule.startswith('ABJ-'))
        self.assertTrue(JournalOperation.objects
                        .filter(type_operation='CREATION_MEMBRE').exists())

    def test_tf06_adresse_electronique_deja_utilisee(self):
        self.connecter(self.administratif)
        reponse = self.client.post(reverse('membres:creer'), {
            'nom': 'AUTRE', 'prenoms': 'Personne',
            'email': self.membre_abj.email, 'section': self.abidjan.pk,
            'date_adhesion': date.today().isoformat(), 'statut': 'ACTIF'})
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('email', reponse.context['formulaire'].errors)

    def test_tf07_recherche_multicriteres(self):
        self.connecter(self.administratif)
        reponse = self.client.get(reverse('membres:liste'), {'q': 'KOUAME'})
        noms = [m.nom for m in reponse.context['page']]
        self.assertEqual(noms, ['KOUAME'])

    def test_tf07b_filtre_par_section(self):
        self.connecter(self.administratif)
        reponse = self.client.get(reverse('membres:liste'),
                                  {'section': self.korhogo.pk})
        noms = [m.nom for m in reponse.context['page']]
        self.assertEqual(noms, ['BAMBA'])

    def test_tf18_consultation_de_la_fiche_d_un_membre(self):
        self.connecter(self.administratif)
        reponse = self.client.get(reverse('membres:detail', args=[self.membre_abj.pk]))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, self.membre_abj.matricule)


class TestAdhesions(BaseFonctionnelle):

    def test_tf08_soumission_publique_d_une_demande(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        diplome = SimpleUploadedFile('diplome.pdf', b'%PDF-1.4 contenu factice',
                                     content_type='application/pdf')
        reponse = self.client.post(reverse('adhesions:soumettre'), {
            'nom': 'SANOGO', 'prenoms': 'Aminata', 'email': 'aminata@exemple.org',
            'telephone': '+225 05 00 00 00 00', 'grade': 'Maître-Assistante',
            'etablissement': 'UFHB', 'section': self.abidjan.pk,
            'motivation': 'Participer aux activités scientifiques.',
            # Au moins une pièce justificative est désormais exigée (RG12).
            'pieces-TOTAL_FORMS': '2', 'pieces-INITIAL_FORMS': '0',
            'pieces-MIN_NUM_FORMS': '0', 'pieces-MAX_NUM_FORMS': '1000',
            'pieces-0-type_piece': 'DIPLOME', 'pieces-0-fichier': diplome,
            'pieces-1-type_piece': ''})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(DemandeAdhesion.objects.count(), 1)
        self.assertEqual(DemandeAdhesion.objects.get().pieces.count(), 1)

    def test_tf09_traitement_complet_d_une_demande(self):
        demande = DemandeAdhesion.objects.create(
            nom='CISSE', prenoms='Mariam', email='mariam@exemple.org',
            section=self.abidjan)
        self.connecter(self.administratif)

        self.client.post(reverse('adhesions:traiter', args=[demande.pk]),
                         {'statut': 'EN_EXAMEN', 'motif': ''})
        self.client.post(reverse('adhesions:traiter', args=[demande.pk]),
                         {'statut': 'VALIDEE', 'motif': ''})

        demande.refresh_from_db()
        self.assertEqual(demande.statut, DemandeAdhesion.Statut.VALIDEE)
        self.assertTrue(Membre.objects.filter(email='mariam@exemple.org').exists())

    def test_tf09b_transition_interdite_depuis_l_interface(self):
        demande = DemandeAdhesion.objects.create(
            nom='KONE', prenoms='Aya', email='aya2@exemple.org', section=self.abidjan)
        self.connecter(self.administratif)
        self.client.post(reverse('adhesions:traiter', args=[demande.pk]),
                         {'statut': 'VALIDEE', 'motif': ''})
        demande.refresh_from_db()
        self.assertEqual(demande.statut, DemandeAdhesion.Statut.EN_ATTENTE)
        self.assertEqual(Membre.objects.filter(email='aya2@exemple.org').count(), 0)


class TestCotisationsEtPaiements(BaseFonctionnelle):

    def test_tf10_emission_collective_depuis_l_interface(self):
        self.connecter(self.financier)
        reponse = self.client.post(reverse('cotisations:emettre'), {
            'exercice': 2027, 'montant': '30000',
            'date_echeance': '2027-03-31'})
        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(Cotisation.objects.filter(exercice=2027).count(), 2)

    def test_tf11_enregistrement_d_un_paiement(self):
        self.connecter(self.financier)
        reponse = self.client.post(
            reverse('cotisations:paiement', args=[self.cotisation.pk]),
            {'montant': '25000', 'mode': 'MOBILE_MONEY', 'reference': 'REC-42'})
        self.assertEqual(reponse.status_code, 302)
        self.cotisation.refresh_from_db()
        self.assertEqual(self.cotisation.statut, Cotisation.Statut.PAYEE)
        self.assertEqual(Paiement.objects.count(), 1)

    def test_tf12_paiement_superieur_au_reste_est_refuse(self):
        self.connecter(self.financier)
        reponse = self.client.post(
            reverse('cotisations:paiement', args=[self.cotisation.pk]),
            {'montant': '40000', 'mode': 'ESPECES', 'reference': ''})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(Paiement.objects.count(), 0)
        self.cotisation.refresh_from_db()
        self.assertEqual(self.cotisation.montant_paye, Decimal('0'))

    def test_la_presidente_ne_peut_pas_enregistrer_un_paiement(self):
        """La Trésorière est seule habilitée à valider/modifier un paiement —
        la Présidente garde la vue globale (liste, export), pas la saisie."""
        self.connecter(self.admin)
        reponse = self.client.post(
            reverse('cotisations:paiement', args=[self.cotisation.pk]),
            {'montant': '25000', 'mode': 'ESPECES', 'reference': ''})
        self.assertEqual(reponse.status_code, 403)
        self.assertEqual(Paiement.objects.count(), 0)

    def test_la_presidente_garde_la_vue_globale_des_cotisations(self):
        self.connecter(self.admin)
        reponse = self.client.get(reverse('cotisations:liste'))
        self.assertEqual(reponse.status_code, 200)

    def test_tf13_consultation_des_cotisations_en_retard(self):
        retard = fabrique.cotisation(membre_lie=self.membre_krg, jours_ecart=30,
                                     statut=Cotisation.Statut.EN_RETARD)
        self.connecter(self.financier)
        reponse = self.client.get(reverse('cotisations:liste'),
                                  {'exercice': 2026, 'statut': 'EN_RETARD'})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual([c.pk for c in reponse.context['page']], [retard.pk])

    def test_tf17_export_csv(self):
        self.connecter(self.financier)
        reponse = self.client.get(reverse('cotisations:export'), {'exercice': 2026})
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('text/csv', reponse['Content-Type'])
        self.assertIn('attachment', reponse['Content-Disposition'])
        contenu = reponse.content.decode('utf-8')
        self.assertIn(self.membre_abj.matricule, contenu)


class TestMoteurEtTableauDeBord(BaseFonctionnelle):

    def test_tf14_declenchement_manuel_du_moteur(self):
        from io import StringIO

        fabrique.cotisation(membre_lie=self.membre_krg, jours_ecart=20)
        sortie = StringIO()
        call_command('detecter_retards', stdout=sortie)
        self.assertIn('relance', sortie.getvalue())

    def test_tf14b_moteur_en_mode_simulation(self):
        from io import StringIO

        from apps.relances.models import Relance

        fabrique.cotisation(membre_lie=self.membre_krg, jours_ecart=20)
        sortie = StringIO()
        call_command('detecter_retards', '--simulation', stdout=sortie)
        self.assertIn('SIMULATION', sortie.getvalue())
        self.assertEqual(Relance.objects.count(), 0)

    def test_tf15_historique_des_relances(self):
        from apps.relances.services import executer_detection

        fabrique.cotisation(membre_lie=self.membre_krg, jours_ecart=20)
        executer_detection()
        self.connecter(self.financier)
        reponse = self.client.get(reverse('relances:liste'))
        self.assertEqual(reponse.status_code, 200)
        self.assertGreaterEqual(len(reponse.context['page'].object_list), 1)

    def test_tf16_affichage_du_tableau_de_bord(self):
        self.connecter(self.admin)
        reponse = self.client.get(reverse('dashboard:accueil'), {'exercice': 2026})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.context['indicateurs']['effectif_total'], 2)

    def test_tf16b_le_tableau_de_bord_est_cloisonne_par_section(self):
        # Le responsable de section a désormais un tableau de bord dédié
        # (uniquement l'effectif de sa section, sans cotisations/relances/
        # adhésions) plutôt qu'une vue cloisonnée du tableau de bord général.
        self.connecter(self.resp_abidjan)
        reponse = self.client.get(reverse('dashboard:accueil'), {'exercice': 2026})
        self.assertEqual(reponse.context['section'], self.abidjan)
        self.assertEqual(reponse.context['effectif_actif'], 1)

    def test_tf16c_page_de_synthese_d_une_section(self):
        self.connecter(self.administratif)
        reponse = self.client.get(reverse('sections:detail', args=[self.abidjan.pk]))
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.context['section'], self.abidjan)

    def test_tf16d_section_hors_perimetre_refusee(self):
        self.connecter(self.resp_abidjan)
        reponse = self.client.get(reverse('sections:detail', args=[self.korhogo.pk]))
        self.assertEqual(reponse.status_code, 403)


class TestComptesEtPerimetreResserre(BaseFonctionnelle):
    """TF26-TF30 : fonctionnalités ajoutées après le chapitre 6 initial."""

    def test_tf26_activation_d_un_compte_membre_et_connexion(self):
        from apps.notifications.models import Notification

        demande = DemandeAdhesion.objects.create(
            nom='SANOGO', prenoms='Aminata', email='aminata.tf26@exemple.org',
            section=self.abidjan)
        self.connecter(self.administratif)
        self.client.post(reverse('adhesions:traiter', args=[demande.pk]),
                         {'statut': 'EN_EXAMEN', 'motif': ''})
        self.client.post(reverse('adhesions:traiter', args=[demande.pk]),
                         {'statut': 'VALIDEE', 'motif': ''})
        self.client.logout()

        demande.refresh_from_db()
        compte = demande.membre.utilisateur
        self.assertFalse(compte.is_active)

        notification = Notification.objects.get(type='ACTIVATION_COMPTE', membre=demande.membre)
        chemin = urlparse(notification.contexte['lien']).path
        # Le premier accès au jeton réel redirige vers l'URL « set-password » :
        # deux temps, comme le veut PasswordResetConfirmView.
        reponse_get = self.client.get(chemin, follow=True)
        url_pose = reponse_get.redirect_chain[-1][0]
        reponse = self.client.post(url_pose, {'new_password1': 'NouveauMdp2026!',
                                              'new_password2': 'NouveauMdp2026!'})
        self.assertEqual(reponse.status_code, 302)

        compte.refresh_from_db()
        self.assertTrue(compte.is_active)
        self.assertTrue(self.client.login(username=compte.email, password='NouveauMdp2026!'))

    def test_tf27_mot_de_passe_oublie_et_reinitialisation(self):
        from apps.notifications.models import Notification

        self.client.post(reverse('accounts:mot_de_passe_oublie'),
                         {'email': self.financier.email})
        notification = Notification.objects.get(type='REINITIALISATION_MOT_DE_PASSE')
        chemin = urlparse(notification.contexte['lien']).path
        reponse_get = self.client.get(chemin, follow=True)
        url_pose = reponse_get.redirect_chain[-1][0]

        self.client.post(url_pose, {'new_password1': 'Nouveau2026Mdp!',
                                    'new_password2': 'Nouveau2026Mdp!'})

        self.assertFalse(self.client.login(username=self.financier.email,
                                           password=fabrique.MOT_DE_PASSE))
        self.assertTrue(self.client.login(username=self.financier.email,
                                          password='Nouveau2026Mdp!'))

    def test_tf28_creation_d_un_compte_responsable_par_l_administrateur(self):
        from apps.accounts.models import Utilisateur

        self.connecter(self.admin)
        reponse = self.client.post(reverse('accounts:comptes_creer'), {
            'nom': 'TRAORE', 'prenoms': 'Mariam', 'email': 'mariam.tf28@afemc-ci.org',
            'role': Utilisateur.Role.RESP_SECTION, 'section': self.korhogo.pk})
        self.assertEqual(reponse.status_code, 302)

        compte = Utilisateur.objects.get(email='mariam.tf28@afemc-ci.org')
        self.assertEqual(compte.role, Utilisateur.Role.RESP_SECTION)
        self.assertFalse(compte.is_active)

    def test_tf29_la_coordinatrice_consulte_les_cotisations_sans_les_modifier(self):
        """Cotisations de sa section en lecture seule ; ni adhésions ni relances."""
        self.connecter(self.resp_abidjan)
        page = self.client.get(reverse('cotisations:liste')).context['page']
        self.assertEqual({c.membre.section for c in page}, {self.abidjan})
        self.assertEqual(self.client.get(
            reverse('cotisations:paiement', args=[self.cotisation.pk])).status_code, 403)
        for nom_url in ('adhesions:liste', 'relances:liste'):
            with self.subTest(url=nom_url):
                self.assertEqual(self.client.get(reverse(nom_url)).status_code, 403)

    def test_tf30_demande_d_adhesion_sans_document_est_refusee(self):
        reponse = self.client.post(reverse('adhesions:soumettre'), {
            'nom': 'KEITA', 'prenoms': 'Fanta', 'email': 'fanta@exemple.org',
            'telephone': '+225 07 00 00 00 00', 'grade': 'Assistante',
            'etablissement': 'UFHB', 'section': self.abidjan.pk,
            'motivation': "Participer aux activités de l'association.",
            'pieces-TOTAL_FORMS': '2', 'pieces-INITIAL_FORMS': '0',
            'pieces-MIN_NUM_FORMS': '0', 'pieces-MAX_NUM_FORMS': '1000',
            'pieces-0-type_piece': '', 'pieces-1-type_piece': ''})
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(DemandeAdhesion.objects.filter(email='fanta@exemple.org').exists())

    def test_tf31_nomination_d_une_membre_a_une_fonction(self):
        """La Présidente nomme une membre Trésorière : même compte, nouveaux accès."""
        from apps.accounts.models import Utilisateur

        compte = fabrique.utilisateur('MEMBRE', email=self.membre_abj.email)
        self.membre_abj.utilisateur = compte
        self.membre_abj.save()
        comptes_avant = Utilisateur.objects.count()

        self.connecter(self.admin)
        self.client.post(reverse('accounts:nommer'),
                         {'membre': self.membre_abj.pk, 'role': 'RESP_FINANCIER'})
        self.assertEqual(Utilisateur.objects.count(), comptes_avant)

        self.client.logout()
        self.connecter(compte)                  # mêmes identifiants qu'avant
        self.assertEqual(self.client.get(reverse('cotisations:liste')).status_code, 200)

    def test_tf32_fin_de_fonctions_retire_les_acces_et_garde_le_compte(self):
        from apps.accounts.services import nommer_responsable

        compte = fabrique.utilisateur('MEMBRE', email=self.membre_abj.email)
        self.membre_abj.utilisateur = compte
        self.membre_abj.save()
        nommer_responsable(self.membre_abj, 'RESP_FINANCIER', nomme_par=self.admin)

        self.connecter(self.admin)
        self.client.post(reverse('accounts:fin_fonctions', args=[compte.pk]))

        self.client.logout()
        self.connecter(compte)
        self.assertEqual(self.client.get(reverse('cotisations:liste')).status_code, 403)
        reponse = self.client.get(reverse('membres:detail', args=[self.membre_abj.pk]))
        self.assertContains(reponse, 'Historique des cotisations')
