"""« À faire » : ce que chaque utilisatrice a à traiter aujourd'hui, selon sa fonction.

Recalculé à chaque consultation à partir des données, jamais stocké : la
liste reflète toujours l'état réel, sans tâche planifiée à maintenir.

Chaque tâche ne pointe que vers des écrans que la fonction concernée a le
droit d'ouvrir (RG08) : une Coordinatrice apprend qu'une membre de sa
section est en retard — ce que la relance R04 lui dit déjà par courriel —
mais sans montant ni accès aux écrans financiers.
"""
from dataclasses import dataclass, field
from datetime import timedelta

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

URGENT, A_FAIRE, A_SURVEILLER = 'urgent', 'a_faire', 'a_surveiller'
ORDRE_PRIORITES = {URGENT: 0, A_FAIRE: 1, A_SURVEILLER: 2}
LIBELLES_PRIORITES = {URGENT: 'Urgent', A_FAIRE: 'À faire', A_SURVEILLER: 'À surveiller'}

ELEMENTS_AFFICHES = 8          # au-delà, « et N autres » : la liste reste lisible
DEMANDE_EN_SOUFFRANCE_JOURS = 7
ECHEANCE_PROCHE_JOURS = 15
NOUVELLE_MEMBRE_JOURS = 7


@dataclass
class Element:
    """Une ligne nommée sous une tâche (une membre, une demande, une section)."""
    nom: str
    prenoms: str = ''
    detail: str = ''
    url: str = ''


@dataclass
class Tache:
    priorite: str
    titre: str
    explication: str
    nombre: int
    url: str = ''
    action: str = 'Traiter'
    elements: list = field(default_factory=list)

    @property
    def libelle_priorite(self):
        return LIBELLES_PRIORITES[self.priorite]

    @property
    def elements_affiches(self):
        return self.elements[:ELEMENTS_AFFICHES]

    @property
    def elements_masques(self):
        return max(0, len(self.elements) - ELEMENTS_AFFICHES)

    @property
    def elements_sont_des_personnes(self):
        return any(e.prenoms for e in self.elements)


def taches_pour(utilisateur):
    """Tâches de l'utilisatrice connectée, les plus urgentes d'abord."""
    from apps.accounts.models import Utilisateur
    R = Utilisateur.Role
    calcul = {
        R.ADMIN: _taches_presidente,
        R.RESP_ADMIN: _taches_secretaire_generale,
        R.RESP_FINANCIER: _taches_tresoriere,
        R.RESP_SECTION: _taches_coordinatrice,
        R.MEMBRE: _taches_membre,
    }.get(utilisateur.role)
    taches = [t for t in (calcul(utilisateur) if calcul else []) if t.nombre]
    return sorted(taches, key=lambda t: ORDRE_PRIORITES[t.priorite])


def compteur(taches):
    """Nombre affiché sur le bouton : ce qui demande une action, pas la veille."""
    return sum(1 for t in taches if t.priorite != A_SURVEILLER)


# ----------------------------------------------------------------- utilitaires
def _aujourdhui():
    return timezone.localdate()


def _fiche(membre):
    return reverse('membres:detail', args=[membre.pk])


def _ordre(prefixe=''):
    from apps.core.utils import ordre_alphabetique
    return ordre_alphabetique(prefixe)


def _fcfa(montant):
    from apps.notifications.templatetags.courriel import fcfa
    return fcfa(montant)


# -------------------------------------------------------- tâches partagées
def _demandes_a_traiter():
    from apps.adhesions.models import DemandeAdhesion

    demandes = list(DemandeAdhesion.objects
                    .filter(statut__in=[DemandeAdhesion.Statut.EN_ATTENTE,
                                        DemandeAdhesion.Statut.EN_EXAMEN])
                    .select_related('section').order_by(*_ordre()))
    if not demandes:
        return []
    limite = timezone.now() - timedelta(days=DEMANDE_EN_SOUFFRANCE_JOURS)
    anciennes = [d for d in demandes if d.date_soumission < limite]
    return [Tache(
        priorite=URGENT if anciennes else A_FAIRE,
        titre="Demandes d'adhésion à traiter",
        explication=(f"{len(anciennes)} attend(ent) une décision depuis plus de "
                     f"{DEMANDE_EN_SOUFFRANCE_JOURS} jours." if anciennes else
                     "Des candidates attendent une décision de validation ou de rejet."),
        nombre=len(demandes), url=reverse('adhesions:liste'), action='Voir les demandes',
        elements=[Element(d.nom, d.prenoms,
                          f"{d.section.libelle} · déposée le {d.date_soumission:%d/%m/%Y} · "
                          f"{d.get_statut_display().lower()}",
                          reverse('adhesions:traiter', args=[d.pk])) for d in demandes])]


def _cotisations_non_emises():
    from apps.cotisations.models import Cotisation
    from apps.membres.models import Membre

    exercice = _aujourdhui().year
    sans_cotisation = list(Membre.objects.filter(statut=Membre.Statut.ACTIF)
                           .exclude(cotisations__exercice=exercice)
                           .select_related('section').order_by(*_ordre()))
    if not sans_cotisation:
        return []
    deja_emises = Cotisation.objects.filter(exercice=exercice).exists()
    return [Tache(
        priorite=A_FAIRE,
        titre=f"Cotisations {exercice} à émettre",
        explication=("Ces membres actifs n'ont pas encore de cotisation pour l'exercice : "
                     "l'émission collective ne crée que celles qui manquent."
                     if deja_emises else
                     f"Aucune cotisation n'a encore été émise pour {exercice}."),
        nombre=len(sans_cotisation), url=reverse('cotisations:emettre'),
        action='Émettre les cotisations',
        elements=[Element(m.nom, m.prenoms, m.section.libelle, _fiche(m))
                  for m in sans_cotisation])]


def _retards_anciens(priorite, action_possible):
    """Retards de plus de 90 jours : la relance automatique s'arrête (R06),
    la suite relève d'un traitement humain."""
    from apps.cotisations.models import Cotisation

    limite = _aujourdhui() - timedelta(days=90)
    retards = list(Cotisation.objects
                   .filter(statut=Cotisation.Statut.EN_RETARD, date_echeance__lt=limite)
                   .select_related('membre', 'membre__section')
                   .order_by(*_ordre('membre__'), 'exercice'))
    if not retards:
        return []
    return [Tache(
        priorite=priorite,
        titre='Retards de plus de 90 jours',
        explication=("Les relances automatiques sont terminées : ces situations "
                     "demandent un contact direct." if action_possible else
                     "Relances automatiques terminées : situations suivies par la Trésorière."),
        nombre=len(retards), url=reverse('cotisations:liste') + '?statut=EN_RETARD',
        action='Voir les retards',
        elements=[Element(c.membre.nom, c.membre.prenoms,
                          f"{c.exercice} · reste {_fcfa(c.reste_a_payer)} · "
                          f"échéance {c.date_echeance:%d/%m/%Y}", _fiche(c.membre))
                  for c in retards])]


# ------------------------------------------------------------ par fonction
def _taches_presidente(utilisateur):
    from apps.accounts.models import Utilisateur
    from apps.notifications.models import Notification
    from apps.sections.models import Section

    R = Utilisateur.Role
    taches = []
    actifs = Utilisateur.objects.filter(is_active=True)

    for role, consequence in (
            (R.RESP_FINANCIER, "personne ne peut enregistrer de paiement"),
            (R.RESP_ADMIN, "la gestion administrative repose sur vous seule")):
        if not actifs.filter(role=role).exists():
            taches.append(Tache(
                priorite=URGENT if role == R.RESP_FINANCIER else A_FAIRE,
                titre=f"Aucune {R(role).label} en fonction",
                explication=f"Tant que la fonction est vacante, {consequence}.",
                nombre=1, url=reverse('accounts:nommer'), action='Nommer une responsable'))

    # Une même responsable doit être à la fois Coordinatrice ET active : un
    # exclude() sur deux conditions d'une relation multiple ne le garantit pas.
    coordonnees = actifs.filter(role=R.RESP_SECTION).values('section_id')
    sans_coordinatrice = list(Section.objects.filter(active=True)
                              .exclude(pk__in=coordonnees).order_by('libelle'))
    if sans_coordinatrice:
        taches.append(Tache(
            priorite=A_FAIRE, titre='Sections sans Coordinatrice',
            explication="Personne ne suit les membres de ces sections au quotidien.",
            nombre=len(sans_coordinatrice), url=reverse('accounts:nommer'),
            action='Nommer une Coordinatrice',
            elements=[Element(s.libelle, detail=s.etablissement or s.ville,
                              url=reverse('sections:detail', args=[s.pk]))
                      for s in sans_coordinatrice]))

    taches += _demandes_a_traiter()
    taches += _cotisations_non_emises()

    echecs = Notification.objects.filter(statut=Notification.Statut.ECHEC).count()
    if echecs:
        taches.append(Tache(
            priorite=A_FAIRE, titre='Courriels non distribués',
            explication="Trois tentatives ont échoué (adresse erronée, panne du service…). "
                        "Vérifiez l'adresse puis renvoyez-les.",
            nombre=echecs, url=reverse('notifications:liste') + '?statut=ECHEC',
            action='Voir les courriels'))

    en_attente = list(Utilisateur.objects
                      .filter(role__in=[R.RESP_ADMIN, R.RESP_FINANCIER, R.RESP_SECTION],
                              is_active=False)
                      .order_by(*_ordre()))
    en_attente = [u for u in en_attente if not u.has_usable_password()]
    if en_attente:
        taches.append(Tache(
            priorite=A_SURVEILLER, titre="Responsables n'ayant pas activé leur compte",
            explication="Si le lien reçu a expiré, elles peuvent en obtenir un nouveau "
                        "avec « Mot de passe oublié ? » sur la page de connexion.",
            nombre=len(en_attente), url=reverse('accounts:comptes_liste'),
            action='Voir les responsables',
            elements=[Element(u.nom, u.prenoms, u.get_role_display()) for u in en_attente]))

    taches += _retards_anciens(A_SURVEILLER, action_possible=False)
    return taches


def _taches_secretaire_generale(utilisateur):
    from apps.membres.models import Membre

    taches = _demandes_a_traiter()
    sans_acces = list(Membre.objects.filter(statut=Membre.Statut.ACTIF,
                                            utilisateur__is_active=False)
                      .select_related('section', 'utilisateur').order_by(*_ordre()))
    sans_acces = [m for m in sans_acces if not m.utilisateur.has_usable_password()]
    if sans_acces:
        taches.append(Tache(
            priorite=A_SURVEILLER, titre="Membres n'ayant pas encore activé leur compte",
            explication="Le lien d'activation leur a été envoyé à leur admission. S'il a "
                        "expiré, elles peuvent en obtenir un nouveau avec « Mot de passe "
                        "oublié ? » sur la page de connexion.",
            nombre=len(sans_acces), url=reverse('membres:liste'), action='Voir les membres',
            elements=[Element(m.nom, m.prenoms, m.section.libelle, _fiche(m))
                      for m in sans_acces]))
    return taches


def _taches_tresoriere(utilisateur):
    from apps.cotisations.models import Cotisation

    aujourdhui = _aujourdhui()
    taches = _retards_anciens(URGENT, action_possible=True)

    retards_45 = list(Cotisation.objects
                      .filter(statut=Cotisation.Statut.EN_RETARD,
                              date_echeance__lt=aujourdhui - timedelta(days=45),
                              date_echeance__gte=aujourdhui - timedelta(days=90))
                      .select_related('membre').order_by(*_ordre('membre__')))
    if retards_45:
        taches.append(Tache(
            priorite=A_FAIRE, titre='Retards de 45 à 90 jours',
            explication="La relance R05 vous a été adressée en copie : un rappel "
                        "personnel peut débloquer la situation.",
            nombre=len(retards_45), url=reverse('cotisations:liste') + '?statut=EN_RETARD',
            action='Voir les retards',
            elements=[Element(c.membre.nom, c.membre.prenoms,
                              f"reste {_fcfa(c.reste_a_payer)} · "
                              f"{(aujourdhui - c.date_echeance).days} jours de retard",
                              _fiche(c.membre)) for c in retards_45]))

    taches += _cotisations_non_emises()

    partiels = list(Cotisation.objects.filter(statut=Cotisation.Statut.PARTIEL)
                    .select_related('membre').order_by(*_ordre('membre__')))
    if partiels:
        taches.append(Tache(
            priorite=A_SURVEILLER, titre='Paiements partiels à solder',
            explication="Un premier versement a été reçu, le solde reste à encaisser.",
            nombre=len(partiels), url=reverse('cotisations:liste') + '?statut=PARTIEL',
            action='Voir les cotisations',
            elements=[Element(c.membre.nom, c.membre.prenoms,
                              f"{c.exercice} · reste {_fcfa(c.reste_a_payer)}",
                              _fiche(c.membre)) for c in partiels]))

    proches = list(Cotisation.objects
                   .filter(statut__in=[Cotisation.Statut.EN_ATTENTE, Cotisation.Statut.PARTIEL],
                           date_echeance__gte=aujourdhui,
                           date_echeance__lte=aujourdhui + timedelta(days=ECHEANCE_PROCHE_JOURS))
                   .select_related('membre').order_by(*_ordre('membre__')))
    if proches:
        taches.append(Tache(
            priorite=A_SURVEILLER,
            titre=f"Échéances dans les {ECHEANCE_PROCHE_JOURS} prochains jours",
            explication="Les membres concernés reçoivent automatiquement les rappels R01 et R02.",
            nombre=len(proches), url=reverse('cotisations:liste'), action='Voir les cotisations',
            elements=[Element(c.membre.nom, c.membre.prenoms,
                              f"échéance {c.date_echeance:%d/%m/%Y} · "
                              f"reste {_fcfa(c.reste_a_payer)}", _fiche(c.membre))
                      for c in proches]))
    return taches


def _taches_coordinatrice(utilisateur):
    from apps.cotisations.models import Cotisation
    from apps.membres.models import Membre
    from apps.relances.models import RegleRelance

    section = utilisateur.section
    if section is None:
        return []
    membres = Membre.objects.filter(section=section)
    taches = []

    # Seuil de la relance qui la met en copie (R04) : noms seulement, sans
    # montant — exactement ce que le courriel de relance lui apprend déjà.
    r04 = RegleRelance.objects.filter(code='R04', active=True).first()
    seuil = r04.decalage_jours if r04 else 15
    limite = _aujourdhui() - timedelta(days=seuil)
    en_retard = list(membres.filter(cotisations__statut=Cotisation.Statut.EN_RETARD,
                                    cotisations__date_echeance__lt=limite)
                     .distinct().order_by(*_ordre()))
    if en_retard:
        taches.append(Tache(
            priorite=A_FAIRE, titre='Membres de votre section à contacter',
            explication=f"Leur cotisation est en retard de plus de {seuil} jours. Un mot "
                        "de votre part peut aider ; le suivi financier reste assuré "
                        "par la Trésorière.",
            nombre=len(en_retard), action='',
            elements=[Element(m.nom, m.prenoms, url=_fiche(m)) for m in en_retard]))

    incompletes = list(membres.filter(statut=Membre.Statut.ACTIF)
                       .filter(Q(telephone='') | Q(grade='')).order_by(*_ordre()))
    if incompletes:
        taches.append(Tache(
            priorite=A_FAIRE, titre='Fiches à compléter',
            explication="Téléphone ou grade manquant : complétez-les pour faciliter le suivi.",
            nombre=len(incompletes), action='',
            elements=[Element(m.nom, m.prenoms,
                              ' et '.join(x for x, vide in (('téléphone', not m.telephone),
                                                            ('grade', not m.grade)) if vide)
                              + ' manquant',
                              reverse('membres:modifier', args=[m.pk]))
                      for m in incompletes]))

    depuis = timezone.now() - timedelta(days=NOUVELLE_MEMBRE_JOURS)
    nouvelles = list(membres.filter(cree_le__gte=depuis).order_by(*_ordre()))
    if nouvelles:
        taches.append(Tache(
            priorite=A_SURVEILLER, titre='Nouvelles membres à accueillir',
            explication=f"Arrivées dans votre section ces {NOUVELLE_MEMBRE_JOURS} derniers jours.",
            nombre=len(nouvelles), action='',
            elements=[Element(m.nom, m.prenoms, f"depuis le {m.cree_le:%d/%m/%Y}", _fiche(m))
                      for m in nouvelles]))

    ecartees = list(membres.filter(statut__in=[Membre.Statut.INACTIF, Membre.Statut.SUSPENDU])
                    .order_by(*_ordre()))
    if ecartees:
        taches.append(Tache(
            priorite=A_SURVEILLER, titre='Membres inactifs ou suspendus',
            explication="Membres de votre section qui ne participent plus aux cotisations.",
            nombre=len(ecartees), action='',
            elements=[Element(m.nom, m.prenoms, m.get_statut_display(), _fiche(m))
                      for m in ecartees]))
    return taches


def _taches_membre(utilisateur):
    from apps.cotisations.models import Cotisation

    fiche = getattr(utilisateur, 'fiche_membre', None)
    if fiche is None:
        return []
    aujourdhui = _aujourdhui()
    taches = []
    for c in (fiche.cotisations.exclude(statut=Cotisation.Statut.PAYEE)
              .order_by('date_echeance')):
        if c.date_echeance < aujourdhui:
            priorite, quand = URGENT, f"échéance dépassée depuis le {c.date_echeance:%d/%m/%Y}"
        elif c.date_echeance <= aujourdhui + timedelta(days=ECHEANCE_PROCHE_JOURS):
            priorite, quand = A_FAIRE, f"à régler avant le {c.date_echeance:%d/%m/%Y}"
        else:
            priorite, quand = A_SURVEILLER, f"échéance le {c.date_echeance:%d/%m/%Y}"
        taches.append(Tache(
            priorite=priorite, titre=f"Votre cotisation {c.exercice}",
            explication=f"Reste à payer : {_fcfa(c.reste_a_payer)}, {quand}. Le règlement "
                        "se fait auprès de la Trésorière.",
            nombre=1, url=_fiche(fiche), action='Voir ma fiche'))
    return taches
