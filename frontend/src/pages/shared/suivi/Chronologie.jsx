/** Frise de tout ce qui s'est passé pour l'élève, filtrable par type. */
import { useState } from "react";
import { motion } from "framer-motion";
import { Award, BookCheck, ClipboardCheck, FileText, HeartHandshake, MessageCircle, Target } from "lucide-react";
import { t } from "../../../i18n";
import { COLONNES } from "./TableauObjectifs";

const TYPES = {
  competence: { label: "Compétences", Icone: Award, cls: "bg-violet-100 text-violet-800" },
  evaluation: { label: "Évaluations du suivi", Icone: BookCheck, cls: "bg-blue-100 text-blue-800" },
  examen: { label: "Examens en ligne", Icone: ClipboardCheck, cls: "bg-indigo-100 text-indigo-800" },
  objectif: { label: "Objectifs", Icone: Target, cls: "bg-emerald-100 text-emerald-800" },
  plan: { label: "Accompagnement", Icone: HeartHandshake, cls: "bg-amber-100 text-amber-800" },
  rapport: { label: "Rapports", Icone: FileText, cls: "bg-slate-200 text-slate-800" },
  observation: { label: "Participation", Icone: MessageCircle, cls: "bg-sky-100 text-sky-800" },
};

export default function Chronologie({ evenements }) {
  const [filtre, setFiltre] = useState("");
  const presents = Object.keys(TYPES).filter((k) => evenements.some((e) => e.type === k));
  const lignes = evenements.filter((e) => !filtre || e.type === filtre);
  if (!evenements.length) return <p className="card text-sm text-slate-600">{t("Rien n'est encore enregistré pour cet élève. Chaque évaluation, objectif ou rapport apparaîtra ici.")}</p>;
  return (
    <div className="card space-y-4">
      <div className="flex flex-wrap gap-1">
        <button type="button" onClick={() => setFiltre("")} className={`rounded-full px-3 py-1 text-xs ${!filtre ? "bg-primary text-white" : "bg-slate-100 text-slate-700"}`}>{t("Toutes")}</button>
        {presents.map((k) => <button key={k} type="button" onClick={() => setFiltre(k)} className={`rounded-full px-3 py-1 text-xs ${filtre === k ? "bg-primary text-white" : "bg-slate-100 text-slate-700"}`}>{t(TYPES[k].label)}</button>)}
      </div>
      <ol className="relative border-l-2 border-slate-200 ml-3 space-y-3">
        {lignes.map((e, i) => {
          const { Icone, cls } = TYPES[e.type];
          const detail = e.statut ? t(COLONNES.find(([k]) => k === e.statut)?.[1] || e.statut) : e.detail;
          return (
            <motion.li key={`${e.type}-${i}`} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: Math.min(i * 0.02, 0.4) }} className="ml-5 relative">
              <span className={`absolute -left-[33px] top-0 w-6 h-6 rounded-full flex items-center justify-center ${cls}`}><Icone className="w-3 h-3" aria-hidden="true" /></span>
              <p className="text-xs text-slate-500">{e.date}</p>
              <p className="text-sm text-slate-900">{e.titre}{detail ? <span className="text-slate-600"> - {detail}</span> : null}</p>
            </motion.li>
          );
        })}
      </ol>
    </div>
  );
}
