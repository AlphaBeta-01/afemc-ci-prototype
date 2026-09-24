"""Nomination et fin de fonctions des responsables (RG13).

Une responsable est une membre à qui la Présidente confie une fonction :
la fonction s'ajoute à son compte existant, jamais à un second compte.
"""
from django.apps import apps as registre_apps
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Utilisateur
from apps.accounts.services import (NominationImpossible, mettre_fin_aux_fonctions,
                                    nommer_responsable)
from apps.core.models import JournalOperation
from apps.core.tests import fabrique
from apps.membres.models import Membre
from apps.notifications.models import Notification


class BaseNomination(TestCase):

    def setUp(self):
        self.abidjan = fabrique.section('ABJ', "Section d'Abidjan")
        self.korhogo = fabrique.section('KRG', 'Section de Korhogo')
        self.presidente = fabrique.utilisateur('ADMIN')
        self.membre = fabrique.membre(nom='KOUAME', sect=self.abidjan,
                                      email='akissi@exemple.org')
        self.compte = fabrique.utilisateur('MEMBRE', email='akissi@exemple.org',
                                           section_liee=self.abidjan)
        self.membre.utilisateur = self.compte
        self.membre.save()


class TestNommer(BaseNomination):

    def test_la_fonction_s_ajoute_au_compte_existant(self):
        nombre_de_comptes = Utilisateur.objects.count()
        compte = nommer_responsable(self.membre, 'RESP_FINANCIER', nomme_par=self.presidente)

        self.assertEqual(compte.pk, self.compte.pk)                 # même compte
        self.assertEqual(Utilisateur.objects.count(), nombre_de_comptes)
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.role, 'RESP_FINANCIER')
        self.assertIsNone(self.compte.section)
        self.assertTrue(self.compte.check_password(fabrique.MOT_DE_PASSE))  # mot de passe gardé

    def test_la_nomination_est_journalisee_et_notifiee(self):
        nommer_responsable(self.membre, 'RESP_ADMIN', nomme_par=self.presidente)

        entree = JournalOperation.objects.get(type_operation='NOMINATION_RESPONSABLE')
        self.assertEqual(entree.utilisateur, self.presidente)
        self.assertIn(self.membre.matricule, entree.detail)
        self.assertIn('Secrétaire générale', entree.detail)

        notification = Notification.objects.get(type='NOMINATION_RESPONSABLE')
        self.assertEqual(notification.destinataire, 'akissi@exemple.org')
        self.assertEqual(notification.contexte['lien'], '')          # compte déjà actif
        self.assertIn('Secrétaire générale', notification.objet)

    def test_une_membre_sans_compte_recoit_un_compte_relie_et_un_lien(self):
        sans_compte = fabrique.membre(nom='BAMBA', sect=self.korhogo)
        compte = nommer_responsable(sans_compte, 'RESP_FINANCIER', nomme_par=self.presidente)

        sans_compte.refresh_from_db()
        self.assertEqual(sans_compte.utilisateur, compte)
        self.assertFalse(compte.is_active)
        self.assertFalse(compte.has_usable_password())
        notification = Notification.objects.get(type='NOMINATION_RESPONSABLE')
        self.assertIn('/comptes/activation/', notification.contexte['lien'])

    def test_un_compte_existant_non_relie_est_rattache_plutot_que_duplique(self):
        """Ex. une ancienne responsable redevenue Membre par la migration,
        dont la fiche a ensuite été créée avec la même adresse."""
        fiche = fabrique.membre(nom='DIARRA', sect=self.abidjan, email='awa@exemple.org')
        ancien = fabrique.utilisateur('MEMBRE', email='awa@exemple.org')
        Membre.objects.filter(pk=fiche.pk).update(utilisateur=None)
        fiche.refresh_from_db()

        compte = nommer_responsable(fiche, 'RESP_ADMIN', nomme_par=self.presidente)
        self.assertEqual(compte.pk, ancien.pk)
        fiche.refresh_from_db()
        self.assertEqual(fiche.utilisateur_id, ancien.pk)

    def test_la_coordinatrice_prend_par_defaut_la_section_de_la_membre(self):
        nommer_responsable(self.membre, 'RESP_SECTION', nomme_par=self.presidente)
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.section, self.abidjan)

    def test_la_coordinatrice_peut_coordonner_une_autre_section(self):
        nommer_responsable(self.membre, 'RESP_SECTION', section=self.korhogo,
                           nomme_par=self.presidente)
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.section, self.korhogo)

    def test_une_membre_suspendue_ne_peut_pas_etre_nommee(self):
        Membre.objects.filter(pk=self.membre.pk).update(statut=Membre.Statut.SUSPENDU)
        self.membre.refresh_from_db()
        with self.assertRaises(NominationImpossible):
            nommer_responsable(self.membre, 'RESP_FINANCIER', nomme_par=self.presidente)

    def test_la_presidente_ne_peut_pas_recevoir_une_autre_fonction(self):
        fiche = fabrique.membre(nom='KOUADIO', sect=self.abidjan,
                                email=self.presidente.email)
        fiche.utilisateur = self.presidente
        fiche.save()
        with self.assertRaises(NominationImpossible):
            nommer_responsable(fiche, 'RESP_FINANCIER', nomme_par=self.presidente)

    def test_la_fonction_presidente_n_est_pas_attribuable(self):
        with self.assertRaises(NominationImpossible):
            nommer_responsable(self.membre, 'ADMIN', nomme_par=self.presidente)

    def test_une_nomination_identique_est_refusee(self):
        nommer_responsable(self.membre, 'RESP_FINANCIER', nomme_par=self.presidente)
        self.membre.refresh_from_db()
        with self.assertRaises(NominationImpossible):
            nommer_responsable(self.membre, 'RESP_FINANCIER', nomme_par=self.presidente)


class TestFinDeFonctions(BaseNomination):

    def test_la_responsable_redevient_membre_et_garde_son_acces(self):
        nommer_responsable(self.membre, 'RESP_SECTION', section=self.korhogo,
                           nomme_par=self.presidente)
        self.compte.refresh_from_db()
        mettre_fin_aux_fonctions(self.compte, par=self.presidente)

        self.compte.refresh_from_db()
        self.assertEqual(self.compte.role, 'MEMBRE')
        self.assertEqual(self.compte.section, self.abidjan)   # celle de sa fiche
        self.assertTrue(self.compte.is_active)
        self.assertTrue(JournalOperation.objects.filter(type_operation='FIN_FONCTIONS').exists())
        notification = Notification.objects.get(type='FIN_FONCTIONS')
        self.assertTrue(notification.contexte['reste_membre'])

    def test_un_compte_externe_est_desactive(self):
        externe = fabrique.utilisateur('RESP_ADMIN', email='externe@exemple.org')
        mettre_fin_aux_fonctions(externe, par=self.presidente)
        externe.refresh_from_db()
        self.assertEqual(externe.role, 'MEMBRE')
        self.assertFalse(externe.is_active)

    def test_impossible_sur_soi_meme_ou_sur_un_simple_membre(self):
        with self.assertRaises(NominationImpossible):
            mettre_fin_aux_fonctions(self.presidente, par=self.presidente)
        with self.assertRaises(NominationImpossible):
            mettre_fin_aux_fonctions(self.compte, par=self.presidente)


class TestEcransNomination(BaseNomination):

    def test_nomination_depuis_l_ecran(self):
        self.client.force_login(self.presidente)
        reponse = self.client.post(reverse('accounts:nommer'), {
            'membre': self.membre.pk, 'role': 'RESP_FINANCIER'})
        self.assertRedirects(reponse, reverse('accounts:comptes_liste'))
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.role, 'RESP_FINANCIER')

    def test_la_membre_est_preselectionnee_depuis_sa_fiche(self):
        self.client.force_login(self.presidente)
        fiche = self.client.get(reverse('membres:detail', args=[self.membre.pk]))
        lien = f"{reverse('accounts:nommer')}?membre={self.membre.pk}"
        self.assertContains(fiche, lien)
        reponse = self.client.get(lien)
        self.assertEqual(str(reponse.context['formulaire']['membre'].value()),
                         str(self.membre.pk))

    def test_une_membre_inactive_n_est_pas_proposee(self):
        Membre.objects.filter(pk=self.membre.pk).update(statut=Membre.Statut.INACTIF)
        self.client.force_login(self.presidente)
        reponse = self.client.post(reverse('accounts:nommer'), {
            'membre': self.membre.pk, 'role': 'RESP_FINANCIER'})
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.context['formulaire'].errors['membre'])

    def test_fin_de_fonctions_depuis_l_ecran(self):
        nommer_responsable(self.membre, 'RESP_FINANCIER', nomme_par=self.presidente)
        self.client.force_login(self.presidente)
        self.client.post(reverse('accounts:fin_fonctions', args=[self.compte.pk]))
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.role, 'MEMBRE')

    def test_seule_la_presidente_nomme_ou_met_fin_aux_fonctions(self):
        secretaire = fabrique.utilisateur('RESP_ADMIN', email='sg@afemc-ci.org')
        self.client.force_login(secretaire)
        self.assertEqual(self.client.get(reverse('accounts:nommer')).status_code, 403)
        reponse = self.client.post(reverse('accounts:nommer'), {
            'membre': self.membre.pk, 'role': 'RESP_FINANCIER'})
        self.assertEqual(reponse.status_code, 403)
        reponse = self.client.post(reverse('accounts:fin_fonctions', args=[secretaire.pk]))
        self.assertEqual(reponse.status_code, 403)
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.role, 'MEMBRE')

    def test_un_compte_externe_ne_peut_pas_reprendre_l_adresse_d_une_membre(self):
        self.client.force_login(self.presidente)
        reponse = self.client.post(reverse('accounts:comptes_creer'), {
            'nom': 'KOUAME', 'prenoms': 'Akissi', 'email': 'AKISSI@exemple.org',
            'role': 'RESP_FINANCIER'})
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('Nommer une responsable',
                      reponse.context['formulaire'].errors['email'][0])

    def test_une_coordinatrice_voit_ses_propres_cotisations(self):
        """Elle est aussi une membre cotisante ; les cotisations des autres
        membres restent hors de son périmètre (RG08)."""
        fabrique.cotisation(membre_lie=self.membre)
        nommer_responsable(self.membre, 'RESP_SECTION', nomme_par=self.presidente)
        self.client.force_login(self.compte)

        sa_fiche = self.client.get(reverse('membres:detail', args=[self.membre.pk]))
        self.assertContains(sa_fiche, 'Historique des cotisations')

        autre = fabrique.membre(nom='YAO', sect=self.abidjan)
        fiche_autre = self.client.get(reverse('membres:detail', args=[autre.pk]))
        self.assertNotContains(fiche_autre, 'Historique des cotisations')


class TestMigrationDesResponsables(TestCase):
    """Migration 0003 : les comptes responsables existants redeviennent Membre."""

    def test_les_responsables_redeviennent_membres_sauf_la_presidente(self):
        from importlib import import_module
        migration = import_module(
            'apps.accounts.migrations.0003_responsables_redeviennent_membres')

        abidjan = fabrique.section('ABJ', "Section d'Abidjan")
        korhogo = fabrique.section('KRG', 'Section de Korhogo')
        presidente = fabrique.utilisateur('ADMIN')
        tresoriere = fabrique.utilisateur('RESP_FINANCIER', email='tresoriere@exemple.org')
        coordinatrice = fabrique.utilisateur('RESP_SECTION', email='coord@exemple.org',
                                             section_liee=korhogo)
        fiche = fabrique.membre(nom='COULIBALY', sect=abidjan, email='coord@exemple.org')
        fiche.utilisateur = coordinatrice
        fiche.save()

        migration.ramener_au_role_membre(registre_apps, None)

        for compte in (presidente, tresoriere, coordinatrice):
            compte.refresh_from_db()
        self.assertEqual(presidente.role, 'ADMIN')
        self.assertEqual(tresoriere.role, 'MEMBRE')
        self.assertIsNone(tresoriere.section)
        self.assertEqual(coordinatrice.role, 'MEMBRE')
        self.assertEqual(coordinatrice.section, abidjan)       # section de sa fiche
        self.assertTrue(tresoriere.is_active)                  # l'accès est conservé
        traces = JournalOperation.objects.filter(type_operation='FIN_FONCTIONS_MIGRATION')
        self.assertEqual(traces.count(), 2)
        self.assertTrue(traces.filter(detail__contains='Section de Korhogo').exists())
