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
