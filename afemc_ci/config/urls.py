"""Routage principal de l'application."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(pattern_name='dashboard:accueil'), name='racine'),
    path('comptes/', include('apps.accounts.urls')),
    path('sections/', include('apps.sections.urls')),
    path('membres/', include('apps.membres.urls')),
    path('adhesions/', include('apps.adhesions.urls')),
    path('cotisations/', include('apps.cotisations.urls')),
    path('relances/', include('apps.relances.urls')),
    path('tableau-de-bord/', include('apps.dashboard.urls')),
]

if settings.DEBUG:
    # Sert les pièces justificatives déposées, uniquement hors production
    # (un vrai déploiement les sert via le serveur web ou un stockage dédié).
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
