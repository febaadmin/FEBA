/**
 * Relevé financier d'un élève : totaux, échéances (dû, payé, restant, statut)
 * et paiements. Données calculées par le serveur (compute_dues) ; utilisé par
 * le personnel et par les parents (pour leurs enfants uniquement).
 */
import { useQuery } from "@tanstack/react-query";
import { paymentsAPI } from "../../api";
import { t } from "../../i18n";
import { formatCalendarDate } from "../../utils/datetime";

const TON = { overdue: "bg-red-50 text-red-700", partial: "bg-amber-50 text-amber-700", paid: "bg-emerald-50 text-emerald-700",
  upcoming: "bg-slate-100 text-slate-600", exempted: "bg-primary-50 text-primary-700" };

export function Totaux({ totaux, testid }) {
  const cartes = [["Attendu", totaux.attendu_affiche], ["Payé", totaux.paye_affiche], ["Reste à payer", totaux.restant_affiche],
    ["Dont en retard", totaux.retard_affiche], ["Recouvrement", totaux.taux_recouvrement === null ? t("Non calculable") : `${totaux.taux_recouvrement} %`]];
  return (
    <div className="grid grid-cols-2 sm:grid-cols-5 gap-2" data-testid={testid}>
      {cartes.map(([titre, valeur]) => (
        <div key={titre} className="rounded-xl border border-slate-100 bg-slate-50/60 p-3">
          <p className="text-xs text-slate-500">{t(titre)}</p>
          <p className="font-bold text-slate-900 tabular-nums">{valeur}</p>
        </div>
      ))}
    </div>
  );
}

export default function ReleveEleve({ eleveId, academyKey }) {
  const q = useQuery({ queryKey: ["situation-eleve", academyKey, eleveId], queryFn: () => paymentsAPI.situationEleve(eleveId), enabled: Boolean(eleveId) });
  const s = q.data?.data;
  if (q.isPending) return <div className="h-40 rounded-xl bg-slate-100 animate-pulse" />;
  if (q.isError || !s) return <p role="alert" className="text-sm text-red-700">{t("La situation financière n'a pas pu être chargée.")}</p>;
  return (
    <div className="space-y-4 text-sm" data-testid="releve-eleve">
      <Totaux totaux={s.totaux} testid="releve-totaux" />
      {s.totaux.hors_echeancier_minor > 0 && (
        <p className="text-xs text-slate-600">{t("Paiements hors échéancier (nature sans tarif ou trop-perçu)")} : <strong>{s.totaux.hors_echeancier_affiche}</strong></p>
      )}
      {!s.echeancier_configure ? (
        <p className="text-slate-500">{t("Aucun tarif ne s'applique à cet élève : le montant dû n'est pas calculable.")}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full" data-testid="releve-echeances">
            <thead><tr className="text-left text-xs text-slate-500">
              {["Frais", "Échéance", "Date", "Dû", "Payé", "Reste", "Statut"].map((h) => <th key={h} className="py-1.5 pr-3 font-medium">{t(h)}</th>)}
            </tr></thead>
            <tbody>
              {s.echeances.map((e) => (
                <tr key={`${e.fee_id}-${e.installment_id}`} className="border-t border-slate-100">
                  <td className="py-1.5 pr-3">{e.fee_label}</td>
                  <td className="py-1.5 pr-3">{e.installment_label}</td>
                  <td className="py-1.5 pr-3 whitespace-nowrap">{formatCalendarDate(e.due_date)}</td>
                  <td className="py-1.5 pr-3 tabular-nums">{e.expected_display}</td>
                  <td className="py-1.5 pr-3 tabular-nums">{e.paid_display}</td>
                  <td className="py-1.5 pr-3 tabular-nums">{e.outstanding_display}</td>
                  <td className="py-1.5 pr-3"><span className={`badge ${TON[e.status] || ""}`}>{t(e.status_label)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {s.paiements.length > 0 && (
        <div>
          <h4 className="font-semibold text-slate-800 mb-1">{t("Paiements")}</h4>
          <ul className="divide-y divide-slate-100">
            {s.paiements.map((p) => (
              <li key={p.id} className="py-1.5 flex flex-wrap justify-between gap-2">
                <span>{formatCalendarDate(p.date)} · {t(p.nature)} · {t(p.mode)} · {p.reference}</span>
                <span className={`tabular-nums ${p.statut === "annulé" ? "line-through text-slate-400" : ""}`}>
                  {p.montant}{p.rembourse ? ` (${t("remboursé")} ${p.rembourse})` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
