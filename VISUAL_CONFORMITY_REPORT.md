# VISUAL_CONFORMITY_REPORT.md — Conformité visuelle V6.2 (20/07/2026)

Passe corrective **de conformité** partant du dernier commit V6.1. Les
captures annotées font foi pour le CHOIX des images : « Bonne image » =
utilisée, « Pas la bonne / Mauvaise image » = retirée. Aucune interprétation
personnelle n'a remplacé une image explicitement désignée.

## 1. Tableau de conformité

Statut : **« Conforme à la capture annotée et vérifié dans le navigateur »**.

| ID | Page | Section | Ancienne image | Image attendue (annotée) | Image réellement utilisée | Slug final | Source | Desktop | Tablette | Mobile | Statut |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C1 | Accueil `/` | Mosaïque de présentation | vue drone « Here will change the WORLD » | façade FEBA logo + nom + fresques, composition verticale | même façade FEBA (logo + nom + fresques) | `campus-facade-logo` | API + fallback | ✔ | ✔ | ✔ | Conforme et vérifié navigateur |
| C2 | À propos `/a-propos` | « Une équipe engagée » · La direction | portrait serré du directeur | directeur **à son bureau** (vue large, mains + logo FEBA visibles) | directeur à son bureau | `apropos-direction-2` | fallback statique | ✔ | ✔ | ✔ | Conforme et vérifié navigateur |
| C3 | Académique `/academique` | « Deux langues, un monde d'opportunités » | têtes coupées (mur crème) | enseignante + enfants clairement visibles (têtes + bustes) | même photo, **recadrée** | `bilingue-accompagnement` | fallback statique | ✔ | ✔ | ✔ | Conforme et vérifié navigateur |
| C4 | Galerie `/galerie` | « Notre campus » (cartes 2 & 3) | 2 façades « Mauvaise image » (`campus-facade`, `campus-fresque`) | 2 « Bonne image » (façade logo/fresques + façade à la devise) | façade logo/fresques + façade devise | `campus-facade-logo`, `campus-devise` | API + fallback | ✔ | ✔ | ✔ | Conforme et vérifié navigateur |

## 2. Détail par correction

### C1 — Mosaïque d'accueil
- **Ancien chemin** : `/site/img/campus-fresque-1600.webp` (retiré de la carte).
- **Nouveau chemin** : `/site/img/campus-facade-logo-1600.webp`.
- `object-fit: cover`, `object-position: 50% 48%`.
- Fichier : `HomePage.jsx`. Aucun doublon adjacent (les 3 autres tuiles sont
  distinctes : classe, accompagnement, lecture).

### C2 — À propos · La direction
- **Ancien** : `apropos-encadrement` (portrait serré) → « Pas la bonne image ».
- **Nouveau** : `apropos-direction-2` (restauré depuis git `5ffdbfd`, ré-optimisé
  webp 800+1600), `object-position: 50% 30%`.
- Utilisé **uniquement** sur « La direction » (ni galerie, ni mosaïque).
- Cartes distinctes : La direction (bureau) / Les enseignants
  (`accompagnement-duo`) / L'encadrement (`apropos-equipe-pedagogique`).
- `apropos-direction` (première photo de bureau) reste banni.

### C3 — Académique · cadrage
- **Média conservé**, **cadrage réellement corrigé** (pas un simple micro-décalage) :
  - point focal `70% 42%` → **`50% 66%`** (desktop) / **`50% 70%`** (mobile) ;
  - conteneur agrandi `h-72 sm:h-96` → **`h-80 sm:h-[28rem]`** ;
  - overlay **responsive** `left-navy-md` : dégradé **bas** sur mobile (image
    pleinement visible, texte en pied) → dégradé **gauche** dès `sm` ;
  - texte resserré (`max-w-full sm:max-w-[46%]`) pour ne pas masquer la scène.
- Résultat : tête entière de l'enseignante + buste + têtes/bustes des enfants
  visibles **sur desktop ET sur mobile** (captures à l'appui).

### C4 — Galerie · Notre campus
- **Retirées de l'album** : `campus-facade` (« Façade de l'école »),
  `campus-fresque` (« Façade aux fresques ») — annotées « Mauvaise image ».
- **Ajoutées** : `campus-facade-logo` (« Façade FEBA — logo et fresques »),
  `campus-devise` (« La devise de l'école »).
- Ordre final : `campus-logo`, `campus-facade-logo`, `campus-devise`,
  `campus-cour` — 4 vues distinctes.

## 3. Cohérence des sources (anti-réapparition)

Le même choix est appliqué **partout** pour empêcher toute réapparition d'une
ancienne image (base vide, backend indisponible, rechargement, réinstallation
depuis le ZIP) :

| Source | Alignée ? |
|---|---|
| Backend seed (`seed_website.py` : album + `GALLERY_FOCALS`) | ✅ |
| Fallback frontend (`siteDefaults.js` : `DEFAULT_SLIDES`, `DEFAULT_ALBUMS`) | ✅ |
| Registre des points focaux (`mediaMeta.js`) | ✅ |
| Composants React (`HomePage`, `AboutPage`, `AcademicsPage`) | ✅ |
| Fichiers statiques webp 800+1600 | ✅ |

Reseed vérifié : album « Notre campus » **−2 obsolètes** (les deux façades
retirées). Le navigateur affiche les nouvelles images (rechargement forcé +
DB seedée) — la conformité ne repose PAS uniquement sur la réponse API.

## 4. Preuves

- **Tests de conformité par slug exact** : `frontend/src/site/visual-conformity.test.jsx`
  (6 cas) — vérifient que c'est **la bonne image** (slug exact) à chaque
  emplacement, et que les images rejetées sont absentes. **6/6 verts.**
- **Navigateur** : captures réelles dans `livraison_v6_2/captures/`
  (accueil, à-propos, académique, galerie ; desktop 1440 + mobile/tablette) et
  assertions DOM (`getComputedStyle`, `img.currentSrc`).
- Suites complètes : **62 tests frontend**, **300 backend** (+1 skip), eslint
  **0 erreur**, build prod **OK**.
