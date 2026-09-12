"""Utilitaires partagés."""
from django.core.paginator import Paginator


def paginer(selection, requete, taille=25):
    paginator = Paginator(selection, taille)
    return paginator.get_page(requete.GET.get('page'))
