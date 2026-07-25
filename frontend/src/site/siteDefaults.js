/**
 * siteDefaults — contenu de repli du site vitrine (V6).
 *
 * Le carrousel et la galerie préfèrent TOUJOURS le contenu administré
 * (API /website/hero-slides/ et /gallery/). Mais si l'API est momentanément
 * indisponible ou vide (base non seedée, redéploiement, panne réseau), ces
 * défauts — bâtis sur les 57 médias RÉELS packagés avec leurs points focaux
 * — garantissent un carrousel premium à 5 slides et une galerie pleine,
 * jamais une image statique unique ni un « bientôt disponible ».
 *
 * Les points focaux proviennent du registre central mediaMeta.js : une seule
 * source de vérité pour le cadrage, partagée avec les visuels administrés.
 */
import { metaFor } from "./mediaMeta";

const img = (slug) => `/site/img/${slug}-1600.webp`;
const focal = (slug) => metaFor(img(slug)).position;

/** 5 slides de repli — mêmes thèmes et images que le seed backend. */
export const DEFAULT_SLIDES = [
  {
    id: "def-1", title: "Bienvenue à FEBA",
    subtitle: "Faith & Excellence Bilingual Academy — école bilingue à Akpakpa, Cotonou.",
    cta_label: "Découvrir l'école", cta_url: "/a-propos",
    // V6.1 : bâtiment principal avec panneau « Faith & Excellence » lisible.
    image_src: img("campus-logo"), focal: focal("campus-logo"),
  },
  {
    id: "def-2", title: "Grandir dans l'excellence",
    subtitle: "Un encadrement de qualité, des valeurs et un suivi personnalisé.",
    cta_label: "Nos programmes", cta_url: "/academique",
    image_src: img("hero-excellence"), focal: focal("hero-excellence"),
  },
  {
    id: "def-3", title: "Français et anglais au quotidien",
    subtitle: "Un enseignement bilingue dès le plus jeune âge.",
    cta_label: "Le bilinguisme à FEBA", cta_url: "/academique",
    image_src: img("hero-bilingue"), focal: focal("hero-bilingue"),
  },
  {
    id: "def-4", title: "Apprendre, grandir et s'épanouir",
    subtitle: "Musique, arts, sport et jeux éducatifs dans un cadre sécurisé.",
    cta_label: "La vie à FEBA", cta_url: "/vie-scolaire",
    image_src: img("hero-vie-scolaire"), focal: focal("hero-vie-scolaire"),
  },
  {
    id: "def-5", title: "Admissions ouvertes",
    subtitle: "Rejoignez la famille FEBA : la préinscription ne prend que quelques minutes.",
    cta_label: "Inscrire mon enfant", cta_url: "/admissions",
    image_src: img("hero-admissions"), focal: focal("hero-admissions"),
  },
];

/**
 * Albums de repli de la galerie. Chaque slug n'apparaît qu'UNE fois dans
 * l'ensemble de la galerie (aucun doublon), et diffère des slides du hero.
 */
const ALBUM_DEFS = [
  ["Vie de classe", "Apprentissages quotidiens, lecture et travaux de groupe.", [
    ["academique-classe", "Cours en classe"],
    ["academique-carte", "Découverte du monde"],
    ["academique-participation", "Participation en classe"],
    ["niveau-primaire", "Travail en primaire"],
    ["niveau-primaire-lecture", "Lecture en classe"],
    ["academique-lecture", "Lecture accompagnée"],
    ["academique-bibliotheque", "À la bibliothèque"],
    ["academique-sciences", "Atelier sciences"],
    ["academique-numerique", "Initiation au numérique"],
    ["galerie-ecriture", "Travaux d'écriture"],
    ["galerie-etude", "Temps d'étude"],
    ["galerie-devoirs", "Devoirs en classe"],
    ["galerie-soutien", "Soutien individualisé"],
    ["accompagnement-duo", "Accompagnement personnalisé"],
  ]],
  ["Activités et épanouissement", "Musique, arts, sport et expression.", [
    ["activite-musique-groupe", "Groupe de musique"],
    ["activite-musique-atelier", "Atelier musique"],
    ["activite-musique-scene", "Répétition musicale"],
    ["activite-percussions", "Percussions et héritage culturel"],
    ["activite-arts", "Arts plastiques"],
    ["activite-football", "Football"],
    ["activite-football-cour", "Sport dans la cour"],
    ["activite-expression", "Expression orale"],
    ["activite-ronde", "Jeux dans la cour"],
    ["niveau-maternelle-cour", "Marelle en maternelle"],
  ]],
  // V6.2 — cartes « Bonne image » validées : les deux façades non retenues
  // (campus-facade, campus-fresque) sont retirées au profit de la façade au
  // logo/fresques et de la façade à la devise. Backend + fallback identiques.
  ["Notre campus", "Les espaces de l'école à Akpakpa.", [
    ["campus-logo", "Le bâtiment principal"],
    ["campus-facade-logo", "Façade FEBA — logo et fresques"],
    ["campus-devise", "La devise de l'école"],
    ["campus-cour", "La cour de récréation"],
  ]],
  ["Petite enfance", "Garderie et maternelle : éveil et jeux éducatifs.", [
    ["petite-enfance-creche", "La crèche FEBA"],
    ["niveau-garderie", "Éveil en garderie"],
    ["niveau-garderie-jeux", "Jeux de construction"],
    ["niveau-maternelle", "Activités en maternelle"],
  ]],
  ["FEBA Online", "Cours en ligne pour les enfants de la diaspora.", [
    ["online-visio", "Cours en visioconférence"],
    ["online-cours-francais", "Cours de français en ligne"],
    ["online-lecon", "Leçon interactive"],
  ]],
  // V6.1 — « Mosaïque de l'école » (galerie-mosaique-3) retirée : elle
  // contenait un portrait de bureau désormais banni du site.
  ["Moments FEBA", "Instantanés de la vie de l'école.", [
    ["valeurs-equipe", "Esprit d'équipe"],
    ["galerie-projet", "Travail de groupe"],
    ["apropos-equipe", "L'équipe pédagogique"],
    ["admissions-visite", "Accueil des familles"],
    ["galerie-mosaique-1", "Mosaïque de la vie scolaire"],
    ["galerie-mosaique-2", "Mosaïque des apprentissages"],
  ]],
];

export const DEFAULT_ALBUMS = ALBUM_DEFS.map(([title, description, items], ai) => ({
  id: `def-album-${ai}`,
  title,
  description,
  items: [
    ...items.map(([slug, caption], ii) => ({
      id: `def-${ai}-${ii}`,
      kind: "image",
      caption,
      alt_text: caption,
      image_src: `/site/img/${slug}-800.webp`,
      focal: focal(slug),
    })),
    // La vidéo institutionnelle rejoint « Moments FEBA », chargée au clic.
    ...(title === "Moments FEBA" ? [{
      id: `def-${ai}-video`,
      kind: "video",
      caption: "FEBA en vidéo",
      alt_text: "Vidéo de présentation de l'école",
      image_src: "/site/video/feba-presentation-poster.webp",
      video_url: "/site/video/feba-presentation.mp4",
      focal: "50% 50%",
    }] : []),
  ],
}));
