from django.test import TestCase
from django.urls import reverse

from apps.core.models import JournalOperation
from apps.core.tests import fabrique

from ..models import Notification


def notification_en_echec(**kwargs):
    defaut = dict(destinataire='membre@exemple.org', type='RELANCE_COTISATION',
                  objet='Cotisation 2026', gabarit='notifications/relance.txt',
                  contexte={}, statut=Notification.Statut.ECHEC, tentatives=3,
                  derniere_erreur='adresse invalide')
    defaut.update(kwargs)
    return Notification.objects.create(**defaut)


class TestAccesEcranNotifications(TestCase):

    def setUp(self):
        self.admin = fabrique.utilisateur('ADMIN')
        self.financier = fabrique.utilisateur('RESP_FINANCIER')

    def test_liste_accessible_a_l_administrateur(self):
        self.client.login(username=self.admin.email, password=fabrique.MOT_DE_PASSE)
        reponse = self.client.get(reverse('notifications:liste'))
        self.assertEqual(reponse.status_code, 200)

    def test_liste_refusee_a_un_autre_role(self):
        self.client.login(username=self.financier.email, password=fabrique.MOT_DE_PASSE)
        reponse = self.client.get(reverse('notifications:liste'))
        self.assertEqual(reponse.status_code, 403)

    def test_liste_refusee_sans_authentification(self):
        reponse = self.client.get(reverse('notifications:liste'))
        self.assertEqual(reponse.status_code, 302)

    def test_filtre_par_statut(self):
        notification_en_echec()
        Notification.objects.create(
            destinataire='a@exemple.org', type='ACTIVATION_COMPTE', objet='Activation',
            gabarit='notifications/activation.txt', contexte={},
            statut=Notification.Statut.ENVOYEE)
        self.client.login(username=self.admin.email, password=fabrique.MOT_DE_PASSE)
        reponse = self.client.get(reverse('notifications:liste'), {'statut': 'ECHEC'})
        self.assertEqual(len(reponse.context['page']), 1)


class TestRenvoiNotification(TestCase):

    def setUp(self):
        self.admin = fabrique.utilisateur('ADMIN')
        self.financier = fabrique.utilisateur('RESP_FINANCIER')

    def test_remet_une_notification_en_echec_dans_la_file(self):
        notification = notification_en_echec()
        self.client.login(username=self.admin.email, password=fabrique.MOT_DE_PASSE)
        self.client.post(reverse('notifications:renvoyer', args=[notification.pk]))

        notification.refresh_from_db()
        self.assertEqual(notification.statut, Notification.Statut.EN_ATTENTE)
        self.assertEqual(notification.tentatives, 0)
        self.assertEqual(notification.derniere_erreur, '')
        self.assertTrue(JournalOperation.objects
                        .filter(type_operation='NOTIFICATION_REMISE_EN_FILE').exists())

    def test_sans_effet_sur_une_notification_deja_envoyee(self):
        notification = notification_en_echec(statut=Notification.Statut.ENVOYEE, tentatives=1)
        self.client.login(username=self.admin.email, password=fabrique.MOT_DE_PASSE)
        self.client.post(reverse('notifications:renvoyer', args=[notification.pk]))

        notification.refresh_from_db()
        self.assertEqual(notification.statut, Notification.Statut.ENVOYEE)
        self.assertEqual(notification.tentatives, 1)

    def test_refuse_a_un_role_non_habilite(self):
        notification = notification_en_echec()
        self.client.login(username=self.financier.email, password=fabrique.MOT_DE_PASSE)
        reponse = self.client.post(reverse('notifications:renvoyer', args=[notification.pk]))
        self.assertEqual(reponse.status_code, 403)
        notification.refresh_from_db()
        self.assertEqual(notification.statut, Notification.Statut.ECHEC)

    def test_refuse_en_methode_get(self):
        notification = notification_en_echec()
        self.client.login(username=self.admin.email, password=fabrique.MOT_DE_PASSE)
        reponse = self.client.get(reverse('notifications:renvoyer', args=[notification.pk]))
        self.assertEqual(reponse.status_code, 405)
