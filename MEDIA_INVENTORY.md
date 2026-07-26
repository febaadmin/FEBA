# MEDIA_INVENTORY.md — Inventaire des médias du site vitrine FEBA (V4 → V6.1)

## Delta V7 (25/07/2026)
Ajoutés/optimisés : nouvelle façade FEBA → campus-facade-logo (webp 1600+800) ; vidéo
feba-presentation.mp4 (H.264/AAC, 576×1024, 54 s, 6,6 Mo) + poster ; cachet officiel
cachet_feba.png (+ hd, webp). Recadrage : admissions-famille (focal 50/60). Originaux
conservés dans Downloads / static_files.


## Delta V6.1 (20/07/2026)

**Ajoutés** (webp 800+1600 optimisés, points focaux définis) :
`campus-logo`, `campus-fresque`, `apropos-equipe-pedagogique`,
`petite-enfance-creche`.

**Supprimés** (image de bureau bannie + composite qui l'incrustait) :
`apropos-direction`, `apropos-direction-2`, `galerie-mosaique-3`.

**Total packagé** : 116 fichiers webp (58 visuels × 2 tailles). L'invariant
slug ↔ fichier est garanti par `mediaMeta.test.js` (chaque visuel a ses deux
tailles et un point focal ; aucun fichier orphelin).

---

# MEDIA_INVENTORY.md — Inventaire des médias du site vitrine FEBA (V4)

## Source

Archive fournie : `/Users/m.chris/Desktop/FEBA/Medias/IMG_vid.zip` (193 Mo)
Contenu : dossier `IMG_vid/` — **57 images PNG** (noms UUID, ~2 Mo chacune,
113 Mo au total) + **1 vidéo** `video1.mov`.

> Les fichiers originaux ne sont **ni modifiés ni supprimés**. Seules des
> copies optimisées pour le web sont produites dans
> `frontend/public/site/` par `scripts/optimize_site_media.py`.

## Vidéo

| Fichier | Format | Durée | Dimensions | Poids | Usage |
|---|---|---|---|---|---|
| `video1.mov` (original) | H.264 + AAC (mov) | 51,9 s | 1600×1080 30 fps | 73 Mo | conservé hors web |
| `site/video/feba-presentation.mp4` | H.264 CRF 27 + AAC 96k, faststart | 51,9 s | 1280×864 | ~9 Mo | vidéo institutionnelle (accueil / galerie), chargée **à la demande** (clic sur l'affiche, jamais d'autoplay) |
| `site/video/feba-presentation-poster.webp` | WebP | — | 1280×864 | ~60 Ko | affiche de prévisualisation |

## Images — synthèse technique

- 57 PNG, **aucun doublon binaire** (vérification MD5).
- Formats rencontrés : 1536×1024 (×20), 1448×1086 (×14), 1122×1402 portrait (×7),
  1774×887 panoramique (×6), 1024×1536 portrait (×2), autres panoramiques
  2076×757 / 1817×866 (×5), divers (×3).
- Orientation : 48 paysage, 9 portrait.
- 3 images sont des **collages multi-scènes** (`2ec00d74`, `ba9a5133`,
  `49619860`) → réservées à la galerie, jamais en hero.
- **Aucune image de natation** dans le lot fourni : la section « Vie à FEBA »
  ne présente donc que les activités réellement illustrées (musique,
  percussions, arts plastiques, football, expression orale, jeux éducatifs,
  robotique/numérique, rondes).

## Optimisation web

Chaque image retenue est déclinée en :
- `site/img/<slug>-1600.webp` (qualité 82) — heros, sections pleine largeur, lightbox ;
- `site/img/<slug>-800.webp` (qualité 80) — cartes, grilles, mosaïque galerie.

Total optimisé : **114 fichiers WebP ≈ 9 Mo** (au lieu de 113 Mo de PNG),
chargés en `loading="lazy"` (hors hero) avec dimensions explicites.
Les métadonnées PNG (chunks texte) ne sont pas propagées par la conversion
Pillow → WebP.

## Mapping UUID → slug et affectation éditoriale

| Préfixe UUID | Slug | Description du visuel | Affectation |
|---|---|---|---|
| ad9e0dc6 | hero-campus | Grand bâtiment de l'académie, ciel bleu, palmiers | Carrousel S1 « Bienvenue » |
| 03240d6b | hero-bilingue | Enseignante et élèves, manuels Français/English, drapeaux | Carrousel S3 « Français & anglais » |
| f08d185a | hero-vie-scolaire | Ronde d'enfants dans la cour, fond très clair (espace négatif) | Carrousel S4 « Apprendre, grandir, s'épanouir » |
| 182bfd8a | hero-excellence | Élèves collaborant sur un projet | Carrousel S2 « Grandir dans l'excellence » |
| 15fdd070 | hero-admissions | Famille accueillie par une responsable | Carrousel S5 « Admissions ouvertes » |
| 028e7d0c | campus-garderie-maternelle | Façade rouge/crème « Garderie / Maternelle » | Campus, Accueil |
| 6302672d | campus-facade | Façade FEBA vue rapprochée | Campus |
| 652399ec | campus-batiment | Bâtiment principal avec palmiers | Campus, Contact |
| 0fb2b2d8 | campus-cour | Enfants jouant dans la cour (portrait) | Campus |
| b924bb36 | niveau-garderie | Petits avec blocs éducatifs et éducatrice | Niveaux : Garderie |
| ff3dd775 | niveau-garderie-jeux | Jeux de construction colorés | Garderie (variante) |
| 0ef89dcf | niveau-maternelle | Activités couleurs, formes, collage | Niveaux : Maternelle |
| de6007a2 | niveau-maternelle-cour | Marelle et fresque murale dans la cour | Maternelle, Vie scolaire |
| 385db627 | niveau-primaire | Élèves écrivant sérieusement en classe | Niveaux : Primaire |
| 858d64f0 | niveau-primaire-lecture | Lecture en classe | Primaire (variante) |
| 2c4fc8fa | academique-classe | Enseignante au tableau blanc | Programmes académiques |
| 4efe3f20 | academique-carte | Cours avec carte du monde | Programmes académiques |
| 2c1e8a46 | academique-lecture | Deux élèves lisant un manuel | Académique, Accueil |
| 5fdac19c | academique-bibliotheque | Lecture en bibliothèque | Académique |
| d8fd92d7 | academique-sciences | Expérience de chimie, microscope | Académique : sciences |
| a0166b9d | academique-numerique | Robotique et ordinateur portable | Académique : numérique |
| c5808504 | academique-participation | Élèves levant la main (portrait) | Académique |
| 2e76e906 | bilingue-accompagnement | Enseignante aidant deux jeunes élèves | Section bilinguisme |
| 20f1d147 | accompagnement-individuel | Enseignante aidant deux élèves (panoramique) | Pourquoi FEBA |
| 49e1fa47 | accompagnement-duo | Enseignante avec deux élèves | À propos |
| 2c75f2fe | valeurs-equipe | Groupe d'élèves en projet | Valeurs / esprit d'équipe |
| ab35c86f | valeurs-projet | Groupe d'élèves en projet (variante) | Galerie |
| 00d302b8 | activite-musique-atelier | Atelier musique avec enseignant (panoramique) | Vie à FEBA |
| aa3cb9e6 | activite-musique-groupe | Groupe guitare/batterie/clavier/chant | Vie à FEBA : musique |
| adbaf9bb | activite-musique-scene | Groupe de musique (variante) | Galerie |
| c58f0b8c | activite-percussions | Djembé et percussions (portrait) | Culture & héritage |
| 5e15c55b | activite-arts | Peinture, arts plastiques | Vie à FEBA : arts |
| 21b12b06 | activite-football-cour | Football dans la cour (portrait) | Vie scolaire |
| facbe521 | activite-football | Football sur gazon, maillots FEBA | Vie à FEBA : sport |
| c9177c7d | activite-expression | Élève au micro devant le groupe | Développement personnel |
| ffd2ee74 | activite-ronde | Ronde d'enfants (panoramique) | Vie scolaire |
| 1576cf4c | online-visio | Élève en visioconférence | FEBA Online |
| 3e6f75cb | online-cours-francais | Laptop « cours de français » (panoramique) | FEBA Online |
| ff8bfa27 | online-lecon | Enfant au casque, leçon en ligne | FEBA Online |
| 478e3767 | admissions-famille | Famille marchant dans le couloir (portrait) | Admissions |
| a27417c7 | admissions-visite | Famille en visite (portrait) | Admissions |
| 9e3b46c3 | admissions-accueil | Famille reçue à l'accueil (panoramique) | Admissions |
| ee230580 | admissions-bienvenue | Accueil d'une famille (variante) | Admissions |
| 4e835291 | contact-accueil | Réceptionniste FEBA souriante (portrait) | Contact |
| f872c720 | contact-administration | Responsable au bureau | Contact / administration |
| 6dd81966 | apropos-direction | Bureau de direction avec emblème FEBA | À propos (illustratif, sans nom) |
| c06e94c1 | apropos-direction-2 | Bureau de direction (variante) | Galerie |
| ba066112 | apropos-encadrement | Portrait professionnel (costume bleu marine) | À propos (illustratif) |
| cc8af6c0 | apropos-equipe | Équipe pédagogique au complet | À propos : équipe |
| 35302c29 | galerie-projet | Travail de groupe (variante) | Galerie |
| 3e3ecff2 | galerie-ecriture | Deux élèves écrivant (panoramique clair) | Galerie |
| 59510f62 | galerie-etude | Élèves en étude (panoramique clair) | Galerie |
| ccb2c1bd | galerie-devoirs | Deux élèves écrivant (portrait) | Galerie |
| 5010d5ea | galerie-soutien | Enseignante et élèves (panoramique) | Galerie |
| 2ec00d74 | galerie-mosaique-1 | Collage multi-scènes | Galerie uniquement |
| ba9a5133 | galerie-mosaique-2 | Collage multi-scènes | Galerie uniquement |
| 49619860 | galerie-mosaique-3 | Collage multi-scènes | Galerie uniquement |

## Reproduire l'optimisation

```bash
python3 scripts/optimize_site_media.py --src /chemin/vers/IMG_vid
```

(Pillow requis ; ffmpeg nécessaire uniquement pour l'étape vidéo.)
