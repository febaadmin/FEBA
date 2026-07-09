import { useQuery } from "@tanstack/react-query";
import { scheduleAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import { Clock } from "lucide-react";
import { motion } from "framer-motion";

const DAYS = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi"];
const COLORS = ["bg-emerald-50 border-emerald-200","bg-sky-50 border-sky-200","bg-violet-50 border-violet-200","bg-amber-50 border-amber-200","bg-rose-50 border-rose-200","bg-teal-50 border-teal-200"];

export default function TeacherSchedule() {
  const { data, isLoading } = useQuery({ queryKey: ["teacher-schedule-view"], queryFn: () => scheduleAPI.list() });
  const schedules = data?.data?.results || data?.data || [];

  const byDay = DAYS.map((day, i) => ({
    day, idx: i,
    items: schedules.filter(s => s.day_of_week === i).sort((a,b) => a.start_time > b.start_time ? 1 : -1)
  }));

  const activeDays = byDay.filter(d => d.items.length > 0);

  if (isLoading) return <div className="skeleton h-64 rounded-2xl" />;

  return (
    <div className="space-y-6">
      <PageHeader title="Mon Emploi du Temps" subtitle={`${schedules.length} créneau(x) cette semaine`} />

      {activeDays.length === 0 ? (
        <div className="card text-center py-16 text-slate-400">
          <Clock className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="font-medium">Aucun créneau défini</p>
          <p className="text-sm mt-1">L'administration n'a pas encore saisi votre emploi du temps.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {activeDays.map(({ day, items }, di) => (
            <motion.div key={day} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: di * 0.07 }}
              className="card">
              <p className="font-bold text-slate-800 mb-3 border-b border-slate-100 pb-2">{day}</p>
              <div className="space-y-2">
                {items.map((item, ii) => (
                  <div key={item.id} className={`flex items-start gap-2 p-2.5 rounded-xl border ${COLORS[ii % COLORS.length]}`}>
                    <Clock className="w-3.5 h-3.5 text-slate-400 mt-0.5 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-bold text-slate-800 truncate">{item.subject_name}</p>
                      <p className="text-xs text-slate-500">{item.start_time?.slice(0,5)} – {item.end_time?.slice(0,5)}</p>
                      <p className="text-xs text-slate-400">Classe: {item.class_name} {item.room ? `• ${item.room}` : ""}</p>
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}