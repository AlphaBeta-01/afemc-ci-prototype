"""Composition et acheminement des messages (§ 5.6.3)."""
import time

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import Context, Template, TemplateDoesNotExist
from django.template.loader import get_template, render_to_string
from django.templatetags.static import static
from django.utils import timezone
from django.utils.module_loading import import_string

from .models import Notification


class ErreurEnvoi(Exception):
    """Échec d'acheminement d'une notification."""


def creer_notification(destinataire, type_notification, objet, gabarit, contexte,
                       membre=None, relance=None, canal=Notification.Canal.EMAIL,
                       piece_jointe_generateur=''):
    """Persiste la notification puis tente aussitôt de l'envoyer (§ 5.6.3).

    L'échec de cette tentative immédiate — panne du fournisseur, gabarit
    invalide, etc. — est toujours absorbé par `_tenter_envoi`, jamais
    propagé : la personne qui vient de soumettre une demande d'adhésion ou
    de créer un compte ne doit jamais voir sa page échouer à cause d'un
    problème d'envoi de courriel. `acheminer_notifications_en_attente` reste
    le filet de sécurité qui réessaiera ce qui n'est pas parti du premier
    coup (§ 7 du README, cron toutes les 15 min).

    `piece_jointe_generateur` : chemin Python pointillé d'une fonction
    optionnelle, résolue dynamiquement à l'envoi plutôt qu'importée ici —
    même raisonnement que EMAIL_BACKEND ou AUTH_USER_MODEL : cette
    application ne doit jamais avoir besoin de connaître apps.cotisations
    ou toute autre app pour rester réutilisable (§ guide, apps/notifications).
    """
    notification = Notification.objects.create(
        destinataire=destinataire, membre=membre, relance=relance,
        type=type_notification, canal=canal, objet=objet,
        gabarit=gabarit, contexte=contexte,
        piece_jointe_generateur=piece_jointe_generateur)
    _tenter_envoi(notification)
    return notification


def rendre_gabarit(gabarit, contexte):
    """Rend un gabarit de courriel en texte brut.

    Django échappe le HTML par défaut même dans un fichier `.txt` (via
    `render_to_string`) : une simple apostrophe dans un nom de section
    devenait « &#x27; » dans le corps du message. Sans objet pour un
    courriel en texte brut — l'échappement est donc désactivé ici, une fois
    pour tous les gabarits, plutôt que dans chacun d'eux.
    """
    source = get_template(gabarit).template.source
    return Template('{% autoescape off %}' + source + '{% endautoescape %}').render(
        Context(contexte))


def rendre_gabarit_html(gabarit, contexte):
    """Rend la version HTML d'un courriel, ou None s'il n'en a pas.

    Par convention, la version HTML de `notifications/x.txt` est
    `notifications/x.html` : rien à changer dans les appels existants, ni
    dans les notifications déjà en base (`Notification.gabarit` reste le
    `.txt`), ni dans les règles de relance dont le gabarit a été ajusté
    dans l'admin — une règle pointant vers un `.txt` sans jumeau HTML part
    simplement en texte brut, comme avant.

    Contrairement à `rendre_gabarit`, l'échappement reste actif : les
    valeurs du contexte (nom d'une candidate, motif saisi…) proviennent
    de saisies et ne doivent jamais pouvoir injecter de balises.
    """
    if not gabarit.endswith('.txt'):
        return None
    try:
        get_template(gabarit[:-4] + '.html')
    except TemplateDoesNotExist:
        return None
    return render_to_string(gabarit[:-4] + '.html', {**_contexte_commun(), **contexte})


def _contexte_commun():
    """Valeurs disponibles dans tous les courriels HTML, calculées à l'envoi."""
    try:
        chemin_logo = static('img/logo-afemc-email.png')
    except ValueError:      # manifeste des fichiers statiques incomplet
        chemin_logo = '/static/img/logo-afemc-email.png'
    return {'site_url': settings.SITE_URL,
            'logo_url': settings.SITE_URL + chemin_logo,
            'annee': timezone.now().year}


def envoyer_courriel(destinataire, objet, corps, piece_jointe=None, html=None):
    """`piece_jointe` : tuple (nom_fichier, contenu_bytes, type_mime) optionnel.

    `html` : version mise en forme du message, jointe en alternative au
    texte brut (multipart/alternative) — la messagerie du destinataire
    affiche la meilleure qu'elle sait lire ; le texte brut reste la
    version de repli (messageries en mode texte, lecteurs d'écran, filtres
    anti-spam, qui pénalisent un courriel en HTML seul).
    """
    try:
        message = EmailMultiAlternatives(objet, corps, settings.EMAIL_EXPEDITEUR,
                                         [destinataire])
        if html:
            message.attach_alternative(html, 'text/html')
        if piece_jointe:
            message.attach(*piece_jointe)
        envoyes = message.send(fail_silently=False)
    except Exception as err:                # noqa: BLE001
        raise ErreurEnvoi(str(err)) from err
    if not envoyes:
        raise ErreurEnvoi('Aucun message accepté par le service de messagerie.')
    return envoyes


def _generer_piece_jointe(notification):
    """Résout et appelle le générateur de pièce jointe s'il y en a un.

    Régénérée à chaque tentative plutôt que stockée (comme le corps du
    courriel, cf. `rendre_gabarit`) : évite de conserver un PDF en base
    pour une donnée déjà entièrement présente dans `contexte`.
    """
    if not notification.piece_jointe_generateur:
        return None
    generateur = import_string(notification.piece_jointe_generateur)
    return generateur(notification.contexte)


def _tenter_envoi(notification):
    """Une tentative d'envoi ; met à jour et sauvegarde la notification.

    Capture largement (pas seulement `ErreurEnvoi`) : un gabarit invalide
    (`rendre_gabarit`) ne doit pas plus faire échouer l'appelant qu'une
    panne du fournisseur de messagerie — les deux sont un échec d'envoi du
    point de vue de cette notification, à comptabiliser et à réessayer.
    """
    maximum = settings.MAX_TENTATIVES_NOTIFICATION
    try:
        corps = rendre_gabarit(notification.gabarit, notification.contexte)
        html = rendre_gabarit_html(notification.gabarit, notification.contexte)
        piece_jointe = _generer_piece_jointe(notification)
        envoyer_courriel(notification.destinataire, notification.objet, corps,
                         piece_jointe, html=html)
    except Exception as err:                # noqa: BLE001
        notification.tentatives += 1
        notification.derniere_erreur = str(err)[:255]
        if notification.tentatives >= maximum:
            notification.statut = Notification.Statut.ECHEC
        notification.save()
        return False
    notification.statut = Notification.Statut.ENVOYEE
    notification.date_envoi = timezone.now()
    notification.save()
    return True


def acheminer_notifications_en_attente(taille_lot=100, budget_secondes=60):
    """Rattrape ce que l'envoi immédiat de `creer_notification` n'a pas pu
    délivrer (panne passagère, notification créée avant ce mécanisme…).
    Filet de sécurité plutôt que voie normale — voir § 5.6.3 et le README § 7.

    `budget_secondes` borne le temps total, pas seulement `taille_lot` le
    nombre d'éléments : un grand nombre de notifications en échec (chacune
    pouvant consommer jusqu'à REQUESTS_TIMEOUT secondes côté fournisseur)
    cumulerait sinon un temps largement supérieur au délai du serveur
    d'application (--timeout de gunicorn, voir render.yaml), faisant
    planter la requête HTTP qui a déclenché cet acheminement (§ 7 du
    README). Le reliquat non traité reste EN_ATTENTE et sera repris au
    passage suivant (toutes les 15 min), sans rien perdre.
    """
    maximum = settings.MAX_TENTATIVES_NOTIFICATION
    en_attente = (Notification.objects
                  .filter(statut=Notification.Statut.EN_ATTENTE,
                          tentatives__lt=maximum)
                  .order_by('cree_le')[:taille_lot])
    debut = time.monotonic()
    envoyees, echecs = 0, 0
    for notification in en_attente:
        if time.monotonic() - debut > budget_secondes:
            break
        if _tenter_envoi(notification):
            envoyees += 1
        else:
            echecs += 1
    return envoyees, echecs
