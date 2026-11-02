/** Guides pas à pas et glossaire, selon le rôle. */
import { useAuth } from "../../hooks/useAuth";
import PageHeader from "../../components/ui/PageHeader";
import { t } from "../../i18n";

const PARCOURS = {
  personnel: [
    { titre: "Commencer le suivi d'un élève", etapes: ["Dans Suivi pédagogique, ouvrez Référentiels et créez vos compétences.", "Ouvrez la fiche de l'élève.", "Dans l'onglet Compétences, évaluez une compétence.", "Dans l'onglet Résultats, ajoutez une évaluation ou une observation de participation.", "Dans l'onglet Objectifs, fixez un objectif.", "Consultez la synthèse, puis générez un rapport."] },
    { titre: "Créer son premier examen", etapes: ["Dans Examens et évaluations, ouvrez la Banque de questions et créez vos questions.", "Revenez à la liste et créez une épreuve : classe, dates, durée, tentatives.", "Ajoutez les questions depuis la banque.", "Publiez l'épreuve : elle ne se modifie plus ensuite.", "Suivez les copies, corrigez les questions ouvertes, validez.", "Publiez les résultats, puis transférez vers les notes si l'épreuve doit compter."] },
  ],
  student: [{ titre: "Passer une épreuve", etapes: ["Ouvrez Mes épreuves et lisez les consignes.", "Cliquez sur Commencer : le temps démarre.", "Répondez. Vos réponses sont enregistrées automatiquement.", "En cas de coupure, revenez sur Reprendre.", "Cliquez sur Remettre ma copie et gardez le reçu."] }],
  parent: [{ titre: "Suivre son enfant", etapes: ["Ouvrez Suivi pédagogique et choisissez votre enfant.", "Consultez ses compétences validées et ses objectifs.", "Téléchargez les rapports publiés.", "Ouvrez Résultats des épreuves pour voir les notes publiées."] }],
};
const GLOSSAIRE = [
  ["Compétence", "Ce qu'un élève sait faire, par exemple « comprendre un texte court »."],
  ["Référentiel", "Une liste de compétences, par matière ou par programme."],
  ["Niveau de maîtrise", "À travailler, À renforcer, En progression ou Acquis."],
  ["Progression générale", "Résumé des compétences, évaluations du suivi et objectifs. Les notes officielles n'y entrent pas."],
  ["Évaluation du suivi", "Résultat utile à l'accompagnement. Elle ne compte pas dans le bulletin."],
  ["Note officielle", "Note du module Notes, qui compte dans les moyennes et les bulletins."],
  ["Quiz", "Épreuve d'entraînement. Elle n'a pas à produire de note."],
  ["Examen officiel", "Épreuve qui peut produire une note officielle, après validation."],
  ["Tentative", "Un passage complet d'une épreuve. Chaque tentative est conservée."],
  ["Barème", "Les points attribués à chaque question."],
  ["Transfert", "Création de la note officielle depuis une épreuve validée, une seule fois par élève."],
  ["Publication", "Rendre un résultat ou un rapport visible. Rien n'est visible avant."],
];

export default function Aide() {
  const { user } = useAuth();
  const parcours = PARCOURS[user?.role] || PARCOURS.personnel;
  return (
    <div className="space-y-4">
      <PageHeader title={t("Aide")} subtitle={t("Guides pas à pas et glossaire")} />
      {parcours.map((p) => (
        <section key={p.titre} className="card">
          <h2 className="text-sm font-semibold text-slate-900 mb-2">{t(p.titre)}</h2>
          <ol className="list-decimal pl-5 space-y-1 text-sm text-slate-700">{p.etapes.map((e) => <li key={e}>{t(e)}</li>)}</ol>
        </section>
      ))}
      <section className="card">
        <h2 className="text-sm font-semibold text-slate-900 mb-2">{t("Glossaire")}</h2>
        <dl className="space-y-2 text-sm">
          {GLOSSAIRE.map(([mot, def]) => <div key={mot}><dt className="font-medium text-slate-800">{t(mot)}</dt><dd className="text-slate-600">{t(def)}</dd></div>)}
        </dl>
      </section>
    </div>
  );
}
