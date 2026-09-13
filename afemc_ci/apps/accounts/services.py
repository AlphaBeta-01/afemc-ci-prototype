"""Services liés au compte utilisateur : activation, création de responsables."""
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.core.services import journaliser
from apps.notifications.services import creer_notification

from .models import Utilisateur

ROLES_ATTRIBUABLES = (Utilisateur.Role.RESP_ADMIN, Utilisateur.Role.RESP_SECTION,
                      Utilisateur.Role.RESP_FINANCIER)


def generer_lien_activation(compte):
    """Construit le lien à usage unique de définition du mot de passe (RG11).

    Factorisé ici car utilisé à la fois pour l'admission d'un membre
    (`apps.adhesions.services`) et pour la création d'un compte responsable.
    """
    uidb64 = urlsafe_base64_encode(force_bytes(compte.pk))
    token = default_token_generator.make_token(compte)
    return f"{settings.SITE_URL}{reverse('accounts:activation', args=[uidb64, token])}"


def creer_compte_responsable(nom, prenoms, email, role, section=None, cree_par=None):
    """Crée un compte de responsable, inactif jusqu'à activation par courriel.

    Réservé à l'Administrateur (RG08) : seuls RESP_ADMIN, RESP_SECTION et
    RESP_FINANCIER sont attribuables ici — un compte Administrateur reste du
    ressort de l'administration Django (`createsuperuser`).
    """
    compte = Utilisateur.objects.create_user(
        email=email, password=None, nom=nom, prenoms=prenoms,
        role=role, section=section, is_active=False)

    journaliser(cree_par, 'CREATION_COMPTE_RESPONSABLE',
                f'{compte.email} — {compte.get_role_display()}')

    creer_notification(
        destinataire=compte.email,
        type_notification='CREATION_COMPTE_RESPONSABLE',
        objet='Votre compte AFEMC-CI a été créé',
        gabarit='notifications/compte_responsable.txt',
        contexte={'nom': compte.nom_complet(), 'role': compte.get_role_display(),
                  'section': section.libelle if section else '',
                  'lien': generer_lien_activation(compte)})
    return compte


def demander_reinitialisation_mot_de_passe(email, requete=None):
    """Déclenche l'envoi d'un lien de définition du mot de passe (RG11).

    Le même lien sert aussi bien à activer un compte tout juste créé qu'à
    réinitialiser un mot de passe oublié — `VueActivation` gère les deux cas.
    Volontairement silencieuse si l'adresse n'existe pas, pour ne jamais
    révéler quelles adresses sont enregistrées ; toujours journalisée.
    """
    compte = Utilisateur.objects.filter(email__iexact=email).first()
    journaliser(None, 'DEMANDE_REINITIALISATION_MOT_DE_PASSE', email, requete)
    if compte is None:
        return None

    creer_notification(
        destinataire=compte.email,
        type_notification='REINITIALISATION_MOT_DE_PASSE',
        objet='Réinitialisation de votre mot de passe AFEMC-CI',
        gabarit='notifications/reinitialisation_mot_de_passe.txt',
        contexte={'nom': compte.nom_complet(), 'lien': generer_lien_activation(compte)})
    return compte
