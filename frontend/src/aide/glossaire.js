/**
 * Glossaire du centre d'aide, personnalisé par profil.
 *
 * Un terme existe une seule fois ; il porte ses définitions par profil :
 *   definitions: { "*": commune, superadmin, admin, teacher, parent, student }
 * Un profil voit le terme s'il a une définition propre ou si une définition
 * commune « * » existe. Le super administrateur voit tous les termes, avec la
 * définition la plus administrative disponible. `feature` : module optionnel
 * de l'académie ; terme masqué (sauf super administrateur) s'il est inactif.
 *
 * Chaque texte est une paire [français, anglais].
 */

const PERSONNEL = (fr, en) => ({ superadmin: [fr, en], admin: [fr, en] });

export const TERMES = [
  // ── Administration (personnel seulement) ────────────────────────────
  { id: "academie", terme: ["Académie", "Academy"], definitions: {
    superadmin: ["Établissement géré dans FEBA, isolé des autres : élèves, finances et documents ne se mélangent jamais.", "School managed in FEBA, isolated from the others: students, finances and documents never mix."],
    admin: ["L'établissement que vous administrez. Vous ne voyez que ses données.", "The school you administer. You only see its data."] } },
  { id: "toutes-academies", terme: ["Toutes les Académies", "All academies"], definitions: {
    superadmin: ["Vue consolidée : chaque ligne indique son académie ; les montants restent dans leur devise.", "Consolidated view: each row shows its academy; amounts stay in their currency."] } },
  { id: "module", terme: ["Module optionnel", "Optional module"], definitions: {
    superadmin: ["Fonction activée académie par académie (suivi, examens en ligne, rapports mensuels, admissions, salles virtuelles).", "Feature enabled per academy (follow-up, online exams, monthly reports, admissions, virtual rooms)."] } },
  { id: "incident", terme: ["Incident technique", "Technical incident"], definitions: {
    superadmin: ["Erreur serveur ou alerte de surveillance enregistrée automatiquement, avec ses occurrences et ses niveaux de validation.", "Server error or monitoring alert recorded automatically, with its occurrences and validation levels."] } },
  { id: "annee-active", terme: ["Année scolaire active", "Active school year"], definitions: {
    ...PERSONNEL("Année utilisée par défaut dans les listes, les inscriptions et le tableau de bord.", "Year used by default in lists, enrolments and the dashboard."),
    teacher: ["Année en cours : vos classes, notes et épreuves s'y rattachent.", "Current year: your classes, grades and tests belong to it."] } },
  { id: "mdp-temporaire", terme: ["Mot de passe temporaire", "Temporary password"], definitions: {
    ...PERSONNEL("Mot de passe que vous donnez lors d'une création ou d'une réinitialisation ; l'utilisateur doit le remplacer à la connexion.", "Password you give at creation or reset; the user must replace it at sign-in."),
    "*": ["Mot de passe donné par l'administration, à remplacer à la connexion.", "Password given by the administration, to replace at sign-in."] } },
  { id: "gabarit", terme: ["Gabarit", "Template"], definitions: PERSONNEL(
    "Fond officiel d'un diplôme ou certificat, avec l'emplacement des champs imprimés.", "Official background of a diploma or certificate, with the position of printed fields.") },

  // ── Scolarité ───────────────────────────────────────────────────────
  { id: "classe", terme: ["Classe", "Class"], definitions: {
    superadmin: ["Groupe d'élèves d'une académie, pour une année, rattaché à un niveau et à un parcours linguistique.", "Group of students of an academy, for one year, linked to a level and a language track."],
    admin: ["Groupe d'élèves de votre académie pour une année : niveau, matières, effectif et enseignants affectés.", "Group of students of your academy for one year: level, subjects, headcount and assigned teachers."],
    teacher: ["Groupe d'élèves qui vous est affecté ; vous y notez, faites l'appel et donnez des devoirs pour vos matières.", "Group of students assigned to you; you grade, take attendance and give homework there for your subjects."],
    parent: ["Groupe dans lequel votre enfant est inscrit cette année.", "Group your child is enrolled in this year."],
    student: ["Ton groupe de l'année : tu y suis tes cours avec tes camarades.", "Your group for the year: you take your lessons there with your classmates."] } },
  { id: "niveau", terme: ["Niveau", "Level"], definitions: {
    ...PERSONNEL("Étape du cursus (CI, CM2, 6e…) ; son cycle fixe le barème des notes et sert à définir les tarifs.", "Stage of the curriculum (CI, CM2, 6th grade…); its cycle sets the grading scale and is used to set fees."),
    parent: ["Étape du cursus de votre enfant (par exemple CM2).", "Stage of your child's curriculum (for example CM2)."],
    student: ["Ton année d'études (par exemple CM2 ou 6e).", "Your year of study (for example CM2 or 6th grade)."] } },
  { id: "matiere", terme: ["Matière", "Subject"], definitions: {
    ...PERSONNEL("Discipline enseignée, avec son code, sa langue et son coefficient.", "Subject taught, with its code, language and coefficient."),
    teacher: ["Discipline que vous enseignez ; vous ne notez que vos matières affectées.", "Subject you teach; you only grade your assigned subjects."],
    parent: ["Discipline étudiée par votre enfant.", "Subject studied by your child."],
    student: ["Discipline que tu étudies (mathématiques, français…).", "Subject you study (mathematics, French…)."] } },
  { id: "coefficient", terme: ["Coefficient", "Coefficient"], definitions: {
    ...PERSONNEL("Poids d'une matière dans la moyenne ; un changement s'applique aux bulletins générés ensuite.", "Weight of a subject in the average; a change applies to report cards generated afterwards."),
    "*": ["Poids d'une matière dans la moyenne : une matière à coefficient 3 compte trois fois plus.", "Weight of a subject in the average: a subject with coefficient 3 counts three times more."] } },
  { id: "inscription", terme: ["Inscription", "Enrolment"], definitions: {
    ...PERSONNEL("Rattachement d'un élève à une classe pour une année ; un passage de niveau crée l'inscription suivante.", "Link between a student and a class for one year; a promotion creates the next enrolment."),
    parent: ["Rattachement de votre enfant à une classe pour l'année.", "Your child's link to a class for the year."] } },

  // ── Notes, bulletins, évaluations ───────────────────────────────────
  { id: "note-officielle", terme: ["Note officielle", "Official grade"], definitions: {
    ...PERSONNEL("Note du module Notes, qui compte dans les moyennes et les bulletins ; jamais effacée, supprimée avec justification et restaurable.", "Grade from the Grades module, counted in averages and report cards; never erased, deleted with a justification and restorable."),
    teacher: ["Note que vous saisissez dans « Notes » ; elle compte dans la moyenne et le bulletin.", "Grade you enter in \"Grades\"; it counts in the average and the report card."],
    "*": ["Note qui compte dans la moyenne et le bulletin.", "Grade that counts in the average and the report card."] } },
  { id: "moyenne", terme: ["Moyenne", "Average"], definitions: {
    "*": ["Résultat calculé à partir des notes et de leurs coefficients, par matière puis générale.", "Result computed from grades and their coefficients, per subject then overall."] } },
  { id: "periode", terme: ["Période", "Term"], definitions: {
    "*": ["Partie de l'année (trimestre 1, 2, 3 ou examen) à laquelle une note se rattache.", "Part of the year (term 1, 2, 3 or exam) a grade belongs to."] } },
  { id: "bulletin", terme: ["Bulletin", "Report card"], definitions: {
    ...PERSONNEL("Document PDF des résultats d'une période, généré par élève, par classe ou pour l'académie.", "PDF of a term's results, generated per student, per class or for the academy."),
    teacher: ["Document des résultats d'une période ; vos notes y figurent après génération par l'administration.", "Document of a term's results; your grades appear after the administration generates it."],
    parent: ["Document des résultats de votre enfant pour une période, à télécharger dans « Bulletins ».", "Your child's results for a term, to download in \"Report cards\"."],
    student: ["Ton relevé de résultats pour une période, à télécharger dans « Bulletins ».", "Your results for a term, to download in \"Report cards\"."] } },
  { id: "appreciation", terme: ["Appréciation", "Appreciation"], definitions: {
    ...PERSONNEL("Mention attribuée selon le pourcentage de la note (barème réglable par académie et par cycle).", "Remark given according to the grade percentage (scale set per academy and cycle)."),
    "*": ["Mention qui accompagne une note (Très bien, Assez bien…).", "Remark that goes with a grade (Very good, Fairly good…)."] } },
  { id: "quiz", terme: ["Quiz", "Quiz"], feature: "evaluations_en_ligne", definitions: {
    "*": ["Épreuve en ligne d'entraînement ; elle n'a pas à produire de note.", "Online practice test; it does not have to produce a grade."], parent: null } },
  { id: "examen", terme: ["Examen officiel", "Official exam"], feature: "evaluations_en_ligne", definitions: {
    ...PERSONNEL("Épreuve en ligne qui peut produire une note officielle après validation et transfert.", "Online test that can produce an official grade after validation and transfer."),
    teacher: ["Épreuve en ligne que vous publiez, corrigez, validez puis transférez vers les notes si elle doit compter.", "Online test you publish, mark, validate then transfer to grades if it must count."],
    student: ["Épreuve en ligne qui peut compter dans ta moyenne.", "Online test that can count in your average."],
    parent: ["Épreuve en ligne de votre enfant ; son résultat est visible quand l'enseignant le publie.", "Your child's online test; its result is visible when the teacher publishes it."] } },
  { id: "tentative", terme: ["Tentative", "Attempt"], feature: "evaluations_en_ligne", definitions: {
    teacher: ["Un passage complet d'une épreuve par un élève ; chaque tentative est conservée.", "One complete run of a test by a student; each attempt is kept."],
    student: ["Un passage complet d'une épreuve ; le nombre autorisé est fixé par l'enseignant.", "One complete run of a test; the allowed number is set by the teacher."],
    ...PERSONNEL("Un passage complet d'une épreuve ; chaque tentative est conservée.", "One complete run of a test; each attempt is kept.") } },
  { id: "transfert", terme: ["Transfert", "Transfer"], feature: "evaluations_en_ligne", definitions: {
    ...PERSONNEL("Création de la note officielle depuis une épreuve validée, une seule fois par élève.", "Creation of the official grade from a validated test, once per student."),
    teacher: ["Envoi des résultats validés d'une épreuve vers les notes officielles, une seule fois par élève.", "Sending a test's validated results to official grades, once per student."] } },
  { id: "publication", terme: ["Publication", "Publication"], definitions: {
    ...PERSONNEL("Rendre un résultat ou un rapport visible des familles ; rien n'est visible avant.", "Making a result or report visible to families; nothing is visible before."),
    teacher: ["Rendre un résultat ou un rapport visible des élèves et des parents ; rien n'est visible avant.", "Making a result or report visible to students and parents; nothing is visible before."],
    parent: ["Un résultat ou un rapport n'est visible qu'une fois publié par l'établissement.", "A result or report is only visible once published by the school."],
    student: ["Ton résultat n'apparaît qu'une fois publié par ton enseignant.", "Your result only appears once your teacher publishes it."] } },

  // ── Suivi pédagogique ───────────────────────────────────────────────
  { id: "competence", terme: ["Compétence", "Competency"], feature: "suivi_pedagogique", definitions: {
    "*": ["Ce qu'un élève sait faire, par exemple « comprendre un texte court ».", "What a student can do, for example \"understand a short text\"."],
    student: ["Ce que tu sais faire, par exemple « comprendre un texte court ».", "What you can do, for example \"understand a short text\"."] } },
  { id: "referentiel", terme: ["Référentiel", "Framework"], feature: "suivi_pedagogique", definitions: {
    ...PERSONNEL("Liste de compétences, par matière ou par programme, propre à l'académie.", "List of competencies, by subject or programme, specific to the academy."),
    teacher: ["Liste de compétences que vous évaluez, par matière ou par programme.", "List of competencies you assess, by subject or programme."] } },
  { id: "maitrise", terme: ["Niveau de maîtrise", "Mastery level"], feature: "suivi_pedagogique", definitions: {
    "*": ["À travailler, À renforcer, En progression ou Acquis.", "To work on, To strengthen, In progress or Acquired."] } },
  { id: "evaluation-suivi", terme: ["Évaluation du suivi", "Follow-up assessment"], feature: "suivi_pedagogique", definitions: {
    "*": ["Résultat utile à l'accompagnement ; il ne compte pas dans le bulletin.", "Result useful for support; it does not count in the report card."] } },

  // ── Vie scolaire ────────────────────────────────────────────────────
  { id: "absence", terme: ["Absence", "Absence"], definitions: {
    ...PERSONNEL("Statut de présence d'un élève à une date (présent, absent, en retard, excusé), avec justificatif éventuel.", "Attendance status of a student on a date (present, absent, late, excused), with an optional supporting document."),
    teacher: ["Statut que vous enregistrez pour un élève de vos classes : présent, absent, en retard ou excusé.", "Status you record for a student of your classes: present, absent, late or excused."],
    parent: ["Absence ou retard de votre enfant enregistré par l'établissement.", "Your child's absence or late arrival recorded by the school."],
    student: ["Absence ou retard enregistré à ton nom.", "Absence or late arrival recorded for you."] } },
  { id: "justificatif", terme: ["Justificatif", "Supporting document"], definitions: {
    "*": ["Document joint à une absence ou un retard (certificat, mot des parents).", "Document attached to an absence or late arrival (certificate, note from parents)."], student: null } },
  { id: "devoir", terme: ["Devoir", "Homework"], definitions: {
    teacher: ["Travail que vous donnez à une classe, avec consignes, date limite et pièces jointes.", "Assignment you give to a class, with instructions, due date and attachments."],
    "*": ["Travail à faire pour une date limite, avec ses consignes et pièces jointes.", "Work to do by a due date, with its instructions and attachments."] } },
  { id: "salle-virtuelle", terme: ["Salle virtuelle", "Virtual room"], feature: "virtual_classrooms", definitions: {
    "*": ["Salle de visioconférence pour un cours ou une réunion en ligne.", "Video conferencing room for an online class or meeting."] } },

  // ── Finances ────────────────────────────────────────────────────────
  { id: "tarif", terme: ["Tarif", "Fee"], definitions: {
    ...PERSONNEL("Montant d'une nature de frais (scolarité, inscription…) pour une académie, une année et, si besoin, un niveau.", "Amount of a fee type (tuition, registration…) for an academy, a year and, if needed, a level."),
    parent: ["Montant demandé pour un type de frais (scolarité, inscription, cantine…).", "Amount charged for a type of fee (tuition, registration, canteen…)."] } },
  { id: "echeance", terme: ["Échéance", "Instalment"], definitions: {
    ...PERSONNEL("Part d'un tarif à payer avant une date ; la somme des tranches doit égaler le tarif.", "Part of a fee to pay by a date; the sum of instalments must equal the fee."),
    parent: ["Montant à payer avant une date donnée (par exemple 1re tranche de scolarité).", "Amount to pay by a given date (for example 1st tuition instalment)."] } },
  { id: "reste-a-payer", terme: ["Reste à payer", "Outstanding balance"], definitions: {
    ...PERSONNEL("Montant dû non encore couvert par les paiements confirmés, après réductions et exonérations.", "Amount due not yet covered by confirmed payments, after discounts and exemptions."),
    parent: ["Ce qu'il reste à régler pour votre enfant, après les paiements confirmés.", "What remains to pay for your child, after confirmed payments."] } },
  { id: "recu", terme: ["Reçu", "Receipt"], definitions: {
    ...PERSONNEL("Document PDF généré pour un paiement enregistré.", "PDF generated for a recorded payment."),
    parent: ["Justificatif d'un paiement, à télécharger dans « Paiements ».", "Proof of a payment, to download in \"Payments\"."] } },
  { id: "exoneration", terme: ["Réduction / exonération", "Discount / exemption"], definitions: PERSONNEL(
    "Disposition propre à un élève qui diminue ou supprime un frais, avec motif et auteur conservés.", "Arrangement for one student that reduces or removes a fee, keeping the reason and author.") },
  { id: "recouvrement", terme: ["Taux de recouvrement", "Collection rate"], definitions: PERSONNEL(
    "Part du montant dû aux échéances passées qui a été effectivement payée.", "Share of the amount due on past instalments that has actually been paid.") },
  { id: "devise", terme: ["Devise", "Currency"], definitions: PERSONNEL(
    "Monnaie d'une académie (FCFA, dollar…) ; des montants de devises différentes ne sont jamais additionnés.", "Currency of an academy (CFA franc, dollar…); amounts in different currencies are never added together.") },
];

const ORDRE_ADMIN = ["superadmin", "admin", "*", "teacher", "parent", "student"];

/** Définition d'un terme pour un profil, ou null s'il ne le concerne pas. */
export function definitionPour(terme, role) {
  const defs = terme.definitions;
  if (role === "superadmin") {
    for (const cle of ORDRE_ADMIN) if (defs[cle]) return defs[cle];
    return null;
  }
  if (Object.prototype.hasOwnProperty.call(defs, role)) return defs[role]; // null = masqué explicitement
  return defs["*"] || null;
}

/** Termes du glossaire pour un profil : [{ id, terme, definition }]. */
export function termesPour(role, moduleActif = () => true) {
  return TERMES
    .filter((t) => role === "superadmin" || !t.feature || moduleActif(t))
    .map((t) => ({ id: t.id, terme: t.terme, definition: definitionPour(t, role), feature: t.feature }))
    .filter((t) => t.definition);
}
