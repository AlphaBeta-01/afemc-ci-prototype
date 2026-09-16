"""Point d'entrée pour un ordonnanceur externe (§ 7 du README).

Remplace Celery Beat là où l'hébergement ne propose pas de worker en
arrière-plan sur son plan gratuit (Render notamment) : un cron externe
(GitHub Actions) appelle cette vue à intervalle régulier plutôt que Beat
ne le fasse depuis un processus dédié. Le résultat pour l'application est
identique — mêmes fonctions de service, mêmes règles de gestion — seul le
déclencheur change.
"""
import hmac

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET


def _jeton_valide(requete):
    if not settings.CRON_SECRET:
        return False
    fourni = requete.headers.get('Authorization', '').removeprefix('Bearer ').strip()
    return hmac.compare_digest(fourni, settings.CRON_SECRET)


@require_GET
def executer_taches_planifiees(requete):
    """Détection des retards + acheminement des notifications.

    Prévu pour un appel toutes les 15 minutes (cf. .github/workflows/cron.yml).
    Exécuter la détection à cette fréquence plutôt qu'une fois par jour est
    sans coût réel à l'échelle de l'association (§ 6.3 : moins d'une seconde
    pour un millier de cotisations) et rattrape plus vite un retard récent.
    """
    if not _jeton_valide(requete):
        return JsonResponse({'erreur': 'jeton invalide'}, status=403)

    from apps.notifications.services import acheminer_notifications_en_attente
    from apps.relances.services import executer_detection

    resultat_detection = executer_detection()
    envoyees, echecs = acheminer_notifications_en_attente()

    if requete.GET.get('synthese') == '1':
        from apps.dashboard.tasks import envoyer_synthese
        envoyer_synthese()

    return JsonResponse({
        'horodatage': timezone.now().isoformat(),
        'detection': resultat_detection,
        'notifications_envoyees': envoyees,
        'notifications_echouees': echecs,
    })


@require_GET
def amorcer_administrateur(requete):
    """Crée le premier compte administrateur, sans accès Shell (§ 7 du README).

    Le Shell Render (seul autre moyen d'exécuter `createsuperuser`) exige le
    plan payant Starter. Idempotente : ne fait rien si un compte
    administrateur existe déjà, donc sans risque à laisser en place au-delà
    de la mise en service initiale.
    """
    if not _jeton_valide(requete):
        return JsonResponse({'erreur': 'jeton invalide'}, status=403)

    from apps.accounts.models import Utilisateur

    if Utilisateur.objects.filter(is_superuser=True).exists():
        return JsonResponse({'info': 'un compte administrateur existe déjà'})

    if not (settings.SUPERUSER_BOOTSTRAP_EMAIL and settings.SUPERUSER_BOOTSTRAP_PASSWORD):
        return JsonResponse(
            {'erreur': 'SUPERUSER_BOOTSTRAP_EMAIL / SUPERUSER_BOOTSTRAP_PASSWORD non configurés'},
            status=500)

    compte = Utilisateur.objects.create_superuser(
        email=settings.SUPERUSER_BOOTSTRAP_EMAIL,
        password=settings.SUPERUSER_BOOTSTRAP_PASSWORD,
        nom='Administratrice', prenoms='Principale')
    return JsonResponse({'cree': compte.email})


@require_GET
def diagnostiquer_smtp(requete):
    """Diagnostic temporaire de la connectivité SMTP sortante.

    Un worker gunicorn a été tué (SIGKILL, timeout 30 s) alors qu'il était
    bloqué dans `socket.connect()` vers le serveur SMTP de Brevo. Sans accès
    Shell sur le plan gratuit Render, cette vue teste directement, depuis
    l'environnement réel de production, si la résolution renvoie une adresse
    IPv6 injoignable (blocage fréquent sur les PaaS gratuits) ou si le
    blocage touche aussi l'IPv4 — à retirer une fois la cause confirmée.
    """
    if not _jeton_valide(requete):
        return JsonResponse({'erreur': 'jeton invalide'}, status=403)

    import socket
    import time

    hote, port = settings.EMAIL_HOST, settings.EMAIL_PORT
    resultats = {'hote': hote, 'port': port}

    try:
        adresses = socket.getaddrinfo(hote, port, proto=socket.IPPROTO_TCP)
        resultats['resolution'] = [
            {'famille': 'IPv6' if a[0] == socket.AF_INET6 else 'IPv4', 'adresse': a[4][0]}
            for a in adresses]
    except Exception as err:                # noqa: BLE001
        resultats['resolution_erreur'] = str(err)
        adresses = []

    for famille, nom in [(socket.AF_INET, 'IPv4'), (socket.AF_INET6, 'IPv6')]:
        cible = next((a for a in adresses if a[0] == famille), None)
        if cible is None:
            resultats[f'connexion_{nom}'] = 'aucune adresse de ce type'
            continue
        debut = time.monotonic()
        try:
            essai = socket.socket(famille, socket.SOCK_STREAM)
            essai.settimeout(6)
            essai.connect(cible[4])
            essai.close()
            resultats[f'connexion_{nom}'] = f'ok en {time.monotonic() - debut:.2f}s'
        except Exception as err:            # noqa: BLE001
            resultats[f'connexion_{nom}'] = (
                f'echec apres {time.monotonic() - debut:.2f}s : {err}')

    return JsonResponse(resultats)
