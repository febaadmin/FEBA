# MEDIA_CROP_AUDIT.md — Audit de cadrage des médias (V5 + V6 + V6.1)

## Recadrages V6.1 (20/07/2026) — vignettes galerie annotées « mal cadrée »

Chaque vignette signalée a été inspectée individuellement (fichier source
réel) puis recadrée par point focal propre (registre `mediaMeta.js` **et**
valeur seedée `GALLERY_FOCALS`). Valeurs `object-position` **vérifiées en
navigateur** (getComputedStyle).

| Média | Constat | Focal avant | Focal après (vérifié DOM) |
|---|---|---|---|
| `galerie-devoirs` | portrait : 2 élèves en bas, grand mur crème en haut | 50/32 | **50/66** |
| `galerie-soutien` | portrait : trio (enseignante + 2) en bas, mur crème en haut | 62/42 | **50/68** |
| `galerie-etude` | paysage : 2 élèves à droite, crème à gauche | 55/45 | **66/46** |
| `galerie-ecriture` | paysage : 2 élèves à droite, crème à gauche | 60/45 | **66/46** |
| `accompagnement-duo` | paysage : trio centré, grand mur crème en haut | 80/40 | **52/64** |

Nouveaux médias — points focaux délibérés : `campus-logo` 50/48 (bâtiment +
panneau), `campus-fresque` 50/52 (façade + fresques), `apropos-equipe-pedagogique`
50/38 (visages hauts), `petite-enfance-creche` 50/52 (lits + tout-petits).

Aucun `object-position: center` global : chaque correction est individuelle.

---

# MEDIA_CROP_AUDIT.md — Audit de cadrage des médias (V5 + V6)

## Ajustements V6 (20/07/2026) — recadrages individuels

Aucun `object-position: center` uniforme : chaque visuel problématique a reçu
son propre point focal (registre `mediaMeta.js` + valeur seedée pour la
galerie), et le cas inexploitable a été **remplacé**.

| Image (slug) | Problème | Action V6 | Focal après |
|---|---|---|---|
| `academique-participation` (carte CM1·CM2) | montrait surtout un **mur/plafond crème** ; l'enseignante était marginale | **remplacé** par `valeurs-projet` sur la carte CM1·CM2 ; le visuel reste dans la galerie mais recadré sur l'enseignante | `26% 64%` (mobile `26% 66%`) |
| `valeurs-projet` (nouvelle carte CM1·CM2) | — | cadrage sur le groupe autour de la table | `50% 40%` |
| `activite-percussions` | groupe en bas, grand mur crème en haut | cadrage descendu sur les musiciens | `50% 72%` |
| `activite-ronde` | ronde à droite, crème à gauche | cadrage poussé à droite | `72% 62%` (mobile `74% 66%`) |
| `academique-lecture` (grille d'accueil) | remplace `hero-campus` en doublon | recadrage lecture | `50% 42%` |
| cartes « vie scolaire » | sujets trop bas (têtes coupées au fold) | ratios + focals ajustés (`SchoolLifePage`) | têtes non coupées |
| « Grandir en confiance » | bande crème à gauche | `MediaFrame aspect-[5/4] sm:aspect-[16/11]` + `position 74% 60%` | — |

Vérifié navigateur (375/1280/1920) : voir `VISUAL_FIXES_REPORT.md` §V6.
Test structurel `mediaMeta.test.js` : cohérence focals ↔ fichiers réels.
Test `test_website.py` : la galerie API expose le focal `26% 64%` attendu pour
`academique-participation`.

---

# MEDIA_CROP_AUDIT.md — Audit de cadrage des médias du site vitrine (V5, 19/07/2026)

Chaque média affiché par le site public a été inspecté dans le navigateur
(captures pleine page desktop 1280 / tablette 768 / mobile 375 dans
`captures/avant/`, état corrigé dans `captures/apres/`, accueil aux
9 largeurs 320→1920 dans `captures/breakpoints/`).

**Système mis en place** : point focal par image
(`frontend/src/site/mediaMeta.js` pour les médias packagés ;
`focal_x`/`focal_y` en base pour les médias administrables — slides,
galerie, actualités — modifiables depuis l'admin), dégradés de marque
centralisés (`OVERLAYS`), composant `MediaFrame` (image + dégradé + texte).
La visionneuse de la galerie affiche l'image ENTIÈRE (`object-contain`) :
aucun recadrage en plein écran.

Ratios sources : 1536×1024 (3:2), 1448×1086 (4:3), 1774×887 (2:1),
1122×1402 et 1024×1536 (portraits), collages panoramiques.

| ID | Page | Section | Média (slug) | Ratio source | Conteneur | Problème constaté | Correction appliquée | Desktop | Tablette | Mobile | Statut |
|----|------|---------|--------------|--------------|-----------|-------------------|----------------------|---------|----------|--------|--------|
| M01 | Accueil | Carrousel S1 | hero-campus | 3:2 | 16:6 plein écran | néant (léger recentrage souhaitable) | focal 50/55 administré | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M02 | Accueil | Carrousel S2 | hero-excellence | 3:2 | idem | têtes proches du haut | focal 50/38 | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M03 | Accueil | Carrousel S3 | hero-bilingue | 3:2 | idem | sujets légèrement bas | focal 50/38 | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M04 | Accueil | Carrousel S4 | hero-vie-scolaire | 2:1 | idem | **ronde d'enfants coupée en bas, ~50 % crème vide en haut** | focal 55/78 (mobile 60/80) + dégradé hero marine ; enfants entiers | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M05 | Accueil | Carrousel S5 | hero-admissions | 2:1 | idem | crème vide à gauche, scène à droite | focal 72/45 (mobile 78/45) — le texte du slide occupe la zone libre ; flèches masquées < 640 px (chevauchement titre) | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M06 | Accueil | Présentation (grille) | campus-garderie-maternelle | 4:3 | h-52/64 | néant | focal 50/58 | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M07 | Accueil | Présentation | valeurs-equipe | 3:2 | h-52/64 | têtes près du bord haut | focal 50/32 | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M08 | Accueil | Présentation | accompagnement-individuel | 2:1 | h-52/64 | **~40 % crème vide à gauche** | focal 66/42 (mobile 72/42) : sujets remplissent le cadre | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M09 | Accueil | Présentation | campus-cour | 3:2 | h-52/64 | **ciel/crème sur la moitié haute, enfants coupés** | focal 50/74 : ronde entière visible | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M10 | Accueil + Académique | Carte niveau Garderie | niveau-garderie | 4:3 | carte h-60/64 | têtes près du bord | focal 50/42 + composition image pleine carte, texte sur voile marine bas | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M11 | idem | Carte Maternelle 1&2 | niveau-maternelle | 4:3 | idem | sommet des têtes affleurant | focal 50/42 + voile bas | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M12 | idem | Carte CI·CP | niveau-primaire-lecture | 3:2 | idem | tête du garçon près du bord | focal 50/36 + voile bas | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M13 | idem | Carte CE1·CE2 | niveau-primaire | 3:2 | idem | **hauts de têtes coupés** | focal 50/30 + voile bas | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M14 | idem | Carte CM1·CM2 | academique-participation | 4:5 portrait | idem | **~60 % crème vide à gauche, élèves coupés en bas** | focal 82/28 (mobile 86/28) + **dégradé marine gauche + texte « CM1 · CM2 / Préparation… » dans la zone libre** (maquette) | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M15 | Accueil | Bilinguisme | hero-bilingue | 3:2 | h-72/96 arrondi | sujets bas | focal 50/38 | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M16 | Accueil | Vie à FEBA (8 cartes) | activite-* / niveau-maternelle-cour / academique-sciences / academique-numerique | 3:2 à 2:1 | h-56 overlay | cadrage centre aveugle | focal individuel ×8 + dégradé token bottom-navy | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M17 | Accueil | FEBA Online (3 vignettes) | online-visio / online-lecon / online-cours-francais | 2:1, 4:3 | h-44/56 | crème latérale (cours-francais) | focals 45/45 · 42/45 · 62/48 | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M18 | Accueil | Aperçu galerie (8 vignettes) | divers | divers | h-36/44 grille | cadrage centre aveugle | object-position depuis focal administré (API) | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M19 | Accueil/Actus | Cartes actualités | image_src administré | libre | h-44 | pas de contrôle éditorial du cadrage | `focal` administrable appliqué (NewsPost.focal_x/y) | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M20 | À propos | Bannière | campus-batiment | 3:2 | bandeau navy op-25 | néant | focal 50/55 via SiteImage | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M21 | À propos | Qui sommes-nous | apropos-equipe | 3:2 | h-72/96 | groupe légèrement bas | focal 50/32 | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M22 | À propos | Équipe — carte 1 | apropos-direction | 3:2 | h-72 | tête près du bord haut | focal 50/28 + légende « La direction » sur voile marine | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M23 | À propos | Équipe — carte 2 | accompagnement-duo | 2:1 | h-72 | **moitié gauche crème vide** | focal 80/40 (mobile 84/40) + légende « Les enseignants » | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M24 | À propos | Équipe — carte 3 | apropos-encadrement | 2:3 portrait | h-72 | **TÊTE ENTIÈREMENT COUPÉE (cover centré sur un portrait)** | focal 50/16 : visage entier avec marge au-dessus + légende « L'encadrement » | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M25 | Campus | 6 cartes espaces | hero-campus, campus-*, academique-bibliotheque | 3:2/4:3 | h-52 | cour : enfants coupés | focals individuels (dont campus-cour 50/74) | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M26 | Académique | Bannière | academique-classe | 3:2 | bandeau | néant | focal 50/35 | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M27 | Académique | Bilinguisme | bilingue-accompagnement | 2:1 | h-72/96 | **moitié gauche crème vide** | **dégradé marine gauche + « Français · English / Deux langues, un monde d'opportunités »** ; focal 70/42 | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M28 | Académique | 5 lignes niveaux | mêmes médias que M10–M14 | — | h-56/64 alterné | têtes hautes coupées | focals partagés du registre | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M29 | Académique | 4 piliers | academique-classe/sciences/numerique/carte | 3:2 | h-40 | cadrage centre | focals individuels | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M30 | Admissions | Bannière | hero-admissions | 2:1 | bandeau | crème gauche | focal 72/45 | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M31 | Admissions | Image accueil | admissions-accueil | 2:1 | h-56 | **~40 % crème vide à gauche** | **dégradé marine gauche + « Admissions / L'accueil des familles »** ; focal 70/45 | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M32 | Admissions | Image visite | admissions-famille | 3:4 portrait | h-56 | néant majeur | focal 50/38 + légende « La visite du campus » sur voile bas | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M33 | Vie scolaire | Bannière | activite-musique-groupe | 3:2 | bandeau | néant | focal 50/40 | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M34 | Vie scolaire | 8 cartes activités | activite-* | divers | h-52 | percussion/expression : sujets décentrés | focals individuels | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M35 | Vie scolaire | Grandir en confiance | activite-ronde | 2:1 | h-64/80 | **ronde réduite dans l'angle bas-droit, crème dominante** | focal 65/78 (mobile 68/80) + voile marine haut (top-navy) | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M36 | FEBA Online | Bannière verte | online-visio | 3:2 | bandeau vert op-20 | néant | focal 45/45 | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M37 | FEBA Online | Grande vignette | online-cours-francais | 2:1 | h-48 | **crème gauche vide** | **dégradé VERT FEBA Online gauche + « FEBA Online / Le français en direct… »** ; focal 62/48 | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M38 | FEBA Online | 2 vignettes | online-lecon / activite-percussions | 4:3 | h-44 | cadrage centre | focals 42/45 · 50/45 | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M39 | Actualités | Bannière | activite-expression | 4:5 | bandeau | élève décentré | focal 45/32 | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M40 | Galerie | Bannière | galerie-mosaique-1 | pano | bandeau | néant (collage) | centre | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M41 | Galerie | 42 vignettes (6 albums) | tous | divers | h-36/44 grille | cadrage centre aveugle sur images à crème | **focal administré par média** (seed + admin), appliqué en `object-position` ; visionneuse plein écran en `contain` (image entière) | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M42 | Galerie | Vignette vidéo | poster feba-presentation | 3:2 | h-36/44 | néant | poster + lecture au clic (inchangé) | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M43 | Contact | Bannière | contact-administration | 3:2 | bandeau | néant | focal 50/35 | ✅ | ✅ | ✅ | Corrigé et vérifié |
| M44 | Contact | Image accueil | contact-accueil | 3:4 portrait | h-64 | réceptionniste décalée à gauche | focal 32/32 | ✅ | ✅ | ✅ | Corrigé et vérifié |

**Bilan** : 57 fichiers médias couverts par le registre (test automatisé
`mediaMeta.test.js` : chaque fichier packagé a un point focal défini, chaque
entrée du registre correspond à un fichier réel, positions valides ≤ 100 %) ;
5 zones crème majeures transformées en compositions dégradé+texte
(M14, M23→gradient légende, M27, M31, M37) ; 2 coupes de têtes graves
éliminées (M24, M13) ; 0 image déformée (aucun étirement — uniquement
object-position/fit) ; visionneuse plein écran sans recadrage.
