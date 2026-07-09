import { useQuery } from "@tanstack/react-query";
import { scheduleAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import { Clock } from "lucide-react";

const DAYS = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi"];

export default function StudentSchedule() {
  const { data, isLoading } = useQuery({ queryKey: ["student-schedule"], queryFn: () => scheduleAPI.list() });
  const schedules = data?.data?.results || data?.data || [];
  const byDay = DAYS.map((day, i) => ({ day, items: schedules.filter(s => s.day_of_week === i) }));

  if (isLoading) return <div className="skeleton h-64 rounded-2xl" />;

  return (
    <div className="space-y-6">
      <PageHeader title="Mon Emploi du Temps" subtitle="Planning de la semaine" />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {byDay.filter(d => d.items.length > 0).map(({ day, items }) => (
          <div key={day} className="card">
            <p className="font-bold text-slate-800 mb-3">{day}</p>
            <div className="space-y-2">
              {items.sort((a,b) => a.start_time > b.start_time ? 1 : -1).map(item => (
                <div key={item.id} className="flex items-center gap-2 p-2 bg-sky-50 rounded-xl">
                  <Clock className="w-3 h-3 text-sky-600 shrink-0" />
                  <div>
                    <p className="text-xs font-semibold text-sky-800">{item.subject_name}</p>
                    <p className="text-xs text-sky-600">{item.start_time?.slice(0,5)}–{item.end_time?.slice(0,5)} • {item.teacher_name}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
        {byDay.every(d => d.items.length === 0) && <div className="col-span-3 card text-center py-12 text-slate-400">Aucun créneau défini</div>}
      </div>
    </div>
  );
}