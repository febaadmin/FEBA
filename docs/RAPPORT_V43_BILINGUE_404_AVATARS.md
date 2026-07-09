# FEBA v43 — Rapport : bilingue 404 (route masquée) & avatars/logos en URL absolue

Date : 08/07/2026 · Base : v42 · Diagnostic décisif : le **journal console** de l'Image 3.

---

## Ce que la console a révélé (Image 3)

Deux erreurs précises, invisibles sans la console :
```
GET http://localhost:5173/api/grades/bilingual/?student=8&period=T1&school_yea… 404 (Not Found)
GET http://backend-dev:8000/media/avatars/rousse.jpg   net::ERR_NAME_NOT_RESOLVED
```
Le « Calcul bilingue indisponible » des captures précédentes n'était donc **pas** un problème de données : c'était un vrai **404** sur l'endpoint. Et un avatar pointait encore vers l'hôte interne Docker.

## 1. Bilingue → 404 (route masquée par le routeur)

**Cause racine** : dans `apps/grades/urls.py`, le routeur DRF est enregistré sur le préfixe vide `r''`. Il génère une route `<pk>/` qui **capturait « bilingual » (et « all-history ») comme un identifiant de note** → 404. Les chemins explicites étaient déclarés **après** `router.urls`, donc masqués. C'est exactement le même schéma que le bug `notifications/unread-count` corrigé en v41 — il restait deux routes vulnérables.
**Correction** : les chemins explicites `bilingual/` et `all-history/` sont désormais placés **avant** `router.urls`, donc résolus en priorité. Le calcul bilingue répond de nouveau (et, grâce au filet de sécurité v42, ne renvoie jamais 500 même sans matières FR/EN).

## 2. Avatars / logos en `http://backend-dev:8000/...` (ERR_NAME_NOT_RESOLVED)

**Cause racine** : le champ `avatar` était exposé via le sérialiseur `ImageField` **standard** de DRF, qui construit **automatiquement une URL absolue** (`request.build_absolute_uri`) quand la requête est dans le contexte. En développement, l'hôte vu par Django est `backend-dev:8000` (proxy Vite) — irrésoluble par le navigateur. Le champ n'apparaissait pas dans nos recherches de `build_absolute_uri` car c'est DRF qui le fait en interne.
**Corrections (défense en profondeur, backend + frontend)** :
- **Backend** : `avatar` sérialisé en **chemin relatif** (`/media/avatars/…`) via un `SerializerMethodField` renvoyant `obj.avatar.url`, sans dépendre du request. Idem pour la photo enseignant (`get_user_photo`). Les URLs médias se résolvent alors sur l'origine du client (proxy Vite en dev, Nginx en prod).
- **Frontend** : nouvel utilitaire `resolveMediaUrl()` qui ramène **toute** URL média à un chemin relatif au moment du rendu (gère aussi d'éventuelles valeurs absolues héritées). Appliqué aux avatars (composant AvatarUpload, pages Enseignants et Utilisateurs) et aux logos (hook `useBranding`, page Branding). Les `<img>` avatars reçoivent aussi un `onError` qui masque proprement une image manquante.

## Vérifications

Backend compilé ; graphe de migrations intègre (aucune migration) ; 79 fichiers frontend, 0 erreur ; imports/appels API valides. **4 nouveaux tests** (`BilingualRouteAndAvatarTests`) : `bilingual/` répond 200 (plus 404) ; `all-history/` résolu (pas 404) ; l'avatar sérialisé commence par `/media/` et ne contient jamais `backend-dev` ni `http`. S'ajoutent aux tests v41/v42. Check-list du guide portée à **53 scénarios**.

## Fichiers modifiés
| Fichier | Nature |
|---|---|
| `backend/apps/grades/urls.py` | Routes `bilingual/` + `all-history/` avant `router.urls` (fix 404) |
| `backend/apps/accounts/serializers.py` | `avatar` en chemin relatif |
| `backend/apps/teachers/serializers.py` | Photo enseignant en chemin relatif |
| `frontend/src/utils/media.js` | Nouvel utilitaire `resolveMediaUrl` |
| `frontend/src/components/ui/AvatarUpload.jsx`, `pages/admin/{Teachers,Users,Branding}.jsx`, `hooks/useBranding.js` | Normalisation des URLs média au rendu |
| `backend/tests/test_averages_and_notifications.py` | +4 tests (route bilingue, avatar relatif) |
| Guides PDF | Check-list 53 scénarios |

## Note de mise à jour
Correctifs backend + frontend, sans migration. Après extraction :
```
docker compose up --build -d
# rechargez l'onglet (Cmd+Shift+R)
```
La console de l'onglet Notes → Bilingue doit alors être exempte de 404, et les photos de profil/logos doivent s'afficher (plus aucune référence à backend-dev:8000).
