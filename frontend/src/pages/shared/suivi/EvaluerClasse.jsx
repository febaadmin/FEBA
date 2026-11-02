/** Évaluation collective : une compétence, une classe, un niveau par élève. Enregistrement tout ou rien. */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import { classesAPI, suiviAPI } from "../../../api";
import AideModule from "../../../components/ui/AideModule";
import PageHeader from "../../../components/ui/PageHeader";
import { extractApiError } from "../../../utils/errors";
import { t } from "../../../i18n";
import { AIDE_NIVEAUX } from "./niveaux";

const aujourdhui = () => new Date().toISOString().slice(0, 10);

export default function EvaluerClasse() {
  const qc = useQueryClient();
  const [classe, setClasse] = useState("");
  const [competence, setCompetence] = useState("");
  const [jour, setJour] = useState(aujourdhui());
  const [choix, setChoix] = useState({});
  const { data: cls } = useQuery({ queryKey: ["classes"], queryFn: () => classesAPI.list() });
  const { data: comps } = useQuery({ queryKey: ["suivi-competences", "actives"], queryFn: () => suiviAPI.competences({ actif: true }) });
  const { data: nivs } = useQuery({ queryKey: ["suivi-niveaux"], queryFn: () => suiviAPI.niveaux() });
  const { data: elv, isLoading } = useQuery({ queryKey: ["suivi-eleves", classe], queryFn: () => suiviAPI.eleves({ classe }), enabled: !!classe });
  const eleves = elv?.data?.results || [];
  const niveaux = nivs?.data || [];
  const competences = comps?.data?.results || [];
  const lignes = Object.entries(choix).filter(([, n]) => n);
  const enregistrer = useMutation({
    mutationFn: () => suiviAPI.evaluerLot({ date: jour, lignes: lignes.map(([student, niveau]) => ({ student: Number(student), competence: Number(competence), niveau })) }),
    onSuccess: (r) => { toast.success(t("{n} évaluation(s) enregistrée(s).", { n: r.data.creees })); setChoix({}); qc.invalidateQueries({ queryKey: ["suivi-competences"] }); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  return (
    <div className="space-y-4">
      <PageHeader title={t("Évaluer une classe")} subtitle={t("Une compétence, un niveau pour chaque élève")} action={<Link to="../referentiels" relative="path" className="btn-secondary text-sm">{t("Retour")}</Link>} />
      <AideModule cle="evaluer-classe" description={t("Les élèves laissés sans niveau ne sont pas évalués. Rien n'est écrasé : chaque évaluation s'ajoute à l'historique de l'élève.")} />
      {competences.length === 0 && comps && <p className="card text-sm text-slate-700">{t("Aucune compétence active.")} <Link className="text-primary underline" to="../referentiels" relative="path">{t("Créez vos compétences")}</Link></p>}
      <div className="card grid sm:grid-cols-3 gap-3">
        <div><label className="label" htmlFor="ec-cl">{t("Classe")} *</label><select id="ec-cl" className="input" value={classe} onChange={(e) => { setClasse(e.target.value); setChoix({}); }}><option value="">{t("Choisir")}</option>{(cls?.data?.results || cls?.data || []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
        <div><label className="label" htmlFor="ec-co">{t("Compétence")} *</label><select id="ec-co" className="input" value={competence} onChange={(e) => setCompetence(e.target.value)}><option value="">{t("Choisir")}</option>{competences.map((c) => <option key={c.id} value={c.id}>{c.nom} ({c.referentiel_nom})</option>)}</select></div>
        <div><label className="label" htmlFor="ec-da">{t("Date")} *</label><input id="ec-da" type="date" className="input" value={jour} onChange={(e) => setJour(e.target.value)} /></div>
      </div>
      {classe && competence && (
        <div className="card space-y-3">
          {isLoading && <p className="text-sm text-slate-500">{t("Chargement")}</p>}
          {!isLoading && eleves.length === 0 && <p className="text-sm text-slate-600">{t("Aucun élève de cette classe dans votre périmètre.")}</p>}
          {eleves.length > 0 && (
            <div className="flex flex-wrap gap-2 text-xs" aria-label={t("Tout le monde au même niveau")}>
              {niveaux.map((n) => <button key={n.id} type="button" className="btn-secondary text-xs" title={t(AIDE_NIVEAUX[n.code] || "")} onClick={() => setChoix(Object.fromEntries(eleves.map((e) => [e.id, n.id])))}>{t("Tous : {x}", { x: n.libelle })}</button>)}
            </div>
          )}
          <ul className="divide-y divide-slate-100">
            {eleves.map((e, i) => (
              <motion.li key={e.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i * 0.02, 0.3) }} className="py-2 flex flex-wrap items-center gap-2">
                <span className="flex-1 min-w-40 text-sm text-slate-900">{e.nom}</span>
                <div className="flex flex-wrap gap-1" role="radiogroup" aria-label={e.nom}>
                  {niveaux.map((n) => {
                    const actif = choix[e.id] === n.id;
                    return <button key={n.id} type="button" role="radio" aria-checked={actif} title={t(AIDE_NIVEAUX[n.code] || "")} onClick={() => setChoix({ ...choix, [e.id]: actif ? null : n.id })}
                      className={`rounded-full px-3 py-1 text-xs border transition-all ${actif ? "text-white shadow-sm scale-105" : "bg-white text-slate-600 border-slate-300 hover:border-slate-400"}`} style={actif ? { background: n.couleur, borderColor: n.couleur } : undefined}>{n.libelle}</button>;
                  })}
                </div>
              </motion.li>
            ))}
          </ul>
          {eleves.length > 0 && <div className="flex items-center justify-between gap-2"><span className="text-xs text-slate-600">{t("{a} élève(s) sur {b}", { a: lignes.length, b: eleves.length })}</span>
            <button type="button" className="btn-primary" disabled={!lignes.length || enregistrer.isPending} onClick={() => enregistrer.mutate()}>{t("Enregistrer les évaluations")}</button></div>}
        </div>
      )}
    </div>
  );
}
