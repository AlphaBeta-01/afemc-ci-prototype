"""Routage principal de l'application."""
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

# `MEDIA_URL`/`MEDIA_ROOT` (config/settings/base.py) ne sont volontairement PAS
# montés ici, même en développement : les pièces justificatives d'adhésion
# (§ 5.5.4) sont des documents d'identité sensibles et ne doivent être
# accessibles que via la vue authentifiée `adhesions:telecharger_piece`
# (revue de sécurité) — jamais par un lien direct, non protégé, vers le
# stockage. Un déploiement réel doit appliquer la même règle : ne jamais
# faire servir `MEDIA_ROOT` tel quel par le serveur web ou un bucket public.
