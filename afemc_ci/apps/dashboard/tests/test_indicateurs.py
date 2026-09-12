"""Contrôle de cohérence des indicateurs (test TI12, § 6.3)."""
from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Utilisateur
from apps.cotisations.models import Cotisation
from apps.dashboard.services import indicateurs_globaux
from apps.membres.models import Membre
from apps.sections.models import Section


class TestCoherenceIndicateurs(TestCase):

    def setUp(self):
        self.section = Section.objects.create(code='ABJ', libelle='Abidjan')
        for i in range(10):
            membre = Membre.objects.create(
                nom=f'NOM{i}', prenoms='Aya', email=f'm{i}@exemple.org',
                section=self.section)
            Cotisation.objects.create(
                membre=membre, exercice=2026, montant_du=Decimal('25000'),
                montant_paye=Decimal('25000') if i < 6 else Decimal('0'),
                statut=Cotisation.Statut.PAYEE if i < 6 else Cotisation.Statut.EN_ATTENTE,
                date_echeance=date(2026, 12, 31))

    def test_les_totaux_correspondent_au_calcul_direct(self):
        indicateurs = indicateurs_globaux(2026)
        direct = Cotisation.objects.filter(exercice=2026).aggregate(
            du=Sum('montant_du'), paye=Sum('montant_paye'))
        self.assertEqual(indicateurs['total_du'], direct['du'])
        self.assertEqual(indicateurs['total_paye'], direct['paye'])

    def test_taux_de_recouvrement(self):
        indicateurs = indicateurs_globaux(2026)
        self.assertEqual(round(indicateurs['taux_recouvrement']), 60)

    def test_effectif_total(self):
        self.assertEqual(indicateurs_globaux(2026)['effectif_total'], 10)

    def test_exercice_sans_donnees_ne_provoque_pas_d_erreur(self):
        indicateurs = indicateurs_globaux(2019)
        self.assertEqual(indicateurs['total_du'], Decimal('0'))
        self.assertEqual(indicateurs['taux_recouvrement'], Decimal('0'))


class TestAccesTableauDeBord(TestCase):
    """Le tableau de bord décisionnel est réservé aux responsables (RG08)."""

    def setUp(self):
        self.section = Section.objects.create(code='COC', libelle='Cocody')

    def test_un_responsable_voit_le_tableau_de_bord(self):
        responsable = Utilisateur.objects.create_user(
            email='resp@afemc-ci.org', password='MotDePasse2026!',
            nom='KOFFI', prenoms='Awa', role=Utilisateur.Role.RESP_ADMIN)
        self.client.force_login(responsable)
        reponse = self.client.get(reverse('dashboard:accueil'))
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('indicateurs', reponse.context)

    def test_un_membre_est_redirige_vers_sa_propre_fiche(self):
        membre = Membre.objects.create(nom='YAO', prenoms='Adjoua',
                                       email='yao@exemple.org', section=self.section)
        compte = Utilisateur.objects.create_user(
            email='yao@exemple.org', password='MotDePasse2026!', nom='YAO',
            prenoms='Adjoua', role=Utilisateur.Role.MEMBRE, section=self.section)
        membre.utilisateur = compte
        membre.save(update_fields=['utilisateur'])

        self.client.force_login(compte)
        reponse = self.client.get(reverse('dashboard:accueil'))
        self.assertRedirects(reponse, reverse('membres:detail', args=[membre.pk]))

    def test_un_membre_sans_fiche_associee_voit_une_page_minimale(self):
        compte = Utilisateur.objects.create_user(
            email='orphelin@exemple.org', password='MotDePasse2026!',
            nom='TRAORE', prenoms='Mariam', role=Utilisateur.Role.MEMBRE)
        self.client.force_login(compte)
        reponse = self.client.get(reverse('dashboard:accueil'))
        self.assertEqual(reponse.status_code, 200)
        self.assertNotIn('indicateurs', reponse.context)

    def test_le_responsable_financier_ne_voit_pas_les_adhesions(self):
        financier = Utilisateur.objects.create_user(
            email='financier@afemc-ci.org', password='MotDePasse2026!',
            nom='TRAORE', prenoms='Mariam', role=Utilisateur.Role.RESP_FINANCIER)
        self.client.force_login(financier)
        reponse = self.client.get(reverse('dashboard:accueil'))
        self.assertNotContains(reponse, 'Demandes en attente')
        self.assertNotContains(reponse, "Demandes d'adhésion à traiter")

    def test_le_responsable_administratif_voit_les_adhesions(self):
        administratif = Utilisateur.objects.create_user(
            email='administratif@afemc-ci.org', password='MotDePasse2026!',
            nom='KONE', prenoms='Aya', role=Utilisateur.Role.RESP_ADMIN)
        self.client.force_login(administratif)
        reponse = self.client.get(reverse('dashboard:accueil'))
        self.assertContains(reponse, 'Demandes en attente')
        self.assertContains(reponse, "Demandes d'adhésion à traiter")

    def test_le_responsable_de_section_a_un_tableau_de_bord_dedie(self):
        autre_section = Section.objects.create(code='KRG', libelle='Korhogo')
        Membre.objects.create(nom='YAO', prenoms='Adjoua', email='yao@exemple.org',
                              section=self.section)
        Membre.objects.create(nom='BAMBA', prenoms='Fatou', email='bamba@exemple.org',
                              section=autre_section)          # hors périmètre
        responsable = Utilisateur.objects.create_user(
            email='rs@afemc-ci.org', password='MotDePasse2026!', nom='TRAORE',
            prenoms='Mariam', role=Utilisateur.Role.RESP_SECTION, section=self.section)

        self.client.force_login(responsable)
        reponse = self.client.get(reverse('dashboard:accueil'))
        self.assertEqual(reponse.status_code, 200)
        self.assertTemplateUsed(reponse, 'dashboard/section.html')
        self.assertEqual(reponse.context['effectif_actif'], 1)
        self.assertNotIn('indicateurs', reponse.context)
        self.assertNotContains(reponse, 'Cotisations en retard')
        self.assertNotContains(reponse, "Demandes d'adhésion")

    def test_le_responsable_de_section_sans_section_voit_un_message(self):
        responsable = Utilisateur.objects.create_user(
            email='rs.orphelin@afemc-ci.org', password='MotDePasse2026!',
            nom='TRAORE', prenoms='Mariam', role=Utilisateur.Role.RESP_SECTION)
        self.client.force_login(responsable)
        reponse = self.client.get(reverse('dashboard:accueil'))
        self.assertEqual(reponse.status_code, 200)
        self.assertTemplateUsed(reponse, 'dashboard/aucun_acces.html')
