# FEBA — Rapport de validation (audit complet, octobre 2026)

Environnement : macOS, Python 3.11 (venv), Node 20.20.2, Docker 29.4.1 /
Compose 5.1.3. Services de test jetables : PostgreSQL 16-alpine, Redis 7,
**Mailpit** (SMTP de test). Aucun service de production n'a été contacté.

## 1. Résultats (dernière exécution, commit de livraison)

| Contrôle | Référence (V13 + main) | Final | Statut |
|---|---|---|---|
| Backend SQLite (suite complète) | 1330 ✓, 1 ignoré | **1488 ✓, 3 ignorés, 0 échec** | PASS VÉRIFIÉ |
| Backend PostgreSQL 16 (suite complète) | 1331 ✓ | **1491 ✓, 0 ignoré, 0 échec** | PASS VÉRIFIÉ |
| Frontend Vitest | 246 ✓ / 25 fichiers | **278 ✓ / 30 fichiers** | PASS VÉRIFIÉ |
| ESLint | 0 erreur, 81 avert. | **0 erreur, 80 avert.** | PASS VÉRIFIÉ |
| Build Vite | OK | **OK** | PASS VÉRIFIÉ |
| `makemigrations --check` | aucun changement | **aucun changement** | PASS VÉRIFIÉ |
| Assemblages Docker Compose (5) | valides | **valides** (`scripts/compose_config_check.sh`) | PASS VÉRIFIÉ |
| Routes appelées par le frontend | — | **307/307 résolues** par Django (+ 11 du site public) | PASS VÉRIFIÉ |
| Vérification depuis une extraction neuve du ZIP | — | voir § 4 | voir § 4 |

Ignorés SQLite (3) : 1 préexistant (verrouillage de table, PostgreSQL requis)
et les 2 tests de **concurrence réelle**, volontairement réservés à
PostgreSQL — ils passent sur PostgreSQL.

## 2. Couverture des priorités

| Priorité | Tests backend | Tests frontend | Navigateur réel |
|---|---|---|---|
| Âge | 27 | 8 | colonne et sélecteurs vérifiés |
| Date + heure paiements | 19 | 10 | paiement saisi 14:37 → « 09/10/2026 14:37 » |
| E-mails groupés | 29 (dont 1 SMTP Mailpit) | 9 | aperçu, envoi, rapport |
| Relances | 46 (dont concurrence PostgreSQL) | — | état dégradé, simulation, envoi bloqué |
| Confirmations FHA | 17 (dont concurrence PostgreSQL) | 5 | clic ligne, anti-doublon |
| Audit (isolation, rôles, comptabilité, annonces) | 22 | — | — |

## 3. Points vérifiés spécifiquement

- **Multi-académies** : listes, écritures (7 tests échouaient avant correctif), envois groupés, relances, confirmations.
- **E-mails** : jamais de vrai envoi ; Mailpit reçoit 3 messages individuels (1 destinataire chacun, ni Cc ni Bcc).
- **Idempotence** : relances rejouées et exécutées en parallèle (2 threads, 2 connexions PostgreSQL) → aucun doublon ; double soumission d'un envoi groupé → une campagne ; double requête de confirmation → 200 + 409, un seul e-mail.
- **Pannes** : SMTP refusé/déconnecté → statut « nouvel essai », relance automatique, aucun renvoi des succès ; broker indisponible → campagne en file, reprise planifiée ; worker arrêté → reprise sans doublon.

## 4. Vérification depuis l'archive

Résultat consigné dans `delivery/VERIFICATION_EXTRACTION.txt` (hors archive,
puisqu'il porte sur l'archive elle-même).

## 5. Non exécuté ici — À TESTER EN ENVIRONNEMENT RÉEL

- Envoi via le fournisseur SMTP de production (SPF/DKIM/DMARC).
- Celery Beat et worker en conteneurs de production (healthchecks ajoutés, non exécutés en production).
- Migrations sur une copie de la base de production (testées sur bases neuves SQLite et PostgreSQL, et migration de reprise testée sur données simulées).
- Tests e2e Playwright du dépôt (`e2e/`) : non relancés ; parcours équivalents faits dans le navigateur intégré.
