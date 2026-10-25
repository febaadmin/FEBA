# FEBA — Rapport final : version validée pour la production

25 octobre 2026 · branche `fix/feba-validation-finale` · base : archive
`FEBA_VERSION_PLUGNMEET_SMS_AUDIT_COMPLET.zip` (commit `6cf9dcb`, empreinte
vérifiée). Commit livré : `SOURCE_COMMIT.txt` dans l'archive.

Statuts : **PASS** · **FAIL** · **BLOCKED** · **NOT RUN** · **SIMULATED**.
Détail des tests : `TEST_REPORT.md`. Limites : `KNOWN_LIMITATIONS.md` § 000.
Actions de l'exploitant : `MANUAL_PRODUCTION_ACTIONS.md` § 00.

---

## 1. En bref

- **Code** : prêt à déployer, toutes les suites automatisées vertes, aucun
  test ignoré compté comme réussi.
- **Déploiement** : automatisé (`make prod` → `scripts/deploy_feba.sh`),
  avec contrôle de pré-démarrage, sauvegarde vérifiée, vérifications après
  démarrage et retour arrière automatique. Validé sur une pile identique à
  la production (hors certificat et fournisseurs réels).
- **Non validé en réel** : serveur Hetzner, SMTP Hostinger, Twilio
  (BLOCKED : aucun accès ni identifiant). Rien n'a été déployé, migré ni
  envoyé en production.

## 2. Défauts trouvés et corrigés pendant cette validation

| # | Défaut (reproduit) | Cause racine | Correction | Test de non-régression |
|---|---|---|---|---|
| 1 | Pile de production jamais saine : backend « unhealthy », nginx, worker et Beat jamais démarrés | le contrôle de santé suivait la redirection HTTPS vers `https://localhost:8000` | `SECURE_REDIRECT_EXEMPT` pour `/api/health/` | `test_production_preflight.HealthBehindTlsRedirectTests` |
| 2 | Une configuration de développement ou incomplète démarrait en production sans alerte | aucun contrôle bloquant au démarrage | `apps/core/preflight.py` + `manage.py production_preflight` lancés par le backend, le worker et Beat ; empreinte de configuration comparée | `test_production_preflight.py` (8) |
| 3 | 502 après la recréation du backend | nginx gardait l'ancienne adresse IP du conteneur | résolveur Docker + variables d'amont + rechargement | essai de déploiement |
| 4 | Renouvellement du certificat impossible (ACME) | port 80 redirigé sans exception, webroot non monté | `/.well-known/acme-challenge/` servi depuis `/var/www/certbot` ; `scripts/tls_bootstrap.sh` | ACME 200 sur la pile de recette |
| 5 | Images non reproductibles ; worker et Beat potentiellement d'une autre version que le backend | `npm install`, images construites séparément | `npm ci` ; une image backend unique étiquetée (`current`/`previous`) | essai de déploiement |
| 6 | **Sécurité** : un compte désactivé pouvait encore renouveler son jeton (HTTP 200) | le sérialiseur de renouvellement ne relisait pas l'utilisateur | `ActiveUserTokenRefreshSerializer` : refus 401 et mise en liste noire | `test_session_revocation.py` (5) |
| 7 | Emplois du temps : un cours affiché deux fois (3 séances → 5 cartes) | la grille ne comparait que l'heure de début | comparaison du créneau complet | `ScheduleGrid.test.jsx` (2) |
| 8 | Déploiement : `POSTGRES_PASSWORD` en `:?` cassait `exec` et `logs` ; projet Compose par défaut « feba » risquait une seconde pile à volumes vides | — | interpolation tolérante, projet Compose par défaut | essai de déploiement |
| 9 | Scénarios e2e cassés hors du conteneur prévu (chemin avec espace, navigateur codé en dur, vérification fondée sur le réseau et non l'interface) | — | `fileURLToPath`, `CHROMIUM_PATH`, assertions sur l'interface | 8 scénarios verts |
| 10 | Documentation contradictoire (ancien `FINAL_REPORT.md` V13 « à déployer », rapports Jitsi présentés comme actuels) | — | anciens rapports déplacés ou marqués « DOCUMENT HISTORIQUE » ; `DOCUMENTATION_INDEX.md` ; `DEPLOYMENT_PRODUCTION.md` réécrit | — |

## 3. Résultats

| Domaine | Résultat | Statut |
|---|---|---|
| Backend PostgreSQL + Mailpit + plugNmeet réel | **1643 réussis, 0 ignoré, 0 échec** (607 sous-tests), dont les tests plugNmeet et SMTP réels | PASS |
| Backend SQLite | 1634 réussis, 9 ignorés, 0 échec | PASS |
| Frontend (Vitest, ESLint, build) | 308/308, 0 erreur, build OK | PASS |
| Migrations, `check`, Compose, sûreté du dépôt | aucun écart | PASS |
| Scénarios e2e (8) | tous verts | PASS |
| Réunion plugNmeet réelle 1 enseignant + 2 élèves ≥ 60 min | 15:22 → 16:28 UTC : présences serveur 65,5 / 65,2 / 65,1 min, 0 reconnexion, 3 entrées et 3 sorties seulement ; contrôle toutes les 5 min (salle, `/auth/me`) : 0 échec ; fin par l'enseignant depuis FEBA (HTTP 200) → les 3 participants redirigés vers `/virtual-room/2/ended`. Les 3 participants tournaient sur la même machine | PASS |
| Session : renouvellement après expiration, compte désactivé, onglets, coupure | voir `TEST_REPORT.md` § 4 | PASS |
| Renouvellement préventif du jeton pendant la réunion | jetons d'accès échus à 16:22 ; entre 16:13 et 16:18, rotation des 3 jetons de renouvellement et nouveaux jetons d'accès (échéance 17:17), sans rechargement des onglets FEBA, participants restés dans la salle, `/auth/me` 200 | PASS |
| Déploiement automatisé, refus, retour arrière, idempotence | voir `TEST_REPORT.md` § 5 | PASS |
| E-mail : expéditeur `noreply@globalfeba.com` | Mailpit | SIMULATED |
| SMS miroir et relances | fournisseur de test, vrai worker | SIMULATED |
| SMTP Hostinger, Twilio, serveur Hetzner | aucun accès | BLOCKED |
| Partage d'écran, TURN entre réseaux, certificat Let's Encrypt réel | — | NOT RUN |

## 4. Ce qui reste à faire hors du dépôt

1. Donner un accès SSH valide au serveur, puis suivre
   `MANUAL_PRODUCTION_ACTIONS.md` § 00 (sauvegarde, `.env.prod`,
   `make prod-preflight`, `tls_bootstrap.sh`, `make prod`).
2. Recette plugNmeet en production avec de vrais postes sur des réseaux
   différents, partage d'écran compris, **avant** de désactiver Jitsi et
   de basculer le DNS.
3. Renseigner les identifiants SMTP Hostinger et Twilio, puis un envoi de
   test vers **une seule** adresse et **un seul** numéro autorisés.

## 5. Garanties de l'archive

- construite depuis le commit (`git archive`), arbre de travail propre ;
- aucun `.env` réel, aucun secret plugNmeet (`plugnmeet/runtime` absent),
  aucune dépendance ni cache ;
- `SHA256SUMS.txt` interne ; empreinte de l'archive dans un fichier
  `.sha256` à côté ;
- vérifiée depuis une extraction neuve (voir `DELIVERY_VERIFICATION_*.txt`
  livré à côté de l'archive).
