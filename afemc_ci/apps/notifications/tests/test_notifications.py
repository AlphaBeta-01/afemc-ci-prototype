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

    def test_une_notification_est_creee_en_attente(self):
        notification = notification_test()
        self.assertEqual(notification.statut, Notification.Statut.EN_ATTENTE)

    def test_acheminement_reussi(self):
        notification_test()
        envoyees, echecs = acheminer_notifications_en_attente()
        self.assertEqual((envoyees, echecs), (1, 0))
        self.assertEqual(Notification.objects.first().statut,
                         Notification.Statut.ENVOYEE)

    @patch('apps.notifications.services.envoyer_courriel',
           side_effect=ErreurEnvoi('service indisponible'))
    def test_les_messages_ne_sont_pas_perdus_en_cas_de_panne(self, _):
        notification_test()
        acheminer_notifications_en_attente()
        notification = Notification.objects.first()
        self.assertEqual(notification.statut, Notification.Statut.EN_ATTENTE)
        self.assertEqual(notification.tentatives, 1)

    @patch('apps.notifications.services.envoyer_courriel',
           side_effect=ErreurEnvoi('adresse invalide'))
    def test_echec_definitif_apres_trois_tentatives(self, _):
        notification_test()
        for _essai in range(3):
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
