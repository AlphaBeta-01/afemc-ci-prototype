from django.db.models import ProtectedError
from django.test import TestCase

from apps.accounts.models import Utilisateur
from apps.membres.models import Membre
from apps.sections.models import Section


class TestMembre(TestCase):

    def setUp(self):
        self.abidjan = Section.objects.create(code='ABJ', libelle='Abidjan')
        self.korhogo = Section.objects.create(code='KRG', libelle='Korhogo')

    def creer(self, nom='KOUAME', section=None, email=None):
        section = section or self.abidjan
        return Membre.objects.create(
            nom=nom, prenoms='Akissi', email=email or f'{nom.lower()}@exemple.org',
            section=section)

    def test_le_matricule_est_genere_automatiquement(self):
        membre = self.creer()
        self.assertTrue(membre.matricule.startswith('ABJ-'))
        self.assertTrue(membre.matricule.endswith('0001'))

    def test_les_matricules_sont_incrementes(self):
        premier = self.creer(nom='KOUAME')
        second = self.creer(nom='YAO')
        self.assertNotEqual(premier.matricule, second.matricule)
        self.assertTrue(second.matricule.endswith('0002'))

    def test_le_matricule_porte_le_code_de_la_section(self):
        membre = self.creer(nom='BAMBA', section=self.korhogo)
        self.assertTrue(membre.matricule.startswith('KRG-'))

    def test_une_section_peuplee_ne_peut_etre_supprimee(self):
        self.creer()
        with self.assertRaises(ProtectedError):
            self.abidjan.delete()

    def test_cloisonnement_par_section(self):
        self.creer(nom='KOUAME', section=self.abidjan)
        self.creer(nom='BAMBA', section=self.korhogo)
        responsable = Utilisateur.objects.create_user(
            email='rs@afemc-ci.org', password='MotDePasse2026!', nom='TRAORE',
            prenoms='Mariam', role=Utilisateur.Role.RESP_SECTION, section=self.korhogo)
        visibles = Membre.objects.visibles_par(responsable)
        self.assertEqual(visibles.count(), 1)
        self.assertEqual(visibles.first().section, self.korhogo)

    def test_un_responsable_administratif_voit_tous_les_membres(self):
        self.creer(nom='KOUAME', section=self.abidjan)
        self.creer(nom='BAMBA', section=self.korhogo)
        responsable = Utilisateur.objects.create_user(
            email='ra@afemc-ci.org', password='MotDePasse2026!', nom='KONE',
            prenoms='Aya', role=Utilisateur.Role.RESP_ADMIN)
        self.assertEqual(Membre.objects.visibles_par(responsable).count(), 2)

    def test_effectif_actif_d_une_section(self):
        self.creer(nom='KOUAME')
        inactif = self.creer(nom='YAO')
        inactif.statut = Membre.Statut.INACTIF
        inactif.save()
        self.assertEqual(self.abidjan.effectif_actif(), 1)
