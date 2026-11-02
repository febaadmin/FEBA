/**
 * Graphiques de la fiche. Un seul axe par graphique, légende dès deux séries, valeurs
 * exactes au survol. Une série sans donnée n'est pas tracée, jamais comptée comme zéro.
 */
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useReducedMotion } from "framer-motion";
import { t } from "../../../i18n";

const COULEURS = { suivi: "#2563eb", examens: "#7c3aed", notes: "#0f766e", presents: "#15803d", retards: "#d97706", absences: "#b91c1c" };
const AXE = { tick: { fontSize: 11, fill: "#64748b" }, tickLine: false };
const INFOBULLE = { contentStyle: { borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 12 }, cursor: { fill: "rgba(148,163,184,.12)" } };

function Cadre({ titre, children, hauteur = 240 }) {
  return (
    <figure className="card">
      <figcaption className="text-sm font-semibold text-slate-800 mb-3">{titre}</figcaption>
      <div style={{ width: "100%", height: hauteur }}>
        <ResponsiveContainer>{children}</ResponsiveContainer>
      </div>
    </figure>
  );
}

export function Evolution({ lignes }) {
  const reduit = useReducedMotion();
  if (!lignes.length) return null;
  const series = [["suivi", t("Évaluations du suivi")], ["examens", t("Examens en ligne")], ["notes", t("Notes officielles (ramenées en %)")]]
    .filter(([k]) => lignes.some((l) => l[k] !== null && l[k] !== undefined));
  return (
    <Cadre titre={t("Évolution générale, en %")}>
      <LineChart data={lignes} margin={{ top: 8, right: 16, bottom: 0, left: -12 }}>
        <CartesianGrid stroke="#e2e8f0" vertical={false} />
        <XAxis dataKey="mois" {...AXE} axisLine={{ stroke: "#cbd5e1" }} />
        <YAxis domain={[0, 100]} {...AXE} axisLine={false} />
        <Tooltip {...INFOBULLE} formatter={(v, n) => [`${v} %`, n]} />
        {series.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
        {series.map(([k, nom]) => <Line key={k} type="monotone" dataKey={k} name={nom} stroke={COULEURS[k]} strokeWidth={2} connectNulls dot={{ r: 4, stroke: "#fff", strokeWidth: 2, fill: COULEURS[k] }} activeDot={{ r: 6 }} isAnimationActive={!reduit} animationDuration={900} />)}
      </LineChart>
    </Cadre>
  );
}

export function EvolutionCompetence({ historique }) {
  const reduit = useReducedMotion();
  const competences = [...new Map(historique.map((h) => [h.competence, h.competence_nom])).entries()];
  const [choix, setChoix] = useState("");
  if (!competences.length) return null;
  const id = String(choix || competences[0][0]);
  const points = historique.filter((h) => String(h.competence) === id)
    .sort((a, b) => a.date_evaluation.localeCompare(b.date_evaluation) || a.id - b.id);
  const libelles = Object.fromEntries(historique.map((h) => [h.niveau_rang, h.niveau_libelle]));
  const rangs = Object.keys(libelles).map(Number).sort((a, b) => a - b);
  return (
    <div className="space-y-2">
      <label className="flex flex-wrap items-center gap-2 text-sm text-slate-700">
        {t("Compétence")}
        <select className="input max-w-sm" value={id} onChange={(e) => setChoix(e.target.value)}>
          {competences.map(([k, nom]) => <option key={k} value={k}>{nom}</option>)}
        </select>
      </label>
      <Cadre titre={t("Évolution de la compétence")}>
        <LineChart data={points} margin={{ top: 8, right: 16, bottom: 0, left: 24 }}>
          <CartesianGrid stroke="#e2e8f0" vertical={false} />
          <XAxis dataKey="date_evaluation" {...AXE} axisLine={{ stroke: "#cbd5e1" }} />
          <YAxis dataKey="niveau_rang" ticks={rangs} domain={[rangs[0], rangs[rangs.length - 1]]} allowDecimals={false} width={96}
            tickFormatter={(r) => libelles[r] || r} {...AXE} axisLine={false} />
          <Tooltip {...INFOBULLE} formatter={(r) => [libelles[r] || r, t("Niveau")]} />
          <Line type="stepAfter" dataKey="niveau_rang" stroke={COULEURS.suivi} strokeWidth={2}
            dot={{ r: 4, stroke: "#fff", strokeWidth: 2, fill: COULEURS.suivi }} isAnimationActive={!reduit} />
        </LineChart>
      </Cadre>
    </div>
  );
}

export function ParMatiere({ lignes }) {
  const reduit = useReducedMotion();
  if (!lignes.length) return null;
  const data = lignes.map((l) => ({ nom: l.nom, maitrise: l.maitrise, evaluations: l.evaluations, notes: l.notes_officielles === null ? null : l.notes_officielles * 5 }));
  return (
    <Cadre titre={t("Progression par matière, en %")}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }} barGap={2}>
        <CartesianGrid stroke="#e2e8f0" vertical={false} />
        <XAxis dataKey="nom" {...AXE} axisLine={{ stroke: "#cbd5e1" }} interval={0} />
        <YAxis domain={[0, 100]} {...AXE} axisLine={false} />
        <Tooltip {...INFOBULLE} formatter={(v, n) => [`${v} %`, n]} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="maitrise" name={t("Maîtrise")} fill={COULEURS.examens} radius={[4, 4, 0, 0]} maxBarSize={22} isAnimationActive={!reduit} />
        <Bar dataKey="evaluations" name={t("Évaluations du suivi")} fill={COULEURS.suivi} radius={[4, 4, 0, 0]} maxBarSize={22} isAnimationActive={!reduit} />
        <Bar dataKey="notes" name={t("Notes officielles (ramenées en %)")} fill={COULEURS.notes} radius={[4, 4, 0, 0]} maxBarSize={22} isAnimationActive={!reduit} />
      </BarChart>
    </Cadre>
  );
}

export function RepartitionCompetences({ lignes }) {
  const reduit = useReducedMotion();
  const total = lignes.reduce((s, l) => s + l.nombre, 0);
  if (!total) return null;
  return (
    <figure className="card">
      <figcaption className="text-sm font-semibold text-slate-800 mb-3">{t("Compétences par niveau")}</figcaption>
      <div className="flex flex-wrap items-center gap-4">
        <div style={{ width: 170, height: 170 }} className="relative">
          <ResponsiveContainer>
            <PieChart>
              <Pie data={lignes} dataKey="nombre" nameKey="niveau" innerRadius={52} outerRadius={78} paddingAngle={2} stroke="#fff" isAnimationActive={!reduit}>
                {lignes.map((l) => <Cell key={l.code} fill={l.couleur} />)}
              </Pie>
              <Tooltip {...INFOBULLE} />
            </PieChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none"><span className="text-2xl font-bold text-slate-900">{total}</span><span className="text-xs text-slate-500">{t("évaluées")}</span></div>
        </div>
        <ul className="flex-1 min-w-36 space-y-1 text-sm">
          {lignes.map((l) => <li key={l.code} className="flex items-center gap-2"><span className="w-3 h-3 rounded-sm" style={{ background: l.couleur }} aria-hidden="true" /><span className="flex-1 text-slate-700">{l.niveau}</span><span className="font-semibold text-slate-900">{l.nombre}</span></li>)}
        </ul>
      </div>
    </figure>
  );
}

export function AssiduiteMois({ lignes }) {
  const reduit = useReducedMotion();
  if (!lignes.length) return null;
  return (
    <Cadre titre={t("Assiduité par mois, en séances")}>
      <BarChart data={lignes} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
        <CartesianGrid stroke="#e2e8f0" vertical={false} />
        <XAxis dataKey="mois" {...AXE} axisLine={{ stroke: "#cbd5e1" }} />
        <YAxis allowDecimals={false} {...AXE} axisLine={false} />
        <Tooltip {...INFOBULLE} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="presents" stackId="a" name={t("Présences")} fill={COULEURS.presents} maxBarSize={36} isAnimationActive={!reduit} />
        <Bar dataKey="retards" stackId="a" name={t("Retards")} fill={COULEURS.retards} maxBarSize={36} isAnimationActive={!reduit} />
        <Bar dataKey="absences" stackId="a" name={t("Absences")} fill={COULEURS.absences} radius={[4, 4, 0, 0]} maxBarSize={36} isAnimationActive={!reduit} />
      </BarChart>
    </Cadre>
  );
}

export function ComparaisonPeriodes({ comp }) {
  const reduit = useReducedMotion();
  const data = [
    { nom: t("Progression générale"), a: comp.a.valeur, b: comp.b.valeur },
    { nom: t("Maîtrise"), a: comp.a.composantes.competences, b: comp.b.composantes.competences },
    { nom: t("Évaluations du suivi"), a: comp.a.composantes.evaluations, b: comp.b.composantes.evaluations },
  ].filter((l) => l.a !== null || l.b !== null);
  if (!data.length) return null;
  return (
    <Cadre titre={t("Comparaison des périodes, en %")} hauteur={220}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }} barGap={2}>
        <CartesianGrid stroke="#e2e8f0" vertical={false} />
        <XAxis dataKey="nom" {...AXE} axisLine={{ stroke: "#cbd5e1" }} interval={0} />
        <YAxis domain={[0, 100]} {...AXE} axisLine={false} />
        <Tooltip {...INFOBULLE} formatter={(v, n) => [`${v} %`, n]} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="a" name={t("Période 1")} fill="#94a3b8" radius={[4, 4, 0, 0]} maxBarSize={36} isAnimationActive={!reduit} />
        <Bar dataKey="b" name={t("Période 2")} fill={COULEURS.suivi} radius={[4, 4, 0, 0]} maxBarSize={36} isAnimationActive={!reduit} />
      </BarChart>
    </Cadre>
  );
}
