/**
 * Contenu éditorial de FEBA French Heritage Academy (FEBA FHA).
 *
 * SOURCE : documents de cadrage officiels fournis par la direction FEBA
 * (« FEBA French Heritage Academy — Guidance » et « Cahier de structure du
 * site »). Chaque élément ci-dessous provient de ces documents.
 *
 * RÈGLE ABSOLUE — AUCUNE DONNÉE INVENTÉE
 * Les informations que la direction n'a PAS encore validées ne figurent
 * pas ici : tarif annuel, date de rentrée, horaires définitifs, politique
 * de remboursement, noms des enseignants, prestataire de paiement. Elles
 * sont servies par l'API (/api/website/fha/program/) et restent nulles
 * tant qu'elles ne sont pas saisies par l'administration — le composant
 * masque alors le bloc plutôt que d'afficher une valeur fictive.
 *
 * Chaque entrée est bilingue { fr, en } : le programme s'adresse d'abord à
 * des familles anglophones.
 */

export const FHA_NAME = "FEBA French Heritage Academy";
export const FHA_SHORT = "FEBA FHA";
export const FHA_TAGLINE = "From English Speakers to Confident French Speakers";

export const FHA_INTRO = {
  fr:
    "FEBA French Heritage Academy est un programme d'apprentissage du français " +
    "entièrement en ligne, destiné principalement aux enfants de la diaspora " +
    "africaine vivant aux États-Unis, au Canada et dans d'autres pays " +
    "anglophones. Les cours sont dispensés depuis FEBA au Bénin par des " +
    "enseignants formés à l'enseignement du français aux enfants anglophones.",
  en:
    "FEBA French Heritage Academy is a fully online French learning programme " +
    "designed primarily for children of the African diaspora living in the " +
    "United States, Canada and other English-speaking countries. Classes are " +
    "taught from FEBA in Benin by teachers trained to teach French to " +
    "English-speaking children.",
};

/* Ce que le programme associe (document de cadrage, § 1). */
export const FHA_PILLARS = [
  { fr: "La conversation en français", en: "French conversation" },
  { fr: "La compréhension orale", en: "Listening comprehension" },
  { fr: "La lecture", en: "Reading" },
  { fr: "L'écriture", en: "Writing" },
  { fr: "La grammaire", en: "Grammar" },
  { fr: "La prise de parole", en: "Public speaking" },
  { fr: "La culture africaine", en: "African culture" },
  { fr: "La connaissance de ses origines", en: "Knowledge of one's roots" },
];

/* § 2 — Le problème constaté par les familles. */
export const FHA_PROBLEMS = [
  {
    fr: "Ils ne peuvent pas converser avec leurs grands-parents.",
    en: "They cannot hold a conversation with their grandparents.",
  },
  {
    fr: "Ils répondent en anglais lorsque leurs parents parlent français.",
    en: "They answer in English when their parents speak French.",
  },
  { fr: "Ils lisent difficilement le français.", en: "They struggle to read French." },
  { fr: "Ils ne savent pas écrire correctement.", en: "They cannot write correctly." },
  {
    fr: "Ils connaissent peu l'histoire et la culture de leur famille.",
    en: "They know little of their family's history and culture.",
  },
  {
    fr: "Ils risquent de perdre progressivement le lien avec leurs racines.",
    en: "They risk gradually losing the link with their roots.",
  },
];

/* § 3 — La solution proposée : un parcours scolaire structuré. */
export const FHA_SOLUTIONS = [
  { fr: "Comprendre le français", en: "Understand French" },
  { fr: "Parler avec confiance", en: "Speak with confidence" },
  { fr: "Lire correctement", en: "Read properly" },
  { fr: "Écrire en français", en: "Write in French" },
  { fr: "Communiquer avec leur famille", en: "Communicate with their family" },
  { fr: "Découvrir la culture africaine", en: "Discover African culture" },
  { fr: "Être fiers de leurs origines", en: "Be proud of their roots" },
  {
    fr: "Obtenir une certification FEBA après validation des compétences",
    en: "Earn a FEBA certification once skills are validated",
  },
];

/* § 4 et § 5 — Mission et vision. */
export const FHA_MISSION = {
  fr:
    "Aider les enfants de la diaspora africaine à parler, lire et écrire le " +
    "français avec confiance, tout en restant connectés à leur famille, à leur " +
    "culture et à leurs racines.",
  en:
    "Help children of the African diaspora speak, read and write French with " +
    "confidence, while staying connected to their family, their culture and " +
    "their roots.",
};

export const FHA_VISION = {
  fr:
    "Faire de FEBA French Heritage Academy une référence internationale dans " +
    "l'apprentissage du français et la transmission de l'héritage culturel " +
    "africain aux enfants de la diaspora.",
  en:
    "Make FEBA French Heritage Academy an international reference for French " +
    "learning and for passing on African cultural heritage to the children of " +
    "the diaspora.",
};

/* § 6 — Public cible. Le lancement cible en priorité les États-Unis. */
export const FHA_AUDIENCE = {
  countries: [
    { fr: "États-Unis (priorité au lancement)", en: "United States (launch priority)" },
    { fr: "Canada", en: "Canada" },
    { fr: "Royaume-Uni", en: "United Kingdom" },
    { fr: "Autres pays majoritairement anglophones", en: "Other mainly English-speaking countries" },
  ],
  communities: [
    "Bénin", "Togo", "Côte d'Ivoire", "Sénégal", "Cameroun", "Congo",
    "Guinée", "Mali", "Burkina Faso", "Niger", "Haïti",
  ],
};

/* § 7 — Les trois groupes retenus pour le lancement.
   Âges, tailles de groupe et durées de séance issus du document. */
export const FHA_GROUPS = [
  {
    key: "junior_roots",
    name: "Junior Roots",
    ages: "6 - 9",
    size: { fr: "10 à 12 enfants", en: "10 to 12 children" },
    duration: { fr: "45 à 60 minutes", en: "45 to 60 minutes" },
    methods: {
      fr: ["Jeux", "Images", "Chansons", "Répétitions", "Histoires", "Petites conversations", "Activités manuelles simples"],
      en: ["Games", "Pictures", "Songs", "Repetition", "Stories", "Short conversations", "Simple hands-on activities"],
    },
    goal: {
      fr: "Donner à l'enfant les premières bases du français et lui faire aimer la langue.",
      en: "Give the child their first foundations in French and a love for the language.",
    },
  },
  {
    key: "french_explorers",
    name: "French Explorers",
    ages: "10 - 15",
    size: { fr: "10 à 15 élèves", en: "10 to 15 students" },
    duration: { fr: "60 à 75 minutes", en: "60 to 75 minutes" },
    methods: {
      fr: ["Conversation", "Lecture", "Écriture", "Jeux de rôle", "Vocabulaire", "Grammaire", "Exposés simples", "Activités culturelles"],
      en: ["Conversation", "Reading", "Writing", "Role play", "Vocabulary", "Grammar", "Short presentations", "Cultural activities"],
    },
    goal: {
      fr: "Permettre à l'enfant de parler, lire et écrire progressivement avec plus de confiance.",
      en: "Enable the child to speak, read and write with growing confidence.",
    },
  },
  {
    key: "french_ambassadors",
    name: "French Ambassadors",
    ages: "16 - 17",
    size: { fr: "10 à 15 élèves", en: "10 to 15 students" },
    duration: { fr: "75 à 90 minutes", en: "75 to 90 minutes" },
    methods: {
      fr: ["Conversation approfondie", "Débats", "Exposés", "Rédaction", "Prise de parole", "Culture", "Identité", "Leadership"],
      en: ["In-depth conversation", "Debates", "Presentations", "Essay writing", "Public speaking", "Culture", "Identity", "Leadership"],
    },
    goal: {
      fr: "Donner aux adolescents un français utile pour leur vie personnelle, leurs études, leurs voyages et leur avenir professionnel.",
      en: "Give teenagers French they can use in their personal life, studies, travel and future career.",
    },
    note: {
      fr:
        "Les adolescents de 16 à 17 ans ne pourront pas nécessairement suivre " +
        "un parcours complet de cinq années : un parcours intensif d'un à deux " +
        "ans est prévu selon leur niveau de départ.",
      en:
        "Teenagers aged 16 to 17 may not be able to follow the full five-year " +
        "path: an intensive one- to two-year track is planned depending on " +
        "their starting level.",
    },
  },
];

/* § 8 — Organisation de l'année scolaire.
   La DATE de rentrée n'est pas encore validée : elle vient de l'API. */
export const FHA_YEAR_ORGANISATION = {
  period: { fr: "De septembre à juin", en: "September to June" },
  weeks: { fr: "Environ 34 semaines d'enseignement", en: "About 34 teaching weeks" },
  frequency: { fr: "Deux séances en direct par semaine", en: "Two live sessions per week" },
  extras: [
    { fr: "Un atelier culturel par mois", en: "One cultural workshop per month" },
    { fr: "Un club de conversation", en: "A conversation club" },
    { fr: "Des projets de groupe", en: "Group projects" },
    { fr: "Des évaluations périodiques", en: "Periodic assessments" },
    { fr: "Une cérémonie virtuelle de fin d'année", en: "A virtual end-of-year ceremony" },
  ],
  volume: [
    { fr: "Environ 68 cours réguliers", en: "About 68 regular lessons" },
    { fr: "8 à 10 ateliers culturels", en: "8 to 10 cultural workshops" },
    { fr: "3 évaluations principales", en: "3 main assessments" },
    { fr: "Un projet de fin d'année", en: "One end-of-year project" },
  ],
};

/* § 9 — Le programme de français sur cinq ans. */
export const FHA_PROGRAMME = [
  {
    year: 1,
    title: { fr: "Les fondations", en: "Foundations" },
    objectives: {
      fr: ["Découvrir le français", "Comprendre les consignes simples", "Apprendre les sons", "Mémoriser le vocabulaire de base", "Commencer à parler"],
      en: ["Discover French", "Understand simple instructions", "Learn the sounds", "Memorise basic vocabulary", "Start speaking"],
    },
    outcome: {
      fr: "L'élève peut se présenter, répondre à des questions simples et lire des mots et de courtes phrases.",
      en: "The student can introduce themselves, answer simple questions and read words and short sentences.",
    },
    validation: { fr: "Attestation annuelle de progression", en: "Annual progress certificate" },
  },
  {
    year: 2,
    title: { fr: "La communication quotidienne", en: "Everyday communication" },
    objectives: {
      fr: ["Parler de sa vie quotidienne", "Poser des questions", "Mieux comprendre le français oral", "Commencer à écrire de petits textes"],
      en: ["Talk about daily life", "Ask questions", "Better understand spoken French", "Start writing short texts"],
    },
    outcome: {
      fr: "L'élève peut raconter sa journée, participer à une conversation simple, lire une petite histoire et écrire un court paragraphe.",
      en: "The student can recount their day, take part in a simple conversation, read a short story and write a short paragraph.",
    },
    validation: { fr: "Attestation annuelle de progression", en: "Annual progress certificate" },
  },
  {
    year: 3,
    title: { fr: "L'autonomie en français", en: "Independence in French" },
    objectives: {
      fr: ["Converser plus naturellement", "Mieux lire", "Raconter une expérience", "Présenter un sujet", "Structurer un texte"],
      en: ["Converse more naturally", "Read better", "Recount an experience", "Present a topic", "Structure a text"],
    },
    outcome: {
      fr: "L'élève peut converser avec sa famille, comprendre des conversations courantes, lire avec plus d'autonomie et écrire un texte organisé.",
      en: "The student can converse with their family, understand everyday conversations, read more independently and write an organised text.",
    },
    validation: {
      fr: "Premier Certificat FEBA de compétence en langue française — délivré uniquement après validation des compétences",
      en: "First FEBA Certificate of French language competence — awarded only once skills are validated",
    },
  },
  {
    year: 4,
    title: { fr: "Le français avancé", en: "Advanced French" },
    objectives: {
      fr: ["Améliorer la fluidité", "Développer l'argumentation", "Lire des textes plus complexes", "Écrire de manière structurée"],
      en: ["Improve fluency", "Develop argumentation", "Read more complex texts", "Write in a structured way"],
    },
    outcome: {
      fr: "L'élève peut exprimer son opinion, défendre une idée, présenter un sujet et rédiger différents types de textes.",
      en: "The student can express an opinion, defend an idea, present a topic and write different kinds of texts.",
    },
    validation: { fr: "Certificat FEBA de français avancé", en: "FEBA Advanced French Certificate" },
  },
  {
    year: 5,
    title: { fr: "Maîtrise, identité et leadership", en: "Mastery, identity and leadership" },
    objectives: {
      fr: ["Communiquer avec assurance", "Utiliser le français dans plusieurs situations", "Développer le leadership", "Présenter un projet complet"],
      en: ["Communicate confidently", "Use French in a range of situations", "Develop leadership", "Present a complete project"],
    },
    outcome: {
      fr: "L'élève peut parler avec aisance, lire et écrire avec confiance, participer à une discussion organisée et évoluer dans un environnement francophone.",
      en: "The student can speak fluently, read and write confidently, take part in a structured discussion and thrive in a French-speaking environment.",
    },
    validation: {
      fr: "Diplôme ou certificat final FEBA French Heritage Academy",
      en: "Final FEBA French Heritage Academy diploma or certificate",
    },
  },
];

/* § 10 — Le programme de culture africaine (African Heritage). */
export const FHA_HERITAGE = [
  {
    year: 1,
    title: { fr: "Mes origines", en: "My roots" },
    items: {
      fr: ["Découverte de l'Afrique", "Découverte du Bénin", "Pays d'origine de la famille", "Drapeaux", "Cartes", "Langues", "Symboles", "Famille et communauté"],
      en: ["Discovering Africa", "Discovering Benin", "The family's country of origin", "Flags", "Maps", "Languages", "Symbols", "Family and community"],
    },
  },
  {
    year: 2,
    title: { fr: "Nos traditions", en: "Our traditions" },
    items: {
      fr: ["Vêtements", "Cuisine", "Fêtes", "Musique", "Danses", "Contes", "Proverbes", "Valeurs familiales"],
      en: ["Clothing", "Food", "Celebrations", "Music", "Dance", "Folk tales", "Proverbs", "Family values"],
    },
  },
  {
    year: 3,
    title: { fr: "Histoire et personnalités", en: "History and figures" },
    items: {
      fr: ["Royaumes africains", "Rois et reines", "Héros du Bénin", "Personnalités africaines", "Contribution de la diaspora", "Grandes figures inspirantes"],
      en: ["African kingdoms", "Kings and queens", "Heroes of Benin", "African figures", "The diaspora's contribution", "Inspiring role models"],
    },
  },
  {
    year: 4,
    title: { fr: "L'Afrique d'aujourd'hui", en: "Africa today" },
    items: {
      fr: ["Grandes villes", "Entrepreneurs", "Artistes", "Scientifiques", "Sportifs", "Innovations", "Développement du continent"],
      en: ["Major cities", "Entrepreneurs", "Artists", "Scientists", "Athletes", "Innovation", "The continent's development"],
    },
  },
  {
    year: 5,
    title: { fr: "Identité et leadership", en: "Identity and leadership" },
    items: {
      fr: ["Fierté de ses origines", "Leadership", "Responsabilité", "Solidarité", "Contribution à la communauté", "Projets pour l'Afrique", "Rôle de la diaspora"],
      en: ["Pride in one's roots", "Leadership", "Responsibility", "Solidarity", "Contributing to the community", "Projects for Africa", "The diaspora's role"],
    },
  },
];

/* § 11 — Activités culturelles possibles. */
export const FHA_CULTURAL_ACTIVITIES = [
  "African Story Time",
  { fr: "Journée des tenues africaines", en: "African outfit day" },
  { fr: "Présentation du pays d'origine", en: "Home country presentation" },
  { fr: "Concours de proverbes", en: "Proverb contest" },
  { fr: "Chansons francophones", en: "French-language songs" },
  { fr: "Cuisine virtuelle avec les familles", en: "Virtual cooking with families" },
  { fr: "Rencontres avec des invités au Bénin", en: "Meetings with guests in Benin" },
  { fr: "Visites virtuelles", en: "Virtual tours" },
  { fr: "Club de lecture", en: "Book club" },
  { fr: "Concours d'éloquence", en: "Public speaking contest" },
  "French Game Night",
  "French Spelling Bee",
  { fr: "Projet « My African Heritage »", en: "“My African Heritage” project" },
  { fr: "Cérémonie culturelle annuelle", en: "Annual cultural ceremony" },
];

/* § 13 — Test de placement (15 à 20 minutes). */
export const FHA_PLACEMENT = {
  duration: { fr: "15 à 20 minutes", en: "15 to 20 minutes" },
  skills: [
    { fr: "Compréhension orale", en: "Listening comprehension" },
    { fr: "Expression orale", en: "Speaking" },
    { fr: "Vocabulaire", en: "Vocabulary" },
    { fr: "Lecture", en: "Reading" },
    { fr: "Écriture", en: "Writing" },
    { fr: "Confiance et participation", en: "Confidence and participation" },
  ],
  levels: [
    { fr: "Débutant", en: "Beginner" },
    { fr: "Intermédiaire", en: "Intermediate" },
    { fr: "Avancé", en: "Advanced" },
  ],
  result: [
    { fr: "Groupe recommandé", en: "Recommended group" },
    { fr: "Niveau de départ", en: "Starting level" },
    { fr: "Jours et horaires proposés", en: "Proposed days and times" },
    { fr: "Objectifs prioritaires", en: "Priority objectives" },
    { fr: "Tarif et modalités", en: "Fee and payment terms" },
    { fr: "Date limite pour confirmer la place", en: "Deadline to confirm the place" },
    { fr: "Lien vers contrat et paiement", en: "Link to the contract and payment" },
  ],
};

/* § 22 / cahier de structure § 3 — Parcours d'inscription en 8 étapes. */
export const FHA_ENROLLMENT_STEPS = [
  { fr: "Découverte", en: "Discovery" },
  { fr: "Fiche de renseignements", en: "Enrollment form" },
  { fr: "Test de placement", en: "Placement assessment" },
  { fr: "Proposition d'admission", en: "Admission offer" },
  { fr: "Contrat et autorisations", en: "Contract and authorisations" },
  { fr: "Paiement", en: "Payment" },
  { fr: "Création des accès", en: "Account creation" },
  { fr: "Orientation", en: "Orientation" },
];

/* § 14 — Conditions de certification. */
export const FHA_CERTIFICATION_CONDITIONS = [
  { fr: "Avoir une présence minimale, par exemple 80 %", en: "Meet a minimum attendance, for example 80%" },
  { fr: "Participer régulièrement", en: "Take part regularly" },
  { fr: "Réaliser les activités", en: "Complete the activities" },
  { fr: "Valider les évaluations", en: "Pass the assessments" },
  { fr: "Réussir l'évaluation orale", en: "Pass the oral assessment" },
  { fr: "Montrer une progression en lecture et en écriture", en: "Show progress in reading and writing" },
  { fr: "Présenter le projet final", en: "Present the final project" },
];

/* MENTION OBLIGATOIRE — § 9, année 5 du document de cadrage.
   Doit rester visible partout où une certification est évoquée. */
export const FHA_CERTIFICATION_NOTICE = {
  fr:
    "Les attestations, certificats et diplômes FEBA French Heritage Academy " +
    "sont des certifications INTERNES délivrées par FEBA. Ils ne constituent " +
    "pas une accréditation officielle, sauf si une accréditation vérifiable " +
    "est ajoutée ultérieurement.",
  en:
    "FEBA French Heritage Academy attestations, certificates and diplomas are " +
    "INTERNAL certifications issued by FEBA. They do not constitute official " +
    "accreditation, unless a verifiable accreditation is added at a later stage.",
};

/* Questions fréquentes — réponses strictement limitées à ce que les
   documents de cadrage établissent. Aucune question portant sur le tarif ou
   la date de rentrée n'a de réponse ici : ces informations viennent de
   l'API une fois validées par la direction. */
export const FHA_FAQ = [
  {
    q: { fr: "Sur quelle plateforme se déroulent les cours ?", en: "Which platform is used for the classes?" },
    a: {
      fr: "Les cours en direct se déroulent en visioconférence, avec salle d'attente, mot de passe et accès supervisé. Le lien n'est jamais public : il apparaît uniquement dans l'espace connecté de la famille.",
      en: "Live classes take place by video conference, with a waiting room, a password and supervised access. The link is never public: it appears only in the family's signed-in area.",
    },
  },
  {
    q: { fr: "Mon enfant ne parle pas du tout français. Est-ce un problème ?", en: "My child does not speak French at all. Is that a problem?" },
    a: {
      fr: "Non. Le programme est conçu pour des enfants anglophones, y compris débutants complets. Le test de placement détermine le groupe et le niveau de départ.",
      en: "No. The programme is designed for English-speaking children, including complete beginners. The placement assessment determines the group and starting level.",
    },
  },
  {
    q: { fr: "Combien de séances par semaine ?", en: "How many sessions per week?" },
    a: {
      fr: "Deux séances en direct par semaine, sur une année scolaire de septembre à juin (environ 34 semaines), complétées par un atelier culturel mensuel.",
      en: "Two live sessions per week, over a school year running September to June (about 34 weeks), plus a monthly cultural workshop.",
    },
  },
  {
    q: { fr: "Comment les fuseaux horaires sont-ils gérés ?", en: "How are time zones handled?" },
    a: {
      fr: "Les horaires sont affichés automatiquement dans le fuseau horaire de votre famille. L'administration conserve une heure de référence.",
      en: "Times are displayed automatically in your family's time zone. The administration keeps a reference time.",
    },
  },
  {
    q: { fr: "Les certificats sont-ils officiels ?", en: "Are the certificates official?" },
    a: FHA_CERTIFICATION_NOTICE,
  },
  {
    q: { fr: "Combien d'enfants par groupe ?", en: "How many children per group?" },
    a: {
      fr: "Junior Roots : 10 à 12 enfants. French Explorers et French Ambassadors : 10 à 15 élèves. La capacité totale conseillée pour la première cohorte est de 30 à 40 élèves.",
      en: "Junior Roots: 10 to 12 children. French Explorers and French Ambassadors: 10 to 15 students. The recommended total capacity for the first cohort is 30 to 40 students.",
    },
  },
];

/* Sélecteur de langue : renvoie la variante demandée d'une entrée { fr, en }.
   Accepte aussi les chaînes simples (identiques dans les deux langues). */
export function tr(entry, lang) {
  if (entry == null) return "";
  if (typeof entry === "string") return entry;
  return entry[lang] || entry.fr || entry.en || "";
}
