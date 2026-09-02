/**
 * Formules annuelles FEBA French Heritage Academy.
 *
 * SOURCE UNIQUE — utilisée par la page publique /feba-fha (présentation des
 * offres), par la fiche de renseignements (choix de la famille) et par le
 * récapitulatif. Dupliquer ces tarifs dans chaque écran finirait par les
 * faire diverger : c'est le genre d'écart qu'une famille lit comme une
 * erreur de facturation.
 *
 * Les codes correspondent exactement à
 * `FHAEnrollmentApplication.PLAN_CHOICES` côté backend.
 */

export const PLAN_CODES = ["STANDARD", "PREMIUM", "EXCELLENCE", "UNDECIDED"];

export const FHA_PLANS = [
  {
    code: "STANDARD",
    name: { fr: "Standard", en: "Standard" },
    priceUSD: 699,
    price: { fr: "699 $ / an", en: "$699 / year" },
    rhythm: {
      fr: ["2 cours par semaine", "1 h 15 par cours", "≈ 8 cours par mois", "≈ 72 cours par année scolaire"],
      en: ["2 classes per week", "1 hr 15 per class", "≈ 8 classes per month", "≈ 72 classes per school year"],
    },
    includes: {
      fr: [
        "Cours en direct sur Zoom",
        "Expression orale",
        "Compréhension orale",
        "Lecture",
        "Écriture",
        "Vocabulaire",
        "Grammaire",
        "Prononciation",
        "Héritage africain",
        "Exercices",
        "Devoirs",
        "Évaluations",
        "Bulletin trimestriel",
        "Certificat annuel",
      ],
      en: [
        "Live classes on Zoom",
        "Speaking",
        "Listening",
        "Reading",
        "Writing",
        "Vocabulary",
        "Grammar",
        "Pronunciation",
        "African heritage",
        "Exercises",
        "Homework",
        "Assessments",
        "Termly report card",
        "Annual certificate",
      ],
    },
  },
  {
    code: "PREMIUM",
    name: { fr: "Premium", en: "Premium" },
    priceUSD: 999,
    price: { fr: "999 $ / an", en: "$999 / year" },
    rhythm: {
      fr: ["3 cours par semaine", "1 h 15 par cours", "≈ 12 cours par mois", "≈ 108 cours par année scolaire"],
      en: ["3 classes per week", "1 hr 15 per class", "≈ 12 classes per month", "≈ 108 classes per school year"],
    },
    includes: {
      fr: [
        "Tout le contenu Standard",
        "Une séance supplémentaire chaque semaine",
        "Conversation renforcée",
        "Davantage de lecture",
        "Davantage d'écriture",
        "Exercices supplémentaires",
        "Suivi régulier",
        "Grammaire renforcée",
        "Prononciation renforcée",
        "Projets culturels",
        "Évaluations",
        "Bulletin trimestriel",
        "Certificat annuel",
      ],
      en: [
        "Everything in Standard",
        "One extra session each week",
        "Enhanced conversation practice",
        "More reading",
        "More writing",
        "Additional exercises",
        "Regular progress follow-up",
        "Enhanced grammar",
        "Enhanced pronunciation",
        "Cultural projects",
        "Assessments",
        "Termly report card",
        "Annual certificate",
      ],
    },
  },
  {
    code: "EXCELLENCE",
    name: { fr: "Excellence", en: "Excellence" },
    priceUSD: 1299,
    price: { fr: "1 299 $ / an", en: "$1,299 / year" },
    rhythm: {
      fr: ["3 cours par semaine", "1 h 15 par cours", "≈ 108 cours par année scolaire", "Club de conversation"],
      en: ["3 classes per week", "1 hr 15 per class", "≈ 108 classes per school year", "Conversation club"],
    },
    includes: {
      fr: [
        "Tout le contenu Premium",
        "Club de conversation",
        "Pratique orale renforcée",
        "Prise de parole",
        "Discussions guidées",
        "Jeux de rôle",
        "Présentations",
        "Lecture à voix haute",
        "Correction de prononciation",
        "Travail sur la confiance en soi",
        "Activités culturelles approfondies",
        "Suivi renforcé",
        "Bulletin trimestriel",
        "Certificat annuel",
      ],
      en: [
        "Everything in Premium",
        "Conversation club",
        "Intensive speaking practice",
        "Public speaking",
        "Guided discussions",
        "Role plays",
        "Presentations",
        "Reading aloud",
        "Pronunciation coaching",
        "Confidence building",
        "In-depth cultural activities",
        "Enhanced follow-up",
        "Termly report card",
        "Annual certificate",
      ],
    },
  },
];

/** Options du champ « Formule souhaitée », option indécise comprise. */
export const PLAN_OPTIONS = [
  ...FHA_PLANS.map((p) => ({
    code: p.code,
    label: { fr: `${p.name.fr} — ${p.price.fr}`, en: `${p.name.en} — ${p.price.en}` },
  })),
  {
    code: "UNDECIDED",
    label: {
      fr: "Je ne sais pas encore — j'en discuterai avec l'équipe",
      en: "Not decided yet — I'd like to discuss it with the team",
    },
  },
];

/** Libellé lisible d'un code de formule, pour le récapitulatif. */
export function planLabel(code, lang = "fr") {
  const option = PLAN_OPTIONS.find((o) => o.code === code);
  if (!option) return lang === "fr" ? "Non renseignée" : "Not provided";
  return option.label[lang === "fr" ? "fr" : "en"];
}

/**
 * Visuel du flyer, servi tel quel depuis `public/` — APERÇU à l'écran.
 *
 * C'est le fichier d'origine, non recompressé : la vignette et la vue
 * « en grand » montrent exactement ce que l'établissement a fourni.
 */
export const FHA_FLYER_PATH = "/images/feba-fha/feba-fha-flyer.jpeg";

/**
 * Flyer officiel en PDF — cible de tous les TÉLÉCHARGEMENTS.
 *
 * Pourquoi un PDF plutôt que le JPEG d'aperçu : l'attribut `download` d'un
 * lien vers une image est diversement honoré par les navigateurs mobiles
 * (Safari iOS ouvre l'image dans l'onglet au lieu de l'enregistrer). Un PDF
 * est traité partout comme un document à enregistrer, et s'imprime à
 * l'échelle — ce qu'une famille fait d'un flyer de tarifs.
 *
 * Le fichier est produit par `scripts/build_fha_flyer_pdf.py` à partir du
 * MÊME visuel, sans retouche du contenu, et versionné dans le dépôt : le
 * téléchargement fonctionne dès l'installation, sans commande à lancer.
 */
export const FHA_FLYER_PDF_PATH = "/images/feba-fha/feba-fha-flyer.pdf";

/** Nom du fichier tel qu'il arrive dans le dossier « Téléchargements ». */
export const FHA_FLYER_DOWNLOAD_NAME = "FEBA-French-Heritage-Academy-flyer.pdf";
