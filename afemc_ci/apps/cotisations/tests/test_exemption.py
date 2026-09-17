from django.test import TestCase
from django.urls import reverse

from apps.core.tests import fabrique
from apps.cotisations.models import Cotisation, Exemption


class TestAccorderExemption(TestCase):

    def setUp(self):
        self.membre = fabrique.membre()
        self.cotisation = fabrique.cotisation(membre_lie=self.membre, exercice=2026)

    def test_la_presidente_peut_accorder_une_exemption(self):
        presidente = fabrique.utilisateur('ADMIN')
        self.client.login(username=presidente.email, password=fabrique.MOT_DE_PASSE)
        reponse = self.client.post(
            reverse('cotisations:exempter', args=[self.membre.pk]),
            {'exercice': 2026, 'motif': 'Congé de maternité'})
        self.assertRedirects(reponse, reverse('membres:detail', args=[self.membre.pk]))
        self.assertTrue(Exemption.objects.filter(membre=self.membre, exercice=2026).exists())
        self.cotisation.refresh_from_db()
        self.assertEqual(self.cotisation.statut, Cotisation.Statut.EXEMPTEE)

    def test_la_tresoriere_peut_accorder_une_exemption(self):
        tresoriere = fabrique.utilisateur('RESP_FINANCIER')
        self.client.login(username=tresoriere.email, password=fabrique.MOT_DE_PASSE)
        reponse = self.client.post(
            reverse('cotisations:exempter', args=[self.membre.pk]),
            {'exercice': 2026, 'motif': 'Membre fondatrice honoraire'})
        self.assertEqual(reponse.status_code, 302)
        self.assertTrue(Exemption.objects.filter(membre=self.membre, exercice=2026).exists())

    def test_refuse_a_la_secretaire_generale(self):
        secretaire = fabrique.utilisateur('RESP_ADMIN')
        self.client.login(username=secretaire.email, password=fabrique.MOT_DE_PASSE)
        reponse = self.client.post(
            reverse('cotisations:exempter', args=[self.membre.pk]),
            {'exercice': 2026, 'motif': 'Tentative non autorisée'})
        self.assertEqual(reponse.status_code, 403)
        self.assertFalse(Exemption.objects.filter(membre=self.membre, exercice=2026).exists())

    def test_refuse_a_la_coordinatrice_de_section(self):
        coordinatrice = fabrique.utilisateur('RESP_SECTION', section_liee=self.membre.section)
        self.client.login(username=coordinatrice.email, password=fabrique.MOT_DE_PASSE)
        reponse = self.client.get(reverse('cotisations:exempter', args=[self.membre.pk]))
        self.assertEqual(reponse.status_code, 403)
