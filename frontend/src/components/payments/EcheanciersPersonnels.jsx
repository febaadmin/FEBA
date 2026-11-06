/**
 * Échéanciers personnalisés : adapter les échéances d'UN élève pour un tarif et une
 * année (délai supplémentaire, autre répartition) sans toucher au tarif de sa classe
 * ni aux paiements déjà enregistrés. La somme doit rester égale au montant du tarif
 * (une réduction se définit à part, comme remise). Rien n'est supprimé : revenir à
 * l'échéancier standard désactive l'échéancier personnel, et tout est tracé.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { Plus, Trash2 } from "lucide-react";
import { echeanciersAPI, feeSchedulesAPI, paymentsAPI, studentsAPI } from "../../api";
import { useAcademyKey } from "../../hooks/useEntityContext";
import { t } from "../../i18n";
import { extractApiError } from "../../utils/errors";
import { formatCalendarDate } from "../../utils/datetime";
import { formatMoney } from "../../utils/money";

const liste = (q) => q.data?.data?.results || q.data?.data || [];

export default function EcheanciersPersonnels() {
  const academyKey = useAcademyKey();
  const qc = useQueryClient();
  const [choix, setChoix] = useState({ student: "", fee_schedule: "", school_year: "" });
  const [lignes, setLignes] = useState([]);
  const [motif, setMotif] = useState("");
  const existantsQ = useQuery({ queryKey: ["echeanciers-eleves", academyKey], queryFn: () => echeanciersAPI.list() });
  const elevesQ = useQuery({ queryKey: ["eleves-liste", academyKey], queryFn: () => studentsAPI.list({ is_active: true }) });
  const tarifsQ = useQuery({ queryKey: ["fee-schedules", academyKey], queryFn: feeSchedulesAPI.list });
  const filtresQ = useQuery({ queryKey: ["paiements-filtres", academyKey], queryFn: () => paymentsAPI.filtres() });
  const tarifs = liste(tarifsQ).filter((f) => f.is_active !== false);
  const annees = filtresQ.data?.data?.annees || [];
  const tarif = tarifs.find((f) => String(f.id) === String(choix.fee_schedule));
  const mineur = (v) => Math.round(Number(v || 0) * 100);
  const cible = !tarif ? null : tarif.installment_mode === "split" ? mineur(tarif.amount_value)
    : tarif.installments.reduce((s, i) => s + mineur(i.amount_value), 0);
  const total = lignes.reduce((s, l) => s + Math.round(Number(l.montant || 0) * 100), 0);

  const partir = (f) => {
    setChoix((c) => ({ ...c, fee_schedule: f, school_year: c.school_year || (tarifs.find((x) => String(x.id) === String(f))?.school_year ?? annees[0]?.id ?? "") }));
    const tf = tarifs.find((x) => String(x.id) === String(f));
    setLignes((tf?.installments || []).map((i) => ({ label: i.label, due_date: i.due_date, montant: i.amount_value })));
  };
  const definir = useMutation({
    mutationFn: () => echeanciersAPI.definir({ ...choix, motif, echeances: lignes }),
    onSuccess: () => {
      ["echeanciers-eleves", "journal-financier"].forEach((k) => qc.invalidateQueries({ queryKey: [k, academyKey] }));
      qc.invalidateQueries({ queryKey: ["situation"] });
      toast.success(t("Échéancier personnel enregistré."));
      setLignes([]); setMotif(""); setChoix({ student: "", fee_schedule: "", school_year: "" });
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const retablir = useMutation({
    mutationFn: (g) => echeanciersAPI.retablir({ student: g.eleve_id, fee_schedule: g.tarif_id, school_year: g.annee_id, motif: g.motif }),
    onSuccess: () => {
      ["echeanciers-eleves", "journal-financier"].forEach((k) => qc.invalidateQueries({ queryKey: [k, academyKey] }));
      qc.invalidateQueries({ queryKey: ["situation"] });
      toast.success(t("Retour à l'échéancier standard."));
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const pret = choix.student && choix.fee_schedule && choix.school_year && lignes.length > 0 && motif.trim() && cible === total;

  return (
    <div className="space-y-3" data-testid="echeanciers-personnels">
      <form className="card space-y-3" onSubmit={(e) => { e.preventDefault(); if (pret) definir.mutate(); }}>
        <h3 className="font-semibold text-slate-800">{t("Adapter l'échéancier d'un élève")}</h3>
        <p className="text-xs text-slate-500">{t("Délai supplémentaire ou autre répartition, pour cet élève uniquement. Les paiements déjà enregistrés sont conservés et réimputés.")}</p>
        <div className="grid sm:grid-cols-3 gap-3">
          <label className="text-sm"><span className="label">{t("Élève")}</span>
            <select className="input" value={choix.student} onChange={(e) => setChoix((c) => ({ ...c, student: e.target.value }))} data-testid="ep-eleve">
              <option value="">{t("Choisir")}</option>
              {liste(elevesQ).map((s) => <option key={s.id} value={s.id}>{s.full_name || `${s.first_name} ${s.last_name}`}</option>)}
            </select></label>
          <label className="text-sm"><span className="label">{t("Tarif")}</span>
            <select className="input" value={choix.fee_schedule} onChange={(e) => partir(e.target.value)} data-testid="ep-tarif">
              <option value="">{t("Choisir")}</option>
              {tarifs.map((f) => <option key={f.id} value={f.id}>{f.label || t(f.payment_type_label)} · {f.amount_display}</option>)}
            </select></label>
          <label className="text-sm"><span className="label">{t("Année scolaire")}</span>
            <select className="input" value={choix.school_year} onChange={(e) => setChoix((c) => ({ ...c, school_year: e.target.value }))}>
              <option value="">{t("Choisir")}</option>{annees.map((a) => <option key={a.id} value={a.id}>{a.nom}</option>)}
            </select></label>
        </div>
        {tarif && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-xs text-slate-500">
                  {["Libellé", "Date limite", "Montant", ""].map((h) => <th key={h} className="py-1.5 pr-3 font-medium">{h && t(h)}</th>)}
                </tr></thead>
                <tbody>
                  {lignes.map((l, i) => (
                    <tr key={i} className="border-t border-slate-100">
                      <td className="py-1.5 pr-3"><input className="input" aria-label={t("Libellé")} value={l.label} maxLength={80}
                        onChange={(e) => setLignes(lignes.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))} /></td>
                      <td className="py-1.5 pr-3"><input className="input" type="date" aria-label={t("Date limite")} required value={l.due_date}
                        onChange={(e) => setLignes(lignes.map((x, j) => (j === i ? { ...x, due_date: e.target.value } : x)))} /></td>
                      <td className="py-1.5 pr-3"><input className="input" type="number" min="0" step="any" aria-label={t("Montant")} required value={l.montant}
                        onChange={(e) => setLignes(lignes.map((x, j) => (j === i ? { ...x, montant: e.target.value } : x)))} /></td>
                      <td className="py-1.5"><button type="button" aria-label={t("Retirer l'échéance")} className="p-1.5 text-slate-400 hover:text-red-700"
                        onClick={() => setLignes(lignes.filter((_, j) => j !== i))}><Trash2 className="w-4 h-4" /></button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <button type="button" className="btn-secondary inline-flex items-center gap-1" onClick={() => setLignes([...lignes, { label: "", due_date: "", montant: "" }])}>
                <Plus className="w-4 h-4" aria-hidden="true" />{t("Ajouter une échéance")}
              </button>
              <span className={`tabular-nums ${cible === total ? "text-emerald-700" : "text-red-700"}`} role="status" data-testid="ep-somme">
                {t("Total")} {formatMoney(total / 100, tarif.currency)} / {formatMoney(cible / 100, tarif.currency)} {cible === total ? "✓" : `· ${t("la somme doit être égale au montant du tarif")}`}
              </span>
            </div>
            <label className="text-sm block"><span className="label">{t("Motif")}</span>
              <input className="input" required value={motif} onChange={(e) => setMotif(e.target.value)} placeholder={t("Ex. accord du 5 novembre avec la famille")} /></label>
            <div className="flex justify-end"><button type="submit" className="btn-primary" disabled={!pret || definir.isPending} data-testid="ep-enregistrer">{t("Enregistrer l'échéancier")}</button></div>
          </>
        )}
      </form>

      <div className="card space-y-2">
        <h3 className="font-semibold text-slate-800">{t("Échéanciers personnels en vigueur")}</h3>
        {existantsQ.isPending ? <div className="h-16 rounded-xl bg-slate-100 animate-pulse motion-reduce:animate-none" /> : liste(existantsQ).length === 0 ? (
          <p className="text-sm text-slate-500">{t("Aucun échéancier personnel : tous les élèves suivent l'échéancier standard de leur tarif.")}</p>
        ) : (
          <ul className="divide-y divide-slate-100 text-sm" data-testid="ep-liste">
            {liste(existantsQ).map((g) => (
              <li key={`${g.eleve_id}-${g.tarif_id}-${g.annee_id}`} className="py-2 flex flex-wrap justify-between gap-2">
                <span><strong>{g.eleve}</strong> · {g.tarif} · {g.annee}
                  <span className="block text-xs text-slate-500">{g.echeances.map((e) => `${e.label} ${formatCalendarDate(e.due_date)} ${e.montant}`).join(" · ")}</span></span>
                <button type="button" className="text-xs text-red-700 hover:underline" onClick={() => {
                  const m = window.prompt(t("Motif du retour à l'échéancier standard (obligatoire) :"));
                  if (m && m.trim()) retablir.mutate({ ...g, motif: m.trim() });
                }}>{t("Revenir à l'échéancier standard")}</button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
