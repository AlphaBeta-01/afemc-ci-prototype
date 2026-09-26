"""Activités, comités d'organisation et inscriptions (RG14)."""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.services import nommer_responsable
from apps.activites.models import Activite, Inscription, MembreComite
from apps.core.models import JournalOperation
from apps.core.tests import fabrique
from apps.notifications.models import Notification

S = Activite.Statut


def compte_membre(nom, section, role='MEMBRE'):
    """Une membre du registre avec son compte relié (et éventuellement une fonction)."""
    fiche = fabrique.membre(nom=nom, sect=section, email=f'{nom.lower()}@exemple.org')
    compte = fabrique.utilisateur('MEMBRE', email=fiche.email)
    fiche.utilisateur = compte
    fiche.save()
    if role != 'MEMBRE':
        nommer_responsable(fiche, role)
        compte.refresh_from_db()
    return fiche, compte


class BaseActivites(TestCase):

    def setUp(self):
        self.abidjan = fabrique.section('ABJ', "Section d'Abidjan")
        self.korhogo = fabrique.section('KRG', 'Section de Korhogo')
        self.presidente = fabrique.utilisateur('ADMIN')
        _, self.organisatrice = compte_membre('ORGA', self.abidjan, role='RESP_ORGA')
        self.fiche_comite, self.comite = compte_membre('COMITE', self.abidjan)
        self.fiche_abj, self.membre_abj = compte_membre('KOUAME', self.abidjan)
        self.fiche_krg, self.membre_krg = compte_membre('BAMBA', self.korhogo)

    def activite(self, statut=S.PUBLIEE, section=None, dans_jours=10, places=None, titre='Journée'):
        return Activite.objects.create(
            titre=titre, type=Activite.Type.JOURNEE_SCIENTIFIQUE, lieu='UFHB, Cocody',
            date_debut=timezone.now() + timedelta(days=dans_jours), section=section,
            places=places, statut=statut)

    def donnees_fiche(self, **extra):
        debut = timezone.localtime(timezone.now() + timedelta(days=20))
        return {'titre': 'Colloque', 'type': 'CONFERENCE', 'lieu': 'UVCI',
                'date_debut': debut.strftime('%Y-%m-%dT%H:%M'), 'date_fin': '', 'section': '',
                'places': '', 'description': 'Programme.', **extra}


class TestFonctionResponsableOrganisation(BaseActivites):

    def test_nommee_par_la_presidente_comme_les_autres_fonctions(self):
        self.assertEqual(self.organisatrice.role, 'RESP_ORGA')
        self.assertEqual(self.organisatrice.get_role_display(), "Responsable à l'organisation")

    def test_moindre_privilege(self):
        """Activités oui ; ni membres, ni cotisations, ni adhésions, ni tableau de bord."""
        self.client.force_login(self.organisatrice)
        self.assertRedirects(self.client.get(reverse('dashboard:accueil')),
                             reverse('activites:liste'))
        for nom_url in ('membres:liste', 'cotisations:liste', 'adhesions:liste',
                        'relances:liste', 'accounts:comptes_liste'):
            with self.subTest(url=nom_url):
                self.assertEqual(self.client.get(reverse(nom_url)).status_code, 403)
        menu = self.client.get(reverse('activites:liste'))
        self.assertContains(menu, reverse('activites:creer'))
        self.assertNotContains(menu, reverse('cotisations:liste'))


class TestGestion(BaseActivites):

    def test_creer_une_activite_en_preparation(self):
        self.client.force_login(self.organisatrice)
        reponse = self.client.post(reverse('activites:creer'), self.donnees_fiche())
        activite = Activite.objects.get(titre='Colloque')
        self.assertRedirects(reponse, reverse('activites:detail', args=[activite.pk]))
        self.assertEqual(activite.statut, S.EN_PREPARATION)
        self.assertEqual(activite.cree_par, self.organisatrice)
        self.assertTrue(JournalOperation.objects.filter(type_operation='CREATION_ACTIVITE').exists())

    def test_la_fin_ne_precede_pas_le_debut(self):
        self.client.force_login(self.organisatrice)
        debut = timezone.localtime(timezone.now() + timedelta(days=20))
        reponse = self.client.post(reverse('activites:creer'), self.donnees_fiche(
            date_fin=(debut - timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M')))
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Activite.objects.exists())

    def test_publier_cloturer_annuler(self):
        activite = self.activite(statut=S.EN_PREPARATION)
        self.client.force_login(self.organisatrice)
        url = reverse('activites:statut', args=[activite.pk])
        self.client.post(url, {'statut': S.PUBLIEE})
        activite.refresh_from_db()
        self.assertEqual(activite.statut, S.PUBLIEE)
        self.client.post(url, {'statut': S.TERMINEE})
        activite.refresh_from_db()
        self.assertEqual(activite.statut, S.TERMINEE)
        self.client.post(url, {'statut': S.PUBLIEE})           # transition interdite
        activite.refresh_from_db()
        self.assertEqual(activite.statut, S.TERMINEE)

    def test_la_presidente_supervise_aussi(self):
        self.client.force_login(self.presidente)
        self.client.post(reverse('activites:creer'), self.donnees_fiche())
        self.assertTrue(Activite.objects.filter(titre='Colloque').exists())

    def test_les_autres_fonctions_ne_gerent_pas_les_activites(self):
        tresoriere = fabrique.utilisateur('RESP_FINANCIER')
        self.client.force_login(tresoriere)
        self.assertEqual(self.client.get(reverse('activites:creer')).status_code, 403)


class TestComite(BaseActivites):

    def test_deleguer_puis_retirer(self):
        activite = self.activite(statut=S.EN_PREPARATION)
        self.client.force_login(self.organisatrice)
        self.client.post(reverse('activites:comite_ajouter', args=[activite.pk]),
                         {'membre': self.fiche_comite.pk, 'mission': 'Logistique'})
        place = MembreComite.objects.get(activite=activite)
        self.assertEqual(place.mission, 'Logistique')
        notification = Notification.objects.get(type='COMITE_ORGANISATION')
        self.assertEqual(notification.destinataire, self.fiche_comite.email)

        self.client.post(reverse('activites:comite_retirer', args=[activite.pk, place.pk]))
        self.assertFalse(MembreComite.objects.exists())
        self.assertTrue(JournalOperation.objects.filter(type_operation='RETRAIT_COMITE').exists())

    def test_le_comite_gere_son_activite_et_elle_seule(self):
        sienne = self.activite(statut=S.EN_PREPARATION, titre='Sienne')
        autre = self.activite(statut=S.EN_PREPARATION, titre='Autre')
        MembreComite.objects.create(activite=sienne, membre=self.fiche_comite)
        self.client.force_login(self.comite)

        # Elle voit et modifie la sienne, même en préparation…
        self.assertEqual(self.client.get(reverse('activites:detail', args=[sienne.pk])).status_code, 200)
        self.client.post(reverse('activites:modifier', args=[sienne.pk]),
                         self.donnees_fiche(titre='Sienne modifiée'))
        sienne.refresh_from_db()
        self.assertEqual(sienne.titre, 'Sienne modifiée')

        # … mais ni la publier, ni composer le comité, ni créer, ni toucher aux autres.
        self.assertEqual(self.client.post(reverse('activites:statut', args=[sienne.pk]),
                                          {'statut': S.PUBLIEE}).status_code, 403)
        self.assertEqual(self.client.post(reverse('activites:comite_ajouter', args=[sienne.pk]),
                                          {'membre': self.fiche_abj.pk}).status_code, 403)
        self.assertEqual(self.client.get(reverse('activites:creer')).status_code, 403)
        self.assertEqual(self.client.get(reverse('activites:detail', args=[autre.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('activites:modifier', args=[autre.pk])).status_code, 404)

    def test_le_comite_voit_les_inscrites_les_membres_non(self):
        activite = self.activite()
        MembreComite.objects.create(activite=activite, membre=self.fiche_comite)
        Inscription.objects.create(activite=activite, membre=self.fiche_krg)
        self.client.force_login(self.comite)
        self.assertContains(self.client.get(reverse('activites:detail', args=[activite.pk])), 'BAMBA')
        self.client.force_login(self.membre_abj)
        self.assertNotContains(self.client.get(reverse('activites:detail', args=[activite.pk])), 'BAMBA')


class TestVisibiliteEtInscriptions(BaseActivites):

    def test_une_activite_en_preparation_reste_invisible_des_membres(self):
        activite = self.activite(statut=S.EN_PREPARATION)
        self.client.force_login(self.membre_abj)
        self.assertEqual(self.client.get(reverse('activites:detail', args=[activite.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('activites:liste')), activite.titre)

    def test_activite_de_section_reservee_a_cette_section(self):
        activite = self.activite(section=self.abidjan, titre='Atelier Abidjan')
        self.client.force_login(self.membre_krg)
        self.assertEqual(self.client.get(reverse('activites:detail', args=[activite.pk])).status_code, 404)
        self.client.force_login(self.membre_abj)
        self.assertContains(self.client.get(reverse('activites:liste')), 'Atelier Abidjan')

    def test_s_inscrire_puis_annuler(self):
        activite = self.activite()
        self.client.force_login(self.membre_krg)
        url = reverse('activites:inscription', args=[activite.pk])
        self.client.post(url)
        self.assertTrue(Inscription.objects.filter(activite=activite, membre=self.fiche_krg).exists())
        self.client.post(url, {'action': 'annuler'})
        self.assertFalse(Inscription.objects.exists())

    def test_pas_d_inscription_au_dela_des_places(self):
        activite = self.activite(places=1)
        Inscription.objects.create(activite=activite, membre=self.fiche_abj)
        self.client.force_login(self.membre_krg)
        self.client.post(reverse('activites:inscription', args=[activite.pk]))
        self.assertEqual(activite.inscriptions.count(), 1)

    def test_pas_d_inscription_a_une_activite_passee_ou_non_publiee(self):
        passee = self.activite(dans_jours=-2)
        preparation = self.activite(statut=S.EN_PREPARATION)
        MembreComite.objects.create(activite=preparation, membre=self.fiche_comite)
        self.client.force_login(self.comite)
        for activite in (passee, preparation):
            self.client.post(reverse('activites:inscription', args=[activite.pk]))
        self.assertFalse(Inscription.objects.exists())

    def test_le_nombre_de_places_ne_descend_pas_sous_les_inscrites(self):
        activite = self.activite(places=5)
        for fiche in (self.fiche_abj, self.fiche_krg):
            Inscription.objects.create(activite=activite, membre=fiche)
        self.client.force_login(self.organisatrice)
        reponse = self.client.post(reverse('activites:modifier', args=[activite.pk]),
                                   self.donnees_fiche(places='1'))
        self.assertEqual(reponse.status_code, 200)
        activite.refresh_from_db()
        self.assertEqual(activite.places, 5)

    def test_menu_activites_pour_toutes(self):
        self.client.force_login(self.membre_abj)
        self.assertContains(self.client.get(reverse('activites:liste')), reverse('activites:liste'))
