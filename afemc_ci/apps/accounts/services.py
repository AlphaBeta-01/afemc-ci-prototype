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
                      Utilisateur.Role.RESP_FINANCIER, Utilisateur.Role.RESP_ORGA)


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

    Réservé à la Présidente (RG08) : seuls Secrétaire générale, Coordinatrice
    de section et Trésorière sont attribuables ici — un compte Présidente
    reste du ressort de l'administration Django (`createsuperuser`).
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


class NominationImpossible(Exception):
    """Nomination ou fin de fonctions refusée ; le message s'adresse à la Présidente."""


def nommer_responsable(membre, role, section=None, nomme_par=None, requete=None):
    """Confie une fonction de responsable à une membre du registre (RG13).

    Une responsable est d'abord une membre : sa fonction s'ajoute à son
    compte existant, jamais à un second compte — une personne, une fiche,
    un identifiant. Si la membre n'a pas encore de compte (ancienne membre
    jamais activée), il est créé, rattaché à sa fiche, et le courriel de
    nomination porte le lien d'activation.
    """
    from apps.membres.models import Membre

    if role not in ROLES_ATTRIBUABLES:
        raise NominationImpossible("Cette fonction ne peut pas être attribuée ici.")
    if membre.statut != Membre.Statut.ACTIF:
        raise NominationImpossible(
            f"{membre.nom_complet()} n'est pas une membre active "
            f"({membre.get_statut_display().lower()}) : impossible de la nommer.")
    if role == Utilisateur.Role.RESP_SECTION:
        section = section or membre.section
    else:
        section = None

    compte = membre.utilisateur or Utilisateur.objects.filter(
        email__iexact=membre.email).first()
    fiche_du_compte = getattr(compte, 'fiche_membre', None) if compte else None
    if fiche_du_compte is not None and fiche_du_compte.pk != membre.pk:
        raise NominationImpossible(
            f"L'adresse {membre.email} est déjà celle du compte d'une autre fiche "
            f"(n° d'adhérente {fiche_du_compte.matricule}) : vérifiez qu'il ne s'agit pas d'un doublon.")
    if compte and compte.role == Utilisateur.Role.ADMIN:
        raise NominationImpossible(
            "Le compte de la Présidente ne peut pas recevoir une autre fonction.")
    if compte and compte.role == role and compte.section_id == getattr(section, 'pk', None):
        raise NominationImpossible(
            f"{membre.nom_complet()} occupe déjà cette fonction.")

    if compte is None:
        compte = Utilisateur.objects.create_user(
            email=membre.email, password=None, nom=membre.nom, prenoms=membre.prenoms,
            role=role, section=section, is_active=False)
        ancien_role = 'aucun compte'
    else:
        ancien_role = compte.get_role_display()
        compte.role = role
        compte.section = section
        compte.save(update_fields=['role', 'section'])
    if membre.utilisateur_id != compte.pk:
        membre.utilisateur = compte
        membre.save(update_fields=['utilisateur'])

    fonction = compte.get_role_display() + (f' — {section.libelle}' if section else '')
    journaliser(nomme_par, 'NOMINATION_RESPONSABLE',
                f'{membre.matricule} — {membre.nom_complet()} : {fonction} '
                f'(précédemment : {ancien_role})', requete)
    creer_notification(
        destinataire=compte.email,
        type_notification='NOMINATION_RESPONSABLE',
        objet=f'Vous avez été nommée {compte.get_role_display()} — AFEMC-CI',
        gabarit='notifications/nomination.txt',
        contexte={'nom': membre.nom_complet(), 'role': compte.get_role_display(),
                  'section': section.libelle if section else '',
                  'lien': '' if compte.is_active else generer_lien_activation(compte),
                  'connexion': f"{settings.SITE_URL}{reverse('accounts:connexion')}"},
        membre=membre)
    return compte


def mettre_fin_aux_fonctions(compte, par=None, requete=None):
    """Retire sa fonction à une responsable (RG13) : le retrait des droits
    est immédiat, dès la requête suivante — le rôle est relu en base à
    chaque requête.

    Une responsable membre du registre redevient simple membre : elle
    garde son compte, son historique et ses cotisations. Un compte externe
    (créé hors registre, sans fiche membre) n'a plus de raison d'accéder à
    la plateforme : il est désactivé.
    """
    if compte.role not in ROLES_ATTRIBUABLES:
        raise NominationImpossible("Ce compte n'exerce aucune fonction à retirer.")
    if par is not None and compte.pk == par.pk:
        raise NominationImpossible("Vous ne pouvez pas mettre fin à vos propres fonctions.")

    ancienne_fonction = compte.get_role_display() + (
        f' — {compte.section.libelle}' if compte.section_id else '')
    fiche = getattr(compte, 'fiche_membre', None)
    compte.role = Utilisateur.Role.MEMBRE
    compte.section = fiche.section if fiche else None
    if fiche is None:
        compte.is_active = False
    compte.save(update_fields=['role', 'section', 'is_active'])

    journaliser(par, 'FIN_FONCTIONS',
                f'{compte.email} : fin de fonctions de {ancienne_fonction}'
                + ('' if fiche else ' — compte externe désactivé'), requete)
    creer_notification(
        destinataire=compte.email,
        type_notification='FIN_FONCTIONS',
        objet='Fin de vos fonctions — AFEMC-CI',
        gabarit='notifications/fin_fonctions.txt',
        contexte={'nom': compte.nom_complet(), 'fonction': ancienne_fonction,
                  'reste_membre': fiche is not None},
        membre=fiche)
    return compte
