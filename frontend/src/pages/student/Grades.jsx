/**
 * StudentGrades — v20 CORRIGÉ
 *
 * Corrections :
 *  - CRITIQUE: useQuery ne peut pas être appelé dans .map() (violation Rules of Hooks)
 *    → remplacé par une seule requête "averages" qui récupère les 3 périodes
 *  - currentYear est maintenant défini AVANT d'être utilisé dans les autres queries
 *  - Affiche note_type par note
 *  - Affiche la moyenne par matière (via endpoint averages with by_subject)
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { gradesAPI, schoolsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, Tooltip } from "recharts";
import { t } from "../../i18n";

const NOTE_TYPE_BADGE = {
  devoir:        "bg-blue-50 text-blue-600",
  interrogation: "bg-purple-50 text-purple-600",
  controle:      "bg-indigo-50 text-indigo-600",
  examen:        "bg-orange-50 text-orange-600",
  tp:            "bg-teal-50 text-teal-600",
  autre:         "bg-slate-50 text-slate-500",
};

export default function StudentGrades() {
  const [period, setPeriod] = useState("");

  // 1. Récupérer l'année courante EN PREMIER
  const { data: yearsData } = useQuery({ queryKey: ["years"], queryFn: schoolsAPI.years });
  const years       = yearsData?.data?.results || yearsData?.data || [];
  const currentYear = years.find(y => y.is_current);

  // 2. Notes de l'élève (filtrées par période et année courante si disponible)
  const { data, isLoading } = useQuery({
    queryKey: ["student-grades", period, currentYear?.id],
    queryFn: () => gradesAPI.list({
      ...(period ? { period } : {}),
      ...(currentYear ? { school_year: currentYear.id } : {}),
    }),
    enabled: !!currentYear,
  });
  const grades = data?.data?.results || data?.data || [];

  // 3. Moyennes trimestrielles — UNE requête par période (pas dans .map() !)
  const { data: avgT1 } = useQuery({
    queryKey: ["student-avg", "T1", currentYear?.id],
    queryFn:  () => gradesAPI.averages({ period: "T1", school_year: currentYear?.id }),
    enabled:  !!currentYear?.id,
  });
  const { data: avgT2 } = useQuery({
    queryKey: ["student-avg", "T2", currentYear?.id],
    queryFn:  () => gradesAPI.averages({ period: "T2", school_year: currentYear?.id }),
    enabled:  !!currentYear?.id,
  });
  const { data: avgT3 } = useQuery({
    queryKey: ["student-avg", "T3", currentYear?.id],
    queryFn:  () => gradesAPI.averages({ period: "T3", school_year: currentYear?.id }),
    enabled:  !!currentYear?.id,
  });

  // Moyenne annuelle (BUG N°3) — calculée côté serveur (moyenne des
  // trimestres effectivement notés)
  const { data: avgAnnual } = useQuery({
    queryKey: ["student-avg", "annual", currentYear?.id],
    queryFn:  () => gradesAPI.averages({ period: "annual", school_year: currentYear?.id }),
    enabled:  !!currentYear?.id,
  });

  const avgByPeriod = [
    { period: "T1", avg: avgT1?.data?.average ?? null },
    { period: "T2", avg: avgT2?.data?.average ?? null },
    { period: "T3", avg: avgT3?.data?.average ?? null },
    { period: "Année", avg: avgAnnual?.data?.average ?? null },
  ];

  // 4. Radar — moyennes par matière sur la période sélectionnée
  const { data: radarData_ } = useQuery({
    queryKey: ["student-radar", period, currentYear?.id],
    queryFn:  () => gradesAPI.averages({ period: period || "T1", school_year: currentYear?.id }),
    enabled:  !!currentYear?.id,
  });
  const bySubject = radarData_?.data?.by_subject || {};
  const radarData = Object.values(bySubject).map(s => ({
    subject: s.name.slice(0, 12),
    note:    parseFloat(s.average) || 0,
  }));

  const nc = v => {
    const n = parseFloat(v);
    if (n >= 14) return "text-success font-bold";
    if (n >= 10) return "text-amber-600 font-medium";
    return "text-danger font-medium";
  };

  const cols = [
    { key: "subject", label: t("Matière"),      accessor: "subject_name" },
    { key: "coeff",   label: t("Coeff"),         accessor: "subject_coefficient" },
    { key: "period",  label: t("Période"),       accessor: "period" },
    {
      key: "note_type", label: t("Type"),
      render: r => (
        <span className={`px-2 py-0.5 rounded-lg text-xs font-medium ${NOTE_TYPE_BADGE[r.note_type] || ""}`}>
          {r.note_type_label || r.note_type || "—"}
        </span>
      ),
    },
    { key: "poids",   label: t("Poids"),        render: r => r.note_coefficient || 1 },
    { key: "value",   label: t("Note"),         render: r => <span className={nc(r.value)}>{r.value}/20</span> },
    { key: "appr",    label: t("Appréciation"), accessor: "appreciation" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title={t("Mes Notes")} subtitle={t("Résultats par matière et période")} />

      {/* Moyennes trimestrielles + annuelle (calculées côté serveur) */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {avgByPeriod.map(({ period: p, avg }) => (
          <div key={p} className="card text-center">
            <p className="text-xs font-medium text-slate-500 mb-1">{p}</p>
            <p className={`text-2xl font-bold ${avg !== null ? (parseFloat(avg) >= 10 ? "text-success" : "text-danger") : "text-slate-300"}`}>
              {avg !== null ? `${parseFloat(avg).toFixed(2)}/20` : "—"}
            </p>
          </div>
        ))}
      </div>

      {/* Filtre période */}
      <div className="card flex gap-2 items-center">
        <span className="text-sm font-medium text-slate-600">{t("Filtrer :")}</span>
        {["","T1","T2","T3","exam"].map(p => (
          <button key={p} onClick={() => setPeriod(p)}
            className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${period === p ? "bg-primary text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
            {p || "Toutes"}
          </button>
        ))}
      </div>

      {/* Radar */}
      {radarData.length > 2 && (
        <div className="card">
          <h3 className="font-semibold text-slate-800 mb-4">{t("Profil de performance")}</h3>
          <ResponsiveContainer width="100%" height={260}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="#e2e8f0" />
              <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10 }} />
              <Radar name="Moy. Matière" dataKey="note" stroke="#6366F1" fill="#6366F1" fillOpacity={0.2} />
              <Tooltip formatter={v => [`${parseFloat(v).toFixed(2)}/20`, "Moy. Matière"]} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="card">
        <DataTable columns={cols} data={grades} loading={isLoading} />
      </div>
    </div>
  );
}
