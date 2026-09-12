# Prototype — Système intelligent de gouvernance de l'AFEMC-CI

Prototype développé dans le cadre du mémoire de Master 2
« Étude et modélisation d'un système intelligent pour la gouvernance
des associations : cas de l'AFEMC-CI ».

Il implémente le périmètre décrit au chapitre 5 : authentification et rôles,
membres, sections, demandes d'adhésion, cotisations et paiements, moteur de
détection des retards, moteur de règles de relance, notifications et
tableau de bord décisionnel.

---

## 1. Installation

Prérequis : Python 3.11 ou supérieur.

```bash
cd afemc_ci
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

### Base de données

**Essai rapide (SQLite, sans rien installer)** — mettre `USE_SQLITE=1` dans `.env`,
ou exporter la variable :

```bash
export USE_SQLITE=1              # Windows : set USE_SQLITE=1
```

**Configuration conforme au mémoire (PostgreSQL)** — laisser `USE_SQLITE=0` et créer
la base :

```sql
CREATE DATABASE afemc_ci ENCODING 'UTF8';
CREATE USER afemc WITH PASSWORD 'motdepasse';
GRANT ALL PRIVILEGES ON DATABASE afemc_ci TO afemc;
```

Renseigner ensuite les variables `POSTGRES_*` dans `.env`.

## 2. Démarrage

```bash
python manage.py migrate
python manage.py charger_donnees_demo
python manage.py runserver
```

L'application est accessible sur http://127.0.0.1:8000/

### Comptes de démonstration

Mot de passe commun : `Afemc2026!Demo`

| Adresse                        | Rôle                       |
|--------------------------------|----------------------------|
| `admin@afemc-ci.org`           | Administrateur             |
| `administratif@afemc-ci.org`   | Responsable administratif  |
| `financier@afemc-ci.org`       | Responsable financier      |
| `section.abj@afemc-ci.org`     | Responsable de section     |

### Gestion des comptes responsables

Écran réservé à l'Administrateur (`/comptes/responsables/`) pour créer les
comptes des autres responsables — administratif, financier, de section —
sans passer par l'administration Django. Un compte Administrateur ne peut
pas être créé ici : cela reste du ressort de `createsuperuser`. Comme pour
un membre admis, le compte est créé inactif et un courriel avec lien
d'activation est envoyé ; l'Administrateur peut aussi désactiver/réactiver
un compte existant (sauf le sien).

### Compte du membre admis (activation par courriel)

Valider une demande d'adhésion (`/adhesions/<id>/traiter/`) ne se limite pas à créer
la fiche du registre : un compte `Utilisateur` de rôle *Membre* est créé automatiquement,
**inactif et sans mot de passe**. Un courriel contenant un lien d'activation valable
3 jours (gabarit `notifications/activation.txt`) est déposé dans la file de
notifications ; le membre y choisit son mot de passe (`/comptes/activation/<uid>/<jeton>/`)
et peut alors se connecter. En développement, ce courriel s'affiche dans la console
comme les relances.

La base des liens absolus insérés dans ces courriels se règle via la variable
`SITE_URL` (`.env`), par défaut `http://127.0.0.1:8000`.

## 3. Mécanismes automatisés

```bash
# Analyse sans écriture ni envoi (mode simulation, § 5.6.1)
python manage.py detecter_retards --simulation

# Exécution réelle : mise à jour des statuts et génération des relances
python manage.py detecter_retards

# Analyse à une date choisie (utile pour les démonstrations)
python manage.py detecter_retards --date 2026-12-31

# Acheminement de la file de notifications
python manage.py acheminer_notifications

# Filet de rattrapage : crée le compte et le lien d'activation des membres
# admis qui n'en ont pas encore (ex. déploiement du § 2 en cours d'exploitation)
python manage.py regulariser_comptes_membres --simulation   # aperçu sans écriture
python manage.py regulariser_comptes_membres
```

En développement, les courriels sont affichés dans la console : le contenu exact
des relances est donc visible sans configurer de service de messagerie.

### Exécution automatique (Celery)

Les commandes ci-dessus peuvent être lancées à la main, ou automatiquement par
Celery Beat selon la planification de `config/celery.py` (détection quotidienne
à 2h, acheminement toutes les 15 min, synthèse hebdomadaire le lundi à 7h).
Cela suppose Redis démarré (courtier `CELERY_BROKER_URL`, par défaut
`redis://localhost:6379/0`) et deux processus actifs en parallèle :

```bash
celery -A config worker -l info
celery -A config beat -l info
```

Sans ces deux processus (et sans Redis), rien ne se déclenche tout seul : il
faut alors invoquer les commandes manuellement, comme en développement.

## 4. Campagne de tests (chapitre 6)

```bash
# Tous les tests
python manage.py test apps --settings=config.settings.test

# Avec mesure de la couverture
coverage run manage.py test apps --settings=config.settings.test
coverage report
coverage html            # rapport détaillé dans htmlcov/index.html
```

Résultats attendus — ce sont les chiffres repris au chapitre 6 du mémoire :

| Catégorie | Nombre | Emplacement |
|-----------|--------|-------------|
| Tests unitaires | 94 | core, accounts, membres, adhesions, cotisations, notifications, dashboard |
| Scénarios du moteur (SC01-SC24) | 26 | `apps/relances/tests/test_moteur.py` |
| Tests d'intégration (TI01-TI13) | 13 | `apps/cotisations/tests/test_integration.py` |
| Tests fonctionnels (TF01-TF25) | 25 | `apps/core/tests/test_fonctionnels.py` (dont TF08 et TF16b, adaptés) |
| Tests de sécurité (TS01-TS10) | 10 | `apps/core/tests/test_securite.py` |
| **Total** | **169** | couverture : **95 %** du code applicatif |

Les 33 tests unitaires supplémentaires (par rapport aux 126 initiaux du chapitre 6)
couvrent l'activation de compte, le rattrapage des comptes manquants
(§ 2, « Compte du membre admis », et § 3, `regulariser_comptes_membres`),
le périmètre resserré du responsable financier et du responsable de section
(RG08), et les pièces justificatives exigées à la soumission d'une demande
d'adhésion (RG01, ci-dessous).

### Pièces justificatives d'une demande d'adhésion

Le formulaire public (`/adhesions/demande/`) exige désormais au moins un
document attestant la qualité d'enseignante chercheure de la candidate
(carte professionnelle, attestation d'exercice ou diplôme). Formats acceptés :
PDF, JPG, PNG — 5 Mo maximum par fichier. Les documents déposés sont visibles
par le responsable administratif au moment du traitement
(`/adhesions/<id>/traiter/`), ainsi que dans l'administration Django.

Les fichiers sont stockés sous `media/adhesions/pieces/<id de la demande>/` ;
`MEDIA_ROOT`/`MEDIA_URL` sont définis dans `config/settings/base.py`. En
développement, `runserver` les sert directement ; un déploiement réel doit
les servir via le serveur web ou un stockage dédié (hors périmètre du prototype).

La couverture exclut les migrations, les fichiers de test eux-mêmes et le script de
chargement des données de démonstration (voir `.coveragerc`).

## 5. Captures d'écran à réaliser pour le mémoire

| Figure | Écran | Chemin |
|--------|-------|--------|
| 22 | Interface d'authentification | `/comptes/connexion/` |
| 23 | Tableau de bord décisionnel | `/tableau-de-bord/` |
| 24 | Liste des membres avec filtres | `/membres/` |
| 25 | Fiche détaillée d'un membre | `/membres/1/` |
| 26 | Traitement des demandes d'adhésion | `/adhesions/` |
| 27 | Suivi des cotisations et retards | `/cotisations/?statut=EN_RETARD` |
| E.1 | Enregistrement d'un paiement | `/cotisations/1/paiement/` |
| E.2 | Historique des relances | `/relances/` |
| E.3 | Courriel de relance | console après `detecter_retards` |
| E.4 | Paramétrage des règles de relance | `/admin/relances/reglerelance/` |
| E.5 | Formulaire public d'adhésion | `/adhesions/demande/` |
| E.6 | Page de synthèse d'une section | `/sections/1/` |
| E.7 | Émission collective des cotisations | `/cotisations/emettre/` |
| E.8 | Journal des opérations | `/admin/core/journaloperation/` |
| E.9 | Rapport de couverture des tests | `htmlcov/index.html` |
| E.10 | Affichage sur terminal mobile | mode mobile du navigateur |

Les figures 20, 21 et 28 (architecture en couches, enchaînement du moteur,
architecture de déploiement) sont des schémas à réaliser sous StarUML ou draw.io,
et non des captures d'écran.

Pour obtenir des relances à afficher (figures 27 et 29), exécuter
`python manage.py detecter_retards` après le chargement des données.

## 6. Organisation du code

```
config/          configuration (base, dev, test, prod) et planification Celery
apps/core        journalisation, contrôle d'accès, utilitaires
apps/accounts    authentification, rôles et permissions
apps/sections    organisation territoriale
apps/membres     registre des membres
apps/adhesions   demandes d'adhésion et machine à états
apps/cotisations cotisations, paiements, exemptions
apps/relances    moteur de détection et règles de relance
apps/notifications file de messages et acheminement
apps/dashboard   indicateurs de pilotage
templates/       gabarits HTML (Bootstrap 5)
```
