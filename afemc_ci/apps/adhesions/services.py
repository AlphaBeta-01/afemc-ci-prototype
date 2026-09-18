"""Machine à états du processus d'adhésion (§ 5.5.4)."""
from datetime import date

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.services import journaliser
from apps.membres.models import Membre
from apps.notifications.services import creer_notification

from .models import DemandeAdhesion

S = DemandeAdhesion.Statut

TRANSITIONS = {
    S.EN_ATTENTE: {S.EN_EXAMEN, S.REJETEE},
    S.EN_EXAMEN: {S.VALIDEE, S.REJETEE},
    # INFOS_REQUISES n'est plus proposé pour une nouvelle demande (retiré du
    # processus à la demande de la Présidente/Secrétaire générale) — cette
    # ligne reste uniquement pour qu'une demande déjà dans cet état avant ce
    # changement ne se retrouve pas bloquée sans transition possible.
    S.INFOS_REQUISES: {S.EN_EXAMEN, S.REJETEE},
    S.VALIDEE: set(),      # état terminal
    S.REJETEE: set(),      # état terminal
}


class TransitionInterdite(Exception):
    """Transition non prévue par le processus statutaire."""


class MembreExistant(Exception):
    """Un membre porte déjà cette adresse (contrainte d'unicité, § 5.2.2)."""


def creer_membre_depuis_demande(demande):
    membre = Membre.objects.create(
        nom=demande.nom, prenoms=demande.prenoms, email=demande.email,
        telephone=demande.telephone, grade=demande.grade,
        etablissement=demande.etablissement, section=demande.section,
        date_adhesion=date.today())
    demande.membre = membre
    return membre


def emettre_cotisation_initiale(membre):
    from apps.cotisations.models import Cotisation
    exercice = date.today().year
    cotisation, _ = Cotisation.objects.get_or_create(
        membre=membre, exercice=exercice,
        defaults={'montant_du': settings.COTISATION_MONTANT_DEFAUT,
                  'date_echeance': date(exercice, 12, 31)})
    return cotisation


def creer_compte_acces(membre):
    """Crée le compte d'accès du nouveau membre, inactif jusqu'à activation (RG11).

    Aucun mot de passe n'est fixé ici : le membre en choisit un lui-même via le
    lien d'activation envoyé par courriel (cf. `envoyer_lien_activation`).
    """
    from apps.accounts.models import Utilisateur

    compte = Utilisateur.objects.filter(email=membre.email).first()
    if compte is None:
        compte = Utilisateur.objects.create_user(
            email=membre.email, password=None, nom=membre.nom, prenoms=membre.prenoms,
            role=Utilisateur.Role.MEMBRE, section=membre.section, is_active=False)
    membre.utilisateur = compte
    membre.save(update_fields=['utilisateur'])
    return compte


def envoyer_lien_activation(compte, membre):
    """Envoie le courriel contenant le lien de définition du mot de passe."""
    from apps.accounts.services import generer_lien_activation

    return creer_notification(
        destinataire=compte.email,
        type_notification='ACTIVATION_COMPTE',
        objet='Activez votre compte AFEMC-CI',
        gabarit='notifications/activation.txt',
        contexte={'membre': membre.nom_complet(), 'lien': generer_lien_activation(compte)},
        membre=membre)


def regulariser_comptes_membres(simulation=False):
    """Comble les comptes d'accès manquants pour des membres déjà admis (RG11).

    Filet de rattrapage : une demande peut avoir été validée alors que
    `creer_compte_acces` n'était pas encore déployé (mise à jour du code en
    cours d'exploitation), ou tout autre incident ayant laissé le compte
    manquant. Idempotent : sans effet sur un membre déjà pourvu d'un compte.
    """
    demandes = (DemandeAdhesion.objects
                .filter(statut=S.VALIDEE, membre__isnull=False,
                        membre__utilisateur__isnull=True)
                .select_related('membre'))

    membres = [demande.membre for demande in demandes]
    if simulation:
        return membres

    for membre in membres:
        compte = creer_compte_acces(membre)
        journaliser(None, 'CREATION_COMPTE_MEMBRE',
                    f'{membre.matricule} — {compte.email} (régularisation)')
        envoyer_lien_activation(compte, membre)
    return membres


@transaction.atomic
def changer_statut(demande, nouveau_statut, utilisateur=None, motif=''):
    if nouveau_statut not in TRANSITIONS[demande.statut]:
        raise TransitionInterdite(
            f'Transition {demande.statut} -> {nouveau_statut} non autorisée')
    ancien = demande.statut
    demande.statut = nouveau_statut
    demande.traitee_par = utilisateur
    demande.date_traitement = timezone.now()
    demande.motif = motif
    if nouveau_statut == S.VALIDEE:
        if Membre.objects.filter(email=demande.email).exists():
            raise MembreExistant(
                f'{demande.email} est déjà l\'adresse d\'un membre existant — '
                'vérifiez qu\'il ne s\'agit pas d\'une demande en double.')
        membre = creer_membre_depuis_demande(demande)
        emettre_cotisation_initiale(membre)
        compte = creer_compte_acces(membre)
        journaliser(utilisateur, 'CREATION_COMPTE_MEMBRE',
                    f'{membre.matricule} — {compte.email}')
        envoyer_lien_activation(compte, membre)
    demande.save()
    journaliser(utilisateur, 'CHANGEMENT_STATUT_ADHESION',
                f'demande {demande.pk} : {ancien} -> {nouveau_statut}')
    notifier_candidate(demande)
    return demande


def notifier_nouvelle_demande(demande):
    """Prévient la Présidente et la Secrétaire générale d'un dépôt.

    Sans ce signal, une demande peut rester longtemps invisible : personne ne
    consulte spontanément l'écran des adhésions en l'absence d'une raison de
    le faire.

    Chaque notification tente un envoi immédiat (§ 5.6.3) : sans risque ici
    pour le délai de la requête HTTP de la candidate, car les destinataires
    (Présidente + Secrétaire générale) sont des rôles du bureau national, en
    nombre naturellement restreint — pas un par section. Si ce périmètre
    s'élargissait un jour à des rôles proportionnels au nombre de sections,
    il faudrait alors plafonner les envois immédiats comme
    `acheminer_notifications_en_attente` plafonne son temps total.
    """
    from apps.accounts.models import Utilisateur

    destinataires = Utilisateur.objects.filter(
        role__in=[Utilisateur.Role.ADMIN, Utilisateur.Role.RESP_ADMIN], is_active=True)
    notifications = []
    for responsable in destinataires:
        notifications.append(creer_notification(
            destinataire=responsable.email,
            type_notification='NOUVELLE_DEMANDE_ADHESION',
            objet=f"Nouvelle demande d'adhésion — {demande.nom_complet()}",
            gabarit='notifications/nouvelle_demande.txt',
            contexte={'candidate': demande.nom_complet(),
                      'section': demande.section.libelle,
                      'etablissement': demande.etablissement,
                      'date_soumission': demande.date_soumission.strftime('%d/%m/%Y')}))
    return notifications


def notifier_candidate(demande):
    return creer_notification(
        destinataire=demande.email,
        type_notification='SUIVI_ADHESION',
        objet=f'Votre demande d\'adhésion — {demande.get_statut_display()}',
        gabarit='notifications/adhesion.txt',
        contexte={'candidate': demande.nom_complet(),
                  'statut': demande.get_statut_display(),
                  'section': demande.section.libelle,
                  'motif': demande.motif})
