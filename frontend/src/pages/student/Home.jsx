import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { dashboardAPI, announcementsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import StatCard from "../../components/ui/StatCard";
import { GraduationCap, FileText, Calendar, AlertCircle, Megaphone } from "lucide-react";
import { motion } from "framer-motion";
import AnnouncementModal from "../../components/ui/AnnouncementModal";

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
        title={`Bonjour, ${student.first_name || ""} 👋`}
        subtitle={`${student.class || "—"} • Matricule: ${student.matricule || "—"}`}
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Moyenne générale" icon={GraduationCap} color="primary"
          value={kpis.average != null ? `${kpis.average}/20` : "—"} delay={0} />
        <StatCard title="Devoirs à rendre" icon={FileText} color="accent"
          value={kpis.pending_homework ?? 0} delay={0.1} />
        <StatCard title="Absences" icon={Calendar} color="danger"
          value={kpis.absent_count ?? 0} delay={0.2} />
        <StatCard title="Retards" icon={AlertCircle} color="secondary"
          value={kpis.late_count ?? 0} delay={0.3} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {(d?.recent_grades || []).length > 0 && (
          <div className="card">
            <h3 className="font-semibold text-slate-800 mb-4">Dernières notes</h3>
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
              <Megaphone className="w-4 h-4 text-primary" />Annonces
            </h3>
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