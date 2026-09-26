"""Limites de fréquence des formulaires publics et champ piège (TS15)."""
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.adhesions.models import DemandeAdhesion
from apps.core.limites import LIMITES
from apps.core.models import JournalOperation
from apps.core.tests import fabrique


def maximum(action, portee):
    return min(l.maximum for l in LIMITES[action] if l.portee == portee)


class TestMotDePasseOublie(TestCase):

    def setUp(self):
        self.compte = fabrique.utilisateur('MEMBRE', email='awa@exemple.org')
        self.url = reverse('accounts:mot_de_passe_oublie')

    def test_une_meme_adresse_ne_recoit_pas_plus_de_trois_liens_par_heure(self):
        for _ in range(maximum('mot_de_passe_oublie', 'cible') + 2):
            reponse = self.client.post(self.url, {'email': 'awa@exemple.org'})
            self.assertTemplateUsed(reponse, 'accounts/mot_de_passe_oublie_envoye.html')
        self.assertEqual(len(mail.outbox), maximum('mot_de_passe_oublie', 'cible'))
        self.assertTrue(JournalOperation.objects.filter(type_operation='LIMITE_ATTEINTE').exists())

    def test_la_limite_par_ip_protege_les_autres_adresses(self):
        for i in range(maximum('mot_de_passe_oublie', 'ip') + 3):
            self.client.post(self.url, {'email': f'inconnue{i}@exemple.org'})
        self.client.post(self.url, {'email': 'awa@exemple.org'})
        self.assertEqual(len(mail.outbox), 0)          # même IP : bloquée

    def test_limite_globale_malgre_des_ip_changeantes(self):
        """X-Forwarded-For peut être forgé : la limite globale tient quand même."""
        for i in range(maximum('mot_de_passe_oublie', 'global') + 1):
            self.client.post(self.url, {'email': f'x{i}@exemple.org'},
                             HTTP_X_FORWARDED_FOR=f'10.0.{i // 250}.{i % 250}')
        self.client.post(self.url, {'email': 'awa@exemple.org'},
                         HTTP_X_FORWARDED_FOR='203.0.113.9')
        self.assertEqual(len(mail.outbox), 0)


class TestDemandeAdhesion(TestCase):

    def setUp(self):
        self.section = fabrique.section()
        self.url = reverse('adhesions:soumettre')

    def donnees(self, i=0, **extra):
        return {'nom': 'KONE', 'prenoms': 'Awa', 'email': f'awa{i}@exemple.org',
                'telephone': '0102030405', 'grade': 'Assistante', 'section': self.section.pk,
                'motivation': 'Adhérer.', 'pieces-TOTAL_FORMS': '1',
                'pieces-INITIAL_FORMS': '0', 'pieces-MIN_NUM_FORMS': '0',
                'pieces-MAX_NUM_FORMS': '1000', 'pieces-0-type_piece': '', **extra}

    def donnees_valides(self, i):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return {**self.donnees(i), 'pieces-0-type_piece': 'DIPLOME',
                'pieces-0-fichier': SimpleUploadedFile('diplome.pdf', b'%PDF-1.4 test',
                                                       content_type='application/pdf')}

    def test_trop_de_demandes_depuis_une_meme_adresse(self):
        for i in range(maximum('demande_adhesion', 'ip')):
            self.assertEqual(self.client.post(self.url, self.donnees_valides(i)).status_code, 200)
        reponse = self.client.post(self.url, self.donnees_valides(99))
        self.assertEqual(reponse.status_code, 429)
        self.assertContains(reponse, 'réessayer', status_code=429)
        self.assertEqual(DemandeAdhesion.objects.count(), maximum('demande_adhesion', 'ip'))

    def test_les_saisies_incompletes_ne_comptent_pas(self):
        for i in range(maximum('demande_adhesion', 'ip') + 3):
            self.client.post(self.url, self.donnees(i, nom=''))        # refusées
        self.assertEqual(self.client.post(self.url, self.donnees_valides(1)).status_code, 200)
        self.assertEqual(DemandeAdhesion.objects.count(), 1)

    def test_le_champ_piege_simule_le_succes_sans_rien_enregistrer(self):
        reponse = self.client.post(self.url, self.donnees(site_web='http://spam.example'))
        self.assertTemplateUsed(reponse, 'adhesions/confirmation.html')
        self.assertFalse(DemandeAdhesion.objects.exists())
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(JournalOperation.objects.filter(type_operation='ROBOT_DETECTE').exists())

    def test_le_champ_piege_est_invisible_pour_une_personne(self):
        page = self.client.get(self.url)
        self.assertContains(page, 'name="site_web"')
        self.assertContains(page, 'aria-hidden="true"')
