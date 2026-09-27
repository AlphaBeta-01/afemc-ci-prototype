from io import BytesIO

from django import forms
from django.utils import timezone

from .models import ChiffreCle, PageAccueil, PhotoGalerie, Realisation

CLASSE = {'class': 'form-control'}
TAILLE_MAX_PHOTO = 8 * 1024 * 1024
DIMENSION_PHOTO = 800


def preparer_photo(fichier, dimension=DIMENSION_PHOTO, avec_taille=False):
    """Photo de portrait : orientation corrigée, 800 px au plus, JPEG allégé.

    Ré-encoder l'image la débarrasse aussi de ses métadonnées (EXIF : lieu de
    prise de vue, appareil…) avant sa publication sur une page publique.
    """
    from PIL import Image, ImageOps

    fichier.seek(0)
    image = ImageOps.exif_transpose(Image.open(fichier)).convert('RGB')
    image.thumbnail((dimension, dimension), Image.LANCZOS)
    sortie = BytesIO()
    image.save(sortie, format='JPEG', quality=85, optimize=True, progressive=True)
    if avec_taille:
        return sortie.getvalue(), image.size
    return sortie.getvalue()


class FormulairePageAccueil(forms.ModelForm):
    photo = forms.ImageField(
        label='Photo de la Présidente', required=False,
        help_text='JPG ou PNG, 8 Mo maximum. Elle est allégée automatiquement.',
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/jpeg,image/png'}))
    retirer_photo = forms.BooleanField(label='Retirer la photo actuelle', required=False)

    class Meta:
        model = PageAccueil
        fields = ['accroche', 'sous_titre', 'presentation', 'mission',
                  'presidente_nom', 'presidente_titre', 'presidente_presentation',
                  'presidente_message',
                  'email_contact', 'site_institutionnel', 'contenu_verifie']
        widgets = {
            'accroche': forms.TextInput(attrs=CLASSE),
            'sous_titre': forms.TextInput(attrs=CLASSE),
            'presentation': forms.Textarea(attrs={**CLASSE, 'rows': 6}),
            'mission': forms.Textarea(attrs={**CLASSE, 'rows': 5}),
            'presidente_nom': forms.TextInput(attrs=CLASSE),
            'presidente_titre': forms.TextInput(attrs=CLASSE),
            'presidente_presentation': forms.Textarea(attrs={**CLASSE, 'rows': 6}),
            'presidente_message': forms.Textarea(attrs={**CLASSE, 'rows': 5}),
            'email_contact': forms.EmailInput(attrs=CLASSE),
            'site_institutionnel': forms.URLInput(attrs=CLASSE),
            'contenu_verifie': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, peut_valider=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not peut_valider:          # la validation du contenu revient à la Présidente
            del self.fields['contenu_verifie']

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo and photo.size > TAILLE_MAX_PHOTO:
            raise forms.ValidationError('La photo dépasse 8 Mo.')
        return photo

    def save(self, commit=True):
        page = super().save(commit=False)
        if self.cleaned_data.get('photo'):
            page.presidente_photo = preparer_photo(self.cleaned_data['photo'])
            page.presidente_photo_maj = timezone.now()
        elif self.cleaned_data.get('retirer_photo'):
            page.presidente_photo = None
            page.presidente_photo_maj = timezone.now()
        if commit:
            page.save()
        return page


FormsetChiffres = forms.modelformset_factory(
    ChiffreCle, fields=['valeur', 'libelle', 'precision', 'ordre'], extra=1, can_delete=True,
    widgets={'valeur': forms.TextInput(attrs=CLASSE), 'libelle': forms.TextInput(attrs=CLASSE),
             'precision': forms.TextInput(attrs=CLASSE),
             'ordre': forms.NumberInput(attrs={**CLASSE, 'min': 0})})

FormsetRealisations = forms.modelformset_factory(
    Realisation, fields=['annee', 'periode', 'titre', 'description', 'source', 'publiee'],
    extra=1, can_delete=True,
    widgets={'annee': forms.NumberInput(attrs={**CLASSE, 'min': 1900, 'max': 2100}),
             'periode': forms.TextInput(attrs=CLASSE), 'titre': forms.TextInput(attrs=CLASSE),
             'description': forms.Textarea(attrs={**CLASSE, 'rows': 2}),
             'source': forms.TextInput(attrs=CLASSE),
             'publiee': forms.CheckboxInput(attrs={'class': 'form-check-input'})})


DIMENSION_GALERIE = 1600
MAX_PHOTOS_PAR_ENVOI = 12


class EnvoiMultiple(forms.ClearableFileInput):
    allow_multiple_selected = True


class ChampPhotos(forms.ImageField):
    """Plusieurs images en un seul envoi ; chacune est validée comme une image."""

    def clean(self, donnees, initial=None):
        fichiers = donnees if isinstance(donnees, (list, tuple)) else [donnees]
        fichiers = [f for f in fichiers if f]
        if len(fichiers) > MAX_PHOTOS_PAR_ENVOI:
            raise forms.ValidationError(f'{MAX_PHOTOS_PAR_ENVOI} photos au plus par envoi.')
        propres = []
        for fichier in fichiers:
            if fichier.size > TAILLE_MAX_PHOTO:
                raise forms.ValidationError(f'« {fichier.name} » dépasse 8 Mo.')
            propres.append(super().clean(fichier, initial))
        return propres


class FormulaireAjoutPhotos(forms.Form):
    photos = ChampPhotos(
        label='Ajouter des photos', required=False,
        help_text=f'JPG ou PNG, jusqu\'à {MAX_PHOTOS_PAR_ENVOI} à la fois, 8 Mo maximum chacune. '
                  'Elles sont allégées automatiquement ; ajoutez ensuite une légende.',
        widget=EnvoiMultiple(attrs={'class': 'form-control', 'accept': 'image/jpeg,image/png',
                                    'multiple': True}))

    def enregistrer(self):
        premier_ordre = (PhotoGalerie.objects.order_by('-ordre').values_list('ordre', flat=True)
                         .first() or 0) + 1
        for rang, fichier in enumerate(self.cleaned_data.get('photos') or []):
            donnees, (largeur, hauteur) = preparer_photo(fichier, DIMENSION_GALERIE,
                                                         avec_taille=True)
            PhotoGalerie.objects.create(image=donnees, largeur=largeur, hauteur=hauteur,
                                        ordre=premier_ordre + rang)
        return len(self.cleaned_data.get('photos') or [])


FormsetGalerie = forms.modelformset_factory(
    PhotoGalerie, fields=['legende', 'ordre', 'publiee'], extra=0, can_delete=True,
    widgets={'legende': forms.TextInput(attrs=CLASSE),
             'ordre': forms.NumberInput(attrs={**CLASSE, 'min': 0}),
             'publiee': forms.CheckboxInput(attrs={'class': 'form-check-input'})})
