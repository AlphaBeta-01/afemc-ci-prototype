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
