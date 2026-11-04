/**
 * Tarifs et échéances : grille des tarifs par niveau et nature de frais pour une
 * année, liste détaillée (échéances, élèves exonérés, abonnés ou bénéficiant
 * d'une réduction) et historique des changements.
 *
 * Les montants viennent de FeeSchedule (une seule source, partagée avec les
 * relances, le paiement par carte et les analyses). La résolution affichée dans
 * la grille est celle du serveur : tarif du niveau, sinon de l'année, sinon permanent.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { feeSchedulesAPI, schoolsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import { useAcademy } from "../../context/AcademyContext";
import { useAcademyKey } from "../../hooks/useEntityContext";
import { t } from "../../i18n";
import { extractApiError } from "../../utils/errors";
import { formatDateTime } from "../../utils/datetime";
import { NATURES_FRAIS } from "../../utils/naturesFrais";
import { FeeEditor, SchedulesTab } from "./PaymentReminders";

const ONGLETS = [["grille", "Grille par niveau"], ["tarifs", "Tarifs et échéances"], ["historique", "Historique"]];
const liste = (q) => q.data?.data?.results || q.data?.data || [];

/** Tarif applicable à (niveau, année, nature) : niveau > année > permanent, comme le serveur. */
export function tarifApplicable(fees, levelId, yearId, nature) {
  const actifs = fees.filter((f) => f.is_active !== false && f.payment_type === nature);
  return actifs.find((f) => f.level === levelId && f.school_year === yearId)
    || actifs.find((f) => f.level === levelId && !f.school_year)
    || actifs.find((f) => !f.level && f.school_year === yearId)
    || actifs.find((f) => !f.level && !f.school_year)
    || null;
}

function Grille({ fees, years, levels, onEdit }) {
  const courante = years.find((y) => y.is_current) || years[0];
  const [annee, setAnnee] = useState(null);
  const yearId = annee ?? courante?.id ?? null;
  const natures = NATURES_FRAIS.filter(([code]) => fees.some((f) => f.payment_type === code));
  const niveaux = [...levels].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
  if (!fees.length) {
    return (
      <div className="card text-sm text-slate-600 space-y-2" data-testid="tarifs-vide">
        <p>{t("Aucun tarif n'est encore configuré pour cette académie : le montant attendu et le reste à payer ne peuvent pas être calculés.")}</p>
        <button type="button" className="btn-primary" onClick={() => onEdit({ school_year: yearId || "" })}>{t("Créer le premier tarif")}</button>
      </div>
    );
  }
  return (
    <div className="card space-y-3">
      <label className="text-sm flex items-center gap-2">{t("Année scolaire")}
        <select className="input !w-auto" value={yearId || ""} onChange={(e) => setAnnee(Number(e.target.value) || null)}>
          {years.map((y) => <option key={y.id} value={y.id}>{y.name}</option>)}
        </select>
      </label>
      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="tarifs-grille">
          <thead><tr className="text-left text-xs text-slate-500">
            <th className="py-2 pr-3 font-medium">{t("Niveau")}</th>
            {natures.map(([code, libelle]) => <th key={code} className="py-2 px-2 font-medium text-right">{t(libelle)}</th>)}
          </tr></thead>
          <tbody>
            {niveaux.map((niveau) => (
              <tr key={niveau.id} className="border-t border-slate-100">
                <td className="py-2 pr-3 font-medium text-slate-800">{niveau.name}</td>
                {natures.map(([code]) => {
                  const fee = tarifApplicable(fees, niveau.id, yearId, code);
                  const propre = fee && fee.level === niveau.id;
                  return (
                    <td key={code} className="py-2 px-2 text-right">
                      <button type="button" className="hover:underline tabular-nums" data-testid={`cellule-${niveau.id}-${code}`}
                        title={fee ? (propre ? t("Tarif propre à ce niveau") : t("Tarif général, hérité")) : t("Aucun tarif : cliquer pour en créer un")}
                        onClick={() => onEdit(propre ? fee : { payment_type: code, level: niveau.id, school_year: yearId || "" })}>
                        {fee ? <span className={propre ? "text-slate-900" : "text-slate-400 italic"}>{fee.amount_display}</span> : <span className="text-slate-300">-</span>}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-500">{t("En gris : tarif général hérité (année ou toutes années). Cliquer sur une case crée ou modifie le tarif propre au niveau.")}</p>
    </div>
  );
}

function Historique() {
  const academyKey = useAcademyKey();
  const q = useQuery({ queryKey: ["fee-changes", academyKey], queryFn: feeSchedulesAPI.historique });
  const lignes = q.data?.data || [];
  if (q.isPending) return <div className="card h-24 animate-pulse" />;
  if (!lignes.length) return <div className="card text-sm text-slate-500">{t("Aucun changement de tarif enregistré.")}</div>;
  return (
    <div className="card overflow-x-auto">
      <table className="w-full text-sm" data-testid="tarifs-historique">
        <thead><tr className="text-left text-xs text-slate-500">
          {["Date et heure", "Action", "Tarif", "Ancien montant", "Nouveau montant", "Motif", "Auteur"].map((h) => <th key={h} className="py-2 pr-3 font-medium">{t(h)}</th>)}
        </tr></thead>
        <tbody>
          {lignes.map((h) => (
            <tr key={h.id} className="border-t border-slate-100 align-top">
              <td className="py-2 pr-3 whitespace-nowrap">{formatDateTime(h.date)}</td>
              <td className="py-2 pr-3">{t(h.action_label)}</td>
              <td className="py-2 pr-3">{h.description}</td>
              <td className="py-2 pr-3 tabular-nums">{h.ancien || "-"}</td>
              <td className="py-2 pr-3 tabular-nums">{h.nouveau || "-"}</td>
              <td className="py-2 pr-3">{h.motif || "-"}</td>
              <td className="py-2 pr-3">{h.auteur || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Tarifs() {
  const { isAllAcademies } = useAcademy();
  const academyKey = useAcademyKey();
  const qc = useQueryClient();
  const [onglet, setOnglet] = useState("grille");
  const [edition, setEdition] = useState(null);
  const feesQ = useQuery({ queryKey: ["fee-schedules", academyKey], queryFn: feeSchedulesAPI.list, enabled: !isAllAcademies });
  const yearsQ = useQuery({ queryKey: ["years", academyKey], queryFn: schoolsAPI.years, enabled: !isAllAcademies });
  const levelsQ = useQuery({ queryKey: ["levels", academyKey], queryFn: schoolsAPI.levels, enabled: !isAllAcademies });
  const fees = useMemo(() => feesQ.data?.data || [], [feesQ.data]);
  const enregistrer = useMutation({
    mutationFn: (f) => {
      const corps = { ...f, school_year: f.school_year || null, level: f.level || null };
      return f.id ? feeSchedulesAPI.update(f.id, corps) : feeSchedulesAPI.create(corps);
    },
    onSuccess: () => {
      setEdition(null);
      ["fee-schedules", "fee-changes"].forEach((k) => qc.invalidateQueries({ queryKey: [k, academyKey] }));
      toast.success(t("Tarif enregistré."));
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const ouvrir = (f) => setEdition(f.id ? {
    ...f, amount: f.amount_value, school_year: f.school_year || "", level: f.level || "", motif: "",
    installments: f.installments.map((i) => ({ id: i.id, label: i.label, due_date: i.due_date, amount: i.amount_value })),
  } : { payment_type: f.payment_type || "mensualite", label: "", school_year: f.school_year || "", level: f.level || "",
    amount: "", is_mandatory: true, installment_mode: "split", is_active: true, installments: [], motif: "" });

  return (
    <div className="space-y-4">
      <PageHeader title={t("Tarifs et échéances")} subtitle={t("Montants dus par niveau et nature de frais, échéanciers, réductions et exonérations")} />
      {isAllAcademies ? (
        <div className="card text-sm text-slate-600" data-testid="tarifs-choisir-academie">
          {t("Sélectionnez une académie en haut de la page : chaque académie a ses propres tarifs, dans sa devise.")}
        </div>
      ) : (
        <>
          <div className="flex flex-wrap gap-2" role="tablist">
            {ONGLETS.map(([id, libelle]) => (
              <button key={id} type="button" role="tab" aria-selected={onglet === id} onClick={() => setOnglet(id)} data-testid={`onglet-${id}`}
                className={`px-3 py-1.5 rounded-xl text-sm font-medium ${onglet === id ? "bg-feba-navy text-white" : "bg-white border border-slate-200 text-slate-600"}`}>
                {t(libelle)}
              </button>
            ))}
          </div>
          {feesQ.isError && <div className="card text-sm text-red-700">{extractApiError(feesQ.error)}</div>}
          {onglet === "grille" && !feesQ.isPending && (
            <Grille fees={fees} years={liste(yearsQ)} levels={liste(levelsQ)} onEdit={ouvrir} />
          )}
          {onglet === "tarifs" && <SchedulesTab />}
          {onglet === "historique" && <Historique />}
          {edition && (
            <FeeEditor fee={edition} years={liste(yearsQ)} levels={liste(levelsQ)} saving={enregistrer.isPending}
              onCancel={() => setEdition(null)} onSave={(f) => enregistrer.mutate(f)} />
          )}
        </>
      )}
    </div>
  );
}
