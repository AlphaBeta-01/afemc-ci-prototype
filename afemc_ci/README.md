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

### Mot de passe oublié

Un compte déjà actif peut réinitialiser son mot de passe depuis la page de
connexion (« Mot de passe oublié ? » → `/comptes/mot-de-passe-oublie/`). La
réponse est identique que l'adresse corresponde ou non à un compte, pour ne
jamais révéler quelles adresses sont enregistrées. Le lien envoyé est
strictement le même mécanisme que l'activation initiale (`VueActivation`) :
un compte pas encore activé peut donc aussi s'en servir pour obtenir un
nouveau lien si le premier a expiré.

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
| Tests unitaires | 111 | core, accounts, membres, adhesions, cotisations, notifications, dashboard, sections |
| Scénarios du moteur (SC01-SC24) | 26 | `apps/relances/tests/test_moteur.py` |
| Tests d'intégration (TI01-TI13) | 13 | `apps/cotisations/tests/test_integration.py` |
| Tests fonctionnels (TF01-TF30) | 30 | `apps/core/tests/test_fonctionnels.py` (TF08/TF16b adaptés ; TF26-TF30 nouveaux) |
| Tests de sécurité (TS01-TS12) | 12 | `apps/core/tests/test_securite.py` (TS11-TS12 nouveaux) |
| **Total** | **192** | couverture : **95 %** du code applicatif (mesurée contre PostgreSQL) |

Les 66 tests supplémentaires (par rapport aux 126 initiaux du chapitre 6)
couvrent l'activation de compte et la réinitialisation de mot de passe
(RG11), le rattrapage des comptes manquants (§ 2, « Compte du membre admis »,
et § 3, `regulariser_comptes_membres`), le périmètre resserré du responsable
financier et du responsable de section (RG08), et les pièces justificatives
exigées à la soumission d'une demande d'adhésion (RG12, ci-dessous).

**TF26-TF30** rejouent, de bout en bout depuis l'interface, les scénarios
ajoutés après la rédaction initiale du chapitre 6 : activation d'un compte
membre, mot de passe oublié, création d'un compte responsable, périmètre
resserré du responsable de section, rejet d'une demande sans document.
**TS11-TS12** formalisent les deux failles trouvées et corrigées lors de la
revue de sécurité (accès au détail d'une section, accès à une pièce
justificative). Si le corps du mémoire doit en rendre compte, ce sont ces
identifiants qu'il convient de citer.

### Nouvelles règles de gestion (RG11, RG12)

Le texte du mémoire (§ 4.4) numérote RG01 à RG10. Après consultation de ce
texte, deux règles introduites cette session ont reçu un numéro propre plutôt
que de réemployer RG01 ou RG02 — qui désignent déjà, respectivement,
l'unicité du membre (matricule) et son rattachement à une section, sans
rapport avec ces ajouts (une première version de ce README, écrite avant
consultation du texte, avait réemployé ces deux numéros par erreur ; le code
et les tests ont depuis été corrigés) :

- **RG11 — Activation et réinitialisation du mot de passe du compte d'un
  membre.** Le compte d'un membre nouvellement admis est créé inactif ; un
  lien à usage unique, valable 3 jours, permet de définir le mot de passe et
  active le compte. Le même mécanisme sert de réinitialisation en
  libre-service pour un compte déjà actif (« mot de passe oublié »), avec une
  réponse strictement identique que l'adresse existe ou non, pour ne jamais
  révéler quelles adresses sont enregistrées.
- **RG12 — Pièces justificatives et complétude de la demande d'adhésion.**
  Une demande d'adhésion doit comporter au moins un document attestant la
  qualité d'enseignante chercheure de la candidate (carte professionnelle,
  attestation d'exercice ou diplôme — formats PDF/JPG/PNG, 5 Mo maximum), et
  l'ensemble des champs du formulaire public sont obligatoires.

**Périmètre du responsable de section et du responsable financier — vérifié,
aucune divergence.** Confronté aux chapitres 3, 4 et 5 du mémoire : § 3.2.4
(responsable de section) ne mentionne que la consultation des membres de sa
section ; § 3.2.5 (responsable financier) limite son rôle aux cotisations,
échéances et retards, sans jamais mentionner les adhésions ; le tableau 6
(§ 4.6.2) confirme la même délimitation pour la « Coordinatrice de section »
et la « Trésorière » ; § 5.5 ne décrit qu'un filtrage des *membres* par
section. Le resserrement de périmètre effectué cette session (retrait des
cotisations/adhésions/relances pour ces deux rôles) était donc déjà conforme
au texte du mémoire — c'était une omission du contrôle d'accès dans le code
d'origine, pas un écart avec la spécification, maintenant corrigée.

Une seule formulation reste ambiguë et mérite d'être relue avec attention :
l'interprétation du diagramme de cas d'utilisation (§ 4.6.2) indique que
« les tableaux de bord... se déclinent en deux niveaux... restituant l'état
des adhésions, l'effectif, les cotisations, les retards... », ce qui peut se
lire soit comme l'ensemble des indicateurs disponibles à travers les deux
niveaux combinés (cohérent avec le tableau de bord de section actuel,
effectif uniquement), soit comme suggérant que le niveau section affiche
aussi adhésions et cotisations (ce qui contredirait l'implémentation). À
clarifier côté rédaction si le doute subsiste.

### Revue de sécurité

Deux failles de contrôle d'accès identifiées et corrigées :

- **`/sections/<id>/`** n'était protégée que par la connexion, pas par le
  rôle : un simple membre pouvait consulter les indicateurs financiers et le
  registre de sa section (jusqu'à 50 fiches). Restreint aux responsables
  (`role_requis`), cohérent avec le reste de l'application.
- **Pièces justificatives d'adhésion** : le lien affiché à la personne qui
  traite une demande pointait directement vers `MEDIA_URL`, sans aucune
  vérification de rôle sur le fichier lui-même — n'importe qui connaissant
  ou devinant l'URL pouvait télécharger les pièces d'identité déposées.
  `MEDIA_URL` n'est plus servie par Django ; les documents ne sont
  accessibles que via `adhesions:telecharger_piece`, une vue authentifiée,
  restreinte à `ADMIN`/`RESP_ADMIN` et journalisée (RG09). Un déploiement
  réel doit appliquer la même règle : ne jamais faire servir `MEDIA_ROOT`
  tel quel par le serveur web ou un stockage public.

### Pièces justificatives d'une demande d'adhésion

Le formulaire public (`/adhesions/demande/`) exige désormais au moins un
document attestant la qualité d'enseignante chercheure de la candidate
(carte professionnelle, attestation d'exercice ou diplôme). Formats acceptés :
PDF, JPG, PNG — 5 Mo maximum par fichier. Les documents déposés sont visibles
par le responsable administratif au moment du traitement
(`/adhesions/<id>/traiter/`), ainsi que dans l'administration Django.

Les fichiers sont stockés sous `media/adhesions/pieces/<id de la demande>/` ;
`MEDIA_ROOT` est défini dans `config/settings/base.py`. `MEDIA_URL` n'est
volontairement montée nulle part dans `config/urls.py` — ce sont des documents
d'identité, jamais accessibles par lien direct, y compris en développement.
Ils ne sont servis que par la vue authentifiée `adhesions:telecharger_piece`,
réservée à `ADMIN`/`RESP_ADMIN` (revue de sécurité). Un déploiement réel doit
appliquer la même règle : ne jamais faire servir `MEDIA_ROOT` tel quel par le
serveur web ou un stockage public.

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
| E.11 | Tableau de bord du responsable de section | `/tableau-de-bord/` (connecté en responsable de section) |
| E.12 | Gestion des comptes responsables | `/comptes/responsables/` |
| E.13 | Création d'un compte responsable | `/comptes/responsables/nouveau/` |
| E.14 | Activation de compte / définition du mot de passe | lien reçu par courriel (création de compte ou adhésion validée) |
| E.15 | Mot de passe oublié | `/comptes/mot-de-passe-oublie/` |

Les figures 20, 21 et 28 (architecture en couches, enchaînement du moteur,
architecture de déploiement) sont des schémas à réaliser sous StarUML ou draw.io,
et non des captures d'écran.

La figure E.5 (formulaire public d'adhésion) doit désormais montrer la
section « Pièces justificatives » ajoutée au formulaire. La figure 26
(traitement des demandes d'adhésion) gagne à montrer un dossier avec au
moins un document déposé, visible via le lien « Ouvrir ».

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
