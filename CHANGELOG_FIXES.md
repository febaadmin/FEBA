# CHANGELOG_FIXES.md — Missions V4 → V8 (juillet 2026)

## V8 — Profils, incidents techniques, poids des notes, barèmes, cachets (26/07/2026)

- **P1 — Création du profil Enseignant réparée.** Cause racine : le matricule
  était généré à partir de `Teacher.objects.count() + 1`. Après toute
  suppression, le compteur retombait sur un matricule déjà pris → violation
  d'unicité → **erreur 500**. Le matricule dérive désormais du **plus grand
  suffixe existant** (+ reprise en cas de collision concurrente), la création
  est **atomique**, et les erreurs deviennent des **400 exploitables**.
- **P2 — Audit de tous les profils.** Faille corrigée : le filtrage
  multi-établissement des champs DRF `many=True` était **inopérant** (DRF lit
  `child_relation.queryset`) — un admin pouvait rattacher des matières/classes
  d'un AUTRE établissement. 16 tests (Enseignant, Élève, Parent).
- **P3 — Remontée RÉELLE des erreurs techniques.** Application `incidents` :
  modèle `TechnicalIncident` (référence `ERR-XXXXXX`, gravité, statut, module,
  empreinte, occurrences…), capture des 500 uniquement, **dédoublonnage** par
  empreinte, **sanitisation** centrale (mots de passe, jetons, cookies, cartes),
  **notification réelle** des super administrateurs pointant vers l'incident,
  interface « Incidents techniques » (compteurs, filtres, recherche, statut,
  note, résolution/réouverture) réservée aux super admins. Le message affirmant
  faussement « l'équipe technique a été notifiée » est supprimé : la référence
  n'est annoncée que si l'incident a **réellement** été enregistré.
- **P4 — Poids d'évaluation unique.** Toutes les évaluations pèsent **1** :
  `12` (interrogation) et `5` (examen) donnent **8,50**. Distinction nette
  entre **poids d'évaluation** (toujours 1) et **coefficient de matière**
  (inchangé). Source unique `apps/grades/grading.py`. Migration de données
  (rapport avant / exécution / vérification après) + champ retiré des
  interfaces.
- **P5 — Bulletins sur 10 pour les niveaux 1 à 11.** Barème déduit d'un champ
  **stable** (`Level.order`), conversion appliquée **une seule fois** à
  l'affichage ; appréciations et lettres restent calculées sur l'équivalent
  /20 (6,00/10 ≡ 12/20). Collège et au-delà conservent /20.
- **P6 — Reçu « Le Secrétariat ».** « Signature du Caissier » et « Cachet de
  l'École / School Stamp » supprimés ; zone de validation unique avec le
  **cachet LE SECRETARIAT**.
- **P7 — Cachet « LA DIRECTION » repositionné.** Il débordait d'une cellule à
  hauteur fixe et chevauchait la date. Bloc dédié, centré, insécable, sans
  allonger le bulletin.
- **Défauts trouvés en inspectant les documents réels** : chevauchement du nom
  de l'école et de l'adresse sur le reçu (interligne) ; « Moy. Pond. » restée
  sur l'échelle /20 face à une moyenne /10 ; **observations tronquées** au bord
  droit du reçu ; **date de résolution** d'un incident non renseignée par un
  simple PATCH de statut. Tous corrigés et couverts par des tests.
- Backend **393 tests** (SQLite) / **394** (PostgreSQL 16, chaîne de migrations
  complète), frontend **70**, ESLint **0 erreur**, build prod **OK**.


## V7 — Noms officiels, cachet, précision des notes, façade, vidéo, admissions (25/07/2026)

- **P1** — Nom officiel **« Faith & Excellence Bilingual Academy »** (avec « & »)
  partout ; source de vérité `backend/feba_project/branding.py` ; 0 occurrence
  restante sans « & » ; migrations de données (website 0003, schools 0011).
- **P2** — **« GROUPE ÉDUCATIF FEBA »** remplace « GROUPE SCOLAIRE FEBA » ;
  affiché en tête des bulletins & reçus ; l'école ERP prend son nom officiel.
- **P3** — **Cachet officiel** extrait fidèlement du PDF (1320×1301) → PNG HD +
  transparent + WebP ; apposé automatiquement sur bulletins & reçus (case
  direction), non déformé, dégradation gracieuse si absent.
- **P4** — **La note 10 n'est plus altérée en 9,5/9,75** : cause racine =
  `input type=number step` modifié en silence par la molette/les flèches →
  champs de note en **texte décimal** + normalisation + garde globale
  anti-molette. 8 tests front + 5 tests back (10 reste 10 : DB, API, bulletin).
- **P5** — Nouvelle **façade FEBA** (panneau « Faith & Excellence » + fresques)
  intégrée (accueil + galerie), point focal relevé (panneau visible).
- **P6** — **Vidéo** fournie optimisée (11→6,6 Mo, H.264/AAC, faststart) +
  poster ; visionneuse avec contrôles (lecture/pause, volume, plein écran),
  arrêt à la fermeture, pas de lecture auto avec son.
- **P7** — **Admissions « La visite du campus »** : conteneur agrandi + focal
  descendu → corps entiers des enfants et parents visibles (plus que les têtes).
- Backend **311 tests** (+1 skip), frontend **70 tests**, eslint **0 erreur**,
  build prod OK. Détails : `OFFICIAL_NAMING_REPORT`, `STAMP_INTEGRATION_REPORT`,
  `GRADE_PRECISION_REPORT`, `VIDEO_INTEGRATION_REPORT`, `FINAL_REPORT`.


## V6.2 — Conformité visuelle exacte aux captures annotées (20/07/2026)

Passe corrective ciblée (aucune fonctionnalité modifiée) : utiliser
**exactement** les images marquées « Bonne image », retirer les
« Pas la bonne / Mauvaise image ». Détails : `VISUAL_CONFORMITY_REPORT.md`.

- **C1 — Mosaïque d'accueil** : `campus-fresque` (vue drone, « Pas la bonne
  image ») → **`campus-facade-logo`** (façade FEBA logo + nom + fresques,
  composition verticale propre).
- **C2 — À propos « La direction »** : portrait serré (`apropos-encadrement`,
  « Pas la bonne image ») → **`apropos-direction-2`** restauré (directeur à son
  bureau, vue large, mains + logo FEBA), utilisé **uniquement** sur cette carte.
- **C3 — Académique « Deux langues »** : cadrage réellement corrigé — focal
  `70/42` → `50/66` (mobile `50/70`), conteneur `h-80 sm:h-[28rem]`, overlay
  **responsive** `left-navy-md` (dégradé bas mobile, gauche dès sm), texte
  resserré. Têtes + bustes enseignante/élèves visibles **desktop ET mobile**.
- **C4 — Galerie « Notre campus »** : `campus-facade` + `campus-fresque`
  (« Mauvaise image ») retirées → **`campus-facade-logo`** + **`campus-devise`**.
  4 vues distinctes.
- **Nouveaux médias** webp 800+1600 : `campus-facade-logo`, `campus-devise` ;
  `apropos-direction-2` restauré. Backend seed + fallback `siteDefaults`
  **alignés** (même ordre) → pas de réapparition d'ancienne image.
- **Tests de conformité par slug exact** ajoutés (`visual-conformity.test.jsx`,
  6 cas). Frontend **62 tests**, backend **300** (+1 skip), eslint **0 erreur**,
  build OK. Vérifié navigateur 375 + 1440 (captures + DOM).


## V6.1 — Corrections visuelles finales sur captures annotées (20/07/2026)

- **Médias de remplacement fournis intégrés** (webp 1600+800 optimisés) :
  `campus-logo` (bâtiment + panneau « Faith & Excellence » lisible),
  `campus-fresque` (façade aux fresques pédagogiques), `apropos-equipe-pedagogique`
  (photo d'équipe réelle, 7 personnes), `petite-enfance-creche` (crèche).
- **Accueil** : slide 1 du carrousel → `campus-logo` ; mosaïque de présentation
  → `campus-fresque` (fini l'ancienne façade rouge).
- **Galerie « Notre campus »** : les deux façades rouges quasi identiques
  (`campus-batiment`, `campus-garderie-maternelle`) remplacées par
  `campus-logo` + `campus-fresque` → 4 vues réellement distinctes.
- **Galerie « Petite enfance »** : ajout de `petite-enfance-creche`.
- **Image bannie** : `apropos-direction` **et** `apropos-direction-2` (même
  personne « assise seule dans un bureau ») + `galerie-mosaique-3` (qui
  l'incrustait) **supprimées** du site, des seeds, des valeurs par défaut **et
  du paquet** (fichiers webp retirés + entrées de registre retirées). Vérifié :
  aucun de ces slugs n'apparaît plus dans le DOM public.
- **« Une équipe engagée » (À propos)** : plus de doublon de personne —
  « La direction » = portrait unique du directeur, « Les enseignants » =
  accompagnement en classe, « L'encadrement » = vraie photo d'équipe.
- **Recadrages individuels** (galerie) : `galerie-devoirs` (50/66),
  `galerie-soutien` (50/68), `galerie-etude` (66/46), `galerie-ecriture`
  (66/46), `accompagnement-duo` (52/64) — sujets décentrés/trop bas + fond
  crème corrigés (object-position vérifié en navigateur).
- **Carrousel** : voile gris délavé → habillage marine DA FEBA (dégradé marine
  à gauche `hero-left` + pointe dorée `hero-gold`), centralisé dans `OVERLAYS`,
  appliqué aux 5 slides.
- Vérifié navigateur (DOM + captures, 375→1920) ; 56 tests frontend, 300 backend
  (+1 skip), eslint 0 erreur, build prod OK.


## V6 — Carrousel/galerie incassables, dédoublonnage, recadrages, menu, saisie groupée (20/07/2026)

- **P1 — Carrousel restauré (jamais une image statique).** `HeroCarousel`
  affiche 5 slides réelles ; repli robuste sur médias packagés
  (`siteDefaults.js → DEFAULT_SLIDES`) si l'API ne renvoie rien — jamais une
  image figée, jamais un vide. Flèches (masquées < sm), points, clavier,
  tactile, `prefers-reduced-motion`. Administrable via l'API/l'admin.
  *Vérifié navigateur 375/1280/1920 : 5 slides, auto-défilement, flèches
  masquées sur mobile.*
- **P2 — Galerie remplie.** `GalleryPage`/`HomePage` : repli sur
  `DEFAULT_ALBUMS` si l'API est vide ; suppression de l'état « bientôt
  disponible » quand des médias existent. *Vérifié navigateur : albums pleins,
  vignettes toutes distinctes.*
- **P3 — Doublons d'images éliminés** (voir `MEDIA_DUPLICATES_REPORT.md`).
  `hero-campus` (≈8× avant) ramené à un usage sain ; élagage des galeries au
  seed (`exclude(image_path__in=…).delete()`), grille d'accueil, bannière
  Campus, cartes Campus, carte CM1·CM2.
- **P4/P5 — Recadrages individuels + zones crème** (voir
  `MEDIA_CROP_AUDIT.md`, `VISUAL_FIXES_REPORT.md`). CM1·CM2 (visuel mur crème
  inexploitable → `valeurs-projet`), cartes vie scolaire, « Grandir en
  confiance », points focaux relevés (activités, `academique-participation`
  26% 64%…). Pas de `cover/center` uniforme.
- **P6 — Menu desktop sur une seule ligne.** En-tête `SiteLayout` :
  `whitespace-nowrap`, breakpoint `min-[1200px]`, sous-titre `2xl:block`,
  bascule hamburger propre en-dessous. *Vérifié navigateur : une ligne à
  1280 et 1920, overlay hamburger propre à 375.*
- **P7 — Saisie groupée de notes** (voir `BULK_GRADES_REPORT.md`).
  `POST /api/grades/bulk-create/` atomique (tout ou rien, jamais d'écriture
  partielle), permissions **backend** (enseignant → ses matières/classes,
  anti-IDOR ; admin/superadmin élargis ; parent 403 ; anonyme 401), erreurs
  indexées par ligne, appréciation calculée backend. `BulkGradeModal`
  réutilisable (enseignant/admin/superadmin), la saisie simple est inchangée.
  16 tests backend + 6 tests frontend + E2E session enseignant réelle.
- **Audit V6.** Suite complète rejouée : 2 régressions détectées et corrigées
  — assertion de point focal (`test_website`) alignée sur la valeur V6 seedée,
  et 4 clés de traduction dupliquées (`no-dupe-keys`) retirées.
  Backend **300 tests OK** (+1 skip concurrence documenté), frontend
  **56 tests OK**, `eslint` **0 erreur**, build prod OK.

## V5 — Corrections visuelles du site vitrine (19/07/2026)

- **Système de point focal** :
  - backend : `focal_x`/`focal_y` (0–100, validés) sur HeroSlide,
    GalleryItem et NewsPost (`apps/website`, migration 0002), exposés par
    l'API (`focal`), modifiables via l'admin Django et l'API admin ;
    valeurs seedées pour les 5 slides et les 42 médias de la galerie ;
  - frontend : registre central `src/site/mediaMeta.js` (object-position
    desktop + variante mobile pour les 57 visuels packagés), appliqué
    automatiquement par `SiteImage` (variables CSS `.site-img`, bascule
    < 640 px) — plus aucun `object-position` codé en dur dispersé.
- **Dégradés de marque centralisés** (`OVERLAYS` : bottom/left/right-navy,
  left-green, top-navy, hero) + composant `MediaFrame` (image + dégradé +
  texte) : aucun gradient arbitraire dans les pages.
- **Zones crème vides transformées en compositions** (dégradé FEBA + texte
  de section) : carte CM1·CM2 (maquette), bilinguisme Académique
  (« Deux langues, un monde d'opportunités »), accueil des familles
  (Admissions), grande vignette FEBA Online (dégradé vert), cartes équipe.
- **Recadrages corrigés** : portrait de l'encadrement (tête coupée → visage
  entier, focal 50/16), cartes de niveaux (têtes), ronde « Grandir en
  confiance », hero slide 4 (enfants entiers), grille de présentation,
  galerie et actualités (focal administré).
- **Hero** : dégradés unifiés (tokens), titre mobile réduit, largeur du
  texte limitée, flèches masquées < 640 px (plus de chevauchement).
- Détail complet : `MEDIA_CROP_AUDIT.md` (44 lignes d'audit) et
  `VISUAL_FIXES_REPORT.md` (12 fiches de correction + preuves).
- Tests ajoutés : `mediaMeta.test.js` (6, cohérence registre↔fichiers) et
  `FocalPointTests` backend (4). Totaux : **284 backend / 41 frontend**.

## V4 — rappel

> Corrections et développements de la mission V4 : types de notes, barème
> officiel des appréciations, réinitialisation de mot de passe par
> administrateur, site vitrine public. Les changelogs des missions
> précédentes sont archivés dans `docs/historique/` (…_V3.md) et dans
> l'historique git.

## P1 — Types de notes renommés

- `backend/apps/grades/models.py` : libellés des choix `NOTE_TYPE_CHOICES`
  renommés — `interrogation` → « Interrogation / Devoir de classe »,
  `examen` → « Examen / Évaluation ». **Les valeurs internes stockées en
  base restent inchangées** (identifiants métier stables) : aucune donnée
  existante à migrer, les anciennes notes restent lisibles.
- Migration `grades/0010_alter_grade_note_type.py` (choices uniquement,
  aucun changement de schéma).
- Frontend : listes `NOTE_TYPES` de `admin/Grades.jsx` et
  `teacher/Grades.jsx` alignées ; tous les affichages passent par
  `note_type_display`/`note_type_label` renvoyés par l'API (source unique).
- i18n : nouvelles paires EN (« Quiz / Class test »,
  « Examination / Assessment »).
- Tests : `backend/tests/test_note_types_appreciations.py` (création via
  API pour chaque type renommé, modification, filtre `?note_type=`,
  lecture des anciennes valeurs, rejet des libellés utilisés comme valeur).

## P3 — Barème officiel des appréciations (9 niveaux)

- **Source unique de vérité** : `apps.grades.models.get_appreciation(value,
  max_value=20)` réécrite avec le barème officiel :
  19–20 EXCELLENT · 17–<19 TRÈS SATISFAISANT · 15–<17 SATISFAISANT ·
  13–<15 ACCEPTABLE · 11–<13 PEUT MIEUX FAIRE · 9–<11 INSUFFISANT ·
  7–<9 TRÈS INSUFFISANT · 4–<7 FAIBLE · 0–<4 TRÈS FAIBLE (aucun trou,
  décimales incluses, accents « TRÈS » corrects).
- **Normalisation** des barèmes ≠ 20 : `note/barème×20` (ex. 45/50 → 18 →
  TRÈS SATISFAISANT). Les valeurs invalides (note négative, note > barème,
  barème nul/négatif, non numérique) **lèvent ValueError** au lieu de
  produire une appréciation trompeuse. `None` → « — » (absence de note).
- Tous les consommateurs passent par cette fonction : serializer des notes,
  résumé élève, dashboards élève/parent, bulletins PDF, seed. L'ancienne
  échelle (Excellent/Très Bien/Bien/Assez Bien/Passable/Insuffisant) ne
  subsiste nulle part dans le code actif.
- `seed_demo_data` : appréciations de bulletins désormais calculées par la
  fonction centrale (suppression de seuils locaux dupliqués).
- Migration de données `bulletins/0005_recompute_appreciations.py` :
  recalcule les appréciations STOCKÉES des bulletins existants à partir de
  leur moyenne (réversible — l'inverse recalcule l'ancienne échelle ; la
  moyenne source n'est jamais modifiée).
- Frontend : n'affiche que l'appréciation renvoyée par le backend (aucun
  recalcul local) ; cellules passées par `t()` pour la traduction EN.
- Tests : bornes exhaustives entières 0→20 et décimales (3,99 / 6,99 /
  8,99 / 10,99 / 12,99 / 14,99 / 16,99 / 18,99 / 17,50 / 14,75 / 12,25 /
  10,50 / 8,75 / 6,50), balayage au centième sans trou, barèmes 5/10/25/
  50/100, rejets d'invalides, migration de bulletins.

## P2 — Réinitialisation de mot de passe par administrateur

- **Backend** :
  - `CustomUser.must_change_password` (+ migration accounts/0005) ;
  - `CustomUser.can_reset_password_of()` — règles métier :
    admin → enseignant/parent/élève de SON établissement uniquement ;
    superadmin → admin/enseignant/parent/élève ; jamais un superadmin,
    jamais soi-même ;
  - `POST /api/auth/users/<id>/reset-password/`
    (`AdminResetPasswordView`) : permissions vérifiées côté serveur
    (contournement par ID direct → 403), validateurs Django appliqués à la
    CIBLE, `set_password` (hachage Django, jamais de clair),
    `must_change_password=True`, **révocation de tous les refresh tokens**
    de la cible (blacklist simplejwt — l'auteur garde sa session), journal
    d'audit `PasswordResetLog` (auteur, cible, rôle, établissement, date —
    jamais le mot de passe), rate-limit 10/min/utilisateur ;
  - réponse `/api/auth/login/` et `/api/auth/me/` exposent
    `must_change_password` ; `change-password` lève le drapeau.
- **Frontend** :
  - `ResetPasswordModal` (identité + rôle de la cible, avertissement de
    sécurité, double saisie avec œil, règles de complexité, case de
    confirmation explicite, messages succès/erreur) branché dans
    `admin/Users.jsx`, `superadmin/Users.jsx` (masqué pour les cibles
    superadmin et soi-même) et `superadmin/Admins.jsx` ;
  - parcours complet « mot de passe temporaire » :
    `/change-password-required` (`ForcePasswordChange`) — le routeur
    bloque l'accès aux espaces tant que le drapeau est levé, le login
    redirige vers ce formulaire, la réussite renvoie vers l'espace du rôle.
- Tests : `backend/tests/test_password_reset.py` — matrice de permissions
  complète (23 tests) : admin→enseignant/parent/élève OK ; admin→admin/
  superadmin/soi-même/autre établissement 403 ; superadmin→admin/enseignant/
  parent/élève OK ; superadmin→superadmin 403 ; rôles non admin 403 ;
  anonyme 401 ; confirmation différente 400 ; mots de passe faibles 400 ;
  ancien mot de passe refusé au login, nouveau accepté ; refresh token
  révoqué (l'auteur conserve sa session) ; journal d'audit sans secret ;
  parcours must_change_password de bout en bout.

## P4 — Site vitrine public

### Médias (`scripts/optimize_site_media.py`, `MEDIA_INVENTORY.md`)
- 57 PNG + 1 vidéo inventoriés (dimensions, poids, orientation, doublons —
  aucun) ; originaux intacts.
- 114 WebP responsive (800/1600, ≈9 Mo au lieu de 113 Mo) sous
  `frontend/public/site/img/` avec noms sémantiques ; vidéo H.264+AAC
  compressée 73 Mo → ≈9 Mo + affiche WebP (lecture uniquement au clic).

### Backend CMS (`apps/website` + migration 0001)
- Modèles administrables : `SiteSettings` (identité, coordonnées, réseaux,
  horaires, SEO, statistiques **nullable = masquées**), `HeroSlide`,
  `NewsPost` (actualités ET événements, slug unique, brouillon/publié),
  `GalleryAlbum`/`GalleryItem` (images + vidéo), `ContactMessage`,
  `PreRegistration` (statut new/processing/closed).
- API publique en lecture seule + `POST /contact/` et
  `POST /preregistrations/` : validation backend complète, honeypot
  anti-spam, rate-limit 5/min/IP, **aucune exposition publique des
  soumissions**.
- API d'administration `/api/website/admin/**` (admin/superadmin
  uniquement) + admin Django (`/django-admin/`) pour tout le contenu.
- `manage.py seed_website` : contenu par défaut idempotent construit sur
  les médias réels — **aucune donnée fictive** (pas de fausses actualités,
  stats vides, coordonnées vides tant que l'administration ne les a pas
  saisies).

### Frontend public (`frontend/src/site/`)
- `/` est désormais le site vitrine ; la connexion ERP reste sur `/login`
  (boutons « Connexion » / « Mon espace » + « Inscrire mon enfant » dans le
  header). Les routes privées des 5 profils sont inchangées.
- Pages : Accueil (hero carrousel administrable — autoplay stoppé par
  `prefers-reduced-motion`, tactile, accessible —, présentation/valeurs,
  niveaux, pourquoi FEBA, bilinguisme, vie à FEBA, FEBA Online en vert,
  chiffres seulement si renseignés, actualités réelles, galerie, CTA),
  À propos, Campus, Académique, Admissions (+ formulaire préinscription),
  Vie scolaire, FEBA Online, Actualités + détail, Galerie (mosaïque +
  visionneuse plein écran + vidéo à la demande), Contact (+ formulaire),
  Mentions légales, Confidentialité, 404 publique.
- Écran ERP « Site vitrine » (`admin/Website.jsx`, routes /admin/website et
  /superadmin/website) : messages reçus (lu/non-lu, réponse mailto,
  suppression), préinscriptions (workflow de statut), actualités (CRUD +
  publication), paramètres du site (coordonnées, réseaux, stats, SEO).
- SEO : titres/méta/OG/canonical par page (`Seo.jsx`), JSON-LD « School »,
  `sitemap.xml`, `robots.txt` (espaces privés désindexés).
- Performance : lazy loading images (`srcset` 800/1600, dimensions
  explicites), code splitting complet du routeur — **bundle initial
  visiteur 407 Ko → 113 Ko gzip** (index 295 Ko + chunks site 1–19 Ko).

## Audit / divers

- Routeur : imports statiques des ~60 pages ERP convertis en
  `React.lazy` (mêmes gains pour l'ERP, chunk par page).
- `vite.config.js` : proxys pour `vite preview` (test local du build de
  production).
- i18n : clé dupliquée « Réinitialiser » supprimée (erreur eslint).
- `.claude/launch.json` : lancement démo locale (backend dev_sqlite +
  Vite) documenté et reproductible.
