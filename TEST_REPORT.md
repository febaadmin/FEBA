# FEBA — Rapport de tests de la version finale validée

Exécuté le 25 octobre 2026 sur la branche `fix/feba-validation-finale`
(commit livré : voir `SOURCE_COMMIT.txt` dans l'archive). Les rapports
antérieurs sont dans `docs/historique/`.

Statuts : **PASS** (exécuté, réussi) · **FAIL** (exécuté, échoué) ·
**BLOCKED** (impossible : accès ou identifiants absents) · **NOT RUN**
(non exécuté) · **SIMULATED** (exécuté contre un substitut local : la
chaîne FEBA est réelle, le fournisseur ne l'est pas).

Un test **ignoré** n'est jamais compté comme réussi.

---

## 1. Tests automatisés

| Suite | Résultat | Statut |
|---|---|---|
| Backend PostgreSQL 16 + Mailpit SMTP + plugNmeet v2.5.3 réel | __PG__ | __PG_STATUT__ |
| Backend SQLite | 1634 réussis, **9 ignorés** (concurrence : PostgreSQL requis ; tests plugNmeet/Mailpit réels sans service), 0 échec | PASS |
| Frontend Vitest | 308 / 308 (37 fichiers) | PASS |
| ESLint | 0 erreur (80 avertissements préexistants) | PASS |
| Build Vite | réussi | PASS |
| `makemigrations --check` | aucune migration manquante | PASS |
| `manage.py check` | aucun problème | PASS |
| `scripts/compose_config_check.sh` | tous les assemblages Compose valides (dev, prod, Jitsi, plugNmeet) | PASS |
| `scripts/repo_safety_check.sh` | dépôt sain | PASS |

Tests ajoutés par cette version (ils échouent sur l'ancien code) :
- `backend/tests/test_production_preflight.py` (8) : refus de démarrage
  sur configuration de développement ou incomplète ; santé derrière la
  redirection TLS.
- `backend/tests/test_session_revocation.py` (5) : compte désactivé
  (renouvellement refusé — défaut corrigé), déconnexion, rotation, jeton
  de renouvellement expiré, jeton d'accès expiré.
- `frontend/src/pages/admin/schedule/ScheduleGrid.test.jsx` (2) : un
  cours apparaît une seule fois dans la grille (l'ancien code l'affichait
  deux fois).

## 2. Scénarios navigateur de bout en bout (`e2e/`, Chrome réel)

| Scénario | Résultat | Statut |
|---|---|---|
| `academies.mjs` | 3 passages sur 3 | PASS |
| `espaces-anglais.mjs` | réussi | PASS |
| `site-public-anglais.mjs` | réussi | PASS |
| `devises-et-documents.mjs` | code 0 | PASS |
| `parcours-documents-officiels.mjs` | 54 contrôles, 0 échec | PASS |
| `parcours-preinscription-feba.mjs` | 41 contrôles, 0 échec | PASS |
| `parcours-rapports-mensuels.mjs` | 30 contrôles, 0 échec | PASS |
| `parcours-v9.mjs` | « TOUT EST VERT » | PASS |

## 3. Visioconférence plugNmeet (instance réelle v2.5.3, locale)

| Contrôle | Résultat | Statut |
|---|---|---|
| Réunion 1 enseignant + 2 élèves, caméra et micro simulés (vrais flux WebRTC), salle d'attente, admission par l'enseignant | __LONG__ | __LONG_STATUT__ |
| Premier essai long (13:09–14:04 UTC) | ~55 min continues, puis veille de la machine hôte (fermeture du capot, journal `pmset`) : **interrompu**, non compté | FAIL (environnement) |
| Coupure réseau de 10 s | participant conservé | PASS |
| Coupure réseau de 45 s | plugNmeet retire l'élève après ~35 s ; retour via FEBA possible, reconnexion comptée ; session FEBA ouverte | PASS (limite plugNmeet documentée) |
| Fin de réunion depuis FEBA par l'enseignant | `meeting_ended_at` renseigné, toutes les présences fermées | PASS |
| Partage d'écran | aucune source d'écran dans le navigateur automatisé | NOT RUN |
| Média entre réseaux distincts, TURN | une seule machine | NOT RUN |

## 4. Session et jetons

| Contrôle | Résultat | Statut |
|---|---|---|
| Renouvellement après expiration du jeton d'accès (onglet resté ouvert pendant la veille de la machine) | à la reprise, rotation du jeton de renouvellement, nouvel accès valide, `/auth/me` 200, aucune déconnexion | PASS |
| Renouvellement préventif pendant la réunion longue | __REFRESH__ | __REFRESH_STATUT__ |
| Compte désactivé | renouvellement refusé (401 `user_inactive`), jeton mis en liste noire | PASS (test auto) |
| Déconnexion, rotation, expiration | `test_session_revocation.py` | PASS (test auto) |
| Plusieurs onglets, coupure réseau | session conservée (réunion longue, onglets FEBA séparés) | PASS |

## 5. Production : images, contrôle de pré-démarrage, déploiement

Pile « comme en production » (`docker-compose.prod.yml` + surcouche de
ports locaux, certificat auto-signé, Mailpit à la place du SMTP réel) :

| Contrôle | Résultat | Statut |
|---|---|---|
| Images de production construites depuis le dépôt (`npm ci`, image backend unique pour backend/worker/Beat) | réussi | PASS |
| Démarrage refusé en `DEPLOYMENT_STAGE=production` avec une configuration de test | code 1, erreurs listées | PASS |
| Santé de la pile | 301 HTTP→HTTPS, ACME 200, accueil 200, `/api/health/` 200, `/auth/me` 401 sans jeton, HSTS | PASS |
| Configuration identique backend / worker / Beat | même empreinte | PASS |
| Beat → worker | `process_pending_campaigns`, `retry_due_sms` exécutées | PASS |
| `deploy_feba.sh` : configuration invalide | refus avant toute modification (conteneur inchangé) | PASS |
| `deploy_feba.sh` : échecs volontaires de vérification | retour automatique à la version précédente | PASS |
| `deploy_feba.sh --rollback` | version précédente rétablie, santé 200 | PASS |
| `deploy_feba.sh` depuis l'archive finale extraite | __DEPLOY__ | __DEPLOY_STATUT__ |
| Certificat Let's Encrypt réel | non exécuté (pas de serveur public) | NOT RUN |

## 6. E-mail et SMS

| Contrôle | Résultat | Statut |
|---|---|---|
| Expéditeur `noreply@globalfeba.com` sur les messages produits | vérifié dans Mailpit | SIMULATED |
| SMTP Hostinger réel | aucun identifiant fourni | BLOCKED |
| SMS miroir via le vrai worker Celery | message produit, fournisseur de test | SIMULATED |
| Twilio réel (+1 215 715 5406) | aucun identifiant fourni | BLOCKED |
| Reprise après échec SMTP | 2ᵉ tentative envoyée, aucun SMS en double | SIMULATED |

## 7. Serveur réel

| Contrôle | Statut |
|---|---|
| Accès SSH Hetzner (`89.167.63.1`, `62.238.38.111`) | BLOCKED (clé refusée) |
| Déploiement en production, migration de la base de production | NOT RUN (interdit et inaccessible) |
