"""Règles d'accès et opérations sur les activités (RG14).

Trois niveaux :
- la Responsable à l'organisation (et la Présidente, qui supervise) gère
  toutes les activités : création, publication, clôture, annulation,
  composition des comités ;
- une membre du comité d'organisation gère la seule activité qui lui est
  déléguée : elle en modifie la fiche et suit les inscriptions, sans
  pouvoir la publier, l'annuler, ni toucher au comité ou à d'autres
  activités ;
- toute membre voit les activités publiées ou terminées qui la concernent
  (nationales, ou de sa section) et s'inscrit aux activités à venir.
Les activités en préparation ne sont visibles que de celles qui les gèrent.
"""
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.urls import reverse

from apps.core.services import journaliser

from .models import Activite, Inscription, MembreComite

ROLES_GESTION = ('ADMIN', 'RESP_ORGA')


class OperationImpossible(Exception):
    """Opération refusée ; le message s'adresse à l'utilisatrice."""


def _fiche(utilisateur):
    return getattr(utilisateur, 'fiche_membre', None)


def gere_les_activites(utilisateur):
    return utilisateur.is_authenticated and utilisateur.role in ROLES_GESTION


def est_au_comite(utilisateur, activite):
    fiche = _fiche(utilisateur)
    return fiche is not None and activite.comite.filter(membre=fiche).exists()


def peut_modifier(utilisateur, activite):
    return gere_les_activites(utilisateur) or est_au_comite(utilisateur, activite)


def peut_voir(utilisateur, activite):
    if peut_modifier(utilisateur, activite):
        return True
    if activite.statut not in (Activite.Statut.PUBLIEE, Activite.Statut.TERMINEE):
        return False
    return activite.est_nationale or activite.section_id == _section_de(utilisateur)


def _section_de(utilisateur):
    fiche = _fiche(utilisateur)
    return fiche.section_id if fiche else utilisateur.section_id


def activites_visibles(utilisateur):
    """Activités qu'elle peut ouvrir : toutes pour celles qui gèrent ; sinon
    les publiées ou terminées qui la concernent, plus celles de ses comités."""
    if gere_les_activites(utilisateur):
        return Activite.objects.all()
    fiche = _fiche(utilisateur)
    ouvertes = Q(statut__in=[Activite.Statut.PUBLIEE, Activite.Statut.TERMINEE]) & (
        Q(section__isnull=True) | Q(section_id=_section_de(utilisateur)))
    if fiche is not None:
        ouvertes |= Q(comite__membre=fiche)
    return Activite.objects.filter(ouvertes).distinct()


def peut_s_inscrire(utilisateur, activite):
    from apps.membres.models import Membre

    fiche = _fiche(utilisateur)
    return (fiche is not None and fiche.statut == Membre.Statut.ACTIF
            and activite.inscriptions_ouvertes
            and (activite.est_nationale or activite.section_id == fiche.section_id))


# ------------------------------------------------------------------ actions
def changer_statut(activite, statut, par, requete=None):
    """Publier, clôturer ou annuler : décision réservée à celles qui gèrent."""
    S = Activite.Statut
    transitions = {
        S.EN_PREPARATION: {S.PUBLIEE, S.ANNULEE},
        S.PUBLIEE: {S.TERMINEE, S.ANNULEE, S.EN_PREPARATION},
        S.TERMINEE: set(),
        S.ANNULEE: {S.EN_PREPARATION},
    }
    if not gere_les_activites(par):
        raise OperationImpossible("Seule la Responsable à l'organisation peut changer "
                                  "le statut d'une activité.")
    if statut not in transitions[activite.statut]:
        raise OperationImpossible(f"Une activité « {activite.get_statut_display().lower()} » "
                                  f"ne peut pas passer à « {S(statut).label.lower()} ».")
    ancien = activite.get_statut_display()
    activite.statut = statut
    activite.save(update_fields=['statut', 'modifiee_le'])
    journaliser(par, 'STATUT_ACTIVITE',
                f'{activite.titre} : {ancien} -> {activite.get_statut_display()}', requete)


def ajouter_au_comite(activite, membre, mission, par, requete=None):
    from apps.membres.models import Membre
    from apps.notifications.services import creer_notification

    if not gere_les_activites(par):
        raise OperationImpossible("Seule la Responsable à l'organisation compose les comités.")
    if membre.statut != Membre.Statut.ACTIF:
        raise OperationImpossible(f"{membre.nom_complet()} n'est pas une membre active.")
    try:
        with transaction.atomic():
            MembreComite.objects.create(activite=activite, membre=membre, mission=mission,
                                        ajoutee_par=par)
    except IntegrityError:
        raise OperationImpossible(f"{membre.nom_complet()} fait déjà partie du comité.")
    journaliser(par, 'AJOUT_COMITE',
                f'{activite.titre} : {membre.matricule} — {membre.nom_complet()}', requete)
    from django.conf import settings
    creer_notification(
        destinataire=membre.email, type_notification='COMITE_ORGANISATION',
        objet=f"Comité d'organisation — {activite.titre}",
        gabarit='notifications/comite_organisation.txt',
        contexte={'nom': membre.nom_complet(), 'titre': activite.titre,
                  'date': activite.date_debut.strftime('%d/%m/%Y'), 'lieu': activite.lieu,
                  'mission': mission,
                  'lien': f"{settings.SITE_URL}{reverse('activites:detail', args=[activite.pk])}"},
        membre=membre)


def retirer_du_comite(membre_comite, par, requete=None):
    if not gere_les_activites(par):
        raise OperationImpossible("Seule la Responsable à l'organisation compose les comités.")
    journaliser(par, 'RETRAIT_COMITE',
                f'{membre_comite.activite.titre} : {membre_comite.membre.nom_complet()}', requete)
    membre_comite.delete()


def inscrire(activite, utilisateur, requete=None):
    if not peut_s_inscrire(utilisateur, activite):
        raise OperationImpossible("Les inscriptions ne sont pas ouvertes pour vous sur "
                                  "cette activité (complète, passée ou hors de votre section).")
    fiche = _fiche(utilisateur)
    with transaction.atomic():
        # Verrou sur l'activité : deux inscriptions simultanées ne peuvent pas
        # prendre ensemble la dernière place.
        activite = Activite.objects.select_for_update().get(pk=activite.pk)
        if activite.places_restantes == 0:
            raise OperationImpossible("Il n'y a plus de place disponible.")
        _, creee = Inscription.objects.get_or_create(activite=activite, membre=fiche)
    if creee:
        journaliser(utilisateur, 'INSCRIPTION_ACTIVITE', activite.titre, requete)


def desinscrire(activite, utilisateur, requete=None):
    fiche = _fiche(utilisateur)
    if fiche is None or not activite.est_a_venir:
        raise OperationImpossible("Cette inscription ne peut plus être annulée.")
    supprimees, _ = Inscription.objects.filter(activite=activite, membre=fiche).delete()
    if supprimees:
        journaliser(utilisateur, 'DESINSCRIPTION_ACTIVITE', activite.titre, requete)
