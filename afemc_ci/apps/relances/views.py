from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.core.decorators import role_requis
from apps.core.utils import ordre_alphabetique, paginer
from apps.membres.models import Membre

from .models import Relance, RegleRelance


@login_required
@role_requis('ADMIN', 'RESP_ADMIN', 'RESP_FINANCIER')          # pas RESP_SECTION
def liste(requete):
    relances = (Relance.objects
                .filter(cotisation__membre__in=Membre.objects.visibles_par(requete.user))
                .select_related('regle', 'cotisation', 'cotisation__membre')
                .order_by(*ordre_alphabetique('cotisation__membre__'), '-date_emission'))
    return render(requete, 'relances/liste.html', {
        'page': paginer(relances, requete),
        'regles': RegleRelance.objects.all(),
    })
