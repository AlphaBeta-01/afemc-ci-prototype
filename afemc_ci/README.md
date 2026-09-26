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
| `admin@afemc-ci.org`           | Présidente                 |
| `administratif@afemc-ci.org`   | Secrétaire générale        |
| `financier@afemc-ci.org`       | Trésorière                 |
| `section.abj@afemc-ci.org`     | Coordinatrice de section   |

Ces libellés (Présidente, Secrétaire générale, Trésorière, Coordinatrice de
section) sont ceux affichés dans l'interface ; les rôles internes
(`ADMIN`, `RESP_ADMIN`, `RESP_FINANCIER`, `RESP_SECTION`) n'ont pas changé,
pour ne pas affecter les comptes déjà créés en base.

### Responsables : nomination et fin de fonctions (RG13)

Une responsable — Secrétaire générale, Trésorière, Coordinatrice de
section — est **une membre de l'association à qui une fonction est
confiée**, pas un compte à part. Écran réservé à la Présidente
(`/comptes/responsables/`, menu « Responsables ») :

- **Nommer une responsable** (`/comptes/responsables/nommer/`, ou bouton
  « Nommer à une fonction » sur la fiche d'une membre) : la fonction
  s'ajoute au **compte existant** de la membre — même identifiant, même
  mot de passe. Seules les membres actives peuvent être nommées. Si la
  membre n'a pas encore de compte, il est créé, relié à sa fiche, et le
  courriel de nomination contient le lien d'activation. Une Coordinatrice
  prend par défaut la section de sa fiche.
- **Mettre fin aux fonctions** : le compte redevient un compte Membre ; la
  personne garde son accès, son historique et ses cotisations. Les droits
  de responsable sont retirés **immédiatement**, y compris pour une session
  déjà ouverte (le rôle est relu en base à chaque requête — TS13).
- **Compte externe** (`/comptes/responsables/nouveau/`), l'exception : une
  personne qui n'est pas dans le registre. Refusé pour une adresse déjà
  connue du registre (sinon la même personne aurait deux comptes). En fin
  de fonctions, un compte externe est désactivé.

Chaque nomination et fin de fonctions est journalisée (RG09) et notifiée
par courriel à la personne concernée. Le compte Présidente reste du ressort
de `createsuperuser` / `/taches/amorcer-admin/` et ne peut recevoir aucune
autre fonction ici. Une responsable voit ses propres cotisations sur sa
fiche (lien depuis « Mon profil »).

**Coordinatrice et cotisations (RG08, révisé le 26/09/2026).** La
Coordinatrice consulte les cotisations des membres **de sa section** : liste
des cotisations et export CSV filtrés sur sa section, indicateurs calculés
sur sa section, cotisations et relances visibles sur les fiches de ses
membres. C'est une **consultation seule** : émission des cotisations et
enregistrement des paiements lui restent interdits (403), et aucun bouton
de modification ne lui est proposé. Adhésions et historique des relances
restent hors de son périmètre.

**Passage à ce modèle en production (migration `accounts.0003`).** Au
déploiement, tous les comptes Secrétaire générale, Trésorière et
Coordinatrice existants redeviennent des comptes Membre (la Présidente
n'est pas concernée) ; l'ancienne fonction de chacun est inscrite au
journal (`FIN_FONCTIONS_MIGRATION`). Ensuite, pour chaque responsable :

1. si elle n'a pas encore de fiche membre, la créer via « Nouveau membre »
   **avec la même adresse électronique** que son compte — la fiche y est
   reliée automatiquement ;
2. la nommer depuis sa fiche (« Nommer à une fonction ») ;
3. si elle avait deux comptes (un de membre, un de responsable), nommer le
   compte relié à sa fiche et désactiver l'autre depuis « Responsables ».

Tant que la Trésorière n'est pas nommée, personne ne peut enregistrer de
paiement (rôle exclusif) : à faire juste après le déploiement. Une
ancienne responsable qui reçoit une fiche en cours d'année n'a pas de
cotisation pour l'exercice courant : l'émettre via « Émission collective ».

### « À faire » : les tâches du jour selon la fonction

Un bouton **À faire** dans la barre de navigation, avec un compteur (rouge
s'il y a une urgence), ouvre `/tableau-de-bord/a-faire/` : la liste de ce que
la personne connectée a à traiter, recalculée à chaque consultation
(`apps/dashboard/taches.py`), classée en *Urgent*, *À faire* et *À surveiller*,
chaque tâche menant directement à l'écran concerné.

| Fonction | Tâches |
|---|---|
| Présidente | fonctions vacantes (Trésorière : urgent), sections sans Coordinatrice, demandes d'adhésion, cotisations à émettre, courriels non distribués, responsables n'ayant pas activé leur compte, retards de plus de 90 jours |
| Secrétaire générale | demandes d'adhésion (urgent au-delà de 7 jours), membres n'ayant pas activé leur compte |
| Trésorière | retards de plus de 90 jours (urgent), de 45 à 90 jours, cotisations à émettre, paiements partiels, échéances à 15 jours |
| Coordinatrice | membres de sa section à contacter (retard ≥ seuil de R04, avec le reste à payer, lien vers ses cotisations en lecture seule), fiches à compléter, nouvelles membres, membres inactifs ou suspendus |
| Membre | sa propre cotisation : reste à payer et échéance, ou « Tout est à jour » |

Chaque lien proposé est vérifié par les tests comme accessible à la fonction
concernée : une tâche ne mène jamais à un écran « Accès refusé ».

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

### Service de messagerie (production)

`config/settings/prod.py` envoie les courriels via l'**API HTTP de Brevo**
(bibliothèque `django-anymail`), pas en SMTP : il suffit de renseigner deux
variables dans `.env` :

```
BREVO_API_KEY=<clé API v3 générée dans Brevo>
EMAIL_EXPEDITEUR=<adresse vérifiée dans Brevo>
```

**[Brevo](https://www.brevo.com)** (ex-Sendinblue) est le service retenu pour ce
prototype — gratuit jusqu'à 300 courriels/jour, largement suffisant pour une
association de cette taille. Après création d'un compte gratuit :

1. **Paramètres du compte → Clés API** : générer une clé API v3 (distincte des
   identifiants SMTP).
2. **Onglet Expéditeurs** : vérifier l'adresse qui sera utilisée comme
   `EMAIL_EXPEDITEUR` — Brevo refuse d'envoyer depuis une adresse non vérifiée.

Le SMTP sortant (port 587) a été essayé en premier mais s'est révélé peu fiable
depuis le réseau gratuit de Render : les connexions restaient bloquées en
`socket.connect()` jusqu'à ce que gunicorn tue le worker (timeout), avant même
qu'une erreur propre ne remonte — voir § 7, incident du 16/09. L'API HTTP
(port 443) n'a pas ce problème : les hébergeurs bloquent rarement le HTTPS
standard, contrairement aux ports SMTP. Vérifié en conditions réelles :
envoi effectif d'un courriel d'activation via ce mécanisme, reçu avec succès.

### Mise en forme des courriels

Chaque courriel part en deux versions (`multipart/alternative`) : une version
HTML aux couleurs de l'association (logo, bleu marine et rose, bouton
d'action, récapitulatif lisible sur mobile) et la version texte brut, gardée
comme repli pour les messageries en mode texte, les lecteurs d'écran et les
filtres anti-spam. Par convention, la version HTML de
`notifications/x.txt` est `notifications/x.html` ; le gabarit commun et ses
composants sont dans `templates/notifications/email/`. Un gabarit `.txt`
sans jumeau HTML (par exemple une règle de relance pointée dans l'admin vers
un autre fichier) part simplement en texte brut.

Le logo (`static/img/logo-afemc-email.png`, version allégée) est chargé par
la messagerie depuis `SITE_URL` : il ne s'affiche donc qu'une fois
l'application en ligne, et le nom de l'association est aussi écrit en
toutes lettres pour les messageries qui bloquent les images.

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

**Vérifié en conditions réelles** (worker + beat effectivement lancés, une
vraie action métier — demande de réinitialisation de mot de passe — mise en
file puis acheminée sans aucune commande manuelle, détection des retards
déclenchée via `.delay()` et relances envoyées automatiquement par le
worker) : le mécanisme fonctionne de bout en bout, pas seulement sur le
papier.

**Windows sans Redis.** Redis n'a pas de portage officiellement maintenu sous
Windows. Pour développer ou vérifier l'automatisation sans installer WSL ni
un portage Redis abandonné, Celery peut utiliser le transport fichier de
Kombu (déjà une dépendance de Celery, aucune installation supplémentaire hors
`pywin32`, nécessaire au verrouillage de fichiers sous Windows) :

```powershell
$env:CELERY_BROKER_URL = 'filesystem://'
celery -A config worker -l info --pool=solo   # --pool=solo : requis sous Windows
celery -A config beat -l info
```

Le dossier de file d'attente (`var/celery-filequeue/`, ignoré par git) est
créé automatiquement dès que `CELERY_BROKER_URL` commence par
`filesystem://` (voir `config/settings/base.py`). Sans effet sur la
production, où `CELERY_BROKER_URL` continue de pointer vers Redis par
défaut.

## 4. Campagne de tests (chapitre 6)

```bash
# Tous les tests
python manage.py test apps --settings=config.settings.test

# Avec mesure de la couverture
coverage run manage.py test apps --settings=config.settings.test
coverage report
coverage html            # rapport détaillé dans htmlcov/index.html
```

Chiffres au 26/09/2026 (`python manage.py test apps`) — **ils diffèrent de
ceux du chapitre 6**, à mettre à jour dans le mémoire :

| Catégorie | Nombre | Emplacement |
|-----------|--------|-------------|
| Tests unitaires | 208 | core, accounts, membres, adhesions, cotisations, notifications, dashboard, sections, relances |
| Scénarios du moteur (SC01-SC24 et compléments) | 26 | `apps/relances/tests/test_moteur.py` |
| Tests d'intégration | 12 | `apps/cotisations/tests/test_integration.py` |
| Tests fonctionnels (TF01-TF32) | 34 | `apps/core/tests/test_fonctionnels.py` (TF08/TF16b adaptés ; TF26-TF32 nouveaux) |
| Tests de sécurité (TS01-TS13) | 13 | `apps/core/tests/test_securite.py` (TS11-TS13 nouveaux) |
| **Total** | **293** | couverture : 95 % mesurés à 192 tests — **à re-mesurer** |

Historique : le chapitre 6 en décrivait 126, puis 192 après l'ajout des
fonctionnalités ci-dessous ; les suivants couvrent les courriels HTML,
les relances adressées aux responsables et la nomination des responsables
(RG13).

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
**TF31-TF32** rejouent la nomination d'une membre à une fonction (même
compte, nouveaux accès) et la fin de fonctions (accès retirés, compte
conservé) ; TF28 porte désormais sur le compte externe.
**TS11-TS12** formalisent les deux failles trouvées et corrigées lors de la
revue de sécurité (accès au détail d'une section, accès à une pièce
justificative). **TS13** vérifie que les droits d'une responsable sont
retirés immédiatement en fin de fonctions, même pour une session ouverte. Si le corps du mémoire doit en rendre compte, ce sont ces
identifiants qu'il convient de citer.

### Nouvelles règles de gestion (RG11, RG12, RG13)

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
- **RG13 — Nomination des responsables.** Une fonction de responsable
  (Secrétaire générale, Trésorière, Coordinatrice de section) est confiée
  par la Présidente à une membre active du registre ; elle s'ajoute à son
  compte existant — une personne ne possède qu'un seul compte. La fin de
  fonctions ramène le compte au rôle Membre sans supprimer l'accès, et
  retire immédiatement les droits liés à la fonction. Nominations et fins
  de fonctions sont journalisées. Un compte externe (personne hors
  registre) reste possible à titre d'exception.

> **Mise à jour du 26/09/2026 :** à la demande de l'association, la
> Coordinatrice consulte désormais les cotisations de sa section (lecture
> seule, voir § « Responsables » plus haut). Le paragraphe ci-dessous
> décrit la règle initiale ; § 3.2.4 et le tableau 6 du mémoire sont à
> ajuster en conséquence.

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
apps/cotisations cotisations, paiements
apps/relances    moteur de détection et règles de relance
apps/notifications file de messages et acheminement
apps/dashboard   indicateurs de pilotage
templates/       gabarits HTML (Bootstrap 5)
```

## 7. Déploiement en production (Render)

Hébergeur retenu : **[Render](https://render.com)**. Le dépôt contient un fichier
`render.yaml` (Blueprint) à la racine — Render y lit la définition complète des
services et les crée en un seul clic, plutôt que de les configurer un par un.

### Première mise en service

1. Créer un compte Render, connecté à ce dépôt GitHub.
2. **New + → Blueprint**, sélectionner le dépôt `afemc-ci-prototype`. Render
   détecte `render.yaml` et propose de créer deux ressources : la base
   PostgreSQL et le service web (Gunicorn).
3. Render demande de compléter les variables marquées `sync: false` dans
   `render.yaml` — les informations Brevo (`BREVO_API_KEY`, `EMAIL_EXPEDITEUR`,
   voir § 3 « Service de messagerie ») et les identifiants du premier compte
   administrateur
   (`SUPERUSER_BOOTSTRAP_EMAIL`, `SUPERUSER_BOOTSTRAP_PASSWORD`). Tout le
   reste (secret Django, connexion PostgreSQL, jeton `CRON_SECRET`, nom
   d'hôte, `SITE_URL`) est déduit ou généré automatiquement.
4. Une fois déployé, créer effectivement ce compte administrateur — le Shell
   Render exige le plan payant Starter, indisponible en gratuit ; un point
   d'entrée HTTP protégé par jeton en tient lieu :
   ```bash
   curl -H "Authorization: Bearer <CRON_SECRET, onglet Environment du service>" \
        https://afemc-ci-web.onrender.com/taches/amorcer-admin/
   ```
   Idempotente : ne fait rien si un compte administrateur existe déjà, donc
   sans risque à rappeler par erreur. Se connecter ensuite avec
   `SUPERUSER_BOOTSTRAP_EMAIL` / `SUPERUSER_BOOTSTRAP_PASSWORD`.

### Tâches planifiées sans worker (Background Workers indisponibles en gratuit)

Les « Background Workers » de Render — nécessaires à un worker Celery — ne
sont **pas proposés sur le plan gratuit** (seuls la base de données et un
service web le sont). Plutôt que de payer un service dédié, la détection des
retards est déclenchée par un appel HTTP planifié depuis GitHub Actions
(`.github/workflows/cron.yml`, déjà dans le dépôt) vers `GET /taches/executer/`,
une vue protégée par le jeton `CRON_SECRET` (en-tête `Authorization: Bearer
<jeton>`) — toutes les 15 min, plus un appel supplémentaire le lundi à 7h UTC
pour la synthèse hebdomadaire.

L'envoi des notifications, lui, ne dépend pas de ce cron : `creer_notification`
(§ 5.6.3) tente un envoi immédiat dès la création, dans le cycle
requête/réponse — un candidat ou un responsable reçoit son courriel en
quelques secondes, sans attendre le prochain passage planifié. Cet appel HTTP
reste le filet de sécurité qui réessaie ce qui n'a pas pu partir du premier
coup (panne passagère du fournisseur, etc.), plafonné à `MAX_TENTATIVES_NOTIFICATION`
tentatives avant de passer en échec définitif (visible et renvoyable depuis
l'écran `/notifications/`).

Pour l'activer, une fois le service web déployé :

1. **Dashboard Render → afemc-ci-web → Environment** : copier la valeur
   générée pour `CRON_SECRET`.
2. **Sur GitHub → Settings du dépôt → Secrets and variables → Actions** :
   - Onglet *Secrets* → *New repository secret* → nom `CRON_SECRET`, valeur
     collée à l'étape précédente.
   - Onglet *Variables* → *New repository variable* → nom `RENDER_URL`,
     valeur `https://afemc-ci-web.onrender.com` (l'URL réelle attribuée par
     Render, visible en haut du tableau de bord du service).
3. **Onglet Actions du dépôt → « Tâches planifiées AFEMC-CI » → Run workflow**
   pour vérifier manuellement avant d'attendre la première exécution planifiée.

Si le worker Celery est préféré malgré son coût (~7 $/mois sur Render), rien
n'empêche de le recréer manuellement (« New + → Background Worker », racine
`afemc_ci`, commande `celery -A config worker -B --loglevel=info`, mêmes
variables d'environnement que le service web) et de désactiver le workflow
GitHub Actions.

### Limites du plan gratuit à connaître

- **PostgreSQL gratuit** : expire au bout de 90 jours (à renouveler ou migrer
  vers un plan payant, ~7 $/mois, avant l'échéance).
- **Service web gratuit** : se met en veille après une période d'inactivité ;
  la requête suivante prend 30 à 60 s le temps du réveil (« cold start ») —
  y compris pour l'appel de GitHub Actions, qui peut donc occasionnellement
  échouer sur un réveil trop lent (le workflow le signale sans bloquer les
  exécutions suivantes).
- **Fichiers déposés (`MEDIA_ROOT`)** : stockés sur un disque **éphémère** par
  défaut — les pièces justificatives déposées par les candidates seraient
  perdues à chaque redéploiement. Pour un usage réel au-delà d'une
  démonstration, attacher un [disque persistant Render](https://render.com/docs/disks)
  au service web (quelques dollars/mois) et y faire pointer `MEDIA_ROOT`.

### Déploiement manuel (sans Blueprint)

Si le Blueprint échoue ou pour garder la main sur chaque étape, les mêmes
ressources peuvent être créées à la main dans le tableau de bord Render : une
base PostgreSQL, puis un « Web Service » (racine `afemc_ci`, commande de
build `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`,
commande de démarrage `gunicorn config.wsgi:application`) — en reportant
manuellement les variables d'environnement listées dans `render.yaml`.
