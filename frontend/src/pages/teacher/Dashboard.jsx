import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { dashboardAPI, announcementsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import StatCard from "../../components/ui/StatCard";
import { BookOpen, Users, FileText, Calendar, ClipboardList, Megaphone } from "lucide-react";
import { motion } from "framer-motion";
import AnnouncementModal from "../../components/ui/AnnouncementModal";

export default function TeacherDashboard() {
  const [selectedAnn, setSelectedAnn] = useState(null);
  const { data, isLoading } = useQuery({ queryKey: ["teacher-dashboard"], queryFn: dashboardAPI.teacher });
  const { data: annData } = useQuery({ queryKey: ["announcements"], queryFn: () => announcementsAPI.list() });
  const d = data?.data;
  const announcements = annData?.data?.results || annData?.data || [];

  if (isLoading) return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        {[...Array(5)].map((_,i) => <div key={i} className="skeleton h-28 rounded-2xl" />)}
      </div>
    </div>
  );

  const kpis = d?.kpis || {};

  return (
    <div className="space-y-6">
      <PageHeader title="Mon Tableau de Bord" subtitle="Vue d'ensemble de mes activités" />

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard title="Mes classes"       value={kpis.my_classes ?? 0}        icon={BookOpen}     color="success"   delay={0} />
        <StatCard title="Mes élèves"        value={kpis.my_students ?? 0}       icon={Users}        color="primary"   delay={0.1} />
        <StatCard title="Devoirs en cours"  value={kpis.pending_homework ?? 0}  icon={FileText}     color="accent"    delay={0.2} />
        <StatCard title="Absences (7j)"     value={kpis.absences_this_week ?? 0} icon={Calendar}   color="danger"    delay={0.3} />
        <StatCard title="Notes ce mois"     value={kpis.grades_this_month ?? 0} icon={ClipboardList} color="secondary" delay={0.4} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {(d?.my_classes || []).length > 0 && (
          <div className="card">
            <h3 className="font-semibold text-slate-800 mb-4">Mes Classes</h3>
            <div className="space-y-2">
              {d.my_classes.map((cls, i) => (
                <motion.div key={cls.id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.07 }}
                  className="flex items-center justify-between py-2.5 px-3 bg-emerald-50 rounded-xl">
                  <div>
                    <p className="font-semibold text-slate-800">{cls.name}</p>
                    <p className="text-xs text-slate-500">{cls.level}</p>
                  </div>
                  <div className="flex items-center gap-1 text-xs text-slate-500">
                    <Users className="w-3 h-3" />{cls.student_count} élèves
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        )}

        {(d?.recent_grades || []).length > 0 && (
          <div className="card">
            <h3 className="font-semibold text-slate-800 mb-4">Dernières Notes Saisies</h3>
            <div className="space-y-2">
              {d.recent_grades.map((g, i) => {
                const color = g.value >= 14 ? "text-success" : g.value >= 10 ? "text-amber-600" : "text-danger";
                return (
                  <div key={i} className="flex items-center justify-between py-2 border-b border-slate-50 last:border-0">
                    <div>
                      <p className="text-sm font-medium text-slate-800">{g.student}</p>
                      <p className="text-xs text-slate-400">{g.subject} • {g.period} • {g.date}</p>
                    </div>
                    <span className={`font-bold ${color}`}>{g.value}/20</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {announcements.length > 0 && (
        <div className="card">
          <h3 className="font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <Megaphone className="w-4 h-4 text-primary" />Annonces récentes
          </h3>
          <div className="space-y-2">
            {announcements.slice(0, 4).map(a => (
              <div key={a.id} onClick={() => setSelectedAnn(a)}
                className="flex items-start gap-2 py-2 border-b border-slate-50 last:border-0 cursor-pointer hover:bg-slate-50 rounded-xl px-2 -mx-2 transition-colors">
                <div className="w-2 h-2 rounded-full bg-primary mt-1.5 shrink-0" />
                <div>
                  <p className="text-sm font-medium text-slate-800 hover:text-primary transition-colors">{a.title}</p>
                  <p className="text-xs text-slate-400">{a.created_at?.slice(0,10)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      <AnnouncementModal announcement={selectedAnn} onClose={() => setSelectedAnn(null)} />
    </div>
  );
}