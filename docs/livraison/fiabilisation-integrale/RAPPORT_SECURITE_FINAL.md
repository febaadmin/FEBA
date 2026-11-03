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
