# VISUAL_FIXES_REPORT.md — Corrections visuelles V5 + V6 + V6.1

## V7 (25/07/2026)
P5 façade (panneau « Faith & Excellence » + fresques) sur accueil + galerie ; focal 50/42
(panneau non coupé, crop simulé vérifié). P6 vidéo galerie : visionneuse à contrôles, portrait
letterbox, arrêt à la fermeture. P7 Admissions « La visite du campus » : conteneur h-72 sm:h-80
+ focal 50/60 → corps entiers des enfants/parents visibles (capture navigateur). Résolutions
375/768/1280/1440.


## V6.1 (20/07/2026) — captures annotées : remplacements, image bannie, dégradé

Vérifié dans le navigateur réel sur l'app lancée (dev `:5173` + API `:8000`
reseedée), par captures **et** assertions DOM déterministes (`getComputedStyle`,
`img.currentSrc`). Aucune preuve fabriquée.

| # | Page / Section | Défaut annoté | Correction | Preuve |
|---|---|---|---|---|
| 1 | Galerie · Notre campus | 2 façades rouges quasi identiques (Image 1/2) | remplacées par `campus-logo` + `campus-fresque` (4 vues distinctes) | DOM : `campus-logo`, `campus-facade`, `campus-fresque`, `campus-cour` |
| 2 | Accueil · carrousel | bâtiment à remplacer par « l'image avec le logo » | slide 1 → `campus-logo` (panneau « Faith & Excellence ») | DOM : `slide1 = campus-logo-1600.webp` |
| 3 | Accueil · mosaïque | façade rouge à remplacer par « l'image avec les dessins » | → `campus-fresque` (fresques + logo) | DOM + capture : fresque en mosaïque |
| 4 | Galerie · visionneuse | « cette image ne doit apparaître nulle part » (homme au bureau) | `galerie-mosaique-3` + `apropos-direction*` supprimés (site + paquet) | DOM : `forbiddenPresent = false` ; fichiers retirés |
| 5 | Galerie · vignettes | « image mal cadrée » (devoirs, soutien, étude, écriture, accompagnement) | recadrage individuel par focal | `object-position` vérifié : 50/66, 50/68, 66/46, 66/46, 52/64 |
| 6 | Accueil · carrousel | « couleur grise pas belle » (slide Apprendre/grandir) | voile gris → dégradé marine DA FEBA + pointe dorée (systématique) | capture slides 2 & 5 : dégradé marine ; DOM : `hero-left`+`hero-gold` présents |
| 7 | À propos · Une équipe engagée | image 1 = image 2 (même personne) | 3 cartes distinctes (portrait direction / enseignants / équipe) | DOM : `apropos-encadrement`, `accompagnement-duo`, `apropos-equipe-pedagogique` |
| 8 | Galerie · Petite enfance | nouvelle crèche à intégrer | ajout `petite-enfance-creche` (titre/alt/catégorie/focal) | reseed : Petite enfance 4 médias ; DOM : crèche présente |

Résolutions vérifiées : 375 / 768 / 1280 / 1440 / 1920 (site public sans auth).

---

# VISUAL_FIXES_REPORT.md — Corrections visuelles V5 + V6

## V6 (20/07/2026) — Carrousel, galerie, doublons, recadrages, menu

Vérifié dans un vrai navigateur sur l'application réellement lancée (dev server
`:5173` + API `:8000`), aux largeurs **375 / 1280 / 1920**. Aucune capture n'est
fabriquée.

| # | Défaut (avant) | Correction | Fichier(s) | Preuve navigateur |
|---|---|---|---|---|
| P1 | Accueil : image **statique** à la place du carrousel | Carrousel 5 slides réelles + repli packagé (jamais statique/vide) ; flèches (≥ sm), points, clavier, tactile, `prefers-reduced-motion` | `HeroCarousel.jsx`, `siteDefaults.js` | 1280 : slide « Bienvenue à FEBA », flèches + 5 points ; auto-défilement observé (slides 1→2→3) ; 375 : flèches masquées, 5 points |
| P2 | Galerie : « La galerie sera bientôt disponible » | Repli `DEFAULT_ALBUMS`, état vide seulement si réellement aucun média | `GalleryPage.jsx`, `HomePage.jsx` | 1920 : album « Vie de classe » plein, 8 vignettes distinctes |
| P3 | `hero-campus` répété ≈8×, vignettes dupliquées | Dédoublonnage global + élagage seed | voir `MEDIA_DUPLICATES_REPORT.md` | usage max = 2 (hero↔slide) ; vignettes toutes différentes |
| P4 | CM1·CM2 : visuel montrant surtout mur/plafond crème | Visuel remplacé (`valeurs-projet`), overlay `bottom-navy` | `content.js`, `mediaMeta.js` | carte CM1·CM2 exploitable |
| P4 | Cartes vie scolaire : sujets trop bas | Points focaux relevés | `mediaMeta.js` | têtes non coupées |
| P4 | `academique-participation` : enseignante hors cadre | Focal `26% 64%` (bas-gauche, hors mur crème) | `mediaMeta.js`, seed | vignette « Participation en classe » : enseignante visible |
| P5 | « Grandir en confiance » : bande crème à gauche | `MediaFrame` `aspect-[5/4] sm:aspect-[16/11]` + `position 74% 60%`, overlay | `SchoolLifePage.jsx` | plus de vide crème |
| P6 | Menu desktop **sur 2 lignes** (À propos / Vie scolaire / FEBA Online) | En-tête une ligne : `whitespace-nowrap`, `min-[1200px]`, sous-titre `2xl:block`, hamburger propre en-dessous | `SiteLayout.jsx` | 1280 & 1920 : une seule ligne ; 375 : overlay hamburger propre (9 liens + 2 CTA + fermeture) |

---

# VISUAL_FIXES_REPORT.md — Corrections visuelles V5 (19/07/2026)

Preuves : captures réelles dans `livraison_v5/captures/`
(`avant/` = 30 pages complètes AVANT, `apres/` = 30 pages complètes APRÈS,
`breakpoints/` = accueil aux 9 largeurs 320/375/390/430/768/1024/1280/1440/1920).
Aucune capture n'est fabriquée : toutes proviennent de Chrome headless sur
l'application réellement lancée (dev server + API locales).

## Architecture des corrections

| Élément | Fichier | Rôle |
|---|---|---|
| Registre des points focaux | `frontend/src/site/mediaMeta.js` | object-position desktop + variante mobile pour CHAQUE visuel packagé ; tokens de dégradés `OVERLAYS` (source unique, aucun gradient arbitraire dans les pages) |
| Application automatique | `frontend/src/site/components/SiteImage.jsx` + `.site-img` (index.css) | variables CSS `--site-img-pos` / `--site-img-pos-mobile` (bascule < 640 px) |
| Cadre média du design system | `frontend/src/site/components/MediaFrame.jsx` | image + dégradé token + zone de texte superposée |
| Point focal administrable | `apps/website` (`focal_x`/`focal_y` sur HeroSlide, GalleryItem, NewsPost + migration 0002) | cadrage modifiable depuis l'admin sans toucher au code ; exposé par l'API (`focal`) et appliqué par le carrousel, la galerie et les actualités |
| Tests | `mediaMeta.test.js` (6), `test_website.py::FocalPointTests` (4) | cohérence registre ↔ fichiers, bornes 0–100, valeurs seedées, PATCH admin |

## Corrections détaillées

### F1 — Hero « Apprendre, grandir et s'épanouir » (slide 4)
- **Problème initial** (avant/accueil-*.png, visible en interactif) : ronde
  d'enfants écrasée en bas du cadre, ~50 % de crème vide, enfants coupés.
- **Cause** : `object-position: center` sur une image 2:1 dont le sujet est
  dans le tiers inférieur.
- **Correction** : focal administré 55 %/78 % (mobile 60 %/80 %), dégradé
  hero unifié (token `OVERLAYS.hero` + `top-navy` pour la lisibilité du
  header), titre réduit sur mobile (1.7 rem), largeur de texte limitée.
- **Après** : ronde entière visible, texte lisible, vérifié interactivement
  à 342 px et sur les captures. **Statut : Corrigé et vérifié.**

### F2 — Hero « Admissions ouvertes » (slide 5)
- **Problème** : scène d'accueil à droite, crème vide à gauche ; sur mobile
  le titre passait sous la flèche gauche.
- **Correction** : focal 72 %/45 % (mobile 78 %/45 %) — le bloc de texte du
  carrousel occupe la zone libre ; **flèches masquées < 640 px** (le swipe
  tactile et les points restent, plus aucun chevauchement).
- **Statut : Corrigé et vérifié** (capture interactive mobile).

### F3 — Carte « CM1 · CM2 » (accueil, cf. maquette de mission)
- **Problème** : image `academique-participation` (enseignante à droite,
  ~60 % crème à gauche) affichée en bandeau `cover` centré : carte aux 3/5
  vides, élèves coupés.
- **Correction** : cartes de niveaux refondues en compositions pleine
  image ; pour CM1·CM2, **dégradé marine gauche (`left-navy`) + texte
  « CM1 · CM2 / Préparation à l'entrée au collège : autonomie, méthode et
  excellence » posé DANS l'ancienne zone crème** ; focal 82 %/28 % qui
  garde l'enseignante entière. Rendu identique à la maquette « APRÈS ».
- **Preuve** : comparatif avant/après (accueil-desktop y≈1600–2150).
  **Statut : Corrigé et vérifié.**

### F4 — Cartes de niveaux Garderie → CE1·CE2
- **Problème** : bandeaux images avec hauts de têtes affleurants/coupés
  (CE1·CE2 le plus marqué) + bloc texte séparé sans dialogue avec l'image.
- **Correction** : composition unifiée image + voile `bottom-navy` + texte
  en pied, focal individuel par niveau (50/42 · 50/42 · 50/36 · 50/30).
- **Statut : Corrigé et vérifié.**

### F5 — Section « Une équipe engagée » (À propos)
- **Problème** : portrait 2:3 de l'encadrement **tête totalement coupée**
  (seul le costume restait visible) ; carte centrale à moitié crème ;
  cadrages hétérogènes.
- **Correction** : trois cartes harmonisées h-72 en `MediaFrame`, focal
  individuel (50/28 · 80/40 · **50/16** pour le portrait — visage entier
  avec marge), légendes homogènes sur voile marine (« La direction »,
  « Les enseignants », « L'encadrement » + une phrase), surtitres dorés.
- **Preuve** : comparatif a-propos-desktop y≈1650–2150. **Statut : Corrigé et vérifié.**

### F6 — Section bilinguisme (Académique)
- **Problème** : image `bilingue-accompagnement` avec moitié gauche crème vide.
- **Correction** : `MediaFrame` `left-navy` + **texte « Français · English /
  Deux langues, un monde d'opportunités »** dans la zone libre (texte issu
  de la liste autorisée par le cahier des charges) ; focal 70/42.
- **Statut : Corrigé et vérifié.**

### F7 — « Grandir en confiance » (Vie scolaire)
- **Problème** : ronde minuscule dans l'angle bas-droit, crème dominante.
- **Correction** : focal 65 %/78 % (mobile 68/80) — les enfants remplissent
  le cadre — + voile `top-navy` fondant le reste de crème dans la section
  marine. **Statut : Corrigé et vérifié.**

### F8 — Admissions : « L'accueil des familles »
- **Problème** : ~40 % de crème vide à gauche de la photo d'accueil.
- **Correction** : dégradé `left-navy` + surtitre « Admissions » + titre
  « L'accueil des familles » dans la zone libre ; seconde image légendée
  « La visite du campus » sur voile bas (langage visuel commun).
- **Statut : Corrigé et vérifié.**

### F9 — FEBA Online : « Le français en direct, où que vous soyez »
- **Problème** : grande vignette `online-cours-francais` à crème gauche vide.
- **Correction** : dégradé **vert FEBA Online** (`left-green`, seul usage du
  vert conformément à la charte) + texte de programme ; focal 62/48.
- **Statut : Corrigé et vérifié.**

### F10 — Grille de présentation (accueil)
- **Problème** : `accompagnement-individuel` (crème gauche) et `campus-cour`
  (moitié haute ciel/crème, enfants coupés) mal cadrées.
- **Correction** : focals 66/42 et 50/74. **Statut : Corrigé et vérifié.**

### F11 — Galerie + actualités (médias administrables)
- **Problème** : vignettes recadrées au centre aveuglément ; aucun contrôle
  éditorial du cadrage.
- **Correction** : `focal_x`/`focal_y` en base (42 valeurs seedées par
  média), appliqués en `object-position` dans la grille galerie, l'aperçu
  d'accueil et les cartes actualités ; modifiables via
  `/api/website/admin/**` et l'admin Django. La visionneuse plein écran
  affiche l'image entière (`object-contain`) — jamais recadrée.
- **Statut : Corrigé et vérifié.**

### F12 — Vignettes « Vie à FEBA » et pages Campus/Piliers/Online/Contact
- **Correction** : focal individuel pour les 30+ autres emplacements
  (tableau complet dans MEDIA_CROP_AUDIT.md), dégradés uniquement via
  tokens. **Statut : Corrigé et vérifié.**

## Tableau visuel récapitulatif

| ID | Page | Section | Problème initial | Correction | Point focal | Gradient | Texte ajouté | Desktop | Tablette | Mobile | Statut |
|----|------|---------|------------------|------------|-------------|----------|--------------|---------|----------|--------|--------|
| F1 | Accueil | Hero S4 | enfants coupés, 50 % crème | focal bas + hero overlay + titre mobile réduit | 55/78 (m:60/80) | hero + top-navy | — (texte slide existant) | ✅ | ✅ | ✅ | Corrigé et vérifié |
| F2 | Accueil | Hero S5 | crème gauche, titre sous flèche mobile | focal droite, flèches masquées <640 | 72/45 (m:78/45) | hero | — | ✅ | ✅ | ✅ | Corrigé et vérifié |
| F3 | Accueil/Académique | Carte CM1·CM2 | 60 % crème, élèves coupés | composition maquette | 82/28 (m:86/28) | left-navy | « CM1 · CM2 / Préparation à l'entrée au collège… » | ✅ | ✅ | ✅ | Corrigé et vérifié |
| F4 | Accueil/Académique | Cartes niveaux | têtes affleurantes/coupées | cartes pleine image + focal | 4 valeurs | bottom-navy | libellés niveaux (existants) | ✅ | ✅ | ✅ | Corrigé et vérifié |
| F5 | À propos | Équipe | tête coupée (portrait), carte crème | 3 MediaFrame harmonisées | 50/28 · 80/40 · 50/16 | bottom-navy | « La direction / Les enseignants / L'encadrement » + phrases | ✅ | ✅ | ✅ | Corrigé et vérifié |
| F6 | Académique | Bilinguisme | moitié crème vide | MediaFrame gauche | 70/42 | left-navy | « Deux langues, un monde d'opportunités » | ✅ | ✅ | ✅ | Corrigé et vérifié |
| F7 | Vie scolaire | Grandir en confiance | ronde minuscule, crème dominante | focal bas-droite + voile | 65/78 (m:68/80) | top-navy | — | ✅ | ✅ | ✅ | Corrigé et vérifié |
| F8 | Admissions | Accueil familles | 40 % crème gauche | MediaFrame gauche + légendes | 70/45 · 50/38 | left-navy / bottom-navy | « L'accueil des familles » / « La visite du campus » | ✅ | ✅ | ✅ | Corrigé et vérifié |
| F9 | FEBA Online | Grande vignette | crème gauche | MediaFrame verte | 62/48 | left-green | « Le français en direct, où que vous soyez » | ✅ | ✅ | ✅ | Corrigé et vérifié |
| F10 | Accueil | Grille présentation | 2 images mal cadrées | focals | 66/42 · 50/74 | — | — | ✅ | ✅ | ✅ | Corrigé et vérifié |
| F11 | Galerie/Actus | Médias administrables | recadrage aveugle | focal en base + API + admin | 42 valeurs seedées | — | — | ✅ | ✅ | ✅ | Corrigé et vérifié |
| F12 | Toutes | Autres emplacements | cadrage centre unique | registre complet (57 slugs) | cf. mediaMeta.js | tokens | — | ✅ | ✅ | ✅ | Corrigé et vérifié |

## Vérifications transverses réellement effectuées

- **Débordement horizontal** : `scrollWidth == clientWidth` vérifié en
  navigateur à 320 px sur les 12 pages publiques → aucun débordement.
- **Images cassées** : balayage DOM après lazy-load complet de l'accueil →
  36 images, 0 en 404.
- **Console** : aucune erreur sur l'ensemble des parcours.
- **Breakpoints** : captures accueil aux 9 largeurs imposées (320→1920).
- **Non-régression fonctionnelle** : suites backend (284) et frontend (41)
  vertes, build de production OK, endpoints ERP (dashboard admin, notes,
  dashboard parent avec appréciations) → 200.
