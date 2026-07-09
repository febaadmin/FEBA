import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Users, GraduationCap, BookOpen, DollarSign, Megaphone } from "lucide-react";
import { dashboardAPI, announcementsAPI } from "../../api";
import StatCard from "../../components/ui/StatCard";
import PageHeader from "../../components/ui/PageHeader";
import AnnouncementModal from "../../components/ui/AnnouncementModal";

const MONTHS = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"];

export default function AdminDashboard() {
  const [selectedAnn, setSelectedAnn] = useState(null);
  const { data, isLoading } = useQuery({ queryKey: ["admin-dashboard"], queryFn: dashboardAPI.admin });
  const { data: annData } = useQuery({ queryKey: ["admin-announcements"], queryFn: () => announcementsAPI.list() });
  const d = data?.data;
  const announcements = annData?.data?.results || annData?.data || [];

  const chartData = (d?.monthly_revenue || []).map(m => ({ month: MONTHS[m.month-1], montant: m.amount }));

  if (isLoading) return (
    <div className="space-y-6">
      <div className="grid grid-cols-4 gap-4">{[...Array(4)].map((_,i) => <div key={i} className="skeleton h-32 rounded-2xl"/>)}</div>
    </div>
  );

  const kpis = d?.kpis || {};

  return (
    <div className="space-y-6">
      <PageHeader title="Tableau de bord" subtitle="Vue d'ensemble de l'établissement" />

      {/* Active year badge */}
      {d?.active_year && (
        <div className="flex items-center gap-2 px-4 py-2 bg-blue-50 border border-blue-200 rounded-xl w-fit">
          <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
          <span className="text-sm font-medium text-blue-800">
            Année scolaire active : <strong>{d.active_year.name}</strong>
          </span>
          <span className="text-xs text-blue-500 ml-1">— statistiques filtrées sur cette année</span>
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Élèves actifs"    value={kpis.total_students ?? 0}  icon={GraduationCap} color="primary"   delay={0} />
        <StatCard title="Enseignants"      value={kpis.total_teachers ?? 0}  icon={Users}         color="secondary" delay={0.1} />
        <StatCard title="Classes"          value={kpis.total_classes ?? 0}   icon={BookOpen}      color="accent"    delay={0.2} />
        <StatCard title="Revenus du mois"  value={`${(kpis.monthly_revenue ?? 0).toLocaleString()} FCFA`} icon={DollarSign} color="success" delay={0.3} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h3 className="font-semibold text-slate-800 mb-4">Revenus mensuels (FCFA)</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={v => `${(v/1000).toFixed(0)}k`} />
              <Tooltip formatter={v => [`${v.toLocaleString()} FCFA`, "Montant"]} />
              <Bar dataKey="montant" fill="#6366F1" radius={[6,6,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="card">
          <h3 className="font-semibold text-slate-800 mb-4">Évolution des revenus</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={v => [`${v.toLocaleString()} FCFA`]} />
              <Line type="monotone" dataKey="montant" stroke="#6366F1" strokeWidth={2} dot={{ fill: "#6366F1", r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h3 className="font-semibold text-slate-800 mb-4">Derniers paiements</h3>
          <div className="space-y-3">
            {(d?.recent_payments || []).map((p, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-slate-50 last:border-0">
                <div>
                  <p className="text-sm font-medium text-slate-800">{p.student}</p>
                  <p className="text-xs text-slate-400">{p.type} • {p.date} • {p.reference_number}</p>
                </div>
                <span className="text-sm font-bold text-success">{p.amount?.toLocaleString()} FCFA</span>
              </div>
            ))}
            {(d?.recent_payments || []).length === 0 && <p className="text-sm text-slate-400 text-center py-4">Aucun paiement</p>}
          </div>
        </div>

        <div className="card">
          <h3 className="font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <Megaphone className="w-4 h-4 text-primary" />Annonces actives
          </h3>
          <div className="space-y-2">
            {announcements.slice(0,4).map(a => (
              <div key={a.id} onClick={() => setSelectedAnn(a)}
                className="flex items-start gap-2 py-2 border-b border-slate-50 last:border-0 cursor-pointer hover:bg-slate-50 rounded-xl px-2 -mx-2 transition-colors">
                <div className="w-2 h-2 rounded-full bg-primary mt-1.5 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-800 hover:text-primary transition-colors">{a.title}</p>
                  <p className="text-xs text-slate-400">{(a.target_roles || []).join(", ")} • {a.created_at?.slice(0,10)}</p>
                </div>
              </div>
            ))}
            {announcements.length === 0 && <p className="text-sm text-slate-400 text-center py-4">Aucune annonce</p>}
          </div>
        </div>
      </div>
      <AnnouncementModal announcement={selectedAnn} onClose={() => setSelectedAnn(null)} />
    </div>
  );
}