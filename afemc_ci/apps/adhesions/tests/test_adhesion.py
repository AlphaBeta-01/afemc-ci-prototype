from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Utilisateur
from apps.adhesions.models import DemandeAdhesion, PieceJustificative
from apps.adhesions.services import (TransitionInterdite, changer_statut,
                                     regulariser_comptes_membres)
from apps.cotisations.models import Cotisation
from apps.membres.models import Membre
from apps.sections.models import Section

S = DemandeAdhesion.Statut


class TestCycleAdhesion(TestCase):

    def setUp(self):
        self.section = Section.objects.create(code='ABJ', libelle='Abidjan')
        self.demande = DemandeAdhesion.objects.create(
            nom='DIABATE', prenoms='Salimata', email='salimata@exemple.org',
            section=self.section)

    def test_une_demande_est_en_attente_a_la_creation(self):
        self.assertEqual(self.demande.statut, S.EN_ATTENTE)

    def test_validation_directe_sans_examen_est_refusee(self):
        with self.assertRaises(TransitionInterdite):
            changer_statut(self.demande, S.VALIDEE)

    def test_validation_cree_le_membre_et_la_cotisation(self):
        changer_statut(self.demande, S.EN_EXAMEN)
        changer_statut(self.demande, S.VALIDEE)
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.statut, S.VALIDEE)
        self.assertIsNotNone(self.demande.membre)
        self.assertEqual(Membre.objects.count(), 1)
        self.assertEqual(Cotisation.objects.count(), 1)

    def test_rejet_ne_cree_aucun_membre(self):
        changer_statut(self.demande, S.REJETEE, motif='Dossier incomplet')
        self.assertEqual(Membre.objects.count(), 0)
        self.assertEqual(self.demande.motif, 'Dossier incomplet')

    def test_une_demande_validee_ne_peut_etre_rouverte(self):
        changer_statut(self.demande, S.EN_EXAMEN)
        changer_statut(self.demande, S.VALIDEE)
        with self.assertRaises(TransitionInterdite):
            changer_statut(self.demande, S.EN_EXAMEN)

    def test_le_traitement_est_journalise(self):
        from apps.core.models import JournalOperation
        changer_statut(self.demande, S.EN_EXAMEN)
        self.assertTrue(JournalOperation.objects
                        .filter(type_operation='CHANGEMENT_STATUT_ADHESION').exists())

    def test_une_notification_est_produite(self):
        from apps.notifications.models import Notification
        changer_statut(self.demande, S.EN_EXAMEN)
        self.assertEqual(Notification.objects.count(), 1)

    def test_la_validation_cree_un_compte_membre_inactif(self):
        from apps.accounts.models import Utilisateur
        changer_statut(self.demande, S.EN_EXAMEN)
        changer_statut(self.demande, S.VALIDEE)
        self.demande.refresh_from_db()
        compte = self.demande.membre.utilisateur
        self.assertIsNotNone(compte)
        self.assertEqual(compte.role, Utilisateur.Role.MEMBRE)
        self.assertEqual(compte.email, self.demande.email)
        self.assertFalse(compte.is_active)
        self.assertFalse(compte.has_usable_password())

    def test_la_validation_envoie_un_lien_d_activation(self):
        from apps.notifications.models import Notification
        changer_statut(self.demande, S.EN_EXAMEN)
        changer_statut(self.demande, S.VALIDEE)
        self.demande.refresh_from_db()
        notification = Notification.objects.get(type='ACTIVATION_COMPTE')
        self.assertEqual(notification.destinataire, self.demande.membre.utilisateur.email)
        self.assertIn('/comptes/activation/', notification.contexte['lien'])


class TestRegularisationComptesMembres(TestCase):
    """Filet de rattrapage pour les membres admis sans compte (RG02)."""

    def setUp(self):
        self.section = Section.objects.create(code='ABJ', libelle='Abidjan')

    def _demande_validee_sans_compte(self, email='oubliee@exemple.org'):
        """Reproduit l'état antérieur au déploiement de `creer_compte_acces`."""
        demande = DemandeAdhesion.objects.create(
            nom='COULIBALY', prenoms='Fatou', email=email, section=self.section)
        membre = Membre.objects.create(
            nom=demande.nom, prenoms=demande.prenoms, email=demande.email,
            section=demande.section)
        demande.membre = membre
        demande.statut = S.VALIDEE
        demande.save()
        return demande, membre

    def test_regularise_un_membre_sans_compte(self):
        from apps.accounts.models import Utilisateur
        from apps.notifications.models import Notification

        _, membre = self._demande_validee_sans_compte()
        regularises = regulariser_comptes_membres()

        membre.refresh_from_db()
        self.assertEqual(regularises, [membre])
        self.assertIsNotNone(membre.utilisateur)
        self.assertEqual(membre.utilisateur.role, Utilisateur.Role.MEMBRE)
        self.assertFalse(membre.utilisateur.is_active)
        self.assertTrue(Notification.objects.filter(type='ACTIVATION_COMPTE',
                                                     membre=membre).exists())

    def test_mode_simulation_ne_modifie_rien(self):
        _, membre = self._demande_validee_sans_compte()
        regularises = regulariser_comptes_membres(simulation=True)

        membre.refresh_from_db()
        self.assertEqual(regularises, [membre])
        self.assertIsNone(membre.utilisateur)

    def test_est_sans_effet_sur_un_membre_deja_pourvu(self):
        demande = DemandeAdhesion.objects.create(
            nom='YAO', prenoms='Adjoua', email='yao@exemple.org',
            section=self.section)
        changer_statut(demande, S.EN_EXAMEN)
        changer_statut(demande, S.VALIDEE)          # crée déjà le compte normalement

        self.assertEqual(regulariser_comptes_membres(), [])


class TestVisibiliteMenuAdhesions(TestCase):
    """Le responsable financier ne gère pas les adhésions (RG08) : le menu doit
    refléter cette exclusion, déjà en vigueur côté contrôle d'accès
    (`role_requis` sur `adhesions:liste`)."""

    def setUp(self):
        self.section = Section.objects.create(code='ABJ', libelle='Abidjan')

    def _connecter(self, role):
        compte = Utilisateur.objects.create_user(
            email=f'{role.lower()}@afemc-ci.org', password='MotDePasse2026!',
            nom='TEST', prenoms=role.title(), role=role)
        self.client.force_login(compte)
        return compte

    def test_le_responsable_financier_ne_voit_pas_le_lien_adhesions(self):
        self._connecter(Utilisateur.Role.RESP_FINANCIER)
        reponse = self.client.get(reverse('cotisations:liste'))
        self.assertNotContains(reponse, reverse('adhesions:liste'))

    def test_le_responsable_financier_reste_bloque_a_l_acces_direct(self):
        self._connecter(Utilisateur.Role.RESP_FINANCIER)
        reponse = self.client.get(reverse('adhesions:liste'))
        self.assertEqual(reponse.status_code, 403)

    def test_le_responsable_administratif_voit_toujours_le_lien(self):
        self._connecter(Utilisateur.Role.RESP_ADMIN)
        reponse = self.client.get(reverse('cotisations:liste'))
        self.assertContains(reponse, reverse('adhesions:liste'))


class TestDepotPiecesJustificatives(TestCase):
    """Une candidate doit prouver sa qualité d'enseignante chercheure (RG01)."""

    def setUp(self):
        self.section = Section.objects.create(code='ABJ', libelle='Abidjan')

    def _donnees_candidature(self, **piece_0):
        donnees = {
            'nom': 'DIABATE', 'prenoms': 'Salimata', 'email': 'salimata@exemple.org',
            'telephone': '+225 07 00 00 00 00', 'grade': 'Maître-Assistante',
            'etablissement': 'UFHB', 'section': self.section.pk,
            'motivation': "Je souhaite adhérer.",
            'pieces-TOTAL_FORMS': '2', 'pieces-INITIAL_FORMS': '0',
            'pieces-MIN_NUM_FORMS': '0', 'pieces-MAX_NUM_FORMS': '1000',
            'pieces-0-type_piece': '', 'pieces-1-type_piece': '',
        }
        donnees.update(piece_0)
        return donnees

    def _fichier(self, nom='diplome.pdf', contenu=b'%PDF-1.4 contenu factice'):
        return SimpleUploadedFile(nom, contenu, content_type='application/pdf')

    def test_la_demande_est_refusee_sans_aucun_document(self):
        reponse = self.client.post(reverse('adhesions:soumettre'), self._donnees_candidature())
        self.assertEqual(reponse.status_code, 200)          # formulaire réaffiché
        self.assertFalse(DemandeAdhesion.objects.exists())
        self.assertIn("Joignez au moins un document",
                      reponse.context['formset'].non_form_errors()[0])

    def test_la_demande_est_acceptee_avec_un_document(self):
        donnees = self._donnees_candidature(**{
            'pieces-0-type_piece': PieceJustificative.TypePiece.DIPLOME,
            'pieces-0-fichier': self._fichier(),
        })
        reponse = self.client.post(reverse('adhesions:soumettre'), donnees)
        self.assertEqual(reponse.status_code, 200)
        demande = DemandeAdhesion.objects.get(email='salimata@exemple.org')
        self.assertEqual(demande.pieces.count(), 1)
        piece = demande.pieces.first()
        self.assertEqual(piece.type_piece, PieceJustificative.TypePiece.DIPLOME)
        self.assertTrue(piece.fichier.name.endswith('.pdf'))

    def test_un_fichier_sans_type_precise_est_rejete(self):
        donnees = self._donnees_candidature(**{'pieces-0-fichier': self._fichier()})
        reponse = self.client.post(reverse('adhesions:soumettre'), donnees)
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(DemandeAdhesion.objects.exists())

    def test_une_extension_non_autorisee_est_rejetee(self):
        executable = SimpleUploadedFile('suspect.exe', b'MZ...',
                                        content_type='application/octet-stream')
        donnees = self._donnees_candidature(**{
            'pieces-0-type_piece': PieceJustificative.TypePiece.AUTRE,
            'pieces-0-fichier': executable,
        })
        reponse = self.client.post(reverse('adhesions:soumettre'), donnees)
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(DemandeAdhesion.objects.exists())

    def test_un_fichier_trop_volumineux_est_rejete(self):
        enorme = SimpleUploadedFile('diplome.pdf', b'0' * (6 * 1024 * 1024),
                                    content_type='application/pdf')
        donnees = self._donnees_candidature(**{
            'pieces-0-type_piece': PieceJustificative.TypePiece.DIPLOME,
            'pieces-0-fichier': enorme,
        })
        reponse = self.client.post(reverse('adhesions:soumettre'), donnees)
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(DemandeAdhesion.objects.exists())

    def test_le_responsable_administratif_voit_le_document_depose(self):
        demande = DemandeAdhesion.objects.create(
            nom='DIABATE', prenoms='Salimata', email='salimata@exemple.org',
            section=self.section)
        PieceJustificative.objects.create(
            demande=demande, type_piece=PieceJustificative.TypePiece.DIPLOME,
            fichier=self._fichier())
        admin = Utilisateur.objects.create_user(
            email='administratif@afemc-ci.org', password='MotDePasse2026!',
            nom='KONE', prenoms='Aya', role=Utilisateur.Role.RESP_ADMIN)
        self.client.force_login(admin)

        reponse = self.client.get(reverse('adhesions:traiter', args=[demande.pk]))
        self.assertContains(reponse, 'Diplôme')
        self.assertContains(reponse, 'Ouvrir')

    def test_l_absence_de_document_est_signalee_au_traitement(self):
        demande = DemandeAdhesion.objects.create(
            nom='DIABATE', prenoms='Salimata', email='salimata@exemple.org',
            section=self.section)
        admin = Utilisateur.objects.create_user(
            email='administratif@afemc-ci.org', password='MotDePasse2026!',
            nom='KONE', prenoms='Aya', role=Utilisateur.Role.RESP_ADMIN)
        self.client.force_login(admin)

        reponse = self.client.get(reverse('adhesions:traiter', args=[demande.pk]))
        self.assertContains(reponse, "n'est pas justifiée")


class TestAccesPiecesJustificatives(TestCase):
    """Un document déposé n'est accessible que via la vue authentifiée
    dédiée — jamais par un lien direct vers le stockage (revue de sécurité)."""

    def setUp(self):
        self.section = Section.objects.create(code='ABJ', libelle='Abidjan')
        self.demande = DemandeAdhesion.objects.create(
            nom='DIABATE', prenoms='Salimata', email='salimata@exemple.org',
            section=self.section)
        self.piece = PieceJustificative.objects.create(
            demande=self.demande, type_piece=PieceJustificative.TypePiece.DIPLOME,
            fichier=SimpleUploadedFile('diplome.pdf', b'%PDF-1.4 contenu factice',
                                       content_type='application/pdf'))

    def test_acces_refuse_sans_authentification(self):
        reponse = self.client.get(reverse('adhesions:telecharger_piece', args=[self.piece.pk]))
        self.assertEqual(reponse.status_code, 302)          # redirigé vers la connexion

    def test_acces_refuse_a_un_role_non_habilite(self):
        financier = Utilisateur.objects.create_user(
            email='financier@afemc-ci.org', password='MotDePasse2026!', nom='TRAORE',
            prenoms='Mariam', role=Utilisateur.Role.RESP_FINANCIER)
        self.client.force_login(financier)
        reponse = self.client.get(reverse('adhesions:telecharger_piece', args=[self.piece.pk]))
        self.assertEqual(reponse.status_code, 403)

    def test_le_responsable_administratif_peut_telecharger_le_document(self):
        from apps.core.models import JournalOperation

        admin = Utilisateur.objects.create_user(
            email='administratif@afemc-ci.org', password='MotDePasse2026!',
            nom='KONE', prenoms='Aya', role=Utilisateur.Role.RESP_ADMIN)
        self.client.force_login(admin)

        reponse = self.client.get(reverse('adhesions:telecharger_piece', args=[self.piece.pk]))
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(b''.join(reponse.streaming_content), b'%PDF-1.4 contenu factice')
        self.assertTrue(JournalOperation.objects
                        .filter(type_operation='CONSULTATION_PIECE_JUSTIFICATIVE').exists())

    def test_le_fichier_n_est_plus_accessible_par_un_lien_direct_vers_media(self):
        # Confirme que config/urls.py ne monte plus MEDIA_URL directement.
        reponse = self.client.get(f'/media/{self.piece.fichier.name}')
        self.assertEqual(reponse.status_code, 404)


class TestChampsObligatoiresDemande(TestCase):
    """Tous les renseignements du formulaire public sont exigés (RG01).

    Seul `motif` (motif de rejet, renseigné par le traitement — pas par la
    candidate) reste facultatif.
    """

    def setUp(self):
        self.section = Section.objects.create(code='ABJ', libelle='Abidjan')

    def _donnees_completes(self):
        return {
            'nom': 'DIABATE', 'prenoms': 'Salimata', 'email': 'salimata@exemple.org',
            'telephone': '+225 07 00 00 00 00', 'grade': 'Maître-Assistante',
            'etablissement': 'UFHB', 'section': self.section.pk,
            'motivation': "Je souhaite adhérer.",
            'pieces-TOTAL_FORMS': '2', 'pieces-INITIAL_FORMS': '0',
            'pieces-MIN_NUM_FORMS': '0', 'pieces-MAX_NUM_FORMS': '1000',
            'pieces-0-type_piece': PieceJustificative.TypePiece.DIPLOME,
            'pieces-0-fichier': SimpleUploadedFile(
                'diplome.pdf', b'%PDF-1.4 contenu factice', content_type='application/pdf'),
            'pieces-1-type_piece': '',
        }

    def test_le_dossier_complet_est_accepte(self):
        reponse = self.client.post(reverse('adhesions:soumettre'), self._donnees_completes())
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(DemandeAdhesion.objects.filter(email='salimata@exemple.org').exists())

    def test_chaque_champ_est_obligatoire(self):
        champs_obligatoires = ['nom', 'prenoms', 'email', 'telephone', 'grade',
                               'etablissement', 'section', 'motivation']
        for champ in champs_obligatoires:
            with self.subTest(champ=champ):
                donnees = self._donnees_completes()
                donnees[champ] = ''
                # Refaire un fichier neuf : un `SimpleUploadedFile` déjà lu par
                # la tentative précédente serait vide au second envoi.
                donnees['pieces-0-fichier'] = SimpleUploadedFile(
                    'diplome.pdf', b'%PDF-1.4 contenu factice', content_type='application/pdf')
                reponse = self.client.post(reverse('adhesions:soumettre'), donnees)
                self.assertEqual(reponse.status_code, 200)
                self.assertFalse(DemandeAdhesion.objects.filter(
                    email='salimata@exemple.org').exists())
                self.assertFalse(DemandeAdhesion.objects.exists())
