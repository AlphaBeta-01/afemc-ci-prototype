from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.core.decorators import role_requis
from apps.cotisations.services import indicateurs_exercice

from .models import Section


@login_required
def liste(requete):
    sections = Section.objects.all()
    if not requete.user.voit_toutes_les_sections and requete.user.section_id:
        sections = sections.filter(pk=requete.user.section_id)
    return render(requete, 'sections/liste.html', {'sections': sections})


@login_required
@role_requis('ADMIN', 'RESP_ADMIN', 'RESP_FINANCIER', 'RESP_SECTION')
def detail(requete, pk):
    section = get_object_or_404(Section, pk=pk)
    if not requete.user.voit_toutes_les_sections and requete.user.section_id != section.pk:
        raise PermissionDenied("Section hors de votre périmètre.")
    exercice = int(requete.GET.get('exercice', timezone.localdate().year))
    return render(requete, 'sections/detail.html', {
        'section': section,
        'exercice': exercice,
        'indicateurs': indicateurs_exercice(exercice, section=section),
        'membres': section.membres.select_related('section').order_by('nom')[:50],
    })
