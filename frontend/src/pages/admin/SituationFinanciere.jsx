/**
 * Situation financière de l'académie : totaux, classes ou niveaux, élèves triés
 * par retard, relevé détaillé d'un élève. Tout est calculé par le serveur à partir
 * des tarifs, échéanciers, réductions et paiements (compute_dues).
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { paymentsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import Modal from "../../components/ui/Modal";
import ReleveEleve, { Totaux } from "../../components/payments/ReleveEleve";
import { useAuth } from "../../hooks/useAuth";
import { useAcademyKey } from "../../hooks/useEntityContext";
import { t } from "../../i18n";
import { extractApiError } from "../../utils/errors";

function Academie({ a, onEleve, racine }) {
  const [groupeChoisi, setGroupeChoisi] = useState(null);
  const [filtre, setFiltre] = useState("tous");
  if (!a.echeancier_configure) {
    return (
      <section className="card text-sm text-slate-600 space-y-2" data-testid="situation-sans-tarif">
        <h2 className="font-bold text-slate-800">{a.academie.nom}</h2>
        <p>{t("Aucun tarif avec échéances : les montants dus ne sont pas calculables pour cette académie.")}</p>
        <Link to={`${racine}/tarifs`} className="text-primary font-medium hover:underline">{t("Configurer les tarifs et échéances")}</Link>
      </section>
    );
  }
  const eleves = a.eleves.filter((e) => (!groupeChoisi || e[a.groupe === "niveau" ? "niveau_id" : "classe_id"] === groupeChoisi)
    && (filtre === "tous" || (filtre === "retard" ? e.retard_minor > 0 : filtre === "solde" ? e.restant_minor > 0 : e.restant_minor === 0)));
  return (
    <section className="space-y-3">
      <div className="card space-y-3">
        <h2 className="font-bold text-slate-800">{a.academie.nom} <span className="text-xs text-slate-500 font-normal">· {a.devise}</span></h2>
        <Totaux totaux={a.totaux} testid="situation-totaux" />
        {a.anomalies.length > 0 && (
          <ul className="text-xs text-amber-700 list-disc pl-5">{a.anomalies.map((m) => <li key={m}>{m}</li>)}</ul>
        )}
      </div>
      <div className="card overflow-x-auto">
        <table className="w-full text-sm" data-testid="situation-groupes">
          <thead><tr className="text-left text-xs text-slate-500">
            {[a.groupe === "niveau" ? "Niveau" : "Classe", "Élèves", "En retard", "Attendu", "Payé", "Reste à payer", "Dont en retard", "Recouvrement"].map((h) =>
              <th key={h} className="py-2 pr-3 font-medium">{t(h)}</th>)}
          </tr></thead>
          <tbody>
            {a.groupes.map((g) => (
              <tr key={`${g.id}`} className={`border-t border-slate-100 cursor-pointer hover:bg-slate-50 ${groupeChoisi === g.id ? "bg-feba-cream/40" : ""}`}
                onClick={() => setGroupeChoisi(groupeChoisi === g.id ? null : g.id)}>
                <td className="py-2 pr-3 font-medium">{g.nom}</td>
                <td className="py-2 pr-3 tabular-nums">{g.eleves}</td>
                <td className="py-2 pr-3 tabular-nums">{g.eleves_en_retard}</td>
                <td className="py-2 pr-3 tabular-nums">{g.attendu_affiche}</td>
                <td className="py-2 pr-3 tabular-nums">{g.paye_affiche}</td>
                <td className="py-2 pr-3 tabular-nums">{g.restant_affiche}</td>
                <td className="py-2 pr-3 tabular-nums">{g.retard_affiche}</td>
                <td className="py-2 pr-3 tabular-nums">{g.taux_recouvrement === null ? "-" : `${g.taux_recouvrement} %`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card space-y-2">
        <div className="flex flex-wrap gap-2 items-center">
          <h3 className="font-semibold text-slate-800 mr-2">{t("Élèves")}</h3>
          {[["tous", "Tous"], ["retard", "En retard"], ["solde", "Reste à payer"], ["a_jour", "Soldé"]].map(([v, l]) => (
            <button key={v} type="button" onClick={() => setFiltre(v)} aria-pressed={filtre === v} data-testid={`filtre-${v}`}
              className={`px-2.5 py-1 rounded-lg text-xs ${filtre === v ? "bg-feba-navy text-white" : "border border-slate-200 text-slate-600"}`}>{t(l)}</button>
          ))}
          <span className="text-xs text-slate-500">{eleves.length} {t("élève(s)")}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="situation-eleves">
            <thead><tr className="text-left text-xs text-slate-500">
              {["Élève", "Classe", "Attendu", "Payé", "Reste à payer", "Dont en retard"].map((h) => <th key={h} className="py-2 pr-3 font-medium">{t(h)}</th>)}
            </tr></thead>
            <tbody>
              {eleves.map((e) => (
                <tr key={e.id} className="border-t border-slate-100 cursor-pointer hover:bg-slate-50" onClick={() => onEleve(e)}>
                  <td className="py-2 pr-3 font-medium">{e.nom}</td>
                  <td className="py-2 pr-3">{e.classe || "-"}</td>
                  <td className="py-2 pr-3 tabular-nums">{e.attendu_affiche}</td>
                  <td className="py-2 pr-3 tabular-nums">{e.paye_affiche}</td>
                  <td className="py-2 pr-3 tabular-nums">{e.restant_affiche}</td>
                  <td className={`py-2 pr-3 tabular-nums ${e.retard_minor > 0 ? "text-red-700 font-medium" : ""}`}>{e.retard_affiche}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

export default function SituationFinanciere() {
  const { user } = useAuth();
  const academyKey = useAcademyKey();
  const [groupe, setGroupe] = useState("classe");
  const [eleve, setEleve] = useState(null);
  const q = useQuery({ queryKey: ["situation", academyKey, groupe], queryFn: () => paymentsAPI.situation({ groupe }) });
  const academies = q.data?.data?.academies || [];
  const racine = user?.role === "superadmin" ? "/superadmin" : "/admin";
  return (
    <div className="space-y-4">
      <PageHeader title={t("Situation financière")} subtitle={t("Montants dus, payés et restant à payer, par classe, niveau et élève")} />
      <div className="flex gap-2" role="group" aria-label={t("Regrouper par")}>
        {[["classe", "Par classe"], ["niveau", "Par niveau"]].map(([v, l]) => (
          <button key={v} type="button" onClick={() => setGroupe(v)} aria-pressed={groupe === v} data-testid={`groupe-${v}`}
            className={`px-3 py-1.5 rounded-xl text-sm font-medium ${groupe === v ? "bg-feba-navy text-white" : "bg-white border border-slate-200 text-slate-600"}`}>{t(l)}</button>
        ))}
      </div>
      {q.isPending && <div className="card h-40 animate-pulse" />}
      {q.isError && <p role="alert" className="card text-sm text-red-700">{extractApiError(q.error)}</p>}
      {academies.map((a) => <Academie key={a.academie.id} a={a} racine={racine} onEleve={setEleve} />)}
      <Modal open={Boolean(eleve)} onClose={() => setEleve(null)} title={eleve ? `${t("Situation financière")} - ${eleve.nom}` : ""} size="xl">
        {eleve && <ReleveEleve eleveId={eleve.id} academyKey={academyKey} />}
      </Modal>
    </div>
  );
}
