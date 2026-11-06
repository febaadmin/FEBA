/**
 * Fiche financière d'un élève : comment le reste dû est calculé (frais théoriques,
 * exonérations, remises, net, payé, reste, retard), tarifs appliqués et ajustements
 * retenus ou écartés, échéances (standard ou personnelles), paiements et reçus,
 * historique des décisions (personnel uniquement : le serveur ne l'envoie pas aux parents).
 *
 * Tout est calculé par le serveur (compute_dues) ; utilisé par le personnel et par
 * les parents (pour leurs enfants uniquement).
 */
import { useQuery } from "@tanstack/react-query";
import { paymentsAPI } from "../../api";
import { t } from "../../i18n";
import { formatCalendarDate, formatDateTime } from "../../utils/datetime";
import { AideKpi } from "./AideKpi";

const TON = { overdue: "bg-red-50 text-red-700", partial: "bg-amber-50 text-amber-700", paid: "bg-emerald-50 text-emerald-700",
  upcoming: "bg-slate-100 text-slate-600", exempted: "bg-primary-50 text-primary-700" };

export const AIDES = {
  theorique: "Somme des échéances des tarifs applicables, avant exonération et remise.",
  exonerations: "Part exonérée (décision motivée, totale ou partielle), déduite en premier.",
  remises: "Remises accordées sur le reste après exonération, selon les règles de cumul.",
  net: "Frais théoriques moins exonérations et remises : ce que la famille doit réellement.",
  paye: "Paiements confirmés, nets des remboursements, imputés sur les échéances. Les paiements annulés ou en attente sont exclus.",
  restant: "Net dû moins payé, sur toutes les échéances de la période (passées et à venir).",
  retard: "Reste dû sur les échéances dont la date est dépassée.",
  recouvrement: "Montant encaissé divisé par le montant net attendu, multiplié par 100.",
};

export function Totaux({ totaux, testid, complet = true }) {
  const pct = (v) => (v === null || v === undefined ? t("Non calculable") : `${v} %`);
  const cartes = [
    ...(complet ? [["Frais théoriques", totaux.theorique_affiche, "theorique"], ["Exonérations", totaux.exonerations_affiche, "exonerations"],
      ["Remises", totaux.remises_affiche, "remises"]] : []),
    ["Net dû", totaux.net_affiche ?? totaux.attendu_affiche, "net"], ["Payé", totaux.paye_affiche, "paye"],
    ["Reste à payer", totaux.restant_affiche, "restant"], ["Dont en retard", totaux.retard_affiche, "retard"],
    ["Recouvrement", pct(totaux.taux_recouvrement), "recouvrement"],
  ].filter(([, v]) => v !== undefined);
  return (
    <div className={`grid grid-cols-2 sm:grid-cols-4 ${complet ? "" : "lg:grid-cols-5"} gap-2`} data-testid={testid}>
      {cartes.map(([titre, valeur, cle]) => (
        <div key={titre} className="rounded-xl border border-slate-100 bg-slate-50/60 p-3 min-w-0">
          <p className="text-xs text-slate-500 flex items-center gap-1">{t(titre)}<AideKpi texte={t(AIDES[cle])} /></p>
          <p className="font-bold text-slate-900 tabular-nums break-words">{valeur}</p>
        </div>
      ))}
    </div>
  );
}

export default function ReleveEleve({ eleveId, academyKey }) {
  const q = useQuery({ queryKey: ["situation-eleve", academyKey, eleveId], queryFn: () => paymentsAPI.situationEleve(eleveId), enabled: Boolean(eleveId) });
  const s = q.data?.data;
  if (q.isPending) return <div className="h-40 rounded-xl bg-slate-100 animate-pulse motion-reduce:animate-none" />;
  if (q.isError || !s) return <p role="alert" className="text-sm text-red-700">{t("La situation financière n'a pas pu être chargée.")}</p>;
  return (
    <div className="space-y-4 text-sm" data-testid="releve-eleve">
      {(s.eleve?.matricule || s.eleve?.classe) && (
        <p className="text-xs text-slate-500">{[s.eleve.matricule, s.eleve.classe, s.eleve.niveau].filter(Boolean).join(" · ")}</p>
      )}
      <Totaux totaux={s.totaux} testid="releve-totaux" />
      {s.explication && (
        <p className="rounded-xl bg-feba-navy/5 px-3 py-2 text-slate-700" data-testid="releve-explication">
          <span className="font-semibold">{t("Calcul du solde")} : </span>
          {`${t("Frais théoriques")} ${s.totaux.theorique_affiche} − ${t("exonérations")} ${s.totaux.exonerations_affiche} − ${t("remises")} ${s.totaux.remises_affiche} = ${t("net dû")} ${s.totaux.net_affiche} ; ${t("payé")} ${s.totaux.paye_affiche} ; ${t("reste")} ${s.totaux.restant_affiche} (${t("dont en retard")} ${s.totaux.retard_affiche}).`}
        </p>
      )}
      {s.totaux.hors_echeancier_minor > 0 && (
        <p className="text-xs text-slate-600">{t("Paiements hors échéancier (nature sans tarif ou trop-perçu)")} : <strong>{s.totaux.hors_echeancier_affiche}</strong></p>
      )}
      {!s.echeancier_configure ? (
        <p className="text-slate-500">{t("Aucun tarif ne s'applique à cet élève : le montant dû n'est pas calculable.")}</p>
      ) : (
        <>
          <section>
            <h4 className="font-semibold text-slate-800 mb-1">{t("Tarifs appliqués")}</h4>
            <ul className="space-y-2" data-testid="releve-tarifs">
              {s.tarifs.map((tf) => (
                <li key={`${tf.tarif_id}-${tf.annee_id}`} className="rounded-xl border border-slate-100 p-3">
                  <div className="flex flex-wrap justify-between gap-2">
                    <span className="font-medium text-slate-800">{tf.libelle}{tf.echeancier_personnel && <span className="badge bg-amber-50 text-amber-700 ml-2">{t("Échéancier personnel")}</span>}</span>
                    <span className="tabular-nums text-slate-600">{tf.theorique_affiche} → <strong className="text-slate-900">{tf.net_affiche}</strong></span>
                  </div>
                  {tf.ajustements?.length > 0 && (
                    <ul className="mt-1 text-xs space-y-0.5">
                      {tf.ajustements.map((a, i) => (
                        <li key={`${a.regle_id ?? "d"}-${i}`} className={a.retenue ? "text-slate-700" : "text-slate-400"}>
                          {a.genre === "exoneration" ? t("Exonération") : t("Remise")} · {a.nom} : {a.retenue ? `− ${a.montant}` : t("non appliquée")}
                          {!a.retenue && a.raison ? ` (${t(a.raison)})` : ""}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          </section>
          <div className="overflow-x-auto">
            <table className="w-full" data-testid="releve-echeances">
              <thead><tr className="text-left text-xs text-slate-500">
                {["Frais", "Échéance", "Date", "Prévu", "Exonéré", "Remise", "Net dû", "Payé", "Reste", "Statut"].map((h) => <th key={h} className="py-1.5 pr-3 font-medium">{t(h)}</th>)}
              </tr></thead>
              <tbody>
                {s.echeances.map((e) => (
                  <tr key={`${e.fee_id}-${e.personnelle ? "p" : "s"}${e.installment_id}`} className="border-t border-slate-100">
                    <td className="py-1.5 pr-3">{e.fee_label}</td>
                    <td className="py-1.5 pr-3">{e.installment_label}{e.personnelle && <span className="sr-only"> ({t("Échéancier personnel")})</span>}</td>
                    <td className="py-1.5 pr-3 whitespace-nowrap">{formatCalendarDate(e.due_date)}</td>
                    <td className="py-1.5 pr-3 tabular-nums">{e.expected_display}</td>
                    <td className="py-1.5 pr-3 tabular-nums">{e.exemption_minor ? e.exemption_display : "-"}</td>
                    <td className="py-1.5 pr-3 tabular-nums">{e.discount_minor ? e.discount_display : "-"}</td>
                    <td className="py-1.5 pr-3 tabular-nums">{e.net_display}</td>
                    <td className="py-1.5 pr-3 tabular-nums">{e.paid_display}</td>
                    <td className="py-1.5 pr-3 tabular-nums">{e.outstanding_display}</td>
                    <td className="py-1.5 pr-3"><span className={`badge ${TON[e.status] || ""}`}>{t(e.status_label)}{e.days_overdue > 0 && e.en_retard ? ` · ${e.days_overdue} ${t("j")}` : ""}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {s.paiements.length > 0 && (
        <section>
          <h4 className="font-semibold text-slate-800 mb-1">{t("Paiements")}</h4>
          <ul className="divide-y divide-slate-100" data-testid="releve-paiements">
            {s.paiements.map((p) => (
              <li key={p.id} className="py-1.5 flex flex-wrap justify-between gap-2">
                <span>{formatCalendarDate(p.date)} · {t(p.nature)} · {t(p.mode)} · {p.reference}
                  {p.recu_disponible && <span className="badge bg-emerald-50 text-emerald-700 ml-2">{t("Reçu disponible")}</span>}</span>
                <span className={`tabular-nums ${p.statut === "annulé" ? "line-through text-slate-400" : ""}`}>
                  {p.montant}{p.rembourse ? ` (${t("remboursé")} ${p.rembourse})` : ""}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {s.historique?.length > 0 && (
        <section>
          <h4 className="font-semibold text-slate-800 mb-1">{t("Historique des décisions financières")}</h4>
          <ul className="divide-y divide-slate-100 text-xs" data-testid="releve-historique">
            {s.historique.map((h, i) => (
              <li key={i} className="py-1.5">
                <span className="text-slate-500">{formatDateTime(h.le)}</span> · <strong>{t(h.action)}</strong> · {h.description}
                {h.motif && <span className="text-slate-600"> · {t("Motif")} : {h.motif}</span>}
                {h.auteur && <span className="text-slate-500"> · {h.auteur}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
