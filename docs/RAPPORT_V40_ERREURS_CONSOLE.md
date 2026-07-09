# FEBA v40 — Rapport : erreurs console (404 classes, avertissements React Router), robustesse

Date : 08/07/2026 · Base : v39 · Diagnostic : capture + vidéo + **journal console du navigateur** que vous avez fourni.

---

## 1. `/api/classes/2/` et `/api/classes/8/` → 404 en boucle (cause racine)

**Symptôme console** : des dizaines de `GET/PATCH/DELETE /api/classes/8/ → 404`, répétés.
**Cause racine (backend)** : le filtre « année active par défaut » introduit en v34 s'appliquait à **TOUTES** les actions du ViewSet, y compris `retrieve` / `update` / `delete`. Conséquence : dès qu'on éditait ou supprimait une classe d'une année **non active** (ex. une classe 2023-2024 alors que l'année active est 2026-2027), l'objet n'était pas dans le queryset → **404**. Vos captures montrent précisément ce cas (contenu 2023-2024 affiché sous une année active 2026-2027, séquelle du désalignement corrigé en v39).
**Cause aggravante (frontend)** : React Query **réessaie 3 fois** par défaut chaque requête échouée → une seule action produisait une salve de 404 dans la console.

**Corrections :**
- **Backend** : le filtre par défaut sur l'année active ne s'applique plus qu'à l'action **`list`**. Les actions de détail (consulter, modifier, supprimer, matières, élèves…) atteignent une classe de **n'importe quelle année** — l'isolation des listes est préservée, mais on peut de nouveau gérer une classe d'une année passée. Plus de 404.
- **Frontend** : configuration globale React Query — **aucun réessai sur les erreurs 4xx** (401/403/404), un seul réessai sur les erreurs réseau/5xx transitoires. Une éventuelle erreur ne génère plus de rafale. Les mutations de classe (créer/modifier/supprimer) gèrent explicitement l'erreur : message clair (« Cette classe n'existe plus », ou détail 409 des dépendances) + rafraîchissement de la liste, sans boucle.

## 2. Avertissements React Router (Future Flags)

**Symptôme console** : deux `React Router Future Flag Warning` (`v7_startTransition`, `v7_relativeSplatPath`).
**Correction** : activation des deux future flags sur le `BrowserRouter` — les avertissements disparaissent et l'application est prête pour React Router v7 (comportement `startTransition` et résolution des routes splat adoptés dès maintenant, sans changement fonctionnel visible).

## 3. `/api/schools/branding/active/` → 401 (transitoire, déjà maîtrisé)

**Analyse** : ce 401 apparaît dans la brève fenêtre où un jeton d'accès expiré est présent au chargement, avant son rafraîchissement automatique. Il est **déjà géré sans effet de bord** : `branding/active` est classé endpoint « non critique » (ne déclenche pas de déconnexion), le hook `useBranding` ne le lance que si un jeton existe et ne réessaie pas sur 401/403, et l'endpoint renvoie de toute façon un logo par défaut (jamais d'écran cassé). Avec la règle « pas de réessai 4xx » ajoutée en §1, ce 401 n'est plus jamais répété. Aucun changement fonctionnel nécessaire ; comportement confirmé robuste.

## 4. Rappel : le décalage puce/contenu (corrigé en v39)

La vidéo rejoue le symptôme « puce 2026-2027 active / tableau 2023-2024 ». La correction est déjà dans le code livré : filtre d'année **déterministe** côté frontend (la puce surlignée et le contenu partagent le même identifiant résolu) + **contrainte base** « une seule année active par établissement » + **migration** de nettoyage `schools/0008`. **Important** : ces correctifs ne prennent effet qu'après **reconstruction du conteneur et application des migrations** — votre enregistrement tournait manifestement encore sur un build antérieur. Voir la note de mise à jour ci-dessous.

## 5. Vérifications

Backend compilé ; graphe de migrations intègre ; 78 fichiers frontend, 0 erreur ; imports/appels API valides. **4 nouveaux tests** (`CrossYearClassDetailTests`) : la liste reste limitée à l'année active par défaut, mais consulter / modifier / supprimer une classe d'une année passée renvoie 200/204 (plus de 404). Check-list du guide portée à **47 scénarios**.

## 6. Fichiers modifiés
| Fichier | Nature |
|---|---|
| `backend/apps/classes/views.py` | Filtre année active par défaut limité à l'action `list` (fix 404 détail) |
| `frontend/src/main.jsx` | React Router future flags v7 ; React Query sans réessai 4xx (queries + mutations) |
| `frontend/src/pages/admin/Classes.jsx` | Gestion d'erreur explicite des mutations (404/409), rafraîchissement au lieu de boucle |
| `backend/tests/test_linked_accounts_and_classes.py` | +4 tests (détail inter-années) |
| Guides PDF | Check-list 47 scénarios |

## 7. Note de mise à jour (IMPORTANT)
Plusieurs correctifs récents (v39 année active unique + migration `schools/0008`, v40 détail inter-années) nécessitent de **reconstruire et migrer** :
```
docker compose down
docker compose up --build -d      # applique automatiquement les migrations, dont schools/0008
# (rechargez l'onglet avec vidage du cache : Cmd+Shift+R)
```
La migration `schools/0008` corrige au passage tout état où plusieurs années étaient actives (à l'origine du décalage puce/contenu). Après cela, la console doit être propre : plus d'avertissement React Router, plus de salve de 404.
