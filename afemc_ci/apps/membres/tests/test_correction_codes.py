"""Migration 0003 : codes de section saisis avec « OO » (lettres) au lieu de « 00 »."""
from importlib import import_module

from django.apps import apps as registre
from django.test import TestCase

from apps.core.models import JournalOperation
from apps.core.tests import fabrique
from apps.membres.models import Membre
from apps.sections.models import Section

migration = import_module('apps.membres.migrations.0003_corrige_codes_sections')


class TestCorrectionCodesSections(TestCase):

    def setUp(self):
        self.bouake = fabrique.section('BKE-OO-257', 'BOUAKE CENTRE')
        self.uvci = fabrique.section('UVC-00-787', 'UVCI CENTRE')
        self.m1 = fabrique.membre(nom='KOUADIO', sect=self.bouake)
        self.m2 = fabrique.membre(nom='KOUAME', sect=self.bouake)
        self.autre = fabrique.membre(nom='BAMBA', sect=self.uvci)
        self.numero_autre = self.autre.matricule

    def rafraichir(self):
        for objet in (self.bouake, self.uvci, self.m1, self.m2, self.autre):
            objet.refresh_from_db()

    def test_corrige_le_code_et_les_numeros_d_adherente(self):
        ancien = self.m1.matricule
        migration.corriger(registre, None)
        self.rafraichir()

        self.assertEqual(self.bouake.code, 'BKE-00-257')
        self.assertEqual(self.m1.matricule, ancien.replace('-OO-', '-00-'))
        self.assertTrue(self.m2.matricule.startswith('BKE-00-257-'))
        self.assertEqual(self.autre.matricule, self.numero_autre)          # intacte
        self.assertEqual(self.uvci.code, 'UVC-00-787')
        trace = JournalOperation.objects.filter(type_operation='CORRECTION_NUMERO_ADHERENTE')
        self.assertEqual(trace.count(), 2)
        self.assertTrue(trace.filter(detail__startswith=f'{ancien} -> ').exists())

    def test_les_nouvelles_fiches_suivent_le_bon_format(self):
        migration.corriger(registre, None)
        self.bouake.refresh_from_db()
        nouvelle = fabrique.membre(nom='YAO', sect=self.bouake)
        self.assertTrue(nouvelle.matricule.startswith('BKE-00-257-'))

    def test_retour_arriere(self):
        ancien = self.m1.matricule
        migration.corriger(registre, None)
        migration.annuler(registre, None)
        self.rafraichir()
        self.assertEqual(self.bouake.code, 'BKE-OO-257')
        self.assertEqual(self.m1.matricule, ancien)
        self.assertEqual(self.uvci.code, 'UVC-00-787')

    def test_s_arrete_sans_rien_modifier_si_le_code_corrige_existe_deja(self):
        fabrique.section('BKE-00-257', 'Doublon')
        ancien = self.m1.matricule
        with self.assertRaises(RuntimeError):
            migration.corriger(registre, None)
        self.rafraichir()
        self.assertEqual(self.bouake.code, 'BKE-OO-257')
        self.assertEqual(Membre.objects.get(pk=self.m1.pk).matricule, ancien)
