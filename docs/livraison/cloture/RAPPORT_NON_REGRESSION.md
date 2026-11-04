# Non-régression : méthode et résultats (04/11/2026)

## 1. Méthode appliquée à chaque lot

1. Identifier les composants touchés et leurs dépendants (grep des imports, routes, menus).
2. Établir une référence : faire passer la suite existante avant de modifier.
3. Modifier, puis rejouer :
   - les tests unitaires du module, sur PostgreSQL local ;
   - les scénarios E2E liés, en navigateur local ;
   - toute la CI GitHub Actions : backend PostgreSQL et SQLite, frontend (tests, lint, build), E2E, images Docker, sécurité, configuration.
4. **Test de mutation** pour les nouveaux contrôles importants : retirer le correctif et vérifier que le test échoue.
5. Fusion seulement après le vert de tous les contrôles obligatoires, vérifié séparément.

## 2. Tests de mutation (le test échoue sans le correctif)

| Contrôle | Sans correctif | Avec correctif |
|---|---|---|
| E2E « écriture refusée : motif affiché » (PR #75) | KO, aucun message | OK |
| Restauration plugNmeet (PR #69) | 3 échecs sur 3, `unexpected eof` | 3 réussites sur 3 |
| `test_reference_fha_concurrence` (PR #74) | `IntegrityError` × 2 | OK |
| Worker Celery avec kombu 5.7.0 (PR #76) | `VersionMismatch`, identique à la production | ping, tâche exécutée |
| Ancien bogue de connexion (phase 2) | 6 contrôles KO | OK |

## 3. Fonctionnalités protégées par des tests automatiques

| Fonctionnalité | Tests unitaires et d'intégration | E2E (CI) |
|---|---|---|
| Authentification, première connexion, sessions expirées, 429, 502, 504, coupures | `test_securite_*`, `LoginPage.*.test` | `connexion` (5 profils × 3 latences, double clic, Entrée, téléphone, anglais, pannes) |
| Logo vers l'accueil | `LoginPage.logo.test` | `comptes` (3 tailles, anglais, avec session) |
| Réinitialisation des mots de passe, y compris superadmin | `test_password_reset` (26) | `comptes` |
| Sélection d'académie, fenêtres modales, menus | `EntitySwitcher.test` | `selecteur` |
| Navigation de tous les écrans des 5 profils | — | `navigation` (routes.json) |
| Formulaires, double envoi, écriture refusée | `useFormulaire.test`, `erreursRequetes.test` | `formulaires`, `comptes` |
| Notes, suppression justifiée, historique | `test_incidents_notes_destinataires`, contrat `mutationFn` | `donnees` |
| Bulletins (auteur, doublons, une page) | `test_bulletin_*`, `AuteurBulletinTests` | `donnees` |
| Examens | `test_evaluations` | `examens` |
| Suivi pédagogique | `test_suivi`, `test_suivi_rapports` | `suivi` |
| Paiements, transactions par carte, relances, rapports mensuels, admissions, site public | tests des modules | `modules` |
| Messagerie | `test_audit_messagerie_devoirs_presences` | `messagerie` |
| Notifications superadmin | `test_technical_incidents`, `NotificationBell.test` | — |
| Flash lumineux au changement de page | — | `flash` |
| Centre d'aide | `aide.test` (19) | `aide` (38) |
| Sauvegarde plugNmeet (surveillance) | `test_surveillance_sauvegarde` (5) | — |
| Celery opérationnel | — | étape CI dédiée, et contrôle au déploiement |

## 4. Résultats

Les chiffres CI exacts de chaque PR figurent dans `RAPPORT_TESTS_E2E.md` et dans l'onglet « Checks » de chaque PR. Aucune PR de cette phase n'a été fusionnée avec un contrôle en échec ou ignoré, et aucun test n'a été désactivé.

## 5. Limites

- Les tests E2E tournent sur une base jetable de démonstration, pas sur les données réelles.
- Pas de rejeu des 5 profils en production avec de vrais comptes : aucun compte de production n'a été créé.
- Les défauts visuels subtils (contraste, alignement) ne sont couverts que par les contrôles de débordement mobile et de flash, ainsi que par les captures vérifiées à l'œil.
