"""Limites de fréquence des formulaires publics (demande d'adhésion, mot de passe oublié).

Sans elles, un robot pouvait soumettre ces formulaires en boucle : chaque
envoi déclenche des courriels, et le quota du service de messagerie
(300 par jour sur l'offre gratuite de Brevo) pouvait être épuisé en quelques
minutes — plus aucune relance, aucun reçu, aucun lien d'activation ne
partait alors de la journée ; les pièces jointes pouvaient aussi remplir le
disque.

Deux niveaux se cumulent :
- par adresse IP, efficace contre un abus ordinaire — mais contournable,
  l'adresse étant lue dans X-Forwarded-For, qu'un robot peut forger ;
- globaux, sur l'ensemble du site : impossibles à contourner, calibrés pour
  qu'un robot ne puisse jamais consommer plus d'environ la moitié du quota
  quotidien de courriels, en laissant largement passer l'usage réel.

Les compteurs vivent dans le cache Django, adossé à la base de données
(voir CACHES) : ils survivent aux redémarrages et sont partagés entre les
processus du serveur.
"""
from dataclasses import dataclass

from django.core.cache import cache

from .services import extraire_ip, journaliser

HEURE, JOUR = 3600, 86400


@dataclass(frozen=True)
class Limite:
    portee: str          # 'ip', 'global' ou 'cible' (ex. une adresse électronique)
    maximum: int
    periode: int         # en secondes


# Usage réel attendu : quelques demandes d'adhésion et réinitialisations par
# jour au plus. Chaque demande d'adhésion envoie 2 courriels (Présidente et
# Secrétaire générale), chaque réinitialisation 1 : au pire, 40 × 2 + 60 = 140
# courriels par jour consommés par un robot, sur les 300 du quota.
LIMITES = {
    'demande_adhesion': (Limite('ip', 5, HEURE), Limite('global', 15, HEURE),
                         Limite('global', 40, JOUR)),
    'mot_de_passe_oublie': (Limite('ip', 5, HEURE), Limite('cible', 3, HEURE),
                            Limite('global', 20, HEURE), Limite('global', 60, JOUR)),
}


def limite_atteinte(action, requete, cible=''):
    """Compte cette tentative ; vrai si l'une des limites de `action` est dépassée.

    Chaque tentative est comptée, même refusée : un robot qui insiste ne fait
    que prolonger son propre blocage. Le dépassement est journalisé (RG09).
    """
    ip = extraire_ip(requete) or 'inconnue'
    depassee = None
    for limite in LIMITES[action]:
        valeur = {'ip': ip, 'global': '*', 'cible': (cible or '').lower()}[limite.portee]
        cle = f'limite:{action}:{limite.portee}:{limite.periode}:{valeur}'
        cache.add(cle, 0, timeout=limite.periode)
        try:
            nombre = cache.incr(cle)
        except ValueError:          # clé expirée entre add() et incr()
            cache.set(cle, 1, timeout=limite.periode)
            nombre = 1
        if nombre > limite.maximum and depassee is None:
            depassee = limite
    if depassee:
        journaliser(None, 'LIMITE_ATTEINTE',
                    f'{action} — {depassee.portee} : plus de {depassee.maximum} '
                    f'en {depassee.periode // 60} min', requete)
    return depassee is not None
