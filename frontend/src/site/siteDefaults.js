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

/**
 * 5 slides de repli — mêmes thèmes et images que le seed backend.
 *
 * P1 : le carrousel restait en français même en mode anglais. C'est la
 * PREMIÈRE chose que voit un visiteur : le laisser non traduit annulait
 * tout le reste de la bilinguisation. Chaque slide porte donc sa variante
 * `_en`, exactement comme le contenu administré côté serveur, pour que le
 * frontend applique le même repli dans les deux cas.
 */
export const DEFAULT_SLIDES = [
  {
    id: "def-1",
    title: "Bienvenue à FEBA", title_en: "Welcome to FEBA",
    subtitle: "Faith & Excellence Bilingual Academy — école bilingue à Akpakpa, Cotonou.",
    subtitle_en: "Faith & Excellence Bilingual Academy — a bilingual school in Akpakpa, Cotonou.",
    cta_label: "Découvrir l'école", cta_label_en: "Discover the school", cta_url: "/a-propos",
    // V6.1 : bâtiment principal avec panneau « Faith & Excellence » lisible.
    image_src: img("campus-logo"), focal: focal("campus-logo"),
  },
  {
    id: "def-2",
    title: "Grandir dans l'excellence", title_en: "Growing in excellence",
    subtitle: "Un encadrement de qualité, des valeurs et un suivi personnalisé.",
    subtitle_en: "Quality supervision, strong values and personalised follow-up.",
    cta_label: "Nos programmes", cta_label_en: "Our programmes", cta_url: "/academique",
    image_src: img("hero-excellence"), focal: focal("hero-excellence"),
  },
  {
    id: "def-3",
    title: "Français et anglais au quotidien", title_en: "French and English every day",
    subtitle: "Un enseignement bilingue dès le plus jeune âge.",
    subtitle_en: "Bilingual teaching from the earliest age.",
    cta_label: "Le bilinguisme à FEBA", cta_label_en: "Bilingualism at FEBA", cta_url: "/academique",
    image_src: img("hero-bilingue"), focal: focal("hero-bilingue"),
  },
  {
    id: "def-4",
    title: "Apprendre, grandir et s'épanouir", title_en: "Learn, grow and flourish",
    subtitle: "Musique, arts, sport et jeux éducatifs dans un cadre sécurisé.",
    subtitle_en: "Music, arts, sport and educational games in a safe setting.",
    cta_label: "La vie à FEBA", cta_label_en: "Life at FEBA", cta_url: "/vie-scolaire",
    image_src: img("hero-vie-scolaire"), focal: focal("hero-vie-scolaire"),
  },
  {
    id: "def-5",
    title: "Admissions ouvertes", title_en: "Admissions are open",
    subtitle: "Rejoignez la famille FEBA : la préinscription ne prend que quelques minutes.",
    subtitle_en: "Join the FEBA family: pre-registration takes only a few minutes.",
    cta_label: "Inscrire mon enfant", cta_label_en: "Enrol my child", cta_url: "/admissions",
    image_src: img("hero-admissions"), focal: focal("hero-admissions"),
  },
];

/**
 * Albums de repli de la galerie. Chaque slug n'apparaît qu'UNE fois dans
 * l'ensemble de la galerie (aucun doublon), et diffère des slides du hero.
 */
const ALBUM_DEFS = [
  [["Vie de classe", "Classroom life"],
   ["Apprentissages quotidiens, lecture et travaux de groupe.",
    "Daily learning, reading and group work."], [
    ["academique-classe", "Cours en classe", "A lesson in class"],
    ["academique-carte", "Découverte du monde", "Discovering the world"],
    ["academique-participation", "Participation en classe", "Taking part in class"],
    ["niveau-primaire", "Travail en primaire", "Primary-school work"],
    ["niveau-primaire-lecture", "Lecture en classe", "Reading in class"],
    ["academique-lecture", "Lecture accompagnée", "Guided reading"],
    ["academique-bibliotheque", "À la bibliothèque", "In the library"],
    ["academique-sciences", "Atelier sciences", "Science workshop"],
    ["academique-numerique", "Initiation au numérique", "Introduction to digital skills"],
    ["galerie-ecriture", "Travaux d'écriture", "Writing work"],
    ["galerie-etude", "Temps d'étude", "Study time"],
    ["galerie-devoirs", "Devoirs en classe", "Homework in class"],
    ["galerie-soutien", "Soutien individualisé", "One-to-one support"],
    ["accompagnement-duo", "Accompagnement personnalisé", "Personalised support"],
  ]],
  [["Activités et épanouissement", "Activities and personal growth"],
   ["Musique, arts, sport et expression.", "Music, arts, sport and self-expression."], [
    ["activite-musique-groupe", "Groupe de musique", "The school band"],
    ["activite-musique-atelier", "Atelier musique", "Music workshop"],
    ["activite-musique-scene", "Répétition musicale", "Music rehearsal"],
    ["activite-percussions", "Percussions et héritage culturel", "Percussion and cultural heritage"],
    ["activite-arts", "Arts plastiques", "Visual arts"],
    ["activite-football", "Football", "Football"],
    ["activite-football-cour", "Sport dans la cour", "Sport in the playground"],
    ["activite-expression", "Expression orale", "Public speaking"],
    ["activite-ronde", "Jeux dans la cour", "Playground games"],
    ["niveau-maternelle-cour", "Marelle en maternelle", "Hopscotch in kindergarten"],
  ]],
  // V6.2 — cartes « Bonne image » validées : les deux façades non retenues
  // (campus-facade, campus-fresque) sont retirées au profit de la façade au
  // logo/fresques et de la façade à la devise. Backend + fallback identiques.
  [["Notre campus", "Our campus"],
   ["Les espaces de l'école à Akpakpa.", "The school's spaces in Akpakpa."], [
    ["campus-logo", "Le bâtiment principal", "The main building"],
    ["campus-facade-logo", "Façade FEBA — logo et fresques", "FEBA frontage — logo and murals"],
    ["campus-devise", "La devise de l'école", "The school motto"],
    ["campus-cour", "La cour de récréation", "The playground"],
  ]],
  [["Petite enfance", "Early years"],
   ["Garderie et maternelle : éveil et jeux éducatifs.",
    "Nursery and kindergarten: awakening and educational games."], [
    ["petite-enfance-creche", "La crèche FEBA", "The FEBA crèche"],
    ["niveau-garderie", "Éveil en garderie", "Awakening in nursery"],
    ["niveau-garderie-jeux", "Jeux de construction", "Building games"],
    ["niveau-maternelle", "Activités en maternelle", "Kindergarten activities"],
  ]],
  [["FEBA French Heritage Academy", "FEBA French Heritage Academy"],
   ["Cours de français en ligne pour les enfants de la diaspora.",
    "Online French lessons for children of the diaspora."], [
    ["online-visio", "Cours en visioconférence", "Video-conference lesson"],
    ["online-cours-francais", "Cours de français en ligne", "Online French lesson"],
    ["online-lecon", "Leçon interactive", "Interactive lesson"],
  ]],
  // V6.1 — « Mosaïque de l'école » (galerie-mosaique-3) retirée : elle
  // contenait un portrait de bureau désormais banni du site.
  [["Moments FEBA", "FEBA moments"],
   ["Instantanés de la vie de l'école.", "Snapshots of school life."], [
    ["valeurs-equipe", "Esprit d'équipe", "Team spirit"],
    ["galerie-projet", "Travail de groupe", "Group work"],
    ["apropos-equipe", "L'équipe pédagogique", "The teaching team"],
    ["admissions-visite", "Accueil des familles", "Welcoming families"],
    ["galerie-mosaique-1", "Mosaïque de la vie scolaire", "School-life mosaic"],
    ["galerie-mosaique-2", "Mosaïque des apprentissages", "Learning mosaic"],
  ]],
];

/* La forme produite est volontairement IDENTIQUE à celle du serveur
   (`title` / `title_en`, `caption` / `caption_en`…) : les composants
   appliquent le même repli de langue, qu'ils affichent du contenu
   administré ou du contenu de repli. */
export const DEFAULT_ALBUMS = ALBUM_DEFS.map(([[title, titleEn], [description, descriptionEn], items], ai) => ({
  id: `def-album-${ai}`,
  title,
  title_en: titleEn,
  description,
  description_en: descriptionEn,
  items: [
    ...items.map(([slug, caption, captionEn], ii) => ({
      id: `def-${ai}-${ii}`,
      kind: "image",
      caption,
      caption_en: captionEn,
      alt_text: caption,
      alt_text_en: captionEn,
      image_src: `/site/img/${slug}-800.webp`,
      focal: focal(slug),
    })),
    // La vidéo institutionnelle rejoint « Moments FEBA », chargée au clic.
    ...(title === "Moments FEBA" ? [{
      id: `def-${ai}-video`,
      kind: "video",
      caption: "FEBA en vidéo",
      caption_en: "FEBA on video",
      alt_text: "Vidéo de présentation de l'école",
      alt_text_en: "Video introducing the school",
      image_src: "/site/video/feba-presentation-poster.webp",
      video_url: "/site/video/feba-presentation.mp4",
      focal: "50% 50%",
    }] : []),
  ],
}));

/**
 * Champ éditorial dans la langue affichée.
 *
 * Le repli est délibéré : une traduction anglaise VIDE renvoie le français
 * plutôt qu'une chaîne vide. Une actualité non traduite reste lisible ;
 * un titre disparu ne l'est pas.
 */
export function pickLang(entry, field, lang) {
  if (!entry) return "";
  if (lang === "en") return entry[`${field}_en`] || entry[field] || "";
  return entry[field] || "";
}
