/**
 * Fiche individuelle de suivi, indépendante de la page des notes. Les notes
 * historiques y figurent à part, avec leur origine, sans jamais être converties.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useParams } from "react-router-dom";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ArrowDownRight, ArrowRight, ArrowUpRight, Minus, Plus } from "lucide-react";
import toast from "react-hot-toast";
import { suiviAPI, subjectsAPI } from "../../../api";
import AideModule from "../../../components/ui/AideModule";
import Modal from "../../../components/ui/Modal";
import Rapports from "./Rapports";
import { AIDE_NIVEAUX } from "./niveaux";
import PageHeader from "../../../components/ui/PageHeader";
import { useAuth } from "../../../hooks/useAuth";
import { extractApiError } from "../../../utils/errors";
import { t } from "../../../i18n";

const VIDE = "Données insuffisantes";
const STATUTS = [["a_commencer", "À commencer"], ["en_cours", "En cours"], ["atteint", "Atteint"], ["non_atteint", "Non atteint"], ["reporte", "Reporté"]];
const TENDANCES = {
  progresse: { label: "Progresse", Icone: ArrowUpRight, cls: "text-green-700" },
  regresse: { label: "Régresse", Icone: ArrowDownRight, cls: "text-red-700" },
  stagne: { label: "Stagne", Icone: ArrowRight, cls: "text-amber-700" },
  premiere: { label: "Première évaluation", Icone: Minus, cls: "text-slate-500" },
};
const aujourdhui = () => new Date().toISOString().slice(0, 10);

function Indicateur({ titre, valeur, detail, raison, action, methode }) {
  const vide = valeur === null;
  return (
    <div className="card">
      <p className="text-sm text-slate-500">{titre}</p>
      {vide ? <p className="text-sm font-medium mt-1 text-slate-700">{t(VIDE)}</p> : <p className="text-2xl font-bold mt-1 text-slate-900">{valeur}</p>}
      {vide && raison && <p className="text-xs text-slate-600 mt-1">{raison}</p>}
      {vide && action}
      {!vide && detail && <p className="text-xs text-slate-500 mt-1">{detail}</p>}
      {methode && <details className="mt-2 text-xs text-slate-500"><summary className="cursor-pointer">{t("Comment est-ce calculé ?")}</summary><p className="mt-1">{methode}</p></details>}
    </div>
  );
}

function Courbe({ titre, lignes, cle, max, unite }) {
  if (lignes.length < 2) return null;
  return (
    <div>
      <h3 className="text-sm font-medium text-slate-700 mb-2">{titre}</h3>
      <div style={{ width: "100%", height: 220 }}>
        <ResponsiveContainer>
          <LineChart data={lignes} margin={{ top: 8, right: 16, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="#e2e8f0" vertical={false} />
            <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#64748b" }} tickLine={false} axisLine={{ stroke: "#cbd5e1" }} />
            <YAxis domain={[0, max]} tick={{ fontSize: 11, fill: "#64748b" }} tickLine={false} axisLine={false} />
            <Tooltip formatter={(v) => [`${v}${unite}`, titre]} labelStyle={{ color: "#0f172a" }} />
            <Line type="linear" dataKey={cle} stroke="#1d4ed8" strokeWidth={2} dot={{ r: 4, fill: "#1d4ed8", stroke: "#fff", strokeWidth: 2 }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function Tableau({ colonnes, lignes }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead><tr className="text-left text-xs text-slate-500 border-b">{colonnes.map((c) => <th key={c} className="py-2 pr-4 font-medium">{c}</th>)}</tr></thead>
        <tbody>{lignes.map((l, i) => <tr key={i} className="border-b border-slate-100">{l.map((v, j) => <td key={j} className="py-2 pr-4 text-slate-700">{v}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

function Formulaire({ champs, valeurs, setValeurs }) {
  return champs.map(({ nom, label, type = "text", options, requis, vide, aide }) => (
    <div key={nom}>
      <label className="label" htmlFor={`suivi-${nom}`}>{label}{requis ? " *" : ""}</label>
      {options && options.length === 0 && vide}
      {aide && aide(valeurs)}
      {options ? (
        <select id={`suivi-${nom}`} className="input" value={valeurs[nom] ?? ""} required={requis}
          onChange={(e) => setValeurs({ ...valeurs, [nom]: e.target.value })}>
          <option value="">{t("Choisir")}</option>
          {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      ) : type === "textarea" ? (
        <textarea id={`suivi-${nom}`} className="input" rows={3} value={valeurs[nom] ?? ""} onChange={(e) => setValeurs({ ...valeurs, [nom]: e.target.value })} />
      ) : type === "checkbox" ? (
        <input id={`suivi-${nom}`} type="checkbox" checked={!!valeurs[nom]} onChange={(e) => setValeurs({ ...valeurs, [nom]: e.target.checked })} />
      ) : (
        <input id={`suivi-${nom}`} className="input" type={type} value={valeurs[nom] ?? ""} required={requis} min={type === "number" ? 0 : undefined} max={type === "number" ? 100 : undefined}
          onChange={(e) => setValeurs({ ...valeurs, [nom]: e.target.value })} />
      )}
    </div>
  ));
}

export default function FicheSuivi() {
  const { id } = useParams();
  const { user } = useAuth();
  const qc = useQueryClient();
  const gere = user?.role !== "student" && user?.role !== "parent";
  const [filtres, setFiltres] = useState({ du: "", au: "", subject: "" });
  const [onglet, setOnglet] = useState("synthese");
  const [saisie, setSaisie] = useState(null);
  const [valeurs, setValeurs] = useState({});
  const [cmp, setCmp] = useState({ a_du: "", a_au: "", b_du: "", b_au: "" });

  const racine = useLocation().pathname.split("/")[1];
  const params = Object.fromEntries(Object.entries(filtres).filter(([, v]) => v));
  const { data, isLoading, isError } = useQuery({ queryKey: ["suivi-fiche", id, params], queryFn: () => suiviAPI.fiche(id, params) });
  const { data: matieresData } = useQuery({ queryKey: ["subjects"], queryFn: () => subjectsAPI.list() });
  const { data: niveauxData } = useQuery({ queryKey: ["suivi-niveaux"], queryFn: () => suiviAPI.niveaux(), enabled: gere });
  const { data: compsData } = useQuery({ queryKey: ["suivi-competences"], queryFn: () => suiviAPI.competences({ actif: true }), enabled: gere });
  const { data: objData } = useQuery({ queryKey: ["suivi-objectifs", id], queryFn: () => suiviAPI.objectifs({ student: id }) });
  const { data: plansData } = useQuery({ queryKey: ["suivi-plans", id], queryFn: () => suiviAPI.plans({ student: id }) });
  const { data: histData } = useQuery({ queryKey: ["suivi-historique", id], queryFn: () => suiviAPI.evaluationsCompetences({ student: id, statut: "validee" }) });
  const { data: obsData } = useQuery({ queryKey: ["suivi-observations", id], queryFn: () => suiviAPI.observations({ student: id }), enabled: gere });
  const { data: propData } = useQuery({ queryKey: ["suivi-propositions", id], queryFn: () => suiviAPI.evaluationsCompetences({ student: id, statut: "proposee" }), enabled: gere });
  const comparaison = useQuery({
    queryKey: ["suivi-comparer", id, cmp],
    queryFn: () => suiviAPI.comparer(id, cmp),
    enabled: Object.values(cmp).every(Boolean),
  });

  const rafraichir = () => ["suivi-fiche", "suivi-objectifs", "suivi-plans", "suivi-propositions", "suivi-historique", "suivi-observations"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
  const opts = { onSuccess: () => { toast.success(t("Enregistré.")); setSaisie(null); setValeurs({}); rafraichir(); }, onError: (e) => toast.error(extractApiError(e)) };
  const enregistrer = useMutation({ mutationFn: ({ fn, corps }) => fn(corps), ...opts });
  const decider = useMutation({ mutationFn: ({ pk, decision }) => suiviAPI.deciderCompetence(pk, { decision }), ...opts });
  const majObjectif = useMutation({ mutationFn: ({ pk, corps }) => suiviAPI.modifierObjectif(pk, corps), ...opts });
  const majPlan = useMutation({ mutationFn: ({ pk, corps }) => suiviAPI.modifierPlan(pk, corps), ...opts });
  const majAction = useMutation({ mutationFn: ({ pk, corps }) => suiviAPI.modifierAction(pk, corps), ...opts });

  if (isLoading) return <p className="text-sm text-slate-500">{t("Chargement")}</p>;
  if (isError) return <p className="card text-sm text-red-700">{t("Le suivi n'a pas pu être chargé.")}</p>;
  const f = data.data;
  const matieres = (matieresData?.data?.results || matieresData?.data || []).map((m) => [m.id, m.name]);
  const niveaux = niveauxData?.data || [];
  const competences = compsData?.data?.results || [];
  const objectifs = objData?.data?.results || [];
  const plans = plansData?.data?.results || [];
  const propositions = propData?.data?.results || [];
  const historique = histData?.data?.results || [];
  const observations = obsData?.data?.results || [];
  const trad = (fr, en) => (localStorage.getItem("feba-lang") === "en" && en ? en : fr);

  const FORMULAIRES = {
    competence: {
      titre: t("Évaluer une compétence"), fn: suiviAPI.evaluerCompetence,
      init: { date_evaluation: aujourdhui() },
      champs: [
        { nom: "competence", label: t("Compétence"), requis: true, options: competences.map((c) => [c.id, c.nom]),
          vide: <p className="text-sm rounded-lg bg-amber-50 border border-amber-200 text-amber-900 p-2 mb-1">{t("Aucune compétence n'existe encore.")} <Link className="underline font-medium" to={`/${racine}/suivi/referentiels`}>{t("Créez vos compétences")}</Link></p> },
        { nom: "niveau", label: t("Niveau"), requis: true, options: niveaux.map((n) => [n.id, trad(n.libelle, n.libelle_en)]),
          aide: (v) => { const n = niveaux.find((x) => String(x.id) === String(v.niveau)); return n ? <p className="text-xs text-slate-500 mb-1">{t(AIDE_NIVEAUX[n.code] || "")}</p> : null; } },
        { nom: "date_evaluation", label: t("Date"), type: "date", requis: true },
        { nom: "commentaire", label: t("Commentaire"), type: "textarea" },
      ],
    },
    evaluation: {
      titre: t("Ajouter une évaluation pédagogique"), fn: suiviAPI.creerEvaluation,
      init: { date_evaluation: aujourdhui(), type: "formative" },
      champs: [
        { nom: "titre", label: t("Titre"), requis: true },
        { nom: "type", label: t("Type"), options: [["initiale", t("Évaluation initiale")], ["formative", t("Évaluation formative")], ["bilan", t("Bilan")], ["autre", t("Autre")]] },
        { nom: "subject", label: t("Matière"), options: matieres },
        { nom: "score_pourcent", label: t("Résultat (%)"), type: "number", requis: true },
        { nom: "date_evaluation", label: t("Date"), type: "date", requis: true },
        { nom: "commentaire", label: t("Commentaire"), type: "textarea" },
      ],
    },
    observation: {
      titre: t("Observer la participation"), fn: suiviAPI.creerObservation,
      init: { date_observation: aujourdhui() },
      champs: [
        { nom: "niveau", label: t("Participation"), requis: true, options: [[1, t("Insuffisante")], [2, t("Occasionnelle")], [3, t("Active")], [4, t("Très active")]] },
        { nom: "subject", label: t("Matière"), options: matieres },
        { nom: "date_observation", label: t("Date"), type: "date", requis: true },
        { nom: "note", label: t("Note"), type: "textarea" },
      ],
    },
    objectif: {
      titre: t("Créer un objectif"), fn: suiviAPI.creerObjectif, init: { priorite: "normale" },
      champs: [
        { nom: "titre", label: t("Titre"), requis: true },
        { nom: "description", label: t("Description"), type: "textarea" },
        { nom: "subject", label: t("Matière"), options: matieres },
        { nom: "competence", label: t("Compétence"), options: competences.map((c) => [c.id, c.nom]) },
        { nom: "criteres_reussite", label: t("Critères de réussite"), type: "textarea" },
        { nom: "date_cible", label: t("Date cible"), type: "date" },
        { nom: "priorite", label: t("Priorité"), options: [["basse", t("Basse")], ["normale", t("Normale")], ["haute", t("Haute")]] },
      ],
    },
    plan: {
      titre: t("Créer un plan d'accompagnement"), fn: suiviAPI.creerPlan, init: { debut: aujourdhui() },
      champs: [
        { nom: "titre", label: t("Titre"), requis: true },
        { nom: "motif", label: t("Motif"), type: "textarea" },
        { nom: "debut", label: t("Début"), type: "date", requis: true },
        { nom: "fin", label: t("Fin"), type: "date" },
        { nom: "partage_famille", label: t("Partager avec la famille"), type: "checkbox" },
      ],
    },
    action: {
      titre: t("Ajouter une action"), fn: suiviAPI.creerAction, init: { type: "exercices" },
      champs: [
        { nom: "type", label: t("Type"), requis: true, options: [["exercices", t("Exercices supplémentaires")], ["revision", t("Révision ciblée")], ["soutien", t("Séance de soutien")], ["activite", t("Activité complémentaire")], ["individuel", t("Accompagnement individuel")], ["hebdomadaire", t("Objectif hebdomadaire")], ["reevaluation", t("Réévaluation")], ["autre", t("Autre")]] },
        { nom: "description", label: t("Description"), type: "textarea", requis: true },
        { nom: "echeance", label: t("Échéance"), type: "date" },
      ],
    },
  };

  const ouvrir = (cle, extra = {}) => { setValeurs({ ...FORMULAIRES[cle].init, ...extra }); setSaisie(cle); };
  const soumettre = (e) => {
    e.preventDefault();
    const corps = Object.fromEntries(Object.entries(valeurs).filter(([, v]) => v !== "" && v !== undefined));
    if (saisie !== "action") corps.student = Number(id);
    enregistrer.mutate({ fn: FORMULAIRES[saisie].fn, corps });
  };

  const onglets = [["synthese", t("Synthèse")], ["competences", t("Compétences")], ["evaluations", t("Résultats")], ["objectifs", t("Objectifs")], ["plans", t("Accompagnement")], ["rapports", t("Rapports")]];
  const boutonAjout = (cle, libelle) => gere && (
    <button type="button" className="btn-secondary flex items-center gap-2 text-sm" onClick={() => ouvrir(cle)}><Plus className="w-4 h-4" />{libelle}</button>
  );
  const comp = comparaison.data?.data;
  const fmtEcart = (v) => (v === null || v === undefined ? t(VIDE) : `${v > 0 ? "+" : ""}${v}`);

  return (
    <div className="space-y-4">
      <AideModule cle={gere ? "fiche-personnel" : "fiche-famille"} description={gere ? t("La fiche réunit le suivi de l'élève, ses examens en ligne et ses notes officielles, chacun avec son origine.") : t("Cette fiche montre ce que l'enseignant a validé.")} />
      <PageHeader title={f.eleve.nom} subtitle={[f.eleve.classe, f.eleve.matricule].filter(Boolean).join(" - ")}
        action={<Link to=".." relative="path" className="btn-secondary text-sm">{t("Retour")}</Link>} />

      <div className="card flex flex-wrap gap-3 items-end">
        <div><label className="label" htmlFor="suivi-du">{t("Du")}</label><input id="suivi-du" type="date" className="input" value={filtres.du} onChange={(e) => setFiltres({ ...filtres, du: e.target.value })} /></div>
        <div><label className="label" htmlFor="suivi-au">{t("Au")}</label><input id="suivi-au" type="date" className="input" value={filtres.au} onChange={(e) => setFiltres({ ...filtres, au: e.target.value })} /></div>
        <div><label className="label" htmlFor="suivi-matiere">{t("Matière")}</label>
          <select id="suivi-matiere" className="input" value={filtres.subject} onChange={(e) => setFiltres({ ...filtres, subject: e.target.value })}>
            <option value="">{t("Toutes")}</option>
            {matieres.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 text-xs" aria-label={t("Périodes rapides")}>
        {[[t("Toutes les données"), null], [t("30 derniers jours"), 30], [t("90 derniers jours"), 90]].map(([l, j]) => (
          <button key={l} type="button" className="btn-secondary text-xs" onClick={() => setFiltres({ ...filtres, du: j ? new Date(Date.now() - j * 864e5).toISOString().slice(0, 10) : "", au: "" })}>{l}</button>
        ))}
      </div>

      <div className="flex gap-1 overflow-x-auto border-b border-slate-200" role="tablist">
        {onglets.map(([k, l]) => (
          <button key={k} type="button" role="tab" aria-selected={onglet === k} onClick={() => setOnglet(k)}
            className={`px-3 py-2 text-sm whitespace-nowrap border-b-2 ${onglet === k ? "border-primary text-primary font-medium" : "border-transparent text-slate-600"}`}>{l}</button>
        ))}
      </div>

      {onglet === "synthese" && (
        <div className="space-y-4">
          {f.eleve.sans_classe && gere && <p role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{t("Cet élève n'a pas de classe. Sans classe, aucun enseignant ne le voit et aucune note ni présence ne peut être saisie. Affectez-le depuis la fiche de l'élève.")}</p>}
          {gere && !f.competences.has_data && !f.evaluations.has_data && !f.objectifs.has_data && (
            <div className="card space-y-2">
              <h2 className="text-sm font-semibold text-slate-900">{t("Commencer le suivi de cet élève")}</h2>
              <ol className="list-decimal pl-5 text-sm text-slate-700 space-y-1">
                <li><Link className="text-primary underline" to={`/${racine}/suivi/referentiels`}>{t("Créez vos compétences")}</Link>{competences.length ? ` (${t("{n} disponible(s)", { n: competences.length })})` : ""}</li>
                <li><button type="button" className="text-primary underline" onClick={() => setOnglet("competences")}>{t("Évaluez une compétence")}</button></li>
                <li><button type="button" className="text-primary underline" onClick={() => setOnglet("evaluations")}>{t("Ajoutez une évaluation ou une observation")}</button></li>
                <li><button type="button" className="text-primary underline" onClick={() => setOnglet("objectifs")}>{t("Fixez un objectif")}</button></li>
              </ol>
            </div>
          )}
          <p className="text-xs text-slate-500">{filtres.du || filtres.au ? t("Période : du {a} au {b}.", { a: filtres.du || "...", b: filtres.au || "..." }) : t("Période : toutes les données enregistrées.")}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <Indicateur titre={t("Progression générale")} valeur={f.progression.has_data ? `${f.progression.valeur} %` : null}
              raison={t("Il faut au moins une compétence évaluée, une évaluation du suivi ou un objectif clos.")}
              detail={t("Compétences : {c}. Évaluations : {e}. Objectifs : {o}.", { c: f.progression.composantes.competences ?? "-", e: f.progression.composantes.evaluations ?? "-", o: f.progression.composantes.objectifs ?? "-" })}
              methode={t("Moyenne pondérée des compétences, des évaluations du suivi et des objectifs, sur les seules données disponibles. Les notes officielles n'y entrent pas.")} />
            <Indicateur titre={t("Assiduité")} valeur={f.assiduite.has_data ? `${f.assiduite.taux} %` : null}
              raison={t("Aucune présence n'est enregistrée pour cette période.")}
              action={gere && <Link className="text-xs text-primary underline" to={`/${racine}/attendance`}>{t("Saisir les présences dans Absences")}</Link>}
              detail={f.assiduite.has_data ? t("{p} présence(s), {r} retard(s), {j} absence(s) justifiée(s), {n} non justifiée(s), sur {t} séance(s).", { p: f.assiduite.presents, r: f.assiduite.retards, j: f.assiduite.absences_justifiees, n: f.assiduite.absences_non_justifiees, t: f.assiduite.total }) : null}
              methode={t("Présences et retards divisés par les séances relevées. Une séance sans relevé n'est pas comptée.")} />
            {f.participation && <Indicateur titre={t("Participation")} valeur={f.participation.moyenne !== null ? `${f.participation.moyenne} / 4` : null}
              raison={t("{n} observation(s) sur 2 nécessaires.", { n: f.participation.nombre })}
              action={gere && <button type="button" className="text-xs text-primary underline" onClick={() => { setOnglet("evaluations"); ouvrir("observation"); }}>{t("Observer la participation")}</button>}
              detail={t("{n} observation(s)", { n: f.participation.nombre })} methode={t("Moyenne des observations saisies par l'enseignant : 1 insuffisante, 2 occasionnelle, 3 active, 4 très active.")} />}
            <Indicateur titre={t("Compétences")} valeur={f.competences.has_data ? `${f.competences.lignes.filter((l) => l.acquis).length} / ${f.competences.lignes.length}` : null}
              raison={t("Aucune compétence évaluée sur cette période.")}
              action={gere && <button type="button" className="text-xs text-primary underline" onClick={() => setOnglet("competences")}>{t("Évaluer une compétence")}</button>}
              detail={f.competences.has_data ? t("acquises") : null} methode={t("Dernier niveau validé de chaque compétence évaluée.")} />
            <Indicateur titre={t("Évaluations du suivi")} valeur={f.evaluations.has_data ? `${f.evaluations.moyenne} %` : null}
              raison={t("Aucune évaluation du suivi sur cette période. Les notes officielles sont dans l'onglet Résultats.")}
              action={gere && <button type="button" className="text-xs text-primary underline" onClick={() => { setOnglet("evaluations"); ouvrir("evaluation"); }}>{t("Ajouter une évaluation")}</button>}
              detail={f.evaluations.has_data ? t("{n} évaluation(s)", { n: f.evaluations.lignes.length }) : null} methode={t("Moyenne des résultats en pourcentage.")} />
            <Indicateur titre={t("Objectifs")} valeur={f.objectifs.has_data ? `${f.objectifs.par_statut.atteint || 0} / ${f.objectifs.total}` : null}
              raison={t("Aucun objectif sur cette période.")}
              action={gere && <button type="button" className="text-xs text-primary underline" onClick={() => setOnglet("objectifs")}>{t("Créer un objectif")}</button>}
              detail={f.objectifs.has_data ? t("atteints") : null} />
          </div>
          {f.par_matiere?.has_data && (
            <div className="card space-y-2">
              <h2 className="text-sm font-semibold text-slate-800">{t("Détail par matière")}</h2>
              <Tableau colonnes={[t("Matière"), t("Maîtrise"), t("Évaluations du suivi"), t("Notes officielles")]}
                lignes={f.par_matiere.lignes.map((l) => [l.nom, l.maitrise === null ? "-" : `${l.maitrise} %`, l.evaluations === null ? "-" : `${l.evaluations} %`, l.notes_officielles === null ? "-" : `${l.notes_officielles} / 20`])} />
            </div>
          )}
          <div className="card space-y-3">
            <h2 className="text-sm font-semibold text-slate-800">{t("Comparer deux périodes")}</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {[["a_du", t("Période 1, du")], ["a_au", t("Période 1, au")], ["b_du", t("Période 2, du")], ["b_au", t("Période 2, au")]].map(([k, l]) => (
                <div key={k}><label className="label" htmlFor={`cmp-${k}`}>{l}</label><input id={`cmp-${k}`} type="date" className="input" value={cmp[k]} onChange={(e) => setCmp({ ...cmp, [k]: e.target.value })} /></div>
              ))}
            </div>
            <p className="text-xs text-slate-500">{t("Choisissez deux périodes pour voir ce qui a changé. Exemple : septembre puis octobre.")}</p>
            {comp && comp.ecart_progression === null && comp.ecart_maitrise === null && comp.ecart_evaluations === null && <p className="text-sm text-slate-600">{t("Pas de comparaison possible : il faut des données du suivi dans les deux périodes.")}</p>}
            {comp && (
              <Tableau colonnes={[t("Mesure"), t("Écart")]} lignes={[
                [t("Progression générale"), fmtEcart(comp.ecart_progression)],
                [t("Maîtrise des compétences"), fmtEcart(comp.ecart_maitrise)],
                [t("Évaluations du suivi"), fmtEcart(comp.ecart_evaluations)],
                [t("Notes officielles, période 1"), comp.note_moyenne_a ?? t(VIDE)],
                [t("Notes officielles, période 2"), comp.note_moyenne_b ?? t(VIDE)],
              ]} />
            )}
          </div>
        </div>
      )}

      {onglet === "competences" && (
        <div className="card space-y-3">
          <div className="flex justify-between items-center gap-2 flex-wrap">
            <h2 className="text-sm font-semibold text-slate-800">{t("Grille de compétences")}</h2>
            {boutonAjout("competence", t("Évaluer une compétence"))}
          </div>
          {gere && propositions.length > 0 && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 space-y-2">
              <p className="text-sm font-medium text-amber-900">{t("Propositions à valider")}</p>
              {propositions.map((p) => (
                <div key={p.id} className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="flex-1">{p.competence_nom} : {p.niveau_libelle}</span>
                  <button type="button" className="btn-secondary text-xs" onClick={() => decider.mutate({ pk: p.id, decision: "validee" })}>{t("Valider")}</button>
                  <button type="button" className="btn-secondary text-xs" onClick={() => decider.mutate({ pk: p.id, decision: "refusee" })}>{t("Refuser")}</button>
                </div>
              ))}
            </div>
          )}
          {!f.competences.has_data && <p className="text-sm text-slate-500">{t("Aucune compétence évaluée pour le moment.")}</p>}
          <ul className="space-y-3">
            {f.competences.lignes.map((l) => {
              const tend = TENDANCES[l.tendance];
              return (
                <li key={l.competence}>
                  <div className="flex flex-wrap justify-between gap-2 text-sm">
                    <span className="text-slate-800">{trad(l.nom, l.nom_en)}{l.domaine ? <span className="text-slate-500"> - {l.domaine}</span> : null}</span>
                    <span className="font-medium text-slate-800">{trad(l.niveau, l.niveau_en)}</span>
                  </div>
                  <div className="h-2 rounded bg-slate-100 mt-1" aria-hidden="true">
                    <div className="h-2 rounded" style={{ width: `${(l.rang / f.competences.rang_max) * 100}%`, background: l.couleur }} />
                  </div>
                  <p className={`text-xs mt-1 flex items-center gap-1 ${tend.cls}`}><tend.Icone className="w-3 h-3" />{t(tend.label)} - {l.date}</p>
                  {l.nombre_evaluations > 1 && (
                    <details className="text-xs text-slate-600 mt-1"><summary className="cursor-pointer">{t("Historique ({n})", { n: l.nombre_evaluations })}</summary>
                      <ul className="mt-1 space-y-0.5">{historique.filter((h) => h.competence === l.competence).map((h) => <li key={h.id}>{h.date_evaluation} : {h.niveau_libelle}{h.commentaire ? ` - ${h.commentaire}` : ""}</li>)}</ul>
                    </details>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {onglet === "evaluations" && (
        <div className="space-y-4">
          <div className="card space-y-3">
            <div className="flex justify-between items-center gap-2 flex-wrap">
              <h2 className="text-sm font-semibold text-slate-800">{t("Évaluations du suivi")}</h2>
              <div className="flex gap-2 flex-wrap">
                {boutonAjout("evaluation", t("Ajouter une évaluation"))}
                {boutonAjout("observation", t("Observer la participation"))}
              </div>
            </div>
            {!f.evaluations.has_data && <p className="text-sm text-slate-500">{t("Aucune évaluation du suivi pour le moment.")}</p>}
            <Courbe titre={t("Évolution des évaluations du suivi")} lignes={f.evaluations.lignes} cle="score" max={100} unite=" %" />
            {f.evaluations.has_data && <Tableau colonnes={[t("Date"), t("Évaluation"), t("Matière"), t("Résultat")]} lignes={f.evaluations.lignes.map((l) => [l.date, l.titre, l.subject_name || "-", `${l.score} %`])} />}
          </div>
          {gere && observations.length > 0 && (
            <div className="card space-y-2">
              <h2 className="text-sm font-semibold text-slate-800">{t("Observations de participation")}</h2>
              <Tableau colonnes={[t("Date"), t("Participation"), t("Note")]} lignes={observations.map((o) => [o.date_observation, t({ 1: "Insuffisante", 2: "Occasionnelle", 3: "Active", 4: "Très active" }[o.niveau]), o.note || "-"])} />
            </div>
          )}
          {f.resultats_examens?.has_data && (
            <div className="card space-y-3">
              <h2 className="text-sm font-semibold text-slate-800">{t("Examens en ligne")}</h2>
              <Courbe titre={t("Évolution des examens en ligne")} lignes={f.resultats_examens.lignes} cle="score" max={100} unite=" %" />
              <Tableau colonnes={[t("Date"), t("Évaluation"), t("Matière"), t("Résultat"), t("Note officielle")]}
                lignes={f.resultats_examens.lignes.map((l) => [l.date, l.titre, l.subject_name, `${l.score} %`, l.transferee ? t("Transférée") : t("Non transférée")])} />
            </div>
          )}
          <div className="card space-y-3">
            <h2 className="text-sm font-semibold text-slate-800">{t("Notes officielles (lecture seule)")}</h2>
            <p className="text-xs text-slate-500">{t("Issues du module Notes. Elles restent gérées par ce module et ne sont pas converties en évaluations du suivi.")}</p>
            {!f.resultats_historiques.has_data && <p className="text-sm text-slate-500">{t("Aucune note officielle.")}</p>}
            <Courbe titre={t("Évolution des notes officielles")} lignes={f.resultats_historiques.lignes} cle="valeur" max={20} unite=" / 20" />
            {f.resultats_historiques.has_data && <Tableau colonnes={[t("Date"), t("Matière"), t("Période"), t("Note")]} lignes={f.resultats_historiques.lignes.map((l) => [l.date, l.subject_name, l.periode, `${l.valeur} / ${l.bareme}`])} />}
          </div>
        </div>
      )}

      {onglet === "objectifs" && (
        <div className="card space-y-3">
          <div className="flex justify-between items-center gap-2 flex-wrap">
            <h2 className="text-sm font-semibold text-slate-800">{t("Objectifs")}</h2>
            {boutonAjout("objectif", t("Créer un objectif"))}
          </div>
          {objectifs.length === 0 && <p className="text-sm text-slate-500">{t("Aucun objectif pour le moment.")}</p>}
          {objectifs.map((o) => (
            <div key={o.id} className="border border-slate-200 rounded-lg p-3 space-y-2">
              <div className="flex flex-wrap justify-between gap-2">
                <div>
                  <p className="text-sm font-medium text-slate-900">{o.titre}{o.class_obj ? ` (${t("collectif")})` : ""}</p>
                  {o.description && <p className="text-xs text-slate-600">{o.description}</p>}
                  {o.criteres_reussite && <p className="text-xs text-slate-600">{t("Critères de réussite")} : {o.criteres_reussite}</p>}
                  {o.competence_nom && <p className="text-xs text-slate-500">{t("Compétence")} : {o.competence_nom}</p>}
                  {o.date_cible && <p className="text-xs text-slate-500">{t("Date cible")} : {o.date_cible}</p>}
                </div>
                {gere ? (
                  <select className="input w-auto text-sm" aria-label={t("Statut")} value={o.statut} onChange={(e) => majObjectif.mutate({ pk: o.id, corps: { statut: e.target.value } })}>
                    {STATUTS.map(([v, l]) => <option key={v} value={v}>{t(l)}</option>)}
                  </select>
                ) : <span className="text-sm text-slate-700">{t(STATUTS.find(([v]) => v === o.statut)?.[1] || "")}</span>}
              </div>
              {o.actions.map((a) => (
                <div key={a.id} className="text-xs text-slate-700 flex flex-wrap justify-between gap-2">
                  <span>{a.description}</span>
                  {a.realisee_le ? <span className="text-green-700">{t("Réalisée le")} {a.realisee_le}</span>
                    : gere && <button type="button" className="text-primary underline" onClick={() => majAction.mutate({ pk: a.id, corps: { realisee_le: aujourdhui() } })}>{t("Marquer réalisée")}</button>}
                </div>
              ))}
              {gere && <button type="button" className="text-xs text-primary underline" onClick={() => ouvrir("action", { objectif: o.id })}>{t("Ajouter une action")}</button>}
            </div>
          ))}
        </div>
      )}

      {onglet === "plans" && (
        <div className="card space-y-3">
          <div className="flex justify-between items-center gap-2 flex-wrap">
            <h2 className="text-sm font-semibold text-slate-800">{t("Plans d'accompagnement")}</h2>
            {boutonAjout("plan", t("Créer un plan d'accompagnement"))}
          </div>
          {plans.length === 0 && <p className="text-sm text-slate-500">{t("Aucun plan d'accompagnement.")}</p>}
          {plans.map((p) => (
            <div key={p.id} className="border border-slate-200 rounded-lg p-3 space-y-2">
              <div className="flex flex-wrap justify-between gap-2">
                <p className="text-sm font-medium text-slate-900">{p.titre}</p>
                {gere ? (
                  <select className="input w-auto text-sm" aria-label={t("Statut")} value={p.statut} onChange={(e) => majPlan.mutate({ pk: p.id, corps: { statut: e.target.value, ...(e.target.value !== "actif" && !p.fin ? { fin: aujourdhui() } : {}) } })}>
                    <option value="actif">{t("Actif")}</option><option value="termine">{t("Terminé")}</option><option value="abandonne">{t("Abandonné")}</option>
                  </select>
                ) : null}
              </div>
              {p.motif && <p className="text-xs text-slate-600">{p.motif}</p>}
              {p.actions.map((a) => (
                <div key={a.id} className="text-xs text-slate-700 flex flex-wrap justify-between gap-2">
                  <span>{a.description}</span>
                  {a.realisee_le ? <span className="text-green-700">{t("Réalisée le")} {a.realisee_le}</span>
                    : gere && <button type="button" className="text-primary underline" onClick={() => majAction.mutate({ pk: a.id, corps: { realisee_le: aujourdhui() } })}>{t("Marquer réalisée")}</button>}
                </div>
              ))}
              {gere && <button type="button" className="text-xs text-primary underline" onClick={() => ouvrir("action", { plan: p.id })}>{t("Ajouter une action")}</button>}
            </div>
          ))}
        </div>
      )}

      {onglet === "rapports" && <Rapports eleve={id} gere={gere} />}

      <Modal open={!!saisie} onClose={() => setSaisie(null)} title={saisie ? FORMULAIRES[saisie].titre : ""}>
        {saisie && (
          <form onSubmit={soumettre} className="space-y-3">
            <Formulaire champs={FORMULAIRES[saisie].champs} valeurs={valeurs} setValeurs={setValeurs} />
            <div className="flex gap-3 justify-end pt-2">
              <button type="button" className="btn-secondary" onClick={() => setSaisie(null)}>{t("Annuler")}</button>
              <button type="submit" className="btn-primary" disabled={enregistrer.isPending}>{t("Enregistrer")}</button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}
