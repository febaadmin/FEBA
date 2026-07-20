import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { dashboardAPI, announcementsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import StatCard from "../../components/ui/StatCard";
import { GraduationCap, FileText, Calendar, AlertCircle, Megaphone } from "lucide-react";
import { motion } from "framer-motion";
import AnnouncementModal from "../../components/ui/AnnouncementModal";
import { t } from "../../i18n";

export default function StudentHome() {
  const [selectedAnn, setSelectedAnn] = useState(null);
  const { data, isLoading } = useQuery({ queryKey: ["student-dashboard"], queryFn: dashboardAPI.student });
  const { data: annData } = useQuery({ queryKey: ["student-announcements"], queryFn: () => announcementsAPI.list() });
  const d = data?.data;
  const announcements = annData?.data?.results || annData?.data || [];

  if (isLoading) return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_,i) => <div key={i} className="skeleton h-28 rounded-2xl" />)}
      </div>
    </div>
  );

  const student = d?.student || {};
  const kpis = d?.kpis || {};

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Bonjour, {name} 👋", { name: student.first_name || "" })}
        subtitle={`${student.class || "—"} • ${t("Matricule")}: ${student.matricule || "—"}`}
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title={t("Moyenne générale")} icon={GraduationCap} color="primary"
          value={kpis.average != null ? `${Number(kpis.average).toFixed(2)}/20` : "—"}
          trend={kpis.progression != null && kpis.progression < 0 ? "down" : "up"}
          trendValue={
            kpis.progression != null
              ? `${kpis.progression >= 0 ? "+" : ""}${kpis.progression} pt vs T1${kpis.appreciation ? ` • ${t(kpis.appreciation)}` : ""}`
              : (kpis.appreciation ? t(kpis.appreciation) : undefined)
          }
          delay={0} />
        <StatCard title={t("Devoirs à rendre")} icon={FileText} color="accent"
          value={kpis.pending_homework ?? 0} delay={0.1} />
        <StatCard title={t("Absences")} icon={Calendar} color="danger"
          value={kpis.absent_count ?? 0} delay={0.2} />
        <StatCard title={t("Retards")} icon={AlertCircle} color="secondary"
          value={kpis.late_count ?? 0} delay={0.3} />
      </div>

      {/* Moyennes par trimestre (BUG N°3) */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: t("Moyenne T1"), value: kpis.average_t1 },
          { label: t("Moyenne T2"), value: kpis.average_t2 },
          { label: t("Moyenne T3"), value: kpis.average_t3 },
          { label: t("Moyenne annuelle"), value: kpis.annual_average },
        ].map(({ label, value }) => (
          <div key={label} className="card text-center py-4">
            <p className="text-xs font-medium text-slate-500 mb-1">{label}</p>
            <p className={`text-xl font-bold ${
              value == null ? "text-slate-300"
                : value >= 10 ? "text-success" : "text-danger"
            }`}>
              {value != null ? `${Number(value).toFixed(2)}/20` : "—"}
            </p>
          </div>
        ))}
      </div>

      {/* FIX (moyennes manquantes) : moyenne français / anglais / par matière —
          absentes du tableau de bord jusqu'ici alors qu'elles étaient déjà
          calculées par le backend pour les bulletins. */}
      {kpis.bilingual && (kpis.bilingual.fr_average != null || kpis.bilingual.en_average != null) && (
        <div className="grid grid-cols-2 gap-4">
          <div className="card text-center py-4">
            <p className="text-xs font-medium text-slate-500 mb-1">{t("Moyenne Français")}</p>
            <p className={`text-xl font-bold ${kpis.bilingual.fr_average == null ? "text-slate-300" : kpis.bilingual.fr_average >= 10 ? "text-success" : "text-danger"}`}>
              {kpis.bilingual.fr_average != null ? `${Number(kpis.bilingual.fr_average).toFixed(2)}/20` : "Aucune note disponible"}
            </p>
          </div>
          <div className="card text-center py-4">
            <p className="text-xs font-medium text-slate-500 mb-1">{t("Moyenne Anglais")}</p>
            <p className={`text-xl font-bold ${kpis.bilingual.en_average == null ? "text-slate-300" : kpis.bilingual.en_average >= 10 ? "text-success" : "text-danger"}`}>
              {kpis.bilingual.en_average != null ? `${Number(kpis.bilingual.en_average).toFixed(2)}/20` : "Aucune note disponible"}
            </p>
          </div>
        </div>
      )}

      {kpis.subject_averages && kpis.subject_averages.length > 0 && (
        <div className="card">
          <h3 className="font-semibold text-slate-800 mb-4">{t("Moyennes par matière")}</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {kpis.subject_averages.map((s) => (
              <div key={s.subject_id} className="flex items-center justify-between px-3 py-2 rounded-xl bg-slate-50">
                <span className="text-sm text-slate-600 truncate pr-2">{s.subject_name}</span>
                <span className={`text-sm font-semibold whitespace-nowrap ${
                  s.average == null ? "text-slate-400" : s.average >= 10 ? "text-success" : "text-danger"
                }`}>
                  {s.average != null ? `${Number(s.average).toFixed(2)}/20` : "Aucune note"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {(d?.recent_grades || []).length > 0 && (
          <div className="card">
            <h3 className="font-semibold text-slate-800 mb-4">{t("Dernières notes")}</h3>
            <div className="space-y-2">
              {d.recent_grades.map((g, i) => {
                const color = g.value >= 14 ? "text-success" : g.value >= 10 ? "text-amber-600" : "text-danger";
                return (
                  <div key={i} className="flex items-center justify-between py-2 border-b border-slate-50 last:border-0">
                    <div>
                      <p className="text-sm font-medium text-slate-800">{g.subject}</p>
                      <p className="text-xs text-slate-400">{g.period} • Coeff: {g.coefficient}</p>
                    </div>
                    <span className={`font-bold ${color}`}>{g.value}/20</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {announcements.length > 0 && (
          <div className="card">
            <h3 className="font-semibold text-slate-800 mb-4 flex items-center gap-2">
              <Megaphone className="w-4 h-4 text-primary" />{t("Annonces")}</h3>
            <div className="space-y-3">
              {announcements.slice(0, 4).map(a => (
                <div key={a.id} onClick={() => setSelectedAnn(a)}
                  className="p-3 bg-primary-50/30 rounded-xl cursor-pointer hover:bg-primary-50 transition-colors">
                  <p className="text-sm font-semibold text-slate-800 hover:text-primary transition-colors">{a.title}</p>
                  <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{a.content?.slice(0, 120)}</p>
                  <p className="text-xs text-slate-400 mt-1">{a.created_at?.slice(0, 10)}</p>
                </div>
              ))}
            </div>
          </div>
        )}
        <AnnouncementModal announcement={selectedAnn} onClose={() => setSelectedAnn(null)} />
      </div>
    </div>
  );
}