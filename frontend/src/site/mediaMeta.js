/**
 * mediaMeta — SOURCE UNIQUE des réglages d'affichage des médias packagés
 * du site vitrine (V5, audit visuel).
 *
 * Chaque visuel a une composition différente (sujet décentré, grande zone
 * crème volontaire, portrait…) : un `object-position: center` global coupait
 * des têtes et laissait des fonds vides. Le point focal de CHAQUE image est
 * défini ici — aucune valeur dispersée dans les composants.
 *
 * - `position` : point focal CSS (object-position) appliqué automatiquement
 *   par <SiteImage> à partir du slug du fichier ;
 * - `mobile`   : variante de point focal < 640 px lorsque le cadrage
 *   desktop ne convient pas au format étroit.
 *
 * Les médias ADMINISTRABLES (slides du carrousel, galerie, actualités)
 * portent leur propre point focal en base (focal_x / focal_y, exposés par
 * l'API en `focal`) — voir apps/website. Ce registre ne couvre que les
 * images statiques packagées (/site/img/…).
 *
 * Les dégradés de marque (OVERLAYS) sont également centralisés ici :
 * aucun composant ne doit définir son propre gradient arbitraire.
 */

// ── Dégradés officiels FEBA (tokens du design system) ────────────────────────
export const OVERLAYS = {
  none: "",
  // Voile bas → texte posé en pied d'image (cartes, vignettes)
  "bottom-navy": "bg-gradient-to-t from-feba-navy/90 via-feba-navy/30 to-transparent",
  // Zone crème à GAUCHE de la photo → composition texte sur dégradé marine
  "left-navy": "bg-gradient-to-r from-feba-navy/90 via-feba-navy/45 to-transparent",
  // V6.2 — variante responsive : dégradé BAS sur mobile (l'image reste
  // pleinement visible, texte posé en pied) → dégradé GAUCHE dès sm.
  "left-navy-md": "bg-gradient-to-t from-feba-navy/85 via-feba-navy/35 to-transparent sm:bg-gradient-to-r sm:from-feba-navy/90 sm:via-feba-navy/45 sm:to-transparent",
  // Zone crème à DROITE
  "right-navy": "bg-gradient-to-l from-feba-navy/90 via-feba-navy/45 to-transparent",
  // Variante FEBA Online (vert réservé à ce programme)
  "left-green": "bg-gradient-to-r from-feba-green/90 via-feba-green/40 to-transparent",
  // Léger assombrissement du haut (lisibilité du header sur les heros)
  "top-navy": "bg-gradient-to-b from-feba-navy/50 via-transparent to-transparent",
  // Hero du carrousel (texte en bas, fondu profond)
  hero: "bg-gradient-to-t from-feba-navy/95 via-feba-navy/45 to-feba-navy/10",
  // V6.1 — ancrage marine du texte à GAUCHE du hero (remplace le voile gris
  // délavé) : dégradé DA FEBA marine → transparent, systématique sur toutes
  // les slides, avec une pointe dorée discrète pour la cohérence de marque.
  "hero-left": "bg-gradient-to-r from-feba-navy/80 via-feba-navy/35 to-transparent",
  "hero-gold": "bg-gradient-to-tr from-feba-gold/15 via-transparent to-transparent",
};

// ── Points focaux par visuel (slug du fichier packagé) ───────────────────────
export const MEDIA_META = {
  // Heros du carrousel (les slides administrés portent leur focal en base ;
  // valeurs par défaut ici pour les usages statiques des mêmes fichiers)
  "hero-campus": { position: "50% 55%" },
  "hero-bilingue": { position: "50% 38%" },
  "hero-vie-scolaire": { position: "55% 78%", mobile: "60% 80%" }, // enfants en bas, crème en haut
  "hero-excellence": { position: "50% 38%" },
  "hero-admissions": { position: "72% 45%", mobile: "78% 45%" }, // famille à droite, crème à gauche
  // Campus
  "campus-garderie-maternelle": { position: "50% 58%" },
  "campus-facade": { position: "50% 45%" },
  "campus-batiment": { position: "50% 55%" },
  // V6.1 — nouveaux visuels de campus (vues réellement distinctes)
  "campus-logo": { position: "50% 48%" },     // bâtiment principal + panneau « Faith & Excellence » lisible
  "campus-fresque": { position: "50% 52%" },  // (V6.1 — non retenu en V6.2, conservé au registre)
  // V6.2 — visuels « Bonne image » validés pour la mosaïque d'accueil / galerie
  "campus-facade-logo": { position: "50% 42%" }, // V7 : nouvelle façade — panneau FEBA (logo + nom) en haut → cadrage relevé pour le garder visible
  "campus-devise": { position: "50% 50%" },      // façade « Here will change the world » (logo + devise + fresques)
  "campus-cour": { position: "50% 74%", mobile: "55% 76%" }, // cour : enfants en bas, ciel/crème en haut
  // Niveaux
  "niveau-garderie": { position: "50% 42%" },
  "niveau-garderie-jeux": { position: "50% 45%" },
  "niveau-maternelle": { position: "50% 42%" },
  "niveau-maternelle-cour": { position: "50% 60%" },
  "niveau-primaire": { position: "50% 30%" },        // têtes hautes dans le cadre
  "niveau-primaire-lecture": { position: "50% 36%" },
  // Académique
  "academique-classe": { position: "50% 35%" },
  "academique-carte": { position: "50% 35%" },
  "academique-lecture": { position: "50% 42%" },
  "academique-bibliotheque": { position: "50% 40%" },
  "academique-sciences": { position: "50% 40%" },
  "academique-numerique": { position: "50% 42%" },
  "academique-participation": { position: "26% 64%", mobile: "26% 66%" }, // enseignante en bas-gauche, grand mur crème → cadrage sur elle
  // Bilinguisme / accompagnement / valeurs
  "bilingue-accompagnement": { position: "50% 66%", mobile: "50% 70%" }, // V6.2 : enseignante + 2 élèves en bas, grand mur crème en haut → descendre le cadrage sur les visages/bustes
  "accompagnement-individuel": { position: "66% 42%", mobile: "72% 42%" },
  "accompagnement-duo": { position: "52% 64%", mobile: "52% 66%" }, // V6.1 : trio en bas, grand mur crème en haut → descendre le cadrage sur les visages
  "valeurs-equipe": { position: "50% 32%" },
  "valeurs-projet": { position: "50% 40%" }, // carte CM1·CM2 : groupe autour de la table
  // Vie scolaire / activités — V6 : focals relevés pour que les visages
  // restent au-dessus du dégradé de texte (« personnes trop basses »).
  "activite-musique-atelier": { position: "58% 42%" },
  "activite-musique-groupe": { position: "50% 36%" },
  "activite-musique-scene": { position: "50% 40%" },
  "activite-percussions": { position: "50% 72%" }, // groupe bas + grand mur crème en haut → cadrage descendu sur les musiciens
  "activite-arts": { position: "50% 32%" },
  "activite-football-cour": { position: "50% 42%" },
  "activite-football": { position: "50% 40%" },
  "activite-expression": { position: "48% 30%" },
  "activite-ronde": { position: "72% 62%", mobile: "74% 66%" }, // ronde à droite, crème à gauche → cadrage poussé à droite
  // FEBA Online
  "online-visio": { position: "45% 45%" },
  "online-cours-francais": { position: "62% 48%", mobile: "70% 48%" }, // laptop à droite, crème à gauche
  "online-lecon": { position: "42% 45%" },
  // Admissions / contact
  "admissions-famille": { position: "50% 60%", mobile: "50% 62%" }, // V7 : famille debout, grand mur crème en haut → descendre le cadrage pour montrer les corps (pas que les têtes)
  "admissions-visite": { position: "50% 35%" },
  "admissions-accueil": { position: "70% 45%", mobile: "76% 45%" }, // accueil à droite, crème à gauche
  "admissions-bienvenue": { position: "65% 42%" },
  "contact-accueil": { position: "32% 32%" },       // réceptionniste à gauche du cadre
  "contact-administration": { position: "50% 35%" },
  // À propos
  // V6.1 — apropos-direction / apropos-direction-2 (même personne « assise
  // seule dans un bureau ») supprimées du site ET du paquet : image bannie.
  "apropos-encadrement": { position: "50% 16%" },   // portrait 2:3 : garder la tête + marge
  // V6.2 — photo du directeur à son bureau restaurée : « Bonne image » demandée
  // pour la carte « La direction » UNIQUEMENT (ni galerie, ni mosaïque).
  "apropos-direction-2": { position: "50% 30%" },
  "apropos-equipe-pedagogique": { position: "50% 38%" }, // V6.1 : photo d'équipe (7 personnes) — visages hauts
  "petite-enfance-creche": { position: "50% 52%" },      // V6.1 : crèche — lits + tout-petits au centre
  "apropos-equipe": { position: "50% 32%" },
  // Galerie (compléments)
  "galerie-projet": { position: "50% 38%" },
  // V6.1 — sujets décentrés / trop bas + grand fond crème : cadrage individuel
  "galerie-ecriture": { position: "66% 46%", mobile: "68% 48%" }, // 2 élèves à droite, crème à gauche
  "galerie-etude": { position: "66% 46%", mobile: "68% 48%" },     // 2 élèves à droite, crème à gauche
  "galerie-devoirs": { position: "50% 66%", mobile: "50% 68%" },   // portrait : élèves en bas, mur crème en haut
  "galerie-soutien": { position: "50% 68%", mobile: "50% 70%" },   // portrait : trio en bas, mur crème en haut
  "galerie-mosaique-1": { position: "50% 50%" },
  "galerie-mosaique-2": { position: "50% 50%" },
  // V6.1 — galerie-mosaique-3 supprimée : elle incrustait le portrait de bureau banni.
};

const SLUG_RE = /\/site\/img\/(.+)-(?:800|1600)\.webp$/;

/** Slug packagé à partir d'une URL /site/img/<slug>-<taille>.webp (ou null). */
export function slugFromSrc(src) {
  const m = typeof src === "string" ? src.match(SLUG_RE) : null;
  return m ? m[1] : null;
}

/** Métadonnées d'affichage d'un média packagé (position par défaut : centre). */
export function metaFor(src) {
  const slug = slugFromSrc(src);
  return (slug && MEDIA_META[slug]) || { position: "50% 50%" };
}
