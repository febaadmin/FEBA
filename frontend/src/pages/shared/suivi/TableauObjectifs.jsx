/**
 * Tableau des objectifs. Glisser une carte change le statut ; la liste de chaque
 * carte fait la même chose au clavier et sur téléphone. Un objectif atteint est salué.
 */
import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Target } from "lucide-react";
import { t } from "../../../i18n";

export const COLONNES = [
  ["a_commencer", "À commencer"], ["en_cours", "En cours"], ["a_verifier", "À vérifier"], ["atteint", "Atteint"], ["non_atteint", "Non atteint"], ["reporte", "Reporté"], ["abandonne", "Abandonné"],
];
const PRINCIPALES = ["a_commencer", "en_cours", "a_verifier", "atteint"];
const PRIORITES = { haute: "bg-red-100 text-red-800", normale: "bg-slate-100 text-slate-700", basse: "bg-slate-50 text-slate-500" };

function Carte({ o, gere, deplacer, ajouterAction, majAction, fete }) {
  return (
    <motion.article layout initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.96 }}
      draggable={gere} onDragStart={(e) => e.dataTransfer.setData("text/plain", String(o.id))}
      className={`relative rounded-xl border border-slate-200 bg-white p-3 space-y-1 shadow-sm hover:shadow-md transition-shadow ${gere ? "cursor-grab active:cursor-grabbing" : ""}`}>
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-medium text-slate-900">{o.titre}{o.class_obj ? ` (${t("collectif")})` : ""}</h3>
        <span className={`rounded-full px-2 py-0.5 text-[11px] whitespace-nowrap ${PRIORITES[o.priorite]}`}>{t({ haute: "Haute", normale: "Normale", basse: "Basse" }[o.priorite])}</span>
      </div>
      {o.description && <p className="text-xs text-slate-600">{o.description}</p>}
      {o.resultat_attendu && <p className="text-xs text-slate-600">{t("Résultat attendu")} : {o.resultat_attendu}</p>}
      {o.criteres_reussite && <p className="text-xs text-slate-600">{t("Critères de réussite")} : {o.criteres_reussite}</p>}
      {o.competence_nom && <p className="text-xs text-slate-500">{t("Compétence")} : {o.competence_nom}</p>}
      {o.date_cible && <p className={`text-xs ${new Date(o.date_cible) < new Date() && !["atteint", "non_atteint", "abandonne"].includes(o.statut) ? "text-red-700 font-medium" : "text-slate-500"}`}>{t("Date cible")} : {o.date_cible}</p>}
      {o.actions.map((a) => (
        <div key={a.id} className="text-xs text-slate-700 flex flex-wrap justify-between gap-2 border-t border-slate-100 pt-1">
          <span>{a.description}</span>
          {a.realisee_le ? <span className="text-green-700">{t("Réalisée le")} {a.realisee_le}</span>
            : gere && <button type="button" className="text-primary underline" onClick={() => majAction(a.id)}>{t("Marquer réalisée")}</button>}
        </div>
      ))}
      {gere && (
        <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
          <button type="button" className="text-xs text-primary underline" onClick={() => ajouterAction(o.id)}>{t("Ajouter une action")}</button>
          <select className="text-xs border border-slate-200 rounded-md px-1 py-0.5" aria-label={t("Statut de {x}", { x: o.titre })} value={o.statut} onChange={(e) => deplacer(o.id, e.target.value)}>
            {COLONNES.map(([v, l]) => <option key={v} value={v}>{t(l)}</option>)}
          </select>
        </div>
      )}
      <AnimatePresence>
        {fete === o.id && (
          <motion.div initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 rounded-xl bg-green-50/95 flex items-center justify-center text-sm font-medium text-green-800" role="status">
            {t("Objectif atteint, bravo !")}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.article>
  );
}

export default function TableauObjectifs({ objectifs, gere, majStatut, ajouterAction, majAction }) {
  const [survol, setSurvol] = useState(null);
  const [fete, setFete] = useState(null);
  const deplacer = (id, statut) => {
    const o = objectifs.find((x) => x.id === id);
    if (!o || o.statut === statut) return;
    majStatut(id, statut);
    if (statut === "atteint") { setFete(id); setTimeout(() => setFete(null), 1800); }
  };
  const visibles = COLONNES.filter(([k]) => PRINCIPALES.includes(k) || objectifs.some((o) => o.statut === k));
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {visibles.map(([cle, libelle]) => {
        const lignes = objectifs.filter((o) => o.statut === cle);
        return (
          <section key={cle} aria-label={t(libelle)} onDragOver={(e) => { if (gere) { e.preventDefault(); setSurvol(cle); } }} onDragLeave={() => setSurvol(null)}
            onDrop={(e) => { e.preventDefault(); setSurvol(null); deplacer(Number(e.dataTransfer.getData("text/plain")), cle); }}
            className={`rounded-2xl p-3 space-y-2 min-h-32 border-2 border-dashed transition-colors ${survol === cle ? "border-primary bg-blue-50" : "border-transparent bg-slate-100/70"}`}>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-600 flex items-center justify-between">{t(libelle)}<span className="rounded-full bg-white px-2 py-0.5 text-slate-700">{lignes.length}</span></h3>
            <AnimatePresence>{lignes.map((o) => <Carte key={o.id} o={o} gere={gere} deplacer={deplacer} ajouterAction={ajouterAction} majAction={majAction} fete={fete} />)}</AnimatePresence>
            {!lignes.length && <p className="text-xs text-slate-500 flex items-center gap-1 py-2"><Target className="w-3 h-3" aria-hidden="true" />{gere ? t("Déposez un objectif ici") : t("Aucun")}</p>}
          </section>
        );
      })}
    </div>
  );
}
