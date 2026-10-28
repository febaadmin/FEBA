# FEBA — Rapport de tests

Exécuté le 2026-09-04.

---

## 1. Totaux

| Suite | Résultat |
|---|---|
| Backend PostgreSQL (référence) | **1297 passés, 0 échec**, 590 sous-tests |
| Backend SQLite | **1296 passés, 1 ignoré** |
| Frontend (Vitest) | **246 passés, 25 fichiers** |
| Parcours navigateur — capture (§38) | **11/11** |
| Parcours navigateur — par rôle (§31) | **17/17** |
| Parcours navigateur — non-régression V10 | **15/15** |
| ESLint | **0 erreur**, 81 avertissements (référence inchangée) |
| `npm run build` | **OK** |
| `makemigrations --check` | **Aucun changement détecté** |
| `manage.py check` | **Aucun problème** |
| `docker compose config` | **5 assemblages valides** |
| `repo_safety_check.sh` | **Dépôt sain** |

### L'unique test ignoré

`test_parent_student.py` — concurrence multi-threads. SQLite en mémoire
verrouille la table entière. **Il s'exécute et passe sur PostgreSQL**, la
base de référence. Ce n'est pas un test contourné : c'est le même test,
exécuté là où il a un sens.

---

## 2. Tests ajoutés

### Backend

| Fichier | Objet | Nombre |
|---|---|---|
| `test_v11_class_language_rules.py` | cas A–H, parcours strict, cloisonnement, même verdict sur les deux chemins, refus expliqué | 16 |
| `test_v11_jitsi_moderators_and_jwt.py` | modérateur par rôle, escalade refusée à l'API, émetteur, algorithme, durée, jeton non signé, jeton périmé | 11 (+5 sous-tests) |
| `test_v11_jitsi_health_checks.py` | `external_api.js` et `/xmpp-websocket`, faux positifs écartés | 5 (+3 sous-tests) |

### Frontend

| Fichier | Objet | Nombre |
|---|---|---|
| `utils/classLanguage.test.js` | cas A–H côté navigateur, parcours strict, résumés, non-divergence affichage/soumission | 20 |
| `components/JitsiMeeting.test.jsx` | §12 — cycle de vie **compté** (ajout de 3 tests) | 15 au total |

---

## 3. Chaque correction prouvée par sa suppression

Un test qui ne tombe jamais ne prouve rien.

| Correctif retiré | Tests qui tombent |
|---|---|
| Validation backend des matières | **10** |
| Dépendances réduites de `JitsiMeeting` | **7** (dont le test §12) |
| Distinction « inconnue » / « interdit » | **3** |

---

## 4. Deux tests qui passaient pour une mauvaise raison

Signalés parce qu'ils sont plus instructifs qu'un échec ordinaire.

**a) La fixture V10 s'activait toute seule.** Depuis le correctif de
`SchoolYear.save()`, `year(..., current=False)` produisait une année
immédiatement active : le test central passait **même avec le défaut
d'origine**.

**b) Deux tests V11 attendaient un 404 qu'ils obtenaient de l'URL
absente.** Le helper inséré entre `@action` et `join` avait supprimé la
route ; les tests recevaient le 404 de Django, pas celui du contrôle
d'accès. Ce sont les parcours navigateur qui l'ont montré — un rappel
que 1297 tests verts ne remplacent pas un vrai clic.

---

## 5. Parcours navigateur

### §38 — le scénario exact de la capture

| # | Vérification | Résultat |
|---|---|---|
| 1 | Connexion administrateur FEBA FHA | **PASS** |
| 2 | La modale Matières s'ouvre | **PASS** |
| 3 | Le parcours francophone est annoncé | **PASS** |
| 4 | Colonne française admise | **PASS** |
| 5 | Colonne anglaise NON admise | **PASS** |
| 6 | Toutes les cases anglaises désactivées (2/2) | **PASS** |
| 7 | Résumé : « Configuration complète — 4 matière(s) française(s) » | **PASS** |
| 8 | **AUCUN toast « au moins une matière anglaise »** | **PASS** |
| 9 | Le backend accepte (HTTP 200) | **PASS** |
| 10 | Après rechargement complet, 4/4 matières toujours affectées | **PASS** |
| 11 | Aucune erreur JavaScript | **PASS** |

### §31 — par rôle, sur la salle virtuelle

| Rôle | Résultat |
|---|---|
| Administrateur FHA | refus explicite (503, visio non configurée en dev), aucun repli public |
| Enseignant FHA | idem |
| **Élève FHA** (autre classe) | **403 — « Vous n'êtes pas inscrit dans le groupe de cette salle. »** |
| Parent FHA | refus explicite |

Pour chacun : aucune mise en page FEBA autour de la conférence, aucun
repli `meet.jit.si`.

---

## 6. Bulletins réellement générés (§39)

Trois PDF produits, ouverts et inspectés visuellement.

| Parcours | Sections | Occurrences interdites |
|---|---|---|
| FRANCOPHONE | partie française seule | **0** |
| ANGLOPHONE | partie anglaise seule | **0** |
| BILINGUE | les deux + moyenne bilingue + formule | — (attendu) |

« Occurrences interdites » = section vide, moyenne d'une langue absente,
formule bilingue sur un parcours monolingue.

---

## 7. Contrôles réseau réels

| Contrôle | Cible | Résultat |
|---|---|---|
| `make jitsi-health` | `meet.globalfeba.com` | **OPÉRATIONNEL**, 9 contrôles au vert |
| DNS | | `89.167.63.1` |
| HTTPS | | 200 |
| `external_api.js` | | 200, `application/javascript` |
| `/xmpp-websocket` | | 200 — le proxy a une règle |
| Chemins sensibles (`/.env`, `/.git/config`…) | | catch-all du SPA, **aucune fuite** |
| En-têtes | | HSTS, `nosniff`, `Permissions-Policy` présents |

---

## 8. Non testé ici

| Point | Statut |
|---|---|
| Réunion à 2 participants (§32) | **À TESTER EN ENVIRONNEMENT RÉEL** |
| Stabilité 30 minutes (§33) | **À TESTER EN ENVIRONNEMENT RÉEL** |
| Poignée de main WebSocket complète | **À TESTER EN ENVIRONNEMENT RÉEL** |
| Refus d'adhésion anonyme sur l'instance en service | **À TESTER EN ENVIRONNEMENT RÉEL** |
| TURN / Coturn (§25) | **À TESTER EN ENVIRONNEMENT RÉEL** |
| `docker compose up` complet | **LIMITATION CONNUE** |

Raisons détaillées dans `KNOWN_LIMITATIONS.md`.
