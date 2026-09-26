"""Utilitaires partagés."""
import unicodedata

from django.core.paginator import Paginator
from django.db.models.functions import Lower


def paginer(selection, requete, taille=25):
    paginator = Paginator(selection, taille)
    return paginator.get_page(requete.GET.get('page'))


def ordre_alphabetique(prefixe=''):
    """Critères de tri A → Z par nom puis prénoms, pour `.order_by(*...)`.

    `Lower` rend le tri insensible à la casse : les noms sont saisis tantôt
    en capitales (« KOUAME »), tantôt non (« Bamba », « N'Dri »), et un tri
    brut placerait toutes les capitales avant les minuscules — c'est le cas
    sous SQLite ; sous PostgreSQL, cela dépend de la collation de la base.
    `prefixe` : chemin vers le membre, ex. 'membre__' ou 'cotisation__membre__'.
    """
    return (Lower(f'{prefixe}nom'), Lower(f'{prefixe}prenoms'))


def cle_alphabetique(texte):
    """Clé de tri insensible à la casse et aux accents (« Émilie » ≈ « emilie »)."""
    decompose = unicodedata.normalize('NFKD', texte or '')
    return ''.join(c for c in decompose if not unicodedata.combining(c)).casefold()


def trier_par_nom(objets, personne=lambda o: o):
    """Trie en Python une petite sélection déjà extraite (encadrés du tableau
    de bord), quand l'ordre de sélection — les plus urgents, les plus récents —
    diffère de l'ordre d'affichage, alphabétique."""
    return sorted(objets, key=lambda o: (cle_alphabetique(personne(o).nom),
                                         cle_alphabetique(personne(o).prenoms)))
