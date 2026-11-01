/** Alertes à examiner. Chacune dit sa règle et ses données ; la décision appartient à l'enseignant. */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import toast from "react-hot-toast";
import { suiviAPI } from "../../../api";
import PageHeader from "../../../components/ui/PageHeader";
import { useAuth } from "../../../hooks/useAuth";
import { extractApiError } from "../../../utils/errors";
import { t } from "../../../i18n";

const CATEGORIES = { positif: "Progression positive", attention: "Attention", surveiller: "À surveiller", objectif: "Objectif atteint" };
const REGLES = { baisse_resultats: "Baisse de résultat (points)", progression_positive: "Hausse de résultat (points)", stagnation: "Évaluations au même niveau", absences: "Absences sur 30 jours", difficultes: "Compétences au premier niveau", objectif_atteint: "Objectif atteint" };

export default function Alertes() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const admin = user?.role === "admin" || user?.role === "superadmin";
  const [statut, setStatut] = useState("nouvelle");
  const { data, isLoading } = useQuery({ queryKey: ["suivi-alertes", statut], queryFn: () => suiviAPI.alertes(statut ? { statut } : {}) });
  const { data: regles } = useQuery({ queryKey: ["suivi-regles"], queryFn: () => suiviAPI.reglesAlertes(), enabled: admin });
  const rafraichir = () => { qc.invalidateQueries({ queryKey: ["suivi-alertes"] }); qc.invalidateQueries({ queryKey: ["suivi-regles"] }); };
  const erreur = { onError: (e) => toast.error(extractApiError(e)) };
  const decider = useMutation({ mutationFn: ({ id, decision }) => suiviAPI.deciderAlerte(id, { decision }), onSuccess: rafraichir, ...erreur });
  const detecter = useMutation({ mutationFn: () => suiviAPI.detecterAlertes(), onSuccess: (r) => { toast.success(t("{n} nouvelle(s) alerte(s).", { n: r.data.nouvelles })); rafraichir(); }, ...erreur });
  const regle = useMutation({ mutationFn: (d) => suiviAPI.modifierRegle(d), onSuccess: rafraichir, ...erreur });
  const liste = data?.data?.results || [];
  return (
    <div className="space-y-4">
      <PageHeader title={t("Alertes pédagogiques")} subtitle={t("Des signaux à examiner, jamais un diagnostic")}
        action={<Link to=".." relative="path" className="btn-secondary text-sm">{t("Retour")}</Link>} />
      <div className="card flex flex-wrap gap-2 items-center">
        <select className="input w-auto" aria-label={t("Statut")} value={statut} onChange={(e) => setStatut(e.target.value)}>
          <option value="nouvelle">{t("Nouvelles")}</option><option value="acceptee">{t("Acceptées")}</option><option value="modifiee">{t("Modifiées")}</option><option value="refusee">{t("Refusées")}</option><option value="">{t("Toutes")}</option>
        </select>
        <button type="button" className="btn-secondary text-sm" disabled={detecter.isPending} onClick={() => detecter.mutate()}>{t("Vérifier maintenant")}</button>
      </div>
      <div className="card space-y-3">
        {isLoading && <p className="text-sm text-slate-500">{t("Chargement")}</p>}
        {!isLoading && liste.length === 0 && <p className="text-sm text-slate-500">{t("Aucune alerte.")}</p>}
        {liste.map((a) => (
          <div key={a.id} className="border border-slate-200 rounded-lg p-3 space-y-1">
            <p className="text-xs font-medium text-slate-600">{t(CATEGORIES[a.categorie])} - {a.eleve}</p>
            <p className="text-sm text-slate-900">{a.message}</p>
            <p className="text-sm text-slate-600">{t("Recommandation")} : {a.recommandation}</p>
            {a.statut === "nouvelle" && (
              <div className="flex gap-2 pt-1">
                <button type="button" className="btn-secondary text-xs" onClick={() => decider.mutate({ id: a.id, decision: "acceptee" })}>{t("Accepter")}</button>
                <button type="button" className="btn-secondary text-xs" onClick={() => decider.mutate({ id: a.id, decision: "refusee" })}>{t("Refuser")}</button>
              </div>
            )}
          </div>
        ))}
      </div>
      {admin && (
        <div className="card space-y-2">
          <h2 className="text-sm font-semibold text-slate-800">{t("Règles de l'académie")}</h2>
          {(regles?.data || []).map((r) => (
            <div key={r.code} className="flex flex-wrap items-center gap-3 text-sm">
              <label className="flex items-center gap-2 flex-1 min-w-48"><input type="checkbox" checked={r.actif} onChange={(e) => regle.mutate({ code: r.code, actif: e.target.checked })} />{t(REGLES[r.code])}</label>
              <input key={r.seuil} type="number" min="1" className="input w-20" aria-label={t("Seuil")} defaultValue={r.seuil}
                onBlur={(e) => Number(e.target.value) !== r.seuil && regle.mutate({ code: r.code, seuil: Number(e.target.value) })} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
