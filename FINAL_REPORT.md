# Rapport de livraison — FEBA **V9**

Base : **V8** (`feba_v6_version_finale_corrigee`), telle que livrée et
auditée par la QA externe.

---

## 1. Le blocker principal, reproduit puis corrigé

### Reproduction

La disposition du conteneur a été reconstituée à l'identique — `backend/`
seul, plus le montage nommé de `KNOWN_LIMITATIONS.md` — et la commande de
la QA rejouée :

```
5 failed, 84 passed, 1 skipped        ← identique au rapport de QA
tests/test_env_dev_email_config.py :  4 skipped
```

### Cause racine

Cinq fichiers de tests répondaient chacun à leur façon à une seule
question — « où est la racine du dépôt ? » :

| Fichier | Mécanisme | Comportement dans le conteneur |
|---|---|---|
| `test_env_dev_email_config.py` | `parent.parent.parent` puis `skipTest` | **4 skipped silencieux** |
| `test_jitsi_production_domain.py` | `dirname` × 3 | 4 échecs |
| `test_production_settings.py` | `skipUnless(os.path.exists(...))` | **1 skipped silencieux** |
| `test_diploma_ready_after_install.py` | `dirname` × 3 | **faux positif** (voir §3) |
| `test_academy_identity_separation.py` | remontée + montage nommé | passait, seul |

Deux d'entre eux répondaient **en se taisant**. C'est le pire des deux
mondes : `pytest` affichait « skipped », qui se lit comme un succès, alors
que ni Mailpit ni le modèle de production n'étaient vérifiés. Un
`.env.dev.example` revenu au backend console serait passé inaperçu —
c'est-à-dire exactement le défaut que ce fichier surveille.

### Correction

Deux pièces qui ne valent qu'ensemble :

1. **`backend/tests/repo_root.py`** — résolution unique, trois chemins
   indépendants : `FEBA_REPO_ROOT`, remontée d'arborescence (marqueurs
   `backend/manage.py` + `frontend/package.json`), puis `/repo`. Si aucun
   n'aboutit, elle **lève** avec un message qui nomme le geste. Aucun
   chemin absolu propre à une machine.
2. **`docker-compose.yml`** — le dépôt entier monté **en lecture seule**
   sur `/repo`, plus `FEBA_REPO_ROOT=/repo`. Le montage fichier par
   fichier disparaît : c'était le défaut, pas la solution.

### Vérification

| Disposition | Avant | Après |
|---|---|---|
| Commande de QA, conteneur | 5 failed, 84 passed, 1 skipped | **88 passed** |
| `test_env_dev_email_config.py` | **4 skipped** | **4 passed** |
| Suite complète, conteneur | 5 failed, 1 156 passed, 5 skipped | **1 196 passed, 0 skipped** |

Le montage a aussi été retiré volontairement : les tests concernés passent
alors de « skipped » à **32 échecs bruyants**. Le silence a disparu.

---

## 2. Jitsi — conflit de ports (§9)

**Mesuré sur les fichiers livrés, pas supposé :**

| Service | Fichier | Ports de l'hôte |
|---|---|---|
| `nginx-prod` | `docker-compose.prod.yml` | 80, 443 |
| `jitsi-web` | `docker-compose.jitsi.prod.yml` | **80, 443** |

Sur le serveur qui sert déjà `globalfeba.com`, la pile Jitsi était
**indéployable** : soit « port is already allocated », soit — si Jitsi
démarrait en premier — le site principal qui ne redémarre plus. La V8
documentait « serveur dédié » sans jamais vérifier cette hypothèse.

**Corrigé en livrant la seconde topologie, pas en renonçant à la première :**

- `docker-compose.jitsi.behind-proxy.yml` — Jitsi n'écoute que sur
  `127.0.0.1`, TLS terminé par le nginx de FEBA, pas de client ACME
  concurrent. `ENABLE_AUTH=1`, `ENABLE_GUESTS=0`, `AUTH_TYPE=jwt`,
  `JWT_ALLOW_EMPTY=0` et `JVB_ADVERTISE_IPS` **conservés**.
- `nginx/sites-available/meet.globalfeba.com.conf` — vhost complet
  (WebSocket XMPP, `colibri-ws`, BOSH, `X-Forwarded-Proto`,
  `frame-ancestors` au lieu de `X-Frame-Options: DENY`, l'application
  affichant la salle en iframe). **Livré mais NON activé** : il référence
  un certificat absent, et nginx refuserait de démarrer — ce nginx servant
  aussi le site principal.
- `make jitsi-proxy-up` / `-down` / `-logs`, et `make jitsi-config-check`
  qui signale désormais le conflit.

**Éprouvé, pas seulement écrit :** le vhost a été servi par un vrai nginx
1.24 contre un serveur qui rejoue les en-têtes reçus. Deux défauts réels
ont été trouvés et corrigés à ce moment — `http2 on;` (syntaxe nginx ≥ 1.25
qui aurait empêché le démarrage) et des en-têtes manquants sur
`colibri-ws`.

---

## 3. Deux tests qui passaient sans rien vérifier

- **`test_5_le_fond_neutralise_est_versionne`** interrogeait `git
  check-ignore` sur `/app/...` en travaillant depuis la racine du dépôt.
  Git répondait « is outside repository » (code 128) et l'assertion
  « code ≠ 0 » s'en satisfaisait. Le test interroge désormais le chemin
  **relatif au dépôt**, et refuse un code autre que 0 ou 1.
- **`test_le_modele_de_production_documente_les_variables_requises`**
  était gardé par un `skipUnless` toujours faux dans le conteneur.

---

## 4. Migration `schools.0015` (§10)

**Auditée, jugée sûre, non modifiée.** Réécrire une migration déjà
appliquée la ferait diverger entre les bases qui l'ont passée et les
autres.

11 tests (`test_migration_0015_data_safety.py`) exécutent la vraie
fonction sur une base peuplée :

| Propriété | Résultat |
|---|---|
| Numéro hors service remplacé sur l'entité | ✅ |
| Numéro recopié dans l'adresse retiré | ✅ |
| Numéro d'entité **légitime** conservé | ✅ |
| Colonne vide **laissée vide** (ne remplit pas) | ✅ |
| **Coordonnées personnelles intactes** (parent, contact, préinscription) | ✅ |
| Idempotente (3 exécutions) | ✅ |
| Base vide traversée sans erreur | ✅ |
| L'inverse ne restaure pas le numéro retiré | ✅ |

Le contrôle qui compte : parents, visiteurs et candidats portent les mêmes
noms de colonnes que l'entité. On leur a donné **délibérément** le numéro
retiré ; la migration n'y touche pas.

---

## 5. Intégration continue (§17)

**Constat : il n'existait AUCUN workflow de Pull Request.** Le dépôt ne
contenait que `deploy.yml`, déclenché par un push sur `main` — une Pull
Request n'était donc validée par rien, et les tests s'exécutaient pour la
première fois *après* la fusion, au moment du déploiement.

`.github/workflows/ci.yml` est ajouté : suites backend PostgreSQL **et**
SQLite, `manage.py check`, `makemigrations --check`, tests/lint/build
frontend, validité des cinq assemblages Compose, cohérence Jitsi, syntaxe
Nginx (vhost Jitsi activé compris), sûreté du dépôt.

Aucun secret de production n'est requis. **`deploy.yml` n'est pas
modifié.**

---

## 6. Non-régression production (§19)

| Fichier | Diff V8 → V9 | Pourquoi | Risque | Vérifié par |
|---|---|---|---|---|
| `.github/workflows/deploy.yml` | **inchangé** | — | — | — |
| `backend/feba_project/settings/prod.py` | **inchangé** | — | — | — |
| `docker-compose.jitsi.prod.yml` | **inchangé** | topologie A conservée | — | — |
| `scripts/backup.sh`, `restore.sh` | **inchangé** | — | — | — |
| `docker-compose.prod.yml` | **+4, −0** | monter `sites-enabled/` (vide) | nul — répertoire vide | `docker compose config` |
| `nginx/nginx.prod.conf` | **+14, −0** | `include sites-enabled/*.conf` | nul — un motif sans correspondance n'est pas une erreur nginx | `nginx -t` vide **et** vhost activé |
| `frontend/nginx.prod.conf` | **+11, −0** | `/images/` répond `404` sur fichier absent | faible — aucune route SPA sous `/images/` | 6 requêtes HTTP réelles |
| `docker-compose.yml` (dev) | **+22, −9** | montage `/repo` en lecture seule | dev uniquement | suite complète en disposition conteneur |

Aucun changement silencieux : les trois fichiers de production touchés le
sont de façon **purement additive**, et leur comportement par défaut est
strictement celui de la V8.

---

## 7. Ce qui n'a pas pu être exécuté

- **`docker compose up` — NON EXÉCUTÉ.** Le démon Docker n'est pas
  disponible dans cet environnement (`docker info` échoue). Le client
  fonctionne : `docker compose config` est validé pour les cinq
  assemblages. Healthchecks, démarrage des services et `/api/health/`
  n'ont donc **pas** été rejoués — ils l'avaient été par la QA sur V8.
- **Appel Jitsi réel — NON EXÉCUTÉ.** L'infrastructure n'existe pas :
  `meet.globalfeba.com` ne résout toujours pas.
- **Envoi d'e-mail réel — NON EXÉCUTÉ.** Backend en mémoire pendant les
  tests ; la configuration Mailpit est vérifiée sur les fichiers.
- **Parcours navigateur — non rejoués.** Ils avaient été exécutés en V8 ;
  aucun code de parcours utilisateur n'a changé en V9.

---

## 8. Aucun résultat inventé

Tous les chiffres de ce rapport et de `TEST_REPORT.md` proviennent de
commandes réellement exécutées dans cet environnement, dont les sorties
figurent dans la transcription. Ce qui n'a pas pu l'être est marqué
**NON EXÉCUTÉ** avec sa raison, jamais remplacé par un PASS.
