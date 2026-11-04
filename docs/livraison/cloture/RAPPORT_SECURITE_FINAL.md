# Sécurité

**FEBA n'est pas déclaré sûr à 100 %.**

| Sujet | État | Preuve |
|---|---|---|
| Backend en root | **Corrigé** : uid 10001, Celery aussi | Production lue : `id`, volumes `feba:feba`, écriture vérifiée |
| Images | nginx 1.28.1 avec paquets à jour ; backend sans `gcc` | Trivy en CI : bloquant sur secret, informatif sur CVE |
| CVE nginx | 3 critiques et 17 élevées, puis 1 et 9 | Trivy |
| CVE backend | 1 critique et 71 élevées **sans correctif Debian publié** | Trivy. Risque accepté, réexaminé à chaque CI |
| Secrets dans les images | 0 | Trivy |
| Secrets dans le dépôt | 8 constats dans l'historique et 6 dans l'archive : tous factices, de test ou faux positifs | Classement ci-dessous |
| Jetons en `localStorage` | **Non corrigé** | Étude ci-dessous |
| CSP | Appliquée. 0 violation sur 10 pages publiques en production | Lecture seule |
| React Router | 0 vulnérabilité npm en production | `npm audit` |
| Isolation, IDOR | Tests PostgreSQL et E2E | Campagne 2, 7, 19 académies, accès entre personnes |
| Test d'intrusion externe | **Non fait** | Prestataire requis |

## Alertes Gitleaks

Classées sans afficher de valeur ni comparer à la production : la comparaison a été refusée par le contrôle de sécurité.

| Fichier | Type | Nature | Preuve |
|---|---|---|---|
| `JITSI_PRODUCTION_ACTIONS.md:239`, `plugnmeet/ops/meet_plugnmeet.sh:48` | `Sec-WebSocket-Key` | Faux positif | Clé publique d'exemple du protocole WebSocket |
| `backend/tests/test_production_preflight.py:26` | Clé d'API | Valeur de test | Fichier de test |
| `backend/tests/test_v11_jitsi_moderators_and_jwt.py:27` | Secret | Valeur de test | Fichier de test |
| `scripts/compose_config_check.sh:52` (2 commits) | Secret Jitsi | Factice | 2 blocs de 8 caractères seulement, répétés, dans un `.env` de validation |
| `scripts/plugnmeet_setup.sh:31` | Empreinte | Faux positif | SHA-256 publique du client plugNmeet v2.5.3 |
| `KNOWN_LIMITATIONS_V8.md:64`, historique seulement | Jeton Stripe de test | Factice | 27 majuscules sans chiffre, mots « DEMO », « CLE », « VALIDE » |

**Action :** aucune rotation nécessaire d'après ces éléments. La comparaison formelle avec les secrets de production reste une décision humaine.

## Cookies HttpOnly : étude, non migré

**Aujourd'hui :** jetons JWT dans `localStorage` (zustand `feba-auth`), envoyés en `Authorization`. Un XSS pourrait les lire. Atténuations en place : CSP bloquante, `script-src 'self'`, avatars et pièces jointes contrôlés, `/media/` sandboxé.

**Migration envisagée**
- `refresh` en cookie `HttpOnly`, `Secure`, `SameSite=Strict`, chemin `/api/auth/` ; `access` gardé en mémoire seulement.
- Renouvellement au démarrage et à l'expiration par `POST /api/auth/refresh/`, protégé CSRF (cookie `SameSite` et contrôle d'origine).
- Déconnexion : mise sur liste noire et effacement du cookie.

**À adapter :** `authStore`, `tokenRefresh`, `useAuth`, intercepteur, garde de route, `academyBoot`, liens signés de fichiers, script plugNmeet (jetons de salle).

**Pourquoi pas maintenant :** c'est un changement transversal de l'authentification de tous les profils, qui demande sa propre PR et la suite E2E en appui. Avec la CSP appliquée, le risque résiduel est un XSS non encore découvert. **Proposition :** lot dédié.

## Dépendances

`npm audit --omit=dev` : 0. Python : job « Sécurité des dépendances » de la CI au vert. `pip-audit` local : non concluant, dépendances non figées.

## Non fait

Test d'intrusion, revue ligne à ligne des 148 déclarations d'API (la couverture repose sur les campagnes automatisées et les tests ciblés), Redis sans mot de passe vérifié, journaux de l'ancien conteneur nginx.

## Complément du 04/11/2026 (phase 3)

### Réinitialisation du mot de passe d'un superadmin (PR #70)

- **Autorisé** : un superadmin réinitialise un **autre** superadmin, jamais lui-même.
- **Ré-authentification** : le champ `requester_password` est obligatoire. S'il manque, réponse 400 ; s'il est faux, réponse 403. Dans les deux cas, aucune modification et aucun journal de réinitialisation.
- **Effets** :
  - mot de passe haché ;
  - changement imposé à la prochaine connexion ;
  - révocation de tous les jetons de renouvellement et fermeture des WebSockets ;
  - `PasswordResetLog`, qui ne contient jamais le mot de passe.
- **Avertissement** : le titulaire reçoit un e-mail, tracé, qui ne contient pas le mot de passe.
- **Refus** : un administrateur reste refusé (403), même s'il fournit un mot de passe.
- **Tests** : 26 tests backend et le scénario E2E `comptes` (superadmin de test créé dans la base jetable). Aucun des 4 comptes réels n'a été touché.
- Il n'existe pas de réinitialisation par e-mail (« mot de passe oublié ») dans FEBA : constaté, rien n'a été ajouté.

### Alertes de sécurité et d'exploitation visibles (PR #73)

La cloche des notifications a été ajoutée à l'interface superadmin, où 87 notifications restaient sans lecteur. Les incidents critiques déclenchent aussi un e-mail, aux mêmes seuils que la cloche.

### Durcissement

- `server_tokens off` sur le frontal et sur le conteneur frontend : la version de nginx n'est plus divulguée (PR #74).
- Écritures refusées : le motif du serveur est toujours affiché. Ce n'est pas une faille, mais une erreur muette pouvait masquer un refus d'autorisation (PR #75).

### Contrôles en lecture seule sur la production

| Contrôle | Résultat |
|---|---|
| TLS | 1.0 et 1.1 refusés ; 1.2 et 1.3 acceptés ; certificat valide jusqu'au 07/12/2026 |
| En-têtes | HSTS (preload), CSP, X-Frame-Options DENY, nosniff, Referrer-Policy, Permissions-Policy |
| Fichiers sensibles | `/.env` et `/.git/config` renvoient la page de l'application, sans fuite |
| Documentation d'API | `/api/schema/` et `/api/docs/` renvoient 404 |
| Admin Django | public, limité à 10 requêtes par minute et par IP, 1 compte habilité ; restriction par IP proposée (décision humaine) |
| Dépendances | `npm audit` et `pip-audit` (prod.txt) : 0 vulnérabilité connue |

### Restent ouverts

- Migration des jetons vers des cookies HttpOnly (étudiée, non faite).
- Test d'intrusion actif sur un environnement de préproduction : il n'existe pas de préproduction.
- Surveillance de la sauvegarde Restic de FEBA : nécessite un accès root.
