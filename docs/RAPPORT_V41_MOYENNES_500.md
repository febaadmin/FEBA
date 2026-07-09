# FEBA v41 — Rapport : erreurs 500 sur les moyennes (espace élève) et 404 notifications

Date : 08/07/2026 · Base : v40 · Diagnostic : captures console de l'espace élève (Marie Agossou, CE1-A).

---

## 1. `/api/grades/averages/` → 500 (Internal Server Error) — bug majeur

**Symptôme console** : sur l'Accueil élève et « Mes notes », une **quinzaine de 500** répétés sur `GET /api/grades/averages/?period=T1|T2|T3&school_year=4`. La moyenne générale affichait « — » et les cartes trimestrielles restaient vides.

**Deux causes racines dans l'endpoint `averages` :**

1. **`float(None)`** — depuis la v32, une matière **non notée** a une moyenne `None` (règle métier : elle est exclue du calcul, pas comptée 0). L'endpoint `averages` faisait `float(info["average"])` **sans garde** → `TypeError` → 500 dès qu'une matière du détail par matière n'était pas notée. C'est exactement le cas de Marie (aucune note dans l'année active) : le détail par matière contenait des `None`. L'endpoint `averages` n'avait pas été mis à jour lors de la correction v32 (les autres — résumé, bilingue, PDF — l'avaient été).

2. **`SchoolYear.DoesNotExist` non gérée** — la résolution de l'année utilisait `SchoolYear.objects.filter(school=school).get(pk=school_year_id)`. Pour un élève dont `get_request_school` renvoie l'établissement mais où l'année demandée n'y est pas trouvée (ou `school=None`), le `.get()` levait une exception **non capturée** (le `except` ne couvrait que `Student.DoesNotExist`) → 500.

**Corrections :**
- Détail par matière **None-safe** : `float(info["average"]) if info["average"] is not None else None` — une matière non notée renvoie `average: null` au lieu de planter.
- **Résolution robuste de l'année** : sur l'établissement **de l'élève** si le tenant est absent (élève/superadmin), et **repli sur l'année active** si l'année demandée n'existe pas (au lieu d'une exception). Si aucune année n'est résolue, réponse 200 avec moyenne nulle.
- **Filet de sécurité** : toute erreur imprévue du calcul est journalisée et renvoie une moyenne nulle (200) — le tableau de bord élève ne casse plus jamais sur les moyennes.

Marie n'ayant aucune note dans l'année active, les moyennes valent désormais `null` proprement (« — » à l'écran), ce qui est correct — plus aucune 500.

## 2. `/api/notifications/unread-count/` → 404

**Symptôme console** : `GET /api/notifications/unread-count/ → 404`, sur toutes les pages (cloche de notifications).
**Cause racine** : le routeur DRF, enregistré sur le préfixe vide `r""`, génère une route `<pk>/` qui **capturait « unread-count »** comme un identifiant de notification → 404. L'alias explicite existait mais était déclaré **après** `router.urls`, donc masqué.
**Correction** : les routes explicites (`unread-count/`, `read-all/`, `<pk>/read/`) sont désormais placées **avant** `router.urls`, donc résolues en priorité. Le compteur de notifications se charge correctement.

## 3. Vérifications

Backend compilé ; graphe de migrations intègre (aucune migration — corrections de logique/routage) ; 78 fichiers frontend, 0 erreur ; imports/appels API valides. Audit complémentaire : aucun autre `float(...["average"])` non gardé dans le code (le seul restant était l'endpoint `averages`). **5 nouveaux tests** (`test_averages_and_notifications.py`) : moyennes sans note → 200/null ; moyennes partielles → pas de `float(None)`, seule la matière notée compte ; année inconnue → repli ; auto-détection de l'élève connecté ; route `unread-count` à tiret → 200. Check-list du guide portée à **49 scénarios**.

## 4. Fichiers modifiés
| Fichier | Nature |
|---|---|
| `backend/apps/grades/views.py` | Endpoint `averages` : None-safe, résolution d'année robuste, filet de sécurité |
| `backend/apps/notifications/urls.py` | Routes explicites avant `router.urls` (fix 404 unread-count) |
| `backend/tests/test_averages_and_notifications.py` | 5 tests de régression |
| Guides PDF | Check-list 49 scénarios |

## 5. Note de mise à jour
Ces correctifs sont purement backend (aucune migration). Après extraction du zip :
```
docker compose up --build -d   # reconstruit le backend
# rechargez l'onglet (Cmd+Shift+R)
```
La console de l'espace élève doit alors être propre : plus de 500 sur les moyennes, plus de 404 sur le compteur de notifications.
