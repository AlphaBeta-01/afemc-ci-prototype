"""Validation du moteur de détection — scénarios SC01 à SC24 (§ 6.5)."""
from datetime import date, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from apps.cotisations.models import Cotisation
from apps.membres.models import Membre
from apps.notifications.models import Notification
from apps.relances.models import Relance, RegleRelance
from apps.relances.services import executer_detection
from apps.sections.models import Section

REFERENCE = date(2026, 6, 15)


class BaseMoteur(TestCase):

    def setUp(self):
        call_command('charger_regles', verbosity=0)
        self.section = Section.objects.create(code='ABJ', libelle='Abidjan')
        self.compteur = 0

    def membre(self, statut=Membre.Statut.ACTIF):
        self.compteur += 1
        return Membre.objects.create(
            nom=f'MEMBRE{self.compteur}', prenoms='Aya',
            email=f'membre{self.compteur}@exemple.org',
            section=self.section, statut=statut)

    def cotisation(self, jours_ecart, paye=0, membre=None, statut=None):
        """jours_ecart > 0 : retard ; < 0 : échéance à venir."""
        membre = membre or self.membre()
        cot = Cotisation.objects.create(
            membre=membre, exercice=2026, montant_du=Decimal('25000'),
            montant_paye=Decimal(paye),
            date_echeance=REFERENCE - timedelta(days=jours_ecart))
        if statut:
            cot.statut = statut
            cot.save(update_fields=['statut'])
        return cot


class TestScenariosMoteur(BaseMoteur):

    def test_sc01_echeance_dans_quinze_jours(self):
        cot = self.cotisation(-15)
        executer_detection(aujourdhui=REFERENCE)
        self.assertEqual(cot.relances.first().regle.code, 'R01')

    def test_sc02_echeance_dans_trois_jours(self):
        cot = self.cotisation(-3)
        executer_detection(aujourdhui=REFERENCE)
        self.assertEqual(cot.relances.first().regle.code, 'R02')

    def test_sc03_echeance_du_jour_meme_aucune_relance_de_retard(self):
        cot = self.cotisation(0)
        executer_detection(aujourdhui=REFERENCE)
        cot.refresh_from_db()
        self.assertNotEqual(cot.statut, Cotisation.Statut.EN_RETARD)
        self.assertFalse(cot.relances.filter(regle__code='R03').exists())

    def test_sc04_echeance_depassee_d_un_jour(self):
        cot = self.cotisation(1)
        executer_detection(aujourdhui=REFERENCE)
        cot.refresh_from_db()
        self.assertEqual(cot.statut, Cotisation.Statut.EN_RETARD)
        self.assertEqual(cot.relances.first().regle.code, 'R03')

    def test_sc05_retard_de_quinze_jours(self):
        cot = self.cotisation(15)
        executer_detection(aujourdhui=REFERENCE)
        self.assertEqual(cot.relances.first().regle.code, 'R04')

    def test_sc06_retard_de_quarante_cinq_jours(self):
        cot = self.cotisation(45)
        executer_detection(aujourdhui=REFERENCE)
        self.assertEqual(cot.relances.first().regle.code, 'R05')

    def test_sc07_retard_de_quatre_vingt_dix_jours(self):
        cot = self.cotisation(90)
        executer_detection(aujourdhui=REFERENCE)
        self.assertEqual(cot.relances.first().regle.code, 'R06')

    def test_sc08_cotisation_payee_aucune_action(self):
        cot = self.cotisation(-30, paye=25000, statut=Cotisation.Statut.PAYEE)
        executer_detection(aujourdhui=REFERENCE)
        self.assertEqual(cot.relances.count(), 0)

    def test_sc10_paiement_partiel_avant_echeance(self):
        cot = self.cotisation(-10, paye=10000)
        executer_detection(aujourdhui=REFERENCE)
        cot.refresh_from_db()
        self.assertEqual(cot.statut, Cotisation.Statut.PARTIEL)
        self.assertFalse(cot.relances.filter(regle__code='R03').exists())

    def test_sc11_paiement_partiel_apres_echeance(self):
        cot = self.cotisation(5, paye=10000)
        executer_detection(aujourdhui=REFERENCE)
        cot.refresh_from_db()
        self.assertEqual(cot.statut, Cotisation.Statut.EN_RETARD)
        notification = Notification.objects.filter(membre=cot.membre).first()
        self.assertEqual(notification.contexte['reste'], '15000.00')

    def test_sc13_membre_suspendu_aucune_relance(self):
        membre = self.membre(statut=Membre.Statut.SUSPENDU)
        cot = self.cotisation(30, membre=membre)
        executer_detection(aujourdhui=REFERENCE)
        self.assertEqual(cot.relances.count(), 0)

    def test_sc15_deux_executions_le_meme_jour(self):
        cot = self.cotisation(20)
        executer_detection(aujourdhui=REFERENCE)
        executer_detection(aujourdhui=REFERENCE)
        self.assertEqual(cot.relances.count(), 1)

    def test_sc16_rattrapage_apres_interruption(self):
        cot = self.cotisation(20)
        executer_detection(aujourdhui=REFERENCE)
        executer_detection(aujourdhui=REFERENCE + timedelta(days=3))
        self.assertEqual(cot.relances.count(), 1)

    def test_sc18_echeance_un_29_fevrier(self):
        membre = self.membre()
        cot = Cotisation.objects.create(
            membre=membre, exercice=2024, montant_du=Decimal('25000'),
            date_echeance=date(2024, 2, 29))
        resultat = executer_detection(aujourdhui=date(2024, 3, 1))
        cot.refresh_from_db()
        self.assertEqual(cot.statut, Cotisation.Statut.EN_RETARD)
        self.assertGreaterEqual(resultat['relances'], 1)

    def test_sc21_modification_du_seuil_d_une_regle(self):
        regle = RegleRelance.objects.get(code='R04')
        regle.decalage_jours = 7
        regle.save()
        cot = self.cotisation(8)
        executer_detection(aujourdhui=REFERENCE)
        self.assertEqual(cot.relances.first().regle.code, 'R04')

    def test_sc22_desactivation_d_une_regle(self):
        RegleRelance.objects.filter(code='R04').update(active=False)
        cot = self.cotisation(20)
        executer_detection(aujourdhui=REFERENCE)
        self.assertFalse(cot.relances.filter(regle__code='R04').exists())
        self.assertTrue(cot.relances.filter(regle__code='R03').exists())

    def test_sc23_mode_simulation_n_ecrit_rien(self):
        cot = self.cotisation(20)
        resultat = executer_detection(simulation=True, aujourdhui=REFERENCE)
        cot.refresh_from_db()
        self.assertEqual(Relance.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(cot.statut, Cotisation.Statut.EN_ATTENTE)
        self.assertGreaterEqual(resultat['relances'], 1)

    def test_sc24_base_sans_cotisation_echue(self):
        resultat = executer_detection(aujourdhui=REFERENCE)
        self.assertEqual(resultat['relances'], 0)
        self.assertEqual(resultat['basculees'], 0)


class TestAbsenceDeFauxPositifs(BaseMoteur):
    """Aucune relance ne doit viser un membre à jour ou suspendu (§ 6.5)."""

    def test_aucun_faux_positif(self):
        self.cotisation(-30, paye=25000, statut=Cotisation.Statut.PAYEE)
        self.cotisation(30, membre=self.membre(statut=Membre.Statut.SUSPENDU))
        executer_detection(aujourdhui=REFERENCE)
        self.assertEqual(Relance.objects.count(), 0)

    def test_aucun_faux_negatif(self):
        for ecart in (1, 15, 45, 90):
            self.cotisation(ecart)
        executer_detection(aujourdhui=REFERENCE)
        self.assertEqual(Relance.objects.count(), 4)
        self.assertEqual(
            Cotisation.objects.filter(statut=Cotisation.Statut.EN_RETARD).count(), 4)


class TestScenariosComplementaires(BaseMoteur):
    """Scénarios SC09, SC14 et SC19 du tableau 23."""

    def test_sc09_paiement_apres_relance_arrete_les_envois(self):
        from apps.cotisations.services import enregistrer_paiement

        cot = self.cotisation(5)
        executer_detection(aujourdhui=REFERENCE)
        nombre = cot.relances.count()
        self.assertGreaterEqual(nombre, 1)

        enregistrer_paiement(cot, Decimal('25000'), 'ESPECES')
        cot.refresh_from_db()
        self.assertEqual(cot.statut, Cotisation.Statut.PAYEE)

        executer_detection(aujourdhui=REFERENCE + timedelta(days=60))
        self.assertEqual(cot.relances.count(), nombre)

    def test_sc14_membre_inactif_aucune_emission_ni_relance(self):
        from apps.cotisations.services import emettre_cotisations_exercice

        inactif = self.membre(statut=Membre.Statut.INACTIF)
        creees, _ = emettre_cotisations_exercice(
            2026, Decimal('25000'), REFERENCE + timedelta(days=30))
        self.assertEqual([c.membre_id for c in creees].count(inactif.pk), 0)
        executer_detection(aujourdhui=REFERENCE)
        self.assertEqual(Relance.objects.filter(
            cotisation__membre=inactif).count(), 0)

    def test_sc19_adresse_invalide_echec_apres_trois_tentatives(self):
        from unittest.mock import patch

        from apps.notifications.services import (ErreurEnvoi,
                                                 acheminer_notifications_en_attente)

        cot = self.cotisation(20)
        with patch('apps.notifications.services.envoyer_courriel',
                   side_effect=ErreurEnvoi('adresse invalide')):
            executer_detection(aujourdhui=REFERENCE)    # tentative n°1, échoue
            self.assertGreaterEqual(Notification.objects.count(), 1)
            for _essai in range(2):                      # tentatives n°2 et n°3
                acheminer_notifications_en_attente()

        notification = Notification.objects.filter(membre=cot.membre).first()
        self.assertEqual(notification.statut, Notification.Statut.ECHEC)
        self.assertEqual(notification.tentatives, 3)
        # la relance reste tracée même si la notification a échoué
        self.assertGreaterEqual(cot.relances.count(), 1)

    def test_sc17_cotisation_d_exercice_anterieur_non_soldee(self):
        membre = self.membre()
        ancienne = Cotisation.objects.create(
            membre=membre, exercice=2024, montant_du=Decimal('25000'),
            date_echeance=date(2024, 3, 31))
        executer_detection(aujourdhui=REFERENCE)
        ancienne.refresh_from_db()
        self.assertEqual(ancienne.statut, Cotisation.Statut.EN_RETARD)
        self.assertEqual(ancienne.relances.first().regle.code, 'R06')
        # une seconde exécution ne produit aucune relance supplémentaire
        executer_detection(aujourdhui=REFERENCE + timedelta(days=30))
        self.assertEqual(ancienne.relances.count(), 1)


class TestGabaritsDesDestinataires(BaseMoteur):
    """Une responsable en copie ne reçoit pas le message adressé au membre."""

    def setUp(self):
        super().setUp()
        from apps.core.tests.fabrique import utilisateur
        from apps.accounts.models import Utilisateur
        self.tresoriere = utilisateur(Utilisateur.Role.RESP_FINANCIER,
                                      email='tresoriere@exemple.org')

    def test_r05_membre_et_tresoriere_recoivent_chacune_leur_gabarit(self):
        cot = self.cotisation(45)
        executer_detection(aujourdhui=REFERENCE)
        self.assertEqual(cot.relances.first().regle.code, 'R05')

        au_membre = Notification.objects.get(destinataire=cot.membre.email)
        self.assertEqual(au_membre.gabarit, 'notifications/relance.txt')

        a_la_tresoriere = Notification.objects.get(destinataire='tresoriere@exemple.org')
        self.assertEqual(a_la_tresoriere.gabarit, 'notifications/relance_responsable.txt')
        self.assertIn(cot.membre.nom_complet(), a_la_tresoriere.objet)

    def test_le_gabarit_responsable_nomme_la_membre_en_retard(self):
        from apps.notifications.services import rendre_gabarit
        cot = self.cotisation(90)
        executer_detection(aujourdhui=REFERENCE)
        notification = Notification.objects.get(destinataire='tresoriere@exemple.org')
        corps = rendre_gabarit(notification.gabarit, notification.contexte)
        self.assertIn(cot.membre.nom_complet(), corps)
        self.assertNotIn('votre cotisation', corps)
