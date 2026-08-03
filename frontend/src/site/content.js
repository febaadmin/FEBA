/**
 * Contenu STRUCTUREL du site vitrine (offre pédagogique, valeurs, activités).
 * Il s'agit de la structure éditoriale issue du cahier des charges et de la
 * charte FEBA — les contenus VARIABLES (slides, actualités, galerie,
 * coordonnées, statistiques) sont administrables via l'API /website/.
 * Les activités listées correspondent aux médias réellement fournis.
 *
 * BILINGUE (P1)
 * -------------
 * Chaque libellé est un couple `{ fr, en }` résolu par `tr(entry, lang)`.
 * Auparavant ces chaînes étaient de simples chaînes françaises : le
 * sélecteur EN/FR changeait la navigation et les titres, mais les cartes
 * de niveau, les valeurs et les activités restaient en français — la page
 * n'était donc ni française ni anglaise.
 *
 * Les noms de niveaux gardent leur forme française à côté de l'équivalent
 * britannique (« CM1 · CM2 » → « Year 5 · Year 6 ») : c'est ainsi que les
 * familles de la diaspora se repèrent entre les deux systèmes.
 */

/* `overlay`/`textSide` (V5) : composition de la carte de niveau.
   - "bottom" : sujets pleins cadre → texte en pied sur voile marine ;
   - "left"   : zone crème à gauche de la photo (ex. CM1·CM2) → le texte
     occupe cette zone libre sur un dégradé marine (solution B du cahier
     des charges — l'espace vide devient une composition intentionnelle). */
export const LEVELS = [
  {
    name: { fr: "Garderie", en: "Nursery" },
    desc: {
      fr: "Éveil et socialisation des tout-petits dans un cadre sécurisé et bienveillant.",
      en: "Awakening and socialising for the youngest children in a safe, caring setting.",
    },
    img: "/site/img/niveau-garderie-1600.webp", overlay: "bottom-navy", textSide: "bottom",
  },
  {
    name: { fr: "Maternelle 1 & 2", en: "Kindergarten 1 & 2" },
    desc: {
      fr: "Découverte des couleurs, des lettres et des nombres, en français et en anglais.",
      en: "Discovering colours, letters and numbers, in French and in English.",
    },
    img: "/site/img/niveau-maternelle-1600.webp", overlay: "bottom-navy", textSide: "bottom",
  },
  {
    name: { fr: "CI · CP", en: "CI · CP (Year 1 · Year 2)" },
    desc: {
      fr: "Entrée dans la lecture, l'écriture et le calcul avec un accompagnement rapproché.",
      en: "Starting to read, write and count with close individual support.",
    },
    img: "/site/img/niveau-primaire-lecture-1600.webp", overlay: "bottom-navy", textSide: "bottom",
  },
  {
    name: { fr: "CE1 · CE2", en: "CE1 · CE2 (Year 3 · Year 4)" },
    desc: {
      fr: "Consolidation des fondamentaux et ouverture progressive sur le monde.",
      en: "Consolidating the fundamentals and gradually opening up to the world.",
    },
    img: "/site/img/niveau-primaire-1600.webp", overlay: "bottom-navy", textSide: "bottom",
  },
  // V6 : l'ancien visuel (academique-participation) montrait surtout un mur
  // crème et un tableau, l'enseignante minuscule en bas — remplacé par une
  // vraie scène d'élèves en projet (autonomie, méthode), carte homogène.
  {
    name: { fr: "CM1 · CM2", en: "CM1 · CM2 (Year 5 · Year 6)" },
    desc: {
      fr: "Préparation à l'entrée au collège : autonomie, méthode et excellence.",
      en: "Preparing for secondary school: independence, method and excellence.",
    },
    img: "/site/img/valeurs-projet-1600.webp", overlay: "bottom-navy", textSide: "bottom",
  },
];

export const WHY_FEBA = [
  {
    title: { fr: "Enseignement bilingue", en: "Bilingual teaching" },
    desc: {
      fr: "Le français et l'anglais pratiqués chaque jour, dès la maternelle.",
      en: "French and English used every day, from kindergarten onwards.",
    },
  },
  {
    title: { fr: "Encadrement de qualité", en: "Quality supervision" },
    desc: {
      fr: "Une équipe pédagogique attentive, formée et bienveillante.",
      en: "An attentive, trained and caring teaching team.",
    },
  },
  {
    title: { fr: "Suivi personnalisé", en: "Personalised follow-up" },
    desc: {
      fr: "Chaque enfant progresse à son rythme, avec un accompagnement individualisé.",
      en: "Every child progresses at their own pace, with individual support.",
    },
  },
  {
    title: { fr: "Cadre sécurisé", en: "Secure setting" },
    desc: {
      fr: "Un campus clôturé et surveillé, pensé pour la sérénité des familles.",
      en: "An enclosed, supervised campus designed to reassure families.",
    },
  },
  {
    title: { fr: "Éducation fondée sur des valeurs", en: "Values-based education" },
    desc: {
      fr: "Excellence, respect, esprit d'équipe, foi et discipline.",
      en: "Excellence, respect, teamwork, faith and discipline.",
    },
  },
  {
    title: { fr: "Ouverture sur le monde", en: "Openness to the world" },
    desc: {
      fr: "Culture, patrimoine africain et horizons internationaux.",
      en: "Culture, African heritage and international horizons.",
    },
  },
];

export const VALUES = [
  {
    title: { fr: "Excellence", en: "Excellence" },
    desc: {
      fr: "Donner à chaque enfant les moyens de viser haut et de réussir.",
      en: "Giving every child the means to aim high and succeed.",
    },
  },
  {
    title: { fr: "Respect", en: "Respect" },
    desc: {
      fr: "Respect de soi, des autres et de son environnement, au quotidien.",
      en: "Respect for oneself, for others and for one's environment, every day.",
    },
  },
  {
    title: { fr: "Esprit d'équipe", en: "Teamwork" },
    desc: {
      fr: "Apprendre ensemble, s'entraider et grandir collectivement.",
      en: "Learning together, helping one another and growing as a group.",
    },
  },
];

/* Activités réellement illustrées par les médias fournis (aucune activité
   sans visuel réel — voir MEDIA_INVENTORY.md). */
export const ACTIVITIES = [
  {
    title: { fr: "Musique", en: "Music" },
    desc: {
      fr: "Guitare, clavier, batterie et chant : l'orchestre de l'école répète chaque semaine.",
      en: "Guitar, keyboard, drums and singing: the school band rehearses every week.",
    },
    img: "/site/img/activite-musique-groupe-1600.webp",
  },
  {
    title: { fr: "Percussions & culture", en: "Percussion & culture" },
    desc: {
      fr: "Djembé et rythmes traditionnels : la fierté de l'héritage africain.",
      en: "Djembe and traditional rhythms: the pride of African heritage.",
    },
    img: "/site/img/activite-percussions-1600.webp",
  },
  {
    title: { fr: "Arts plastiques", en: "Visual arts" },
    desc: {
      fr: "Peinture, dessin et créativité pour développer l'imagination.",
      en: "Painting, drawing and creativity to develop imagination.",
    },
    img: "/site/img/activite-arts-1600.webp",
  },
  {
    title: { fr: "Sport & football", en: "Sport & football" },
    desc: {
      fr: "Esprit d'équipe et dépassement de soi sur le terrain.",
      en: "Teamwork and self-improvement on the pitch.",
    },
    img: "/site/img/activite-football-1600.webp",
  },
  {
    title: { fr: "Expression orale", en: "Public speaking" },
    desc: {
      fr: "Prendre la parole en public avec confiance, en français et en anglais.",
      en: "Speaking in public with confidence, in French and in English.",
    },
    img: "/site/img/activite-expression-1600.webp",
  },
  {
    title: { fr: "Jeux éducatifs", en: "Educational games" },
    desc: {
      fr: "Marelle, rondes et jeux de cour pour apprendre en s'amusant.",
      en: "Hopscotch, circle games and playground games to learn while having fun.",
    },
    img: "/site/img/niveau-maternelle-cour-1600.webp",
  },
  {
    title: { fr: "Sciences", en: "Science" },
    desc: {
      fr: "Expériences et découvertes pour éveiller la curiosité scientifique.",
      en: "Experiments and discoveries to awaken scientific curiosity.",
    },
    img: "/site/img/academique-sciences-1600.webp",
  },
  {
    title: { fr: "Numérique & robotique", en: "Digital & robotics" },
    desc: {
      fr: "Premiers pas avec l'ordinateur et la robotique éducative.",
      en: "First steps with computers and educational robotics.",
    },
    img: "/site/img/academique-numerique-1600.webp",
  },
];

/* Atouts mis en avant pour FEBA French Heritage Academy (FEBA FHA) sur la
   page d'accueil. Le détail complet du programme vit dans fhaContent.js. */
export const ONLINE_FEATURES = [
  {
    fr: "Deux séances en direct par semaine, dans le fuseau horaire de votre famille",
    en: "Two live sessions a week, in your family's time zone",
  },
  {
    fr: "Petits groupes par tranche d'âge, avec des enseignants formés aux enfants anglophones",
    en: "Small groups by age band, with teachers trained to work with English-speaking children",
  },
  {
    fr: "Culture et héritage africains au cœur du programme",
    en: "African culture and heritage at the heart of the programme",
  },
  {
    fr: "Un parcours structuré sur cinq ans, de septembre à juin",
    en: "A structured five-year pathway, from September to June",
  },
];
