/**
 * Centre d'aide : visibilité par profil et moteur de recherche local.
 *
 * Visibilité
 *   - super administrateur : TOUTE la documentation, quelle que soit l'académie ;
 *   - autres profils : les articles de leur rôle, et seulement pour les modules
 *     activés dans leur académie (`peutVoir`, appelé avec `moduleActif`).
 *
 * Recherche (sans service externe)
 *   - index pondéré par champ : titre > mots-clés, module > catégorie > objet >
 *     étapes > reste ; texte de la langue de l'interface, plus celui de l'autre
 *     langue avec un poids réduit (« password » trouve l'article en français) ;
 *   - correspondances exactes, par préfixe (« mess »), par racine (« payer » /
 *     « paiements »), avec faute de frappe (distance d'édition 1 ou 2), et par
 *     synonymes français/anglais (« visio » → salles virtuelles) ;
 *   - tous les mots significatifs doivent être trouvés (mots vides ignorés) ;
 *   - classement par score ; un article très en dessous du meilleur est écarté
 *     (un mot présent seulement dans un détail ne suffit pas à le remonter) ;
 *   - suggestions de mots proches quand rien n'est trouvé.
 */
import { ARTICLES, CATEGORIES, DEPANNAGE, FAQ, GLOSSAIRE, RACINES } from "./articles";

const IDX = { fr: 0, en: 1 };

/** Texte d'une paire [fr, en] dans la langue demandée. */
export const L = (paire, lang) => (Array.isArray(paire) ? paire[IDX[lang] ?? 0] ?? paire[0] : paire ?? "");

/** Minuscules sans accents, pour une recherche tolérante. */
export const normaliser = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

const MOTS_VIDES = new Set(("le la les l de du des d un une et ou a au aux en dans sur pour par avec mon ma mes ton ta tes son sa ses " +
  "ce cet cette ces qui que quoi comment ou est je j me m il elle on nous vous ils y ne pas plus faire " +
  "the a an and or of to in on for by with my your how do does i is are can what where when it this that").split(" "));

/** Racine légère FR/EN : « paiements » → « paiement », « payer » → « pay », « classes » → « class ». */
export function racine(mot) {
  let m = normaliser(mot);
  if (m.length <= 3) return m;
  for (const fin of ["ements", "ement", "ations", "ation", "euses", "euse", "eurs", "eur", "ings", "ing",
    "ions", "ion", "ees", "ee", "er", "ed", "es", "s", "x", "e"]) {
    // Un suffixe long exige une racine d'au moins 4 lettres : « paiements » reste « paiement », pas « pai ».
    if (m.length - fin.length >= (fin.length >= 3 ? 4 : 3) && m.endsWith(fin)) { m = m.slice(0, -fin.length); break; }
  }
  return m;
}

export function mots(texte) {
  return normaliser(texte).split(/[^a-z0-9]+/).filter((m) => m && !MOTS_VIDES.has(m));
}

/**
 * Groupes de synonymes (français et anglais). Un mot saisi appartenant à un
 * groupe cherche aussi tous les autres mots du groupe. Les expressions de
 * plusieurs mots sont reconnues telles quelles (« emploi du temps »).
 */
const SYNONYMES = [
  ["message", "messagerie", "messages", "conversation", "ecrire", "repondre", "messaging", "reply", "chat", "inbox"],
  ["paiement", "payer", "paye", "payment", "pay", "frais", "fees", "recu", "receipt", "facture", "invoice", "encaissement", "mensualite", "scolarite", "tuition", "versement"],
  ["remboursement", "rembourser", "refund"],
  ["relance", "rappel", "retard", "impaye", "reminder", "overdue"],
  ["bulletin", "bulletins", "report card", "releve de notes", "carnet"],
  ["absence", "absences", "presence", "retard", "appel", "attendance", "absent", "excuse"],
  ["note", "notes", "grade", "grades", "moyenne", "average", "mark", "marks"],
  ["appreciation", "mention", "remark"],
  ["classe", "classes", "class", "salle de classe"],
  ["niveau", "level", "cycle"],
  ["eleve", "eleves", "student", "students", "pupil", "enfant", "child", "children", "apprenant"],
  ["enseignant", "enseignants", "professeur", "prof", "teacher", "teachers", "maitre", "formateur"],
  ["parent", "parents", "famille", "family", "tuteur", "guardian", "responsable"],
  ["emploi du temps", "horaire", "horaires", "planning", "timetable", "schedule", "creneau", "seance", "agenda", "calendrier"],
  ["visioconference", "visio", "salle virtuelle", "salles virtuelles", "cours en ligne", "video", "plugnmeet", "virtual room", "online class", "reunion", "meeting", "zoom", "camera", "micro"],
  ["mot de passe", "mdp", "password", "passe", "identifiant", "connexion", "login", "sign in", "se connecter", "credentials"],
  ["utilisateur", "compte", "user", "account", "profil", "profile"],
  ["superadmin", "super administrateur", "super admin", "super administrator"],
  ["administrateur", "admin", "administrator"],
  ["devoir", "devoirs", "homework", "exercice", "travail a faire", "assignment"],
  ["annonce", "annonces", "announcement", "information", "communique", "actualite", "news"],
  ["examen", "epreuve", "quiz", "exam", "test", "evaluation", "controle", "interrogation", "copie"],
  ["banque de questions", "question", "questions", "question bank"],
  ["inscription", "reinscription", "admission", "enrolment", "enrollment", "registration", "preinscription", "passage"],
  ["document", "documents", "certificat", "diplome", "attestation", "certificate", "diploma", "gabarit", "template"],
  ["fichier", "fichiers", "file", "files", "piece jointe", "attachment", "televerser", "upload", "telecharger", "download"],
  ["export", "exporter", "excel", "csv", "tableur"],
  ["logo", "branding", "identite visuelle", "image"],
  ["academie", "ecole", "etablissement", "academy", "school"],
  ["parametre", "parametres", "configuration", "reglage", "settings", "annee scolaire", "matiere", "subject"],
  ["competence", "competences", "referentiel", "skill", "skills", "framework", "suivi", "progression", "objectif", "goal"],
  ["rapport", "rapports", "report", "reports", "rapport mensuel", "monthly report"],
  ["incident", "erreur", "bug", "panne", "error", "probleme", "anomalie"],
  ["notification", "notifications", "cloche", "alerte", "alert", "bell"],
  ["email", "mail", "courriel", "e-mail", "emails groupes", "boite d'envoi", "outbox"],
  ["site", "site vitrine", "website", "public", "contact"],
  ["langue", "anglais", "francais", "language", "english", "french", "traduction"],
  ["supprimer", "suppression", "effacer", "delete", "remove", "restaurer", "restore", "annuler", "cancel"],
  ["creer", "ajouter", "nouveau", "nouvelle", "create", "add", "new"],
  ["modifier", "changer", "editer", "mettre a jour", "edit", "update", "change"],
  ["rechercher", "chercher", "trouver", "filtrer", "trier", "search", "find", "filter", "sort"],
];
const GROUPE = new Map();
const EXPRESSIONS = [];
SYNONYMES.forEach((groupe, i) => groupe.forEach((terme) => {
  const n = normaliser(terme);
  if (n.includes(" ")) EXPRESSIONS.push([n, i]);
  for (const r of [n, racine(n)]) {
    if (!GROUPE.has(r)) GROUPE.set(r, new Set());
    GROUPE.get(r).add(i);
  }
}));
EXPRESSIONS.sort((a, b) => b[0].length - a[0].length);
// Seuls les synonymes d'un mot servent par racine ; les expressions se cherchent entières
// (« cours en ligne » ne doit pas faire correspondre tout texte contenant « cours »).
const racinesDuGroupe = SYNONYMES.map((g) => new Set(g.filter((t) => !t.includes(" ")).map((t) => racine(t))));

/** Distance d'édition bornée (au-delà de `max`, renvoie max + 1). */
export function distance(a, b, max = 2) {
  if (Math.abs(a.length - b.length) > max) return max + 1;
  let prec = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const cour = [i];
    let minLigne = i;
    for (let j = 1; j <= b.length; j++) {
      cour[j] = Math.min(prec[j] + 1, cour[j - 1] + 1, prec[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      minLigne = Math.min(minLigne, cour[j]);
    }
    if (minLigne > max) return max + 1;
    prec = cour;
  }
  return prec[b.length];
}
const tolerance = (n) => (n >= 7 ? 2 : n >= 4 ? 1 : 0);

const POIDS = { titre: 10, motsCles: 6, module: 6, categorie: 4, objet: 3, etapes: 2, reste: 1 };
const AUTRE_LANGUE = 0.5;

function champs(a, lang) {
  const cat = CATEGORIES.find((c) => c.id === a.categorie);
  return {
    titre: L(a.titre, lang), motsCles: a.motsCles || "", module: L(a.module, lang), categorie: cat ? L(cat.titre, lang) : "",
    objet: L(a.objet, lang), etapes: a.etapes.map((e) => L(e, lang)).join(" "),
    reste: [a.resultat, a.consequences, a.permissions, ...a.prerequis, ...a.champs, ...a.erreurs.flat()]
      .map((x) => L(x, lang)).join(" "),
  };
}

const cacheIndex = new Map();
/** Index d'un article : pour chaque champ, ses mots normalisés et leurs racines. */
function indexer(cle, lang, fabriquer) {
  const k = `${lang}:${cle}`;
  if (!cacheIndex.has(k)) {
    const champsTexte = fabriquer();
    const index = {};
    for (const [nom, texte] of Object.entries(champsTexte)) {
      const ms = mots(texte);
      index[nom] = { mots: new Set(ms), racines: new Set(ms.map(racine)), texte: ` ${normaliser(texte).replace(/[^a-z0-9]+/g, " ")} ` };
    }
    cacheIndex.set(k, index);
  }
  return cacheIndex.get(k);
}

/** Termes de la requête : expressions synonymes reconnues, puis mots isolés. */
export function analyser(requete) {
  let reste = ` ${normaliser(requete).replace(/[^a-z0-9]+/g, " ")} `;
  const termes = [];
  for (const [expr, groupe] of EXPRESSIONS) {
    if (reste.includes(` ${expr} `)) {
      termes.push({ brut: expr, racine: expr, groupes: new Set([groupe]), expression: true });
      reste = reste.replace(` ${expr} `, " ");
    }
  }
  const vocab = vocabulaire();
  for (const m of mots(reste)) {
    const r = racine(m);
    const groupes = new Set([...(GROUPE.get(m) || []), ...(GROUPE.get(r) || [])]);
    // Faute de frappe probable : mot inconnu de l'aide, sans synonyme, préfixe d'aucun mot.
    const flou = !groupes.size && !vocab.mots.has(m) && !vocab.racines.has(r)
      && !(m.length >= 3 && vocab.liste.some((v) => v.startsWith(m)));
    // Correction : les mots de l'aide les plus proches (distance minimale, dans la tolérance).
    let corrections = null;
    if (flou) {
      const tol = tolerance(m.length);
      let meilleure = tol + 1;
      corrections = new Set();
      for (const v of vocab.liste) {
        if (Math.abs(v.length - m.length) > tol) continue;
        const d = distance(v, m, tol);
        if (d < meilleure) { meilleure = d; corrections = new Set([v]); } else if (d === meilleure) corrections.add(v);
      }
      if (meilleure > tol) corrections = new Set();
    }
    termes.push({ brut: m, racine: r, groupes, flou, corrections });
  }
  return termes;
}

let vocab_;
/** Tous les mots de l'aide (deux langues), pour distinguer une faute de frappe d'un mot réel. */
function vocabulaire() {
  if (!vocab_) {
    const tous = new Set();
    for (const lang of ["fr", "en"]) {
      for (const a of ARTICLES) for (const t of Object.values(champs(a, lang))) for (const m of mots(t)) tous.add(m);
    }
    vocab_ = { mots: tous, racines: new Set([...tous].map(racine)), liste: [...tous] };
  }
  return vocab_;
}

/** Meilleure correspondance d'un terme dans un champ : facteur de 0 à 1. */
function facteur(terme, champ) {
  if (terme.expression) {
    if (champ.texte.includes(` ${terme.brut} `)) return 1;
  } else {
    if (champ.mots.has(terme.brut) || champ.racines.has(terme.racine)) return 1;
    if (terme.brut.length >= 3) {
      for (const m of champ.mots) if (m.startsWith(terme.brut)) return 0.8;
    }
  }
  for (const g of terme.groupes) {
    for (const r of racinesDuGroupe[g]) if (champ.racines.has(r)) return 0.7;
    for (const s of SYNONYMES[g]) if (s.includes(" ") && champ.texte.includes(` ${normaliser(s)} `)) return 0.7;
  }
  if (terme.corrections) {
    for (const c of terme.corrections) if (champ.mots.has(c) || champ.racines.has(racine(c))) return 0.6;
  }
  return 0;
}

/**
 * Score d'un document : pour chaque terme, la meilleure correspondance pondérée
 * plus un tiers des autres champs où il figure (un terme présent dans le titre,
 * le module ET les mots-clés pèse plus qu'un terme du seul titre) ; 0 si un
 * terme manque.
 */
function score(termes, indexes) {
  let total = 0;
  const trouves = new Set();
  for (const terme of termes) {
    const parChamp = {};
    for (const [index, coef] of indexes) {
      for (const [nom, champ] of Object.entries(index)) {
        const f = facteur(terme, champ);
        if (f) {
          parChamp[nom] = Math.max(parChamp[nom] || 0, f * (POIDS[nom] || 1) * coef);
          if (coef === 1 && f >= 0.8) trouves.add(terme.brut);
        }
      }
    }
    const valeurs = Object.values(parChamp).sort((a, b) => b - a);
    if (!valeurs.length) return { score: 0, trouves };
    total += valeurs[0] + valeurs.slice(1).reduce((a, b) => a + b, 0) / 3;
  }
  return { score: total, trouves };
}

const autre = (lang) => (lang === "en" ? "fr" : "en");
const SEUIL_RELATIF = 0.3;

/** Classe des documents ; garde ceux dont le score atteint 30 % du meilleur. */
function classer(liste, requete, lang, champsDe, cle) {
  const termes = analyser(requete);
  if (!termes.length) return liste.map((x) => ({ x, score: 0, trouves: new Set() }));
  const notes = liste.map((x) => {
    const indexes = [[indexer(cle(x), lang, () => champsDe(x, lang)), 1],
      [indexer(cle(x), autre(lang), () => champsDe(x, autre(lang))), AUTRE_LANGUE]];
    return { x, ...score(termes, indexes) };
  }).filter((n) => n.score > 0);
  const max = Math.max(0, ...notes.map((n) => n.score));
  return notes.filter((n) => n.score >= max * SEUIL_RELATIF).sort((a, b) => b.score - a.score);
}

/**
 * Un profil voit-il cet article ? Le super administrateur voit tout ; les autres
 * profils, les articles de leur rôle dont le module est activé pour leur académie.
 */
export function peutVoir(article, role, moduleActif = () => true) {
  if (role === "superadmin") return true;
  if (!article.roles.includes(role)) return false;
  return !article.feature || moduleActif(article);
}

/**
 * Articles visibles, filtrés par catégorie et classés par pertinence quand une
 * recherche est saisie. Renvoie des articles ; `avecDetails` renvoie aussi le
 * score et les termes trouvés (mise en évidence).
 */
export function articlesPour(role, { lang = "fr", requete = "", categorie = null, moduleActif, avecDetails = false } = {}) {
  const visibles = ARTICLES.filter((a) => peutVoir(a, role, moduleActif))
    .filter((a) => !categorie || a.categorie === categorie);
  const classes = requete.trim() ? classer(visibles, requete, lang, champs, (a) => `a:${a.id}`)
    : visibles.map((x) => ({ x, score: 0, trouves: new Set() }));
  return avecDetails ? classes.map(({ x, score: s, trouves }) => ({ article: x, score: s, trouves })) : classes.map((c) => c.x);
}

export function categoriesPour(role, moduleActif) {
  const presentes = new Set(ARTICLES.filter((a) => peutVoir(a, role, moduleActif)).map((a) => a.categorie));
  return CATEGORIES.filter((c) => presentes.has(c.id));
}

const champsQuestion = (x, lang) => ({ titre: L(x.q, lang), reste: L(x.r, lang) });
const questions = (liste, prefixe, role, lang, requete) => {
  const visibles = liste.filter((x) => role === "superadmin" || x.roles.includes(role));
  if (!requete.trim()) return visibles;
  return classer(visibles, requete, lang, champsQuestion, (x) => `${prefixe}:${liste.indexOf(x)}`).map((c) => c.x);
};

export const faqPour = (role, lang = "fr", requete = "") => questions(FAQ, "faq", role, lang, requete);
export const depannagePour = (role, lang = "fr", requete = "") => questions(DEPANNAGE, "dep", role, lang, requete);
export const glossairePour = (lang = "fr", requete = "") => {
  if (!requete.trim()) return GLOSSAIRE;
  return classer(GLOSSAIRE, requete, lang, ([mot, def], lg) => ({ titre: L(mot, lg), reste: L(def, lg) }),
    (x) => `glo:${GLOSSAIRE.indexOf(x)}`).map((c) => c.x);
};

/** Mots de l'aide proches de la requête, quand rien n'est trouvé. */
export function suggestions(requete, lang = "fr", nombre = 4) {
  const vocabulaire = new Map();
  for (const a of ARTICLES) {
    for (const m of mots(`${L(a.titre, lang)} ${L(a.module, lang)} ${a.motsCles || ""}`)) {
      if (m.length >= 4) vocabulaire.set(m, (vocabulaire.get(m) || 0) + 1);
    }
  }
  const proches = [];
  for (const terme of mots(requete)) {
    for (const [m, n] of vocabulaire) {
      const d = distance(m, terme, 3);
      if (d <= 3 || (terme.length >= 3 && m.startsWith(terme.slice(0, 3)))) proches.push([m, d, n]);
    }
  }
  return [...new Map(proches.sort((a, b) => a[1] - b[1] || b[2] - a[2]).map((p) => [p[0], p])).keys()].slice(0, nombre);
}

/** Lien vers l'écran de la fonctionnalité pour ce profil, ou null. */
export function lienPour(article, role) {
  const chemin = article.liens?.[role];
  return chemin && RACINES[role] ? `${RACINES[role]}/${chemin}` : null;
}

// Rétro-compatibilité des tests existants.
export function correspond(texte, requete) {
  return mots(requete).every((m) => normaliser(texte).includes(m));
}
