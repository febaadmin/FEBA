/**
 * Contenu STRUCTUREL du site vitrine (offre pédagogique, valeurs, activités).
 * Il s'agit de la structure éditoriale issue du cahier des charges et de la
 * charte FEBA — les contenus VARIABLES (slides, actualités, galerie,
 * coordonnées, statistiques) sont administrables via l'API /website/.
 * Les activités listées correspondent aux médias réellement fournis.
 */

/* `overlay`/`textSide` (V5) : composition de la carte de niveau.
   - "bottom" : sujets pleins cadre → texte en pied sur voile marine ;
   - "left"   : zone crème à gauche de la photo (ex. CM1·CM2) → le texte
     occupe cette zone libre sur un dégradé marine (solution B du cahier
     des charges — l'espace vide devient une composition intentionnelle). */
export const LEVELS = [
  { name: "Garderie", desc: "Éveil et socialisation des tout-petits dans un cadre sécurisé et bienveillant.", img: "/site/img/niveau-garderie-1600.webp", overlay: "bottom-navy", textSide: "bottom" },
  { name: "Maternelle 1 & 2", desc: "Découverte des couleurs, des lettres et des nombres, en français et en anglais.", img: "/site/img/niveau-maternelle-1600.webp", overlay: "bottom-navy", textSide: "bottom" },
  { name: "CI · CP", desc: "Entrée dans la lecture, l'écriture et le calcul avec un accompagnement rapproché.", img: "/site/img/niveau-primaire-lecture-1600.webp", overlay: "bottom-navy", textSide: "bottom" },
  { name: "CE1 · CE2", desc: "Consolidation des fondamentaux et ouverture progressive sur le monde.", img: "/site/img/niveau-primaire-1600.webp", overlay: "bottom-navy", textSide: "bottom" },
  // V6 : l'ancien visuel (academique-participation) montrait surtout un mur
  // crème et un tableau, l'enseignante minuscule en bas — remplacé par une
  // vraie scène d'élèves en projet (autonomie, méthode), carte homogène.
  { name: "CM1 · CM2", desc: "Préparation à l'entrée au collège : autonomie, méthode et excellence.", img: "/site/img/valeurs-projet-1600.webp", overlay: "bottom-navy", textSide: "bottom" },
];

export const WHY_FEBA = [
  { title: "Enseignement bilingue", desc: "Le français et l'anglais pratiqués chaque jour, dès la maternelle." },
  { title: "Encadrement de qualité", desc: "Une équipe pédagogique attentive, formée et bienveillante." },
  { title: "Suivi personnalisé", desc: "Chaque enfant progresse à son rythme, avec un accompagnement individualisé." },
  { title: "Cadre sécurisé", desc: "Un campus clôturé et surveillé, pensé pour la sérénité des familles." },
  { title: "Éducation fondée sur des valeurs", desc: "Excellence, respect, esprit d'équipe, foi et discipline." },
  { title: "Ouverture sur le monde", desc: "Culture, patrimoine africain et horizons internationaux." },
];

export const VALUES = [
  { title: "Excellence", desc: "Donner à chaque enfant les moyens de viser haut et de réussir." },
  { title: "Respect", desc: "Respect de soi, des autres et de son environnement, au quotidien." },
  { title: "Esprit d'équipe", desc: "Apprendre ensemble, s'entraider et grandir collectivement." },
];

/* Activités réellement illustrées par les médias fournis (aucune activité
   sans visuel réel — voir MEDIA_INVENTORY.md). */
export const ACTIVITIES = [
  { title: "Musique", desc: "Guitare, clavier, batterie et chant : l'orchestre de l'école répète chaque semaine.", img: "/site/img/activite-musique-groupe-1600.webp" },
  { title: "Percussions & culture", desc: "Djembé et rythmes traditionnels : la fierté de l'héritage africain.", img: "/site/img/activite-percussions-1600.webp" },
  { title: "Arts plastiques", desc: "Peinture, dessin et créativité pour développer l'imagination.", img: "/site/img/activite-arts-1600.webp" },
  { title: "Sport & football", desc: "Esprit d'équipe et dépassement de soi sur le terrain.", img: "/site/img/activite-football-1600.webp" },
  { title: "Expression orale", desc: "Prendre la parole en public avec confiance, en français et en anglais.", img: "/site/img/activite-expression-1600.webp" },
  { title: "Jeux éducatifs", desc: "Marelle, rondes et jeux de cour pour apprendre en s'amusant.", img: "/site/img/niveau-maternelle-cour-1600.webp" },
  { title: "Sciences", desc: "Expériences et découvertes pour éveiller la curiosité scientifique.", img: "/site/img/academique-sciences-1600.webp" },
  { title: "Numérique & robotique", desc: "Premiers pas avec l'ordinateur et la robotique éducative.", img: "/site/img/academique-numerique-1600.webp" },
];

export const ONLINE_FEATURES = [
  "Cours en ligne en petits groupes, adaptés au fuseau horaire des familles",
  "Apprentissage du français par des enseignants qualifiés",
  "Découverte de la culture et du patrimoine africains",
  "Un pont vivant entre les enfants de la diaspora et le Bénin",
];
