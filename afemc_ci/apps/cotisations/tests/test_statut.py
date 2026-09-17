"""Tests unitaires de la fonction de calcul du statut (§ 6.2)."""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from freezegun import freeze_time

from apps.cotisations.models import Cotisation, Exemption
from apps.cotisations.services import calculer_statut, enregistrer_paiement
from apps.membres.models import Membre
from apps.sections.models import Section


def creer_membre_test(nom='KOUAME', email='kouame@exemple.org'):
    section, _ = Section.objects.get_or_create(code='ABJ', defaults={'libelle': 'Abidjan'})
    return Membre.objects.create(nom=nom, prenoms='Akissi', email=email, section=section)


class TestCalculStatutCotisation(TestCase):

    def setUp(self):
        self.membre = creer_membre_test()

    def test_cotisation_integralement_payee(self):
        c = Cotisation(membre=self.membre, montant_du=Decimal('25000'),
                       montant_paye=Decimal('25000'),
                       date_echeance=date(2026, 3, 31))
        self.assertEqual(calculer_statut(c), Cotisation.Statut.PAYEE)

    def test_echeance_depassee_et_impayee(self):
        c = Cotisation(membre=self.membre, montant_du=Decimal('25000'),
                       montant_paye=Decimal('0'),
                       date_echeance=date(2026, 3, 31))
        with freeze_time('2026-04-01'):
            self.assertEqual(calculer_statut(c), Cotisation.Statut.EN_RETARD)

    def test_paiement_partiel_avant_echeance(self):
        c = Cotisation(membre=self.membre, montant_du=Decimal('25000'),
                       montant_paye=Decimal('10000'),
                       date_echeance=date(2026, 3, 31))
        with freeze_time('2026-03-01'):
            self.assertEqual(calculer_statut(c), Cotisation.Statut.PARTIEL)

    def test_le_jour_meme_de_l_echeance_pas_de_retard(self):
        c = Cotisation(membre=self.membre, montant_du=Decimal('25000'),
                       montant_paye=Decimal('0'),
                       date_echeance=date(2026, 3, 31))
        with freeze_time('2026-03-31'):
            self.assertNotEqual(calculer_statut(c), Cotisation.Statut.EN_RETARD)

    def test_exemption_prioritaire_sur_le_retard(self):
        Exemption.objects.create(membre=self.membre, exercice=2026, motif='Statutaire')
        c = Cotisation.objects.create(membre=self.membre, exercice=2026,
                                      montant_du=Decimal('25000'),
                                      date_echeance=date(2026, 1, 1))
        with freeze_time('2026-06-01'):
            self.assertEqual(calculer_statut(c), Cotisation.Statut.EXEMPTEE)

    def test_cotisation_neuve_est_en_attente(self):
        c = Cotisation(membre=self.membre, montant_du=Decimal('25000'),
                       montant_paye=Decimal('0'),
                       date_echeance=date(2026, 12, 31))
        with freeze_time('2026-06-01'):
            self.assertEqual(calculer_statut(c), Cotisation.Statut.EN_ATTENTE)


class TestEnregistrementPaiement(TestCase):

    def setUp(self):
        self.membre = creer_membre_test()
        self.cotisation = Cotisation.objects.create(
            membre=self.membre, exercice=2026, montant_du=Decimal('25000'),
            date_echeance=date(2026, 12, 31))

    def test_paiement_integral(self):
        enregistrer_paiement(self.cotisation, Decimal('25000'), 'ESPECES')
        self.cotisation.refresh_from_db()
        self.assertEqual(self.cotisation.statut, Cotisation.Statut.PAYEE)
        self.assertEqual(self.cotisation.reste_a_payer, Decimal('0'))

    def test_deux_paiements_partiels_successifs(self):
        enregistrer_paiement(self.cotisation, Decimal('10000'), 'ESPECES')
        self.cotisation.refresh_from_db()
        self.assertEqual(self.cotisation.statut, Cotisation.Statut.PARTIEL)
        enregistrer_paiement(self.cotisation, Decimal('15000'), 'MOBILE_MONEY')
        self.cotisation.refresh_from_db()
        self.assertEqual(self.cotisation.statut, Cotisation.Statut.PAYEE)
        self.assertEqual(self.cotisation.montant_paye, Decimal('25000'))

    def test_paiement_superieur_au_reste_est_refuse(self):
        with self.assertRaises(ValidationError):
            enregistrer_paiement(self.cotisation, Decimal('30000'), 'ESPECES')

    def test_paiement_negatif_est_refuse(self):
        with self.assertRaises(ValidationError):
            enregistrer_paiement(self.cotisation, Decimal('-500'), 'ESPECES')

    def test_le_paiement_est_trace(self):
        from apps.core.models import JournalOperation
        enregistrer_paiement(self.cotisation, Decimal('5000'), 'ESPECES')
        self.assertTrue(JournalOperation.objects
                        .filter(type_operation='ENREGISTREMENT_PAIEMENT').exists())

    def test_le_solde_reel_prevaut_sur_un_objet_perime(self):
        """Deux saisies quasi simultanées ne doivent jamais s'écraser :
        même si l'objet transmis est périmé, le reste à payer vérifié est
        toujours celui réellement en base au moment de l'écriture."""
        perime = Cotisation.objects.get(pk=self.cotisation.pk)
        enregistrer_paiement(self.cotisation, Decimal('10000'), 'ESPECES')
        # `perime` ignore encore ce premier paiement (montant_paye=0 en mémoire) ;
        # le reste réel n'est plus que 15000, pas 25000.
        with self.assertRaises(ValidationError):
            enregistrer_paiement(perime, Decimal('20000'), 'ESPECES')
        enregistrer_paiement(perime, Decimal('15000'), 'ESPECES')
        self.cotisation.refresh_from_db()
        self.assertEqual(self.cotisation.montant_paye, Decimal('25000'))
        self.assertEqual(self.cotisation.statut, Cotisation.Statut.PAYEE)


class TestEmissionCotisations(TestCase):

    def setUp(self):
        self.section = Section.objects.create(code='BKE', libelle='Bouaké')
        for i in range(5):
            Membre.objects.create(nom=f'NOM{i}', prenoms='Aya',
                                  email=f'membre{i}@exemple.org', section=self.section)

    def test_une_cotisation_par_membre_actif(self):
        from apps.cotisations.services import emettre_cotisations_exercice
        creees, ignorees = emettre_cotisations_exercice(
            2026, Decimal('25000'), date(2026, 12, 31))
        self.assertEqual(len(creees), 5)
        self.assertEqual(ignorees, 0)

    def test_aucun_doublon_en_cas_de_seconde_emission(self):
        from apps.cotisations.services import emettre_cotisations_exercice
        emettre_cotisations_exercice(2026, Decimal('25000'), date(2026, 12, 31))
        creees, ignorees = emettre_cotisations_exercice(
            2026, Decimal('25000'), date(2026, 12, 31))
        self.assertEqual(len(creees), 0)
        self.assertEqual(ignorees, 5)
        self.assertEqual(Cotisation.objects.count(), 5)

    def test_les_membres_exemptes_sont_ecartes(self):
        from apps.cotisations.services import emettre_cotisations_exercice
        Exemption.objects.create(membre=Membre.objects.first(), exercice=2026,
                                 motif='Statutaire')
        creees, _ = emettre_cotisations_exercice(2026, Decimal('25000'),
                                                 date(2026, 12, 31))
        self.assertEqual(len(creees), 4)

    def test_les_membres_inactifs_sont_ecartes(self):
        from apps.cotisations.services import emettre_cotisations_exercice
        membre = Membre.objects.first()
        membre.statut = Membre.Statut.INACTIF
        membre.save()
        creees, _ = emettre_cotisations_exercice(2026, Decimal('25000'),
                                                 date(2026, 12, 31))
        self.assertEqual(len(creees), 4)
