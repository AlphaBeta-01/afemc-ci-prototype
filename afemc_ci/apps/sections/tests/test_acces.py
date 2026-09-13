from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Utilisateur
from apps.membres.models import Membre
from apps.sections.models import Section


class TestAccesDetailSection(TestCase):
    """Le détail d'une section (indicateurs financiers, registre) n'est pas
    ouvert à un simple membre (revue de sécurité, RG08)."""

    def setUp(self):
        self.section = Section.objects.create(code='ABJ', libelle='Abidjan')

    def test_un_membre_ne_voit_pas_le_detail_de_sa_section(self):
        membre = Membre.objects.create(nom='YAO', prenoms='Adjoua',
                                       email='yao@exemple.org', section=self.section)
        compte = Utilisateur.objects.create_user(
            email='yao@exemple.org', password='MotDePasse2026!', nom='YAO',
            prenoms='Adjoua', role=Utilisateur.Role.MEMBRE, section=self.section)
        membre.utilisateur = compte
        membre.save(update_fields=['utilisateur'])

        self.client.force_login(compte)
        reponse = self.client.get(reverse('sections:detail', args=[self.section.pk]))
        self.assertEqual(reponse.status_code, 403)

    def test_le_bouton_detail_est_masque_pour_un_membre(self):
        compte = Utilisateur.objects.create_user(
            email='membre@exemple.org', password='MotDePasse2026!', nom='YAO',
            prenoms='Adjoua', role=Utilisateur.Role.MEMBRE, section=self.section)
        self.client.force_login(compte)
        reponse = self.client.get(reverse('sections:liste'))
        self.assertNotContains(reponse, reverse('sections:detail', args=[self.section.pk]))

    def test_un_responsable_de_section_voit_toujours_le_detail(self):
        compte = Utilisateur.objects.create_user(
            email='rs@afemc-ci.org', password='MotDePasse2026!', nom='TRAORE',
            prenoms='Mariam', role=Utilisateur.Role.RESP_SECTION, section=self.section)
        self.client.force_login(compte)
        reponse = self.client.get(reverse('sections:detail', args=[self.section.pk]))
        self.assertEqual(reponse.status_code, 200)
