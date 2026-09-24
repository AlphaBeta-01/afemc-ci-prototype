from unittest.mock import patch

from django.test import TestCase

from apps.notifications.models import Notification
from apps.notifications.services import (ErreurEnvoi, acheminer_notifications_en_attente,
                                         creer_notification, rendre_gabarit)


def notification_test(destinataire='membre@exemple.org'):
    return creer_notification(
        destinataire=destinataire, type_notification='RELANCE_COTISATION',
        objet='Cotisation 2026', gabarit='notifications/relance.txt',
        contexte={'membre': 'KOUAME Akissi', 'exercice': 2026, 'montant_du': '25000',
                  'reste': '25000', 'echeance': '31/12/2026', 'jours': 5,
                  'section': 'Abidjan', 'niveau': 'Relance 1'})


class TestAcheminement(TestCase):

    def test_une_notification_est_envoyee_des_sa_creation(self):
        """Envoi immédiat (pas d'attente du prochain passage du cron)."""
        notification = notification_test()
        self.assertEqual(notification.statut, Notification.Statut.ENVOYEE)
        self.assertIsNotNone(notification.date_envoi)

    @patch('apps.notifications.services.envoyer_courriel',
           side_effect=ErreurEnvoi('service indisponible'))
    def test_une_notification_en_echec_reste_en_attente_pour_reessai(self, _):
        notification = notification_test()
        self.assertEqual(notification.statut, Notification.Statut.EN_ATTENTE)
        self.assertEqual(notification.tentatives, 1)

    def test_acheminement_rattrape_ce_que_l_envoi_immediat_n_a_pas_delivre(self):
        """`acheminer_notifications_en_attente` est le filet de sécurité :
        une notification déjà ENVOYEE à la création n'est pas retraitée."""
        with patch('apps.notifications.services.envoyer_courriel',
                   side_effect=ErreurEnvoi('service indisponible')):
            notification_test()          # échoue à la tentative immédiate
        envoyees, echecs = acheminer_notifications_en_attente()
        self.assertEqual((envoyees, echecs), (1, 0))
        self.assertEqual(Notification.objects.first().statut,
                         Notification.Statut.ENVOYEE)

    @patch('apps.notifications.services.envoyer_courriel',
           side_effect=ErreurEnvoi('adresse invalide'))
    def test_echec_definitif_apres_trois_tentatives(self, _):
        notification_test()              # tentative n°1 (immédiate, échoue)
        for _essai in range(2):          # tentatives n°2 et n°3
            acheminer_notifications_en_attente()
        notification = Notification.objects.first()
        self.assertEqual(notification.statut, Notification.Statut.ECHEC)
        self.assertEqual(notification.tentatives, 3)

    def test_le_budget_de_temps_est_respecte(self):
        """Un lot volumineux ne doit jamais dépasser le budget de temps
        alloué (--timeout de gunicorn en production, § 7 du README) : le
        reliquat reste EN_ATTENTE pour le passage suivant plutôt que de
        faire planter la requête en cours."""
        with patch('apps.notifications.services.envoyer_courriel',
                   side_effect=ErreurEnvoi('service indisponible')):
            notification_test('a@exemple.org')
            notification_test('b@exemple.org')
        envoyees, echecs = acheminer_notifications_en_attente(budget_secondes=-1)
        self.assertEqual((envoyees, echecs), (0, 0))
        self.assertTrue(Notification.objects.filter(
            statut=Notification.Statut.EN_ATTENTE).exists())


class TestPieceJointe(TestCase):
    """Générateur résolu dynamiquement par chemin pointillé (§ 5.6.3) —
    apps.notifications ne doit jamais importer une autre app directement."""

    def test_une_notification_sans_generateur_n_a_pas_de_piece_jointe(self):
        from django.core import mail

        notification_test()
        self.assertEqual(mail.outbox[0].attachments, [])

    def test_une_notification_avec_generateur_recoit_sa_piece_jointe(self):
        from django.core import mail

        creer_notification(
            destinataire='membre@exemple.org', type_notification='RECU_PAIEMENT',
            objet='Reçu 2026', gabarit='notifications/recu_paiement.txt',
            contexte={'membre': 'KOUAME Akissi', 'matricule': 'ABJ-2026-0001',
                     'exercice': 2026, 'montant_verse': '10000', 'mode': 'Espèces',
                     'reference': 'REC-1', 'date_paiement': '01/01/2026',
                     'montant_du': '25000', 'montant_paye_cumule': '10000',
                     'reste': '15000', 'statut': 'Partiellement payée'},
            piece_jointe_generateur='apps.cotisations.services.generer_recu_pdf')
        pieces = mail.outbox[0].attachments
        self.assertEqual(len(pieces), 1)
        self.assertEqual(pieces[0][0], 'recu_cotisation_2026.pdf')
        self.assertEqual(pieces[0][2], 'application/pdf')

    def test_un_generateur_introuvable_echoue_proprement(self):
        """Une erreur de configuration (mauvais chemin) est un échec d'envoi
        comme un autre — jamais une exception qui remonte à l'appelant."""
        notification = creer_notification(
            destinataire='membre@exemple.org', type_notification='RECU_PAIEMENT',
            objet='Reçu 2026', gabarit='notifications/recu_paiement.txt',
            contexte={}, piece_jointe_generateur='apps.cotisations.services.inexistant')
        self.assertEqual(notification.statut, Notification.Statut.EN_ATTENTE)
        self.assertEqual(notification.tentatives, 1)
        self.assertTrue(notification.derniere_erreur)


class TestRenduDuGabarit(TestCase):
    """Un courriel en texte brut ne doit pas subir l'échappement HTML."""

    def test_une_apostrophe_n_est_pas_echappee(self):
        corps = rendre_gabarit('notifications/relance.txt', {
            'membre': "KOUAME O'Neil", 'exercice': 2026, 'montant_du': '25000',
            'reste': '25000', 'echeance': '31/12/2026', 'jours': 5,
            'section': "Section d'Abidjan", 'niveau': 'Relance 1'})
        self.assertIn("Section d'Abidjan", corps)
        self.assertNotIn('&#x27;', corps)
        self.assertNotIn('&amp;', corps)


class TestCourrielHtml(TestCase):
    """Version HTML aux couleurs de l'association, en alternative au texte brut."""

    # Contexte minimal de chaque gabarit, tel que le construisent les services.
    CONTEXTES = {
        'activation': {'membre': 'KOUAME Akissi', 'lien': 'https://exemple.org/activer/'},
        'compte_responsable': {'nom': 'KOUAME Akissi', 'role': 'Trésorière', 'section': '',
                               'lien': 'https://exemple.org/activer/'},
        'reinitialisation_mot_de_passe': {'nom': 'KOUAME Akissi',
                                          'lien': 'https://exemple.org/activer/'},
        'adhesion': {'candidate': 'KOUAME Akissi', 'statut': 'Validée',
                     'section': "Section d'Abidjan", 'motif': ''},
        'nouvelle_demande': {'candidate': 'KOUAME Akissi', 'section': "Section d'Abidjan",
                             'etablissement': '', 'date_soumission': '01/09/2026'},
        'recu_paiement': {'membre': 'KOUAME Akissi', 'matricule': 'ABJ-2026-0001',
                          'exercice': 2026, 'montant_verse': '10000.00', 'mode': 'Espèces',
                          'reference': '—', 'date_paiement': '01/09/2026',
                          'montant_du': '25000.00', 'montant_paye_cumule': '10000.00',
                          'reste': '15000.00', 'statut': 'Partiellement payée'},
        'relance': {'membre': 'KOUAME Akissi', 'exercice': 2026, 'montant_du': '25000.00',
                    'reste': '25000.00', 'echeance': '31/03/2026', 'jours': 20,
                    'section': "Section d'Abidjan", 'niveau': 'Relance 1'},
        'relance_responsable': {'membre': 'KOUAME Akissi', 'exercice': 2026,
                                'montant_du': '25000.00', 'reste': '25000.00',
                                'echeance': '31/03/2026', 'jours': 95,
                                'section': "Section d'Abidjan", 'niveau': 'Alerte'},
        'synthese': {'responsable': 'KOUAME Akissi', 'exercice': 2026, 'effectif': 12,
                     'retards': 3, 'taux': '80.0', 'reste': '15000.00'},
    }

    def test_chaque_courriel_a_sa_version_html(self):
        from apps.notifications.services import rendre_gabarit_html

        for nom, contexte in self.CONTEXTES.items():
            with self.subTest(gabarit=nom):
                html = rendre_gabarit_html(f'notifications/{nom}.txt', contexte)
                self.assertIsNotNone(html)
                self.assertIn('AFEMC-CI', html)
                self.assertIn('logo-afemc-email.png', html)

    def test_le_courriel_envoye_contient_texte_et_html(self):
        from django.core import mail

        notification_test()
        message = mail.outbox[0]
        self.assertIn('Reste à régler', message.body)            # texte brut conservé
        self.assertEqual(len(message.alternatives), 1)
        html, type_mime = message.alternatives[0]
        self.assertEqual(type_mime, 'text/html')
        self.assertIn('<html lang="fr"', html)

    def test_le_logo_est_une_adresse_absolue(self):
        """Une messagerie ne peut charger qu'une image à l'adresse complète."""
        from django.conf import settings
        from apps.notifications.services import rendre_gabarit_html

        html = rendre_gabarit_html('notifications/activation.txt',
                                   self.CONTEXTES['activation'])
        self.assertIn(f'src="{settings.SITE_URL}/static/img/logo-afemc-email.png"', html)

    def test_les_saisies_sont_echappees_dans_le_html(self):
        """Nom ou motif saisis par une candidate : jamais de balise injectée."""
        from apps.notifications.services import rendre_gabarit_html

        html = rendre_gabarit_html('notifications/adhesion.txt', {
            **self.CONTEXTES['adhesion'], 'statut': 'Rejetée',
            'candidate': '<script>alert(1)</script>', 'motif': '<b>pièce</b> manquante'})
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<b>pièce</b>', html)

    def test_un_gabarit_sans_jumeau_html_part_en_texte_brut(self):
        """Ex. une règle de relance pointée dans l'admin vers un autre .txt."""
        from django.core import mail
        from apps.notifications.services import rendre_gabarit_html

        self.assertIsNone(rendre_gabarit_html('notifications/inexistant.txt', {}))
        with patch('apps.notifications.services.rendre_gabarit_html', return_value=None):
            notification_test()
        self.assertEqual(mail.outbox[0].alternatives, [])

    def test_les_montants_sont_formates_a_la_francaise(self):
        from apps.notifications.templatetags.courriel import fcfa, virgule

        self.assertEqual(fcfa('25000.00'), '25 000 FCFA')
        self.assertEqual(fcfa('1250.50'), '1 250,50 FCFA')
        self.assertEqual(fcfa('illisible'), 'illisible')
        self.assertEqual(virgule('78.4'), '78,4')
