"""Page d'accueil publique et sa modification par le Bureau."""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.activites.models import Activite
from apps.core.models import JournalOperation
from apps.core.tests import fabrique
from apps.vitrine.models import ChiffreCle, PageAccueil, Realisation


class TestPagePublique(TestCase):

    def test_accessible_sans_connexion_a_la_racine(self):
        reponse = self.client.get('/')
        self.assertEqual(reponse.status_code, 200)
        self.assertTemplateUsed(reponse, 'vitrine/accueil.html')
        self.assertContains(reponse, reverse('adhesions:soumettre'))
        self.assertContains(reponse, reverse('accounts:connexion'))
        self.assertNotContains(reponse, "Modifier la page d'accueil")

    def test_contenu_initial_issu_des_sources(self):
        """Prérempli par migration, chaque réalisation porte sa source."""
        reponse = self.client.get('/')
        self.assertContains(reponse, '1 000')
        self.assertContains(reponse, 'JSIFEC')
        self.assertContains(reponse, 'Source : Fraternité Matin, 20 mai 2026')
        self.assertContains(reponse, '22')                       # sections en 2026
        self.assertContains(reponse, 'NOBAH Céline Sidonie Koco')
        self.assertContains(reponse, 'réélue à l&#x27;unanimité')
        self.assertFalse(PageAccueil.objects.get().contenu_verifie)
        self.assertTrue(all(r.source for r in Realisation.objects.all()))

    def test_une_realisation_masquee_n_apparait_pas(self):
        Realisation.objects.filter(titre__contains='Korhogo').update(publiee=False)
        self.assertNotContains(self.client.get('/'), 'Korhogo')

    def test_seules_les_activites_annoncees_et_publiees_sont_montrees(self):
        demain = timezone.now() + timedelta(days=1)
        for titre, statut, annoncee in (('Colloque public', 'PUBLIEE', True),
                                        ('Réunion interne', 'PUBLIEE', False),
                                        ('Atelier en préparation', 'EN_PREPARATION', True)):
            Activite.objects.create(titre=titre, type='CONFERENCE', lieu='UVCI',
                                    date_debut=demain, statut=statut, annoncee=annoncee)
        reponse = self.client.get('/')
        self.assertContains(reponse, 'Colloque public')
        self.assertNotContains(reponse, 'Réunion interne')
        self.assertNotContains(reponse, 'Atelier en préparation')

    def test_aucune_donnee_personnelle(self):
        membre = fabrique.membre(nom='KONATE', email='konate@exemple.org')
        reponse = self.client.get('/')
        self.assertNotContains(reponse, 'KONATE')
        self.assertNotContains(reponse, membre.email)

    def test_une_personne_connectee_voit_mon_espace(self):
        self.client.force_login(fabrique.utilisateur('MEMBRE'))
        self.assertContains(self.client.get('/'), 'Mon espace')

    def test_les_pages_publiques_ramenent_a_l_accueil(self):
        for url in (reverse('accounts:connexion'), reverse('adhesions:soumettre')):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), "Retour à l'accueil")


class TestModification(TestCase):

    def setUp(self):
        self.presidente = fabrique.utilisateur('ADMIN')
        self.organisatrice = fabrique.utilisateur('RESP_ORGA')

    def donnees(self, **extra):
        page = PageAccueil.objects.get()
        donnees = {'accroche': 'Nouvelle accroche', 'sous_titre': page.sous_titre,
                   'presentation': page.presentation, 'mission': page.mission,
                   'email_contact': 'contact@afemc-ci.org',
                   'site_institutionnel': page.site_institutionnel,
                   'chiffres-TOTAL_FORMS': '0', 'chiffres-INITIAL_FORMS': '0',
                   'realisations-TOTAL_FORMS': '1', 'realisations-INITIAL_FORMS': '0',
                   'galerie-TOTAL_FORMS': '0', 'galerie-INITIAL_FORMS': '0',
                   'realisations-0-annee': '2026', 'realisations-0-titre': 'Nouvelle réalisation',
                   'realisations-0-source': 'Rapport du Bureau',
                   'realisations-0-publiee': 'on'}
        donnees.update(extra)
        return donnees

    def test_la_presidente_modifie_et_valide(self):
        self.client.force_login(self.presidente)
        self.assertContains(self.client.get(reverse('vitrine:modifier')), 'contenu relu et validé')
        self.client.post(reverse('vitrine:modifier'), self.donnees(contenu_verifie='on'))
        page = PageAccueil.objects.get()
        self.assertEqual(page.accroche, 'Nouvelle accroche')
        self.assertTrue(page.contenu_verifie)
        self.assertTrue(Realisation.objects.filter(titre='Nouvelle réalisation').exists())
        self.assertTrue(JournalOperation.objects.filter(
            type_operation='MODIFICATION_PAGE_ACCUEIL').exists())
        self.assertContains(self.client.get('/'), 'Nouvelle accroche')

    def test_la_responsable_a_l_organisation_modifie_sans_pouvoir_valider(self):
        self.client.force_login(self.organisatrice)
        self.assertNotContains(self.client.get(reverse('vitrine:modifier')), 'contenu relu et validé')
        self.client.post(reverse('vitrine:modifier'), self.donnees(contenu_verifie='on'))
        page = PageAccueil.objects.get()
        self.assertEqual(page.accroche, 'Nouvelle accroche')
        self.assertFalse(page.contenu_verifie)

    def test_supprimer_un_chiffre(self):
        chiffre = ChiffreCle.objects.first()
        self.client.force_login(self.presidente)
        self.client.post(reverse('vitrine:modifier'), self.donnees(**{
            'chiffres-TOTAL_FORMS': '1', 'chiffres-INITIAL_FORMS': '1',
            'chiffres-0-id': chiffre.pk, 'chiffres-0-valeur': chiffre.valeur,
            'chiffres-0-libelle': chiffre.libelle, 'chiffres-0-ordre': '0',
            'chiffres-0-DELETE': 'on'}))
        self.assertFalse(ChiffreCle.objects.filter(pk=chiffre.pk).exists())

    def test_reservee_a_la_presidente_et_a_la_responsable(self):
        for role in ('RESP_ADMIN', 'RESP_FINANCIER', 'RESP_SECTION', 'MEMBRE'):
            with self.subTest(role=role):
                self.client.force_login(fabrique.utilisateur(role, email=f'{role.lower()}@x.org'))
                self.assertEqual(self.client.get(reverse('vitrine:modifier')).status_code, 403)


class TestMotDeLaPresidente(TestCase):

    def setUp(self):
        self.presidente = fabrique.utilisateur('ADMIN')

    def image(self, largeur=1600, hauteur=2000, format_='PNG'):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        tampon = BytesIO()
        Image.new('RGB', (largeur, hauteur), (18, 32, 79)).save(tampon, format=format_)
        return SimpleUploadedFile(f'portrait.{format_.lower()}', tampon.getvalue())

    def envoyer(self, **extra):
        page = PageAccueil.objects.get()
        donnees = {'accroche': page.accroche, 'sous_titre': page.sous_titre,
                   'presentation': page.presentation, 'mission': page.mission,
                   'presidente_nom': 'Pr AKA Awa', 'presidente_titre': "Présidente de l'AFEMC-CI",
                   'presidente_message': 'Bienvenue à toutes.',
                   'chiffres-TOTAL_FORMS': '0', 'chiffres-INITIAL_FORMS': '0',
                   'realisations-TOTAL_FORMS': '0', 'realisations-INITIAL_FORMS': '0',
                   'galerie-TOTAL_FORMS': '0', 'galerie-INITIAL_FORMS': '0', **extra}
        self.client.force_login(self.presidente)
        return self.client.post(reverse('vitrine:modifier'), donnees)

    def test_section_masquee_tant_que_rien_n_est_renseigne(self):
        PageAccueil.objects.update(presidente_nom='', presidente_presentation='',
                                   presidente_message='')
        self.assertNotContains(self.client.get('/'), 'id="presidente"')

    def test_le_mot_de_bienvenue_n_est_pas_redige_a_sa_place(self):
        """Présentation à la troisième personne, sourcée ; le mot reste à écrire."""
        page = PageAccueil.objects.get()
        self.assertTrue(page.presidente_presentation)
        self.assertEqual(page.presidente_message, '')
        self.assertContains(self.client.get('/'), 'La Présidente')

    def test_photo_allegee_et_servie_publiquement(self):
        self.envoyer(photo=self.image())
        page = PageAccueil.objects.get()
        from io import BytesIO
        from PIL import Image
        image = Image.open(BytesIO(bytes(page.presidente_photo)))
        self.assertEqual(image.format, 'JPEG')
        self.assertLessEqual(max(image.size), 800)

        self.client.logout()
        accueil = self.client.get('/')
        self.assertContains(accueil, 'Le mot de la Présidente')
        self.assertContains(accueil, 'Pr AKA Awa')
        self.assertContains(accueil, reverse('vitrine:photo_presidente'))
        photo = self.client.get(reverse('vitrine:photo_presidente'))
        self.assertEqual(photo.status_code, 200)
        self.assertEqual(photo['Content-Type'], 'image/jpeg')

    def test_retirer_la_photo(self):
        self.envoyer(photo=self.image())
        self.envoyer(retirer_photo='on')
        self.assertFalse(PageAccueil.objects.get().a_une_photo)
        self.assertEqual(self.client.get(reverse('vitrine:photo_presidente')).status_code, 404)

    def test_un_fichier_qui_n_est_pas_une_image_est_refuse(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        reponse = self.envoyer(photo=SimpleUploadedFile('photo.png', b'<script>x</script>'))
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(PageAccueil.objects.get().a_une_photo)


class TestGalerie(TestCase):

    def setUp(self):
        self.presidente = fabrique.utilisateur('ADMIN')

    def image(self, nom='photo.jpg', taille=(2400, 1600)):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        tampon = BytesIO()
        Image.new('RGB', taille, (224, 18, 126)).save(tampon, format='JPEG')
        return SimpleUploadedFile(nom, tampon.getvalue(), content_type='image/jpeg')

    def envoyer(self, **extra):
        page = PageAccueil.objects.get()
        donnees = {'accroche': page.accroche, 'sous_titre': page.sous_titre,
                   'presentation': page.presentation, 'mission': page.mission,
                   'presidente_nom': page.presidente_nom, 'presidente_titre': page.presidente_titre,
                   'presidente_presentation': page.presidente_presentation,
                   'chiffres-TOTAL_FORMS': '0', 'chiffres-INITIAL_FORMS': '0',
                   'realisations-TOTAL_FORMS': '0', 'realisations-INITIAL_FORMS': '0',
                   'galerie-TOTAL_FORMS': '0', 'galerie-INITIAL_FORMS': '0', **extra}
        self.client.force_login(self.presidente)
        return self.client.post(reverse('vitrine:modifier'), donnees)

    def test_envoyer_plusieurs_photos_d_un_coup(self):
        from apps.vitrine.models import PhotoGalerie
        self.envoyer(photos=[self.image('a.jpg'), self.image('b.jpg', (900, 1400))])
        photos = list(PhotoGalerie.objects.all())
        self.assertEqual(len(photos), 2)
        self.assertLessEqual(max(photos[0].largeur, photos[0].hauteur), 1600)
        self.assertTrue(photos[0].paysage)
        self.assertFalse(photos[1].paysage)

        self.client.logout()
        accueil = self.client.get('/')
        self.assertContains(accueil, "L'association en images")
        self.assertEqual(self.client.get(reverse('vitrine:photo_galerie',
                                                 args=[photos[0].pk])).status_code, 200)

    def test_une_photo_masquee_n_est_ni_affichee_ni_servie(self):
        from apps.vitrine.models import PhotoGalerie
        self.envoyer(photos=[self.image()])
        photo = PhotoGalerie.objects.get()
        PhotoGalerie.objects.filter(pk=photo.pk).update(publiee=False)
        self.client.logout()
        self.assertNotContains(self.client.get('/'), "L'association en images")
        self.assertEqual(self.client.get(reverse('vitrine:photo_galerie',
                                                 args=[photo.pk])).status_code, 404)

    def test_legender_et_supprimer(self):
        from apps.vitrine.models import PhotoGalerie
        self.envoyer(photos=[self.image('a.jpg'), self.image('b.jpg')])
        a, b = PhotoGalerie.objects.order_by('pk')
        self.envoyer(**{'galerie-TOTAL_FORMS': '2', 'galerie-INITIAL_FORMS': '2',
                        'galerie-0-id': a.pk, 'galerie-0-legende': 'École d’été à Korhogo',
                        'galerie-0-ordre': '1', 'galerie-0-publiee': 'on',
                        'galerie-1-id': b.pk, 'galerie-1-legende': '', 'galerie-1-ordre': '2',
                        'galerie-1-DELETE': 'on'})
        self.assertEqual(PhotoGalerie.objects.get().legende, 'École d’été à Korhogo')

    def test_un_faux_fichier_image_est_refuse(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.vitrine.models import PhotoGalerie
        reponse = self.envoyer(photos=[SimpleUploadedFile('x.jpg', b'<html>pas une image</html>')])
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(PhotoGalerie.objects.exists())
