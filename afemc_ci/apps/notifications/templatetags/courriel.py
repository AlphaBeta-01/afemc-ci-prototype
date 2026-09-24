"""Filtres de présentation des courriels HTML."""
from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def fcfa(valeur):
    """« 25000.00 » -> « 25 000 FCFA » (espaces insécables, pas de centimes).

    Les montants arrivent en chaîne dans `contexte` (JSON) : une valeur
    illisible est restituée telle quelle plutôt que de faire échouer l'envoi.
    """
    try:
        montant = Decimal(str(valeur))
    except (InvalidOperation, ValueError):
        return valeur
    if montant == montant.to_integral_value():
        texte = f'{montant:,.0f}'
    else:
        texte = f'{montant:,.2f}'.replace('.', '#')
    return texte.replace(',', ' ').replace('#', ',') + ' FCFA'


@register.filter
def virgule(valeur):
    """« 78.4 » -> « 78,4 » : séparateur décimal français."""
    return str(valeur).replace('.', ',')
