/** Rapports d'un élève : générés depuis les données réelles, rédigés, validés, puis publiés. */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { suiviAPI } from "../../../api";
import ConfirmDialog from "../../../components/ui/ConfirmDialog";
import { extractApiError } from "../../../utils/errors";
import { t } from "../../../i18n";

const TYPES = [["hebdomadaire", "Hebdomadaire"], ["mensuel", "Mensuel"], ["trimestriel", "Trimestriel"], ["annuel", "Annuel"], ["demande", "À la demande"]];
const STATUTS = { brouillon: "Brouillon", valide: "Validé", publie: "Publié" };
const RUBRIQUES = [["bilan", "Bilan général"], ["points_forts", "Points forts"], ["points_ameliorer", "Points à améliorer"], ["difficultes", "Difficultés"], ["recommandations", "Recommandations pédagogiques"], ["appreciation", "Appréciation de l'enseignant"]];

function Rapport({ r, gere, onAction }) {
  const [contenu, setContenu] = useState(r.contenu || {});
  const brouillon = r.statut === "brouillon";
  const [confirmer, setConfirmer] = useState(false);
  const pdf = async () => {
    const res = await suiviAPI.pdfRapport(r.id);
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url; a.download = `rapport-${r.id}.pdf`; a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <div className="border border-slate-200 rounded-lg p-3 space-y-2">
      <div className="flex flex-wrap justify-between gap-2 text-sm">
        <span className="font-medium text-slate-900">{t(TYPES.find(([k]) => k === r.type)?.[1])} - {r.du} - {r.au}</span>
        <span className="text-slate-700">{t(STATUTS[r.statut])} - {t("version {n}", { n: r.numero_version })}</span>
      </div>
      {RUBRIQUES.map(([cle, libelle]) => (
        gere && brouillon ? (
          <div key={cle}><label className="label" htmlFor={`r${r.id}-${cle}`}>{t(libelle)}</label>
            <textarea id={`r${r.id}-${cle}`} className="input" rows={2} value={contenu[cle] || ""} onChange={(e) => setContenu({ ...contenu, [cle]: e.target.value })} /></div>
        ) : (
          <div key={cle} className="text-sm"><p className="text-xs text-slate-500">{t(libelle)}</p><p className="text-slate-800 whitespace-pre-wrap">{contenu[cle] || t("Non renseigné")}</p></div>
        )
      ))}
      <div className="flex flex-wrap gap-2 pt-1">
        <button type="button" className="btn-secondary text-sm" onClick={pdf}>{t("Télécharger le PDF")}</button>
        {gere && brouillon && <button type="button" className="btn-secondary text-sm" onClick={() => onAction(() => suiviAPI.modifierRapport(r.id, contenu))}>{t("Enregistrer")}</button>}
        {gere && brouillon && <button type="button" className="btn-primary text-sm" onClick={() => onAction(async () => { await suiviAPI.modifierRapport(r.id, contenu); await suiviAPI.validerRapport(r.id); })}>{t("Valider")}</button>}
        {gere && r.statut === "valide" && <button type="button" className="btn-primary text-sm" onClick={() => setConfirmer(true)}>{t("Publier")}</button>}
        {gere && r.statut === "publie" && <button type="button" className="btn-secondary text-sm" onClick={() => onAction(() => suiviAPI.nouvelleVersionRapport(r.id))}>{t("Créer une nouvelle version")}</button>}
      </div>
      <ConfirmDialog open={confirmer} onClose={() => setConfirmer(false)} onConfirm={() => { setConfirmer(false); onAction(() => suiviAPI.publierRapport(r.id)); }}
        message={t("Publier ce rapport ? Si l'académie a ouvert le suivi aux familles, il sera visible par l'élève et ses parents.")} />
    </div>
  );
}

export default function Rapports({ eleve, gere }) {
  const qc = useQueryClient();
  const [f, setF] = useState({ type: "mensuel", du: "", au: "" });
  const { data, isLoading } = useQuery({ queryKey: ["suivi-rapports", eleve], queryFn: () => suiviAPI.rapports({ student: eleve }) });
  const opts = { onSuccess: () => { toast.success(t("Enregistré.")); qc.invalidateQueries({ queryKey: ["suivi-rapports", eleve] }); }, onError: (e) => toast.error(extractApiError(e)) };
  const action = useMutation({ mutationFn: (fn) => fn(), ...opts });
  const creer = useMutation({ mutationFn: () => suiviAPI.creerRapport({ ...f, student: Number(eleve) }), ...opts });
  const liste = data?.data?.results || [];
  return (
    <div className="card space-y-3">
      <h2 className="text-sm font-semibold text-slate-800">{t("Rapports pédagogiques")}</h2>
      {gere && (
        <form className="flex flex-wrap gap-2 items-end" onSubmit={(e) => { e.preventDefault(); creer.mutate(); }}>
          <div><label className="label" htmlFor="rap-type">{t("Type")}</label><select id="rap-type" className="input" value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}>{TYPES.map(([k, l]) => <option key={k} value={k}>{t(l)}</option>)}</select></div>
          <div><label className="label" htmlFor="rap-du">{t("Du")}</label><input id="rap-du" required type="date" className="input" value={f.du} onChange={(e) => setF({ ...f, du: e.target.value })} /></div>
          <div><label className="label" htmlFor="rap-au">{t("Au")}</label><input id="rap-au" required type="date" className="input" value={f.au} onChange={(e) => setF({ ...f, au: e.target.value })} /></div>
          <button type="submit" className="btn-primary" disabled={creer.isPending}>{t("Générer le rapport")}</button>
        </form>
      )}
      {isLoading && <p className="text-sm text-slate-500">{t("Chargement")}</p>}
      {!isLoading && liste.length === 0 && <p className="text-sm text-slate-500">{t("Aucun rapport pour le moment.")}</p>}
      {liste.map((r) => <Rapport key={`${r.id}-${r.statut}-${r.numero_version}`} r={r} gere={gere} onAction={(fn) => action.mutate(fn)} />)}
    </div>
  );
}
