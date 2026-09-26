"""Listes triées de A à Z, noms et prénoms affichés séparément.

Les noms sont volontairement saisis avec une casse mélangée, comme en
production (« Bamba », « KOUAME », « n'Dri ») : un tri brut placerait toutes
les capitales avant les minuscules.
"""
from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.adhesions.models import DemandeAdhesion
from apps.core.tests import fabrique
from apps.core.utils import cle_alphabetique, trier_par_nom
from apps.cotisations.models import Cotisation

NOMS_DESORDONNES = ['zadi', 'KOUAME', 'Bamba', 'aka', 'Yao']
ORDRE_ATTENDU = ['aka', 'Bamba', 'KOUAME', 'Yao', 'zadi']


def ordre_des_noms(objets, personne=lambda o: o):
    return [personne(o).nom for o in objets]


class TestTriAlphabetique(TestCase):

    def setUp(self):
        self.section = fabrique.section()
        self.presidente = fabrique.utilisateur('ADMIN')
        self.tresoriere = fabrique.utilisateur('RESP_FINANCIER')
        self.membres = [fabrique.membre(nom=nom, sect=self.section)
                        for nom in NOMS_DESORDONNES]
        for membre in self.membres:
            fabrique.cotisation(membre_lie=membre, exercice=date.today().year)

    def test_liste_des_membres(self):
        self.client.force_login(self.presidente)
        page = self.client.get(reverse('membres:liste')).context['page']
        self.assertEqual(ordre_des_noms(page), ORDRE_ATTENDU)

    def test_meme_nom_departage_par_les_prenoms(self):
        from apps.membres.models import Membre
        Membre.objects.filter(pk=self.membres[1].pk).update(prenoms='Yasmine')
        doublon = fabrique.membre(nom='Kouame', sect=self.section)
        Membre.objects.filter(pk=doublon.pk).update(prenoms='adjoua')

        self.client.force_login(self.presidente)
        page = self.client.get(reverse('membres:liste')).context['page']
        kouame = [m.prenoms for m in page if m.nom.lower() == 'kouame']
        self.assertEqual(kouame, ['adjoua', 'Yasmine'])

    def test_liste_des_cotisations_et_export(self):
        self.client.force_login(self.tresoriere)
        page = self.client.get(reverse('cotisations:liste')).context['page']
        self.assertEqual(ordre_des_noms(page, lambda c: c.membre), ORDRE_ATTENDU)

        export = self.client.get(reverse('cotisations:export')).content.decode()
        noms_exportes = [ligne.split(';')[1] for ligne in export.strip().splitlines()[1:]]
        self.assertEqual(noms_exportes, ORDRE_ATTENDU)

    def test_liste_des_demandes_d_adhesion(self):
        for nom in NOMS_DESORDONNES:
            DemandeAdhesion.objects.create(
                nom=nom, prenoms='Awa', email=f'{nom.lower()}@exemple.org',
                telephone='0102030405', grade='Assistante', section=self.section,
                motivation='Adhérer.')
        self.client.force_login(self.presidente)
        page = self.client.get(reverse('adhesions:liste')).context['page']
        self.assertEqual(ordre_des_noms(page), ORDRE_ATTENDU)

    def test_historique_des_relances(self):
        from django.core.management import call_command
        from apps.relances.services import executer_detection

        call_command('charger_regles', verbosity=0)
        Cotisation.objects.update(date_echeance=date(2020, 1, 1))
        executer_detection()
        self.client.force_login(self.presidente)
        page = self.client.get(reverse('relances:liste')).context['page']
        self.assertEqual(ordre_des_noms(page, lambda r: r.cotisation.membre), ORDRE_ATTENDU)

    def test_liste_des_responsables(self):
        for nom in NOMS_DESORDONNES:
            compte = fabrique.utilisateur('RESP_ADMIN', email=f'{nom.lower()}@afemc-ci.org')
            compte.nom = nom
            compte.save()
        self.client.force_login(self.presidente)
        comptes = self.client.get(reverse('accounts:comptes_liste')).context['comptes']
        noms = [c.nom for c in comptes if c.nom in NOMS_DESORDONNES]
        self.assertEqual(noms, ORDRE_ATTENDU)

    def test_nom_et_prenoms_dans_des_colonnes_separees(self):
        self.client.force_login(self.presidente)
        for url in (reverse('membres:liste'), reverse('accounts:comptes_liste')):
            with self.subTest(url=url):
                reponse = self.client.get(url)
                self.assertContains(reponse, '<th>Nom</th><th>Prénoms</th>', html=False)
                self.assertNotContains(reponse, 'Nom et prénoms')

    def test_encadres_du_tableau_de_bord_affiches_de_a_a_z(self):
        """Sélection par urgence (retards les plus anciens), affichage A → Z."""
        Cotisation.objects.update(statut=Cotisation.Statut.EN_RETARD,
                                  date_echeance=date(2020, 1, 1))
        self.client.force_login(self.presidente)
        retards = self.client.get(reverse('dashboard:accueil')).context['retards']
        self.assertEqual(ordre_des_noms(retards, lambda c: c.membre), ORDRE_ATTENDU)

    def test_ecrans_d_administration(self):
        from apps.relances.models import Relance  # noqa: F401  (liste vide acceptée)
        self.client.force_login(self.presidente)
        self.presidente.is_staff = True
        self.presidente.is_superuser = True
        self.presidente.save()
        for modele in ('membres/membre', 'cotisations/cotisation', 'cotisations/paiement',
                       'relances/relance', 'adhesions/demandeadhesion',
                       'accounts/utilisateur'):
            with self.subTest(modele=modele):
                self.assertEqual(self.client.get(f'/admin/{modele}/').status_code, 200)


class TestCleAlphabetique(TestCase):

    def test_insensible_a_la_casse_et_aux_accents(self):
        self.assertEqual(cle_alphabetique('Émilie'), cle_alphabetique('emilie'))
        self.assertLess(cle_alphabetique('Édith'), cle_alphabetique('Fanta'))

    def test_trier_par_nom(self):
        class Personne:
            def __init__(self, nom, prenoms):
                self.nom, self.prenoms = nom, prenoms
        personnes = [Personne('Ouattara', 'b'), Personne('ÉHOUMAN', 'a'),
                     Personne('ouattara', 'A'), Personne('Diallo', 'z')]
        tries = [(p.nom, p.prenoms) for p in trier_par_nom(personnes)]
        self.assertEqual(tries, [('Diallo', 'z'), ('ÉHOUMAN', 'a'),
                                 ('ouattara', 'A'), ('Ouattara', 'b')])
