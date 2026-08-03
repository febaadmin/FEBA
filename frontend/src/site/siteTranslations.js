/**
 * Traductions du SITE PUBLIC (hors page FEBA FHA, qui a son propre
 * contenu dans fhaContent.js).
 *
 * P1 — Le sélecteur EN/FR était visible partout mais seule la page FEBA
 * FHA changeait réellement de langue : le carrousel, les titres, les
 * sections et le pied de page restaient en français même en mode EN.
 *
 * Ce module centralise les chaînes du site. Chaque entrée est un couple
 * { fr, en } résolu par `tr()` (voir fhaContent.js), ce qui évite les
 * conditions `lang === 'fr' ? … : …` dispersées dans les composants.
 */

/* ── Navigation et pied de page (présents sur TOUTES les pages) ──────── */
export const NAV = {
  home: { fr: "Accueil", en: "Home" },
  about: { fr: "À propos", en: "About" },
  academics: { fr: "Académique", en: "Academics" },
  admissions: { fr: "Admissions", en: "Admissions" },
  schoolLife: { fr: "Vie scolaire", en: "School life" },
  fha: { fr: "FEBA FHA", en: "FEBA FHA" },
  news: { fr: "Actualités", en: "News" },
  gallery: { fr: "Galerie", en: "Gallery" },
  contact: { fr: "Contact", en: "Contact" },
};

export const UI = {
  mySpace: { fr: "Mon espace", en: "My account" },
  login: { fr: "Connexion", en: "Sign in" },
  enrollChild: { fr: "Inscrire mon enfant", en: "Enroll my child" },
  openMenu: { fr: "Ouvrir le menu", en: "Open menu" },
  closeMenu: { fr: "Fermer le menu", en: "Close menu" },
  mainNav: { fr: "Navigation principale", en: "Main navigation" },
  mobileNav: { fr: "Navigation mobile", en: "Mobile navigation" },
  quickLinks: { fr: "Liens rapides", en: "Quick links" },
  ourLevels: { fr: "Nos niveaux", en: "Our year groups" },
  legalNotice: { fr: "Mentions légales", en: "Legal notice" },
  privacy: { fr: "Confidentialité", en: "Privacy" },
  aboutFeba: { fr: "À propos de FEBA", en: "About FEBA" },
  academicPrograms: { fr: "Programmes académiques", en: "Academic programmes" },
  photoGallery: { fr: "Galerie photos", en: "Photo gallery" },
  userArea: { fr: "Espace utilisateurs", en: "User area" },
  fhaDiaspora: { fr: "+ FEBA FHA (diaspora)", en: "+ FEBA FHA (diaspora)" },
  loading: { fr: "Chargement…", en: "Loading…" },
};

/* ── Page d'accueil ──────────────────────────────────────────────────── */
export const HOME = {
  heroFallbackTitle: { fr: "Bienvenue à FEBA", en: "Welcome to FEBA" },
  heroFallbackSubtitle: {
    fr: "Faith & Excellence Bilingual Academy — école bilingue à Akpakpa, Cotonou.",
    en: "Faith & Excellence Bilingual Academy — a bilingual school in Akpakpa, Cotonou.",
  },
  heroFallbackCta: { fr: "Découvrir l'école", en: "Discover the school" },

  welcomeOverline: { fr: "Bienvenue à FEBA", en: "Welcome to FEBA" },
  presentationBody: {
    fr:
      "Située à Akpakpa (Cotonou, Bénin), FEBA est une école bilingue " +
      "français-anglais qui accueille les enfants de la garderie au CM2. " +
      "Notre mission :",
    en:
      "Located in Akpakpa (Cotonou, Benin), FEBA is a French-English " +
      "bilingual school welcoming children from nursery through to Year 6. " +
      "Our mission:",
  },
  presentationHighlight: {
    fr: "développer les talents et construire l'avenir",
    en: "develop every talent and build the future",
  },
  presentationEnd: {
    fr: "de chaque enfant, dans un cadre chaleureux, sécurisé et exigeant.",
    en: "of every child, in a warm, safe and demanding environment.",
  },

  whyTitle: { fr: "Pourquoi choisir FEBA ?", en: "Why choose FEBA?" },
  valuesTitle: { fr: "Nos valeurs", en: "Our values" },
  levelsOverline: { fr: "Nos niveaux", en: "Our year groups" },
  levelsTitle: { fr: "De la garderie au CM2", en: "From nursery to Year 6" },
  bilingualOverline: { fr: "Bilinguisme", en: "Bilingual education" },
  bilingualTitle: {
    fr: "Deux langues, un même niveau d'exigence",
    en: "Two languages, one standard of excellence",
  },
  activitiesOverline: { fr: "Vie scolaire", en: "School life" },
  activitiesTitle: { fr: "La vie à FEBA", en: "Life at FEBA" },
  discoverSchoolLife: { fr: "Découvrir la vie à FEBA", en: "Discover life at FEBA" },
  newsTitle: { fr: "Actualités", en: "News" },
  allNews: { fr: "Toutes les actualités", en: "All news" },

  statsStudents: { fr: "Élèves épanouis", en: "Thriving students" },
  statsTeachers: { fr: "Enseignants qualifiés", en: "Qualified teachers" },
  statsYears: { fr: "Années d'expérience", en: "Years of experience" },
  statsSuccess: { fr: "Taux de réussite", en: "Success rate" },

  ctaTitle: { fr: "Rejoignez la famille FEBA", en: "Join the FEBA family" },
  ctaText: {
    fr: "Inscrivez votre enfant dès aujourd'hui et offrez-lui une éducation bilingue d'excellence.",
    en: "Enrol your child today and give them an outstanding bilingual education.",
  },
  ctaContact: { fr: "Nous contacter", en: "Contact us" },
};

/* ── Contenu structurel traduit ──────────────────────────────────────── */
/* Les libellés de `content.js` étaient uniquement en français. Cette
   table fournit leur équivalent anglais, indexé par le nom français —
   ce qui évite de dupliquer tout le fichier de contenu. */
export const CONTENT_EN = {
  // Niveaux
  "Garderie": "Nursery",
  "Maternelle 1 & 2": "Kindergarten 1 & 2",
  "CI · CP": "Year 1 · Year 2",
  "CE1 · CE2": "Year 3 · Year 4",
  "CM1 · CM2": "Year 5 · Year 6",
  // Valeurs
  "Excellence": "Excellence",
  "Foi": "Faith",
  "Respect": "Respect",
  "Discipline": "Discipline",
  "Solidarité": "Solidarity",
  "Créativité": "Creativity",
  // Activités
  "Musique": "Music",
  "Percussions & culture": "Percussion & culture",
  "Arts plastiques": "Visual arts",
  "Sport & football": "Sport & football",
  "Expression orale": "Public speaking",
  "Jeux éducatifs": "Educational games",
  "Sciences": "Science",
  "Numérique & robotique": "Digital & robotics",
};

/**
 * Traduit un libellé de contenu structurel.
 * Repli sur le texte français si aucune traduction n'existe : mieux vaut
 * un mot non traduit qu'une chaîne vide.
 */
export function trContent(label, lang) {
  if (lang !== "en") return label;
  return CONTENT_EN[label] || label;
}
