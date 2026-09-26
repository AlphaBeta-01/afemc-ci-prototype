"""« À faire » : tâches du jour selon la fonction de l'utilisatrice connectée."""
from datetime import date, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.adhesions.models import DemandeAdhesion
from apps.core.tests import fabrique
from apps.cotisations.models import Cotisation
from apps.dashboard.taches import A_FAIRE, A_SURVEILLER, URGENT, taches_pour
from apps.membres.models import Membre
from apps.notifications.models import Notification

AUJOURDHUI = date.today()


def titres(utilisateur):
    return {t.titre: t for t in taches_pour(utilisateur)}


class BaseAFaire(TestCase):

    def setUp(self):
        call_command('charger_regles', verbosity=0)
        self.abidjan = fabrique.section('ABJ', "Section d'Abidjan")
        self.korhogo = fabrique.section('KRG', 'Section de Korhogo')
        self.presidente = fabrique.utilisateur('ADMIN')
        self.secretaire = fabrique.utilisateur('RESP_ADMIN')
        self.tresoriere = fabrique.utilisateur('RESP_FINANCIER')
        self.coordinatrice = fabrique.utilisateur('RESP_SECTION', email='coord@afemc-ci.org',
                                                  section_liee=self.abidjan)
        fabrique.utilisateur('RESP_SECTION', email='coord.krg@afemc-ci.org',
                             section_liee=self.korhogo)

    def cotisation(self, membre, jours_de_retard, paye='0'):
        return fabrique.cotisation(membre_lie=membre, exercice=AUJOURDHUI.year, paye=paye,
                                   jours_ecart=jours_de_retard,
                                   statut=Cotisation.Statut.EN_RETARD if jours_de_retard > 0
                                   and paye == '0' else None)

    def demande(self, nom='KONE', il_y_a_jours=0):
        demande = DemandeAdhesion.objects.create(
            nom=nom, prenoms='Aminata', email=f'{nom.lower()}@exemple.org',
            telephone='0102030405', grade='Assistante', section=self.abidjan,
            motivation='Adhérer.')
        DemandeAdhesion.objects.filter(pk=demande.pk).update(
            date_soumission=timezone.now() - timedelta(days=il_y_a_jours))
        return demande


class TestPresidente(BaseAFaire):

    def test_fonction_de_tresoriere_vacante_est_urgente(self):
        self.tresoriere.is_active = False
        self.tresoriere.save()
        tache = titres(self.presidente)['Aucune Trésorière en fonction']
        self.assertEqual(tache.priorite, URGENT)
        self.assertEqual(tache.url, reverse('accounts:nommer'))

    def test_section_sans_coordinatrice(self):
        fabrique.section('BKE', 'Section de Bouaké')
        tache = titres(self.presidente)['Sections sans Coordinatrice']
        self.assertEqual([e.nom for e in tache.elements], ['Section de Bouaké'])

    def test_courriels_en_echec(self):
        Notification.objects.create(destinataire='x@exemple.org', type='TEST', objet='o',
                                    gabarit='notifications/relance.txt',
                                    statut=Notification.Statut.ECHEC, tentatives=3)
        self.assertEqual(titres(self.presidente)['Courriels non distribués'].nombre, 1)

    def test_rien_a_faire(self):
        self.assertEqual(taches_pour(self.presidente), [])


class TestSecretaireGenerale(BaseAFaire):

    def test_demandes_a_traiter_urgentes_au_dela_de_sept_jours(self):
        self.demande('KONE', il_y_a_jours=1)
        self.assertEqual(titres(self.secretaire)["Demandes d'adhésion à traiter"].priorite,
                         A_FAIRE)
        self.demande('BAMBA', il_y_a_jours=10)
        tache = titres(self.secretaire)["Demandes d'adhésion à traiter"]
        self.assertEqual(tache.priorite, URGENT)
        self.assertEqual([e.nom for e in tache.elements], ['BAMBA', 'KONE'])   # A → Z

    def test_ne_voit_pas_les_taches_financieres(self):
        self.cotisation(fabrique.membre(sect=self.abidjan), jours_de_retard=100)
        self.assertNotIn('Retards de plus de 90 jours', titres(self.secretaire))


class TestTresoriere(BaseAFaire):

    def test_niveaux_de_retard_et_suivi(self):
        self.cotisation(fabrique.membre(nom='AKA', sect=self.abidjan), jours_de_retard=100)
        self.cotisation(fabrique.membre(nom='YAO', sect=self.abidjan), jours_de_retard=50)
        self.cotisation(fabrique.membre(nom='KOFFI', sect=self.abidjan), jours_de_retard=-5)
        partiel = fabrique.membre(nom='DIALLO', sect=self.abidjan)
        Cotisation.objects.create(membre=partiel, exercice=AUJOURDHUI.year - 1,
                                  montant_du=Decimal('25000'), montant_paye=Decimal('10000'),
                                  date_echeance=AUJOURDHUI + timedelta(days=60),
                                  statut=Cotisation.Statut.PARTIEL)
        taches = titres(self.tresoriere)
        self.assertEqual(taches['Retards de plus de 90 jours'].priorite, URGENT)
        self.assertEqual(taches['Retards de 45 à 90 jours'].elements[0].nom, 'YAO')
        self.assertEqual(taches['Paiements partiels à solder'].priorite, A_SURVEILLER)
        self.assertIn('Échéances dans les 15 prochains jours', taches)
        self.assertIn(f'Cotisations {AUJOURDHUI.year} à émettre', taches)   # DIALLO

    def test_les_plus_urgentes_d_abord(self):
        self.cotisation(fabrique.membre(sect=self.abidjan), jours_de_retard=100)
        fabrique.membre(sect=self.abidjan)                      # sans cotisation
        priorites = [t.priorite for t in taches_pour(self.tresoriere)]
        self.assertEqual(priorites, sorted(priorites, key=[URGENT, A_FAIRE, A_SURVEILLER].index))


class TestCoordinatrice(BaseAFaire):

    def test_membres_en_retard_de_sa_section_seule(self):
        self.cotisation(fabrique.membre(nom='KOFFI', sect=self.abidjan), jours_de_retard=20)
        self.cotisation(fabrique.membre(nom='BAMBA', sect=self.korhogo), jours_de_retard=20)
        tache = titres(self.coordinatrice)['Membres de votre section à contacter']
        self.assertEqual([e.nom for e in tache.elements], ['KOFFI'])      # sa section seule
        self.assertIn('reste', tache.elements[0].detail)
        self.assertTrue(tache.url.startswith(reverse('cotisations:liste')))  # lecture seule

        self.client.force_login(self.coordinatrice)
        page = self.client.get(reverse('dashboard:a_faire'))
        self.assertContains(page, 'KOFFI')
        self.assertNotContains(page, 'BAMBA')

    def test_pas_de_contact_avant_le_seuil_de_la_relance_r04(self):
        self.cotisation(fabrique.membre(nom='KOFFI', sect=self.abidjan), jours_de_retard=5)
        self.assertNotIn('Membres de votre section à contacter', titres(self.coordinatrice))

    def test_fiches_a_completer(self):
        membre = fabrique.membre(nom='KOFFI', sect=self.abidjan)
        Membre.objects.filter(pk=membre.pk).update(telephone='')
        tache = titres(self.coordinatrice)['Fiches à compléter']
        self.assertEqual(tache.elements[0].url, reverse('membres:modifier', args=[membre.pk]))
        self.assertIn('téléphone', tache.elements[0].detail)


class TestMembre(BaseAFaire):

    def setUp(self):
        super().setUp()
        self.fiche = fabrique.membre(nom='KOFFI', sect=self.abidjan, email='koffi@exemple.org')
        self.compte = fabrique.utilisateur('MEMBRE', email='koffi@exemple.org')
        self.fiche.utilisateur = self.compte
        self.fiche.save()

    def test_cotisation_en_retard_urgente(self):
        self.cotisation(self.fiche, jours_de_retard=10)
        tache = titres(self.compte)[f'Votre cotisation {AUJOURDHUI.year}']
        self.assertEqual(tache.priorite, URGENT)
        self.assertIn('25 000', tache.explication)

    def test_membre_a_jour(self):
        self.cotisation(self.fiche, jours_de_retard=10, paye='25000')
        Cotisation.objects.update(statut=Cotisation.Statut.PAYEE)
        self.client.force_login(self.compte)
        self.assertContains(self.client.get(reverse('dashboard:a_faire')), 'Tout est à jour')


class TestAccesEtBouton(BaseAFaire):

    def peupler(self):
        for jours in (100, 50, 20, -5):
            self.cotisation(fabrique.membre(sect=self.abidjan), jours_de_retard=jours)
        fabrique.membre(sect=self.abidjan)
        incomplete = fabrique.membre(sect=self.abidjan)
        Membre.objects.filter(pk=incomplete.pk).update(grade='')
        self.demande('KONE', il_y_a_jours=10)
        fabrique.section('BKE', 'Section de Bouaké')

    def test_chaque_lien_propose_est_autorise_pour_la_fonction(self):
        """Une tâche qui mènerait à « Accès refusé » serait pire qu'aucune tâche."""
        self.peupler()
        for compte in (self.presidente, self.secretaire, self.tresoriere, self.coordinatrice):
            self.client.force_login(compte)
            taches = taches_pour(compte)
            self.assertTrue(taches, compte.role)
            urls = {t.url for t in taches if t.url} | {
                e.url for t in taches for e in t.elements if e.url}
            for url in urls:
                with self.subTest(role=compte.role, url=url):
                    self.assertEqual(self.client.get(url).status_code, 200)

    def test_bouton_et_compteur_dans_la_barre_de_navigation(self):
        self.peupler()
        self.client.force_login(self.tresoriere)
        reponse = self.client.get(reverse('dashboard:accueil'))
        self.assertContains(reponse, reverse('dashboard:a_faire'))
        self.assertEqual(reponse.context['a_faire'].nombre, 3)       # hors « À surveiller »
        self.assertTrue(reponse.context['a_faire'].urgent)
        self.assertContains(reponse, 'text-bg-danger')

    def test_page_reservee_aux_personnes_connectees(self):
        reponse = self.client.get(reverse('dashboard:a_faire'))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn(reverse('accounts:connexion'), reponse.url)
