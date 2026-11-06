import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Area, AreaChart, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { AXE, BLEU, CURSEUR, GRILLE, VERT, useAnimation } from "../../theme/graphiques";
import Infobulle from "../../components/charts/Infobulle";
import { AideKpi } from "../../components/payments/AideKpi";
import { Users, GraduationCap, BookOpen, DollarSign, Megaphone } from "lucide-react";
import { dashboardAPI, announcementsAPI } from "../../api";
import StatCard from "../../components/ui/StatCard";
import PageHeader from "../../components/ui/PageHeader";
import AnnouncementModal from "../../components/ui/AnnouncementModal";
import { t } from "../../i18n";
import { libelleCible } from "../../utils/destinataires";
import { useMoney } from "../../hooks/useMoney";

const MONTHS = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"];

export default function AdminDashboard() {
  // P0 : la devise vient de l'académie active, jamais d'un symbole codé en dur.
  const money = useMoney();
  const [selectedAnn, setSelectedAnn] = useState(null);
  const { data, isLoading } = useQuery({ queryKey: ["admin-dashboard"], queryFn: dashboardAPI.admin });
  const { data: annData } = useQuery({ queryKey: ["admin-announcements"], queryFn: () => announcementsAPI.list() });
  const d = data?.data;
  const announcements = annData?.data?.results || annData?.data || [];

  const anim = useAnimation();
  // Cumul : somme des mois successifs, à partir des seuls montants réels renvoyés par le serveur.
  const mois = d?.monthly_revenue || [];
  const chartData = mois.map((m, i) => ({
    month: t(MONTHS[m.month - 1]), montant: m.amount,
    cumul: mois.slice(0, i + 1).reduce((s, x) => s + (Number(x.amount) || 0), 0),
  }));

  if (isLoading) return (
    <div className="space-y-6">
      <div className="grid grid-cols-4 gap-4">{[...Array(4)].map((_,i) => <div key={i} className="skeleton h-32 rounded-2xl"/>)}</div>
    </div>
  );

  const kpis = d?.kpis || {};

  return (
    <div className="space-y-6">
      <PageHeader title={t("Tableau de bord")} subtitle={t("Vue d'ensemble de l'établissement")} />

      {/* Active year badge */}
      {d?.active_year && (
        <div className="flex items-center gap-2 px-4 py-2 bg-primary-50 border border-primary-200 rounded-xl w-fit">
          <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
          <span className="text-sm font-medium text-primary-800">{t("Année scolaire active :")} <strong>{d.active_year.name}</strong>
          </span>
          <span className="text-xs text-blue-500 ml-1">- {t("statistiques filtrées sur cette année")}</span>
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title={t("Élèves actifs")}    value={kpis.total_students ?? 0}  icon={GraduationCap} color="primary"   delay={0} />
        <StatCard title={t("Enseignants")}      value={kpis.total_teachers ?? 0}  icon={Users}         color="secondary" delay={0.1} />
        <StatCard title={t("Classes")}          value={kpis.total_classes ?? 0}   icon={BookOpen}      color="accent"    delay={0.2} />
        {/* V8 — Le serveur rend le montant dans la devise de l'académie.
            Le repli local ne sert qu'aux réponses d'une version antérieure. */}
        <StatCard title={t("Revenus du mois")}  value={kpis.monthly_revenue_display || money.format(kpis.monthly_revenue ?? 0)} icon={DollarSign} color="success" delay={0.3} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card" data-testid="dash-revenus-mois">
          <h3 className="font-semibold text-slate-800 mb-1 flex items-center gap-1.5">
            {t("Revenus mensuels")}{money.symbol ? ` (${money.symbol})` : ""}
            <AideKpi texte={t("Paiements confirmés encaissés chaque mois de l'année scolaire active.")} />
          </h3>
          <p className="text-xs text-slate-500 mb-3">{t("Montant encaissé par mois")}</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData}>
              <CartesianGrid {...GRILLE} vertical={false} />
              <XAxis dataKey="month" tick={AXE} />
              <YAxis tick={AXE} tickFormatter={v => `${(v/1000).toFixed(0)}k`} width={44} />
              <Tooltip cursor={CURSEUR} content={<Infobulle format={(v) => money.format(v)} />} />
              <Bar dataKey="montant" name={t("Montant")} fill={BLEU} radius={[4, 4, 0, 0]} maxBarSize={36} {...anim} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="card" data-testid="dash-revenus-cumul">
          <h3 className="font-semibold text-slate-800 mb-1 flex items-center gap-1.5">
            {t("Cumul des encaissements")}
            <AideKpi texte={t("Somme des montants encaissés depuis le début de la période affichée, mois après mois.")} />
          </h3>
          <p className="text-xs text-slate-500 mb-3">{t("Total encaissé depuis le premier mois affiché")}</p>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={chartData} margin={{ top: 8, right: 12 }}>
              <defs><linearGradient id="degrade-cumul" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={VERT} stopOpacity={0.28} /><stop offset="100%" stopColor={VERT} stopOpacity={0.02} />
              </linearGradient></defs>
              <CartesianGrid {...GRILLE} vertical={false} />
              <XAxis dataKey="month" tick={AXE} />
              <YAxis tick={AXE} tickFormatter={v => `${(v/1000).toFixed(0)}k`} width={44} />
              <Tooltip content={<Infobulle format={(v) => money.format(v)} />} />
              <Area type="monotone" dataKey="cumul" name={t("Cumul")} stroke={VERT} strokeWidth={2} fill="url(#degrade-cumul)"
                dot={{ r: 3, strokeWidth: 2, fill: "#fff" }} activeDot={{ r: 5 }} {...anim} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h3 className="font-semibold text-slate-800 mb-4">{t("Derniers paiements")}</h3>
          <div className="space-y-3">
            {(d?.recent_payments || []).map((p, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-slate-50 last:border-0">
                <div>
                  <p className="text-sm font-medium text-slate-800">{p.student}</p>
                  <p className="text-xs text-slate-400">{t(p.type)} • {p.paid_at_display || p.date} • {p.reference_number}</p>
                </div>
                <span className="text-sm font-bold text-success">{money.amountOf(p)}</span>
              </div>
            ))}
            {(d?.recent_payments || []).length === 0 && <p className="text-sm text-slate-400 text-center py-4">{t("Aucun paiement")}</p>}
          </div>
        </div>

        <div className="card">
          <h3 className="font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <Megaphone className="w-4 h-4 text-primary" />{t("Annonces actives")}</h3>
          <div className="space-y-2">
            {announcements.slice(0,4).map(a => (
              <div key={a.id} onClick={() => setSelectedAnn(a)}
                className="flex items-start gap-2 py-2 border-b border-slate-50 last:border-0 cursor-pointer hover:bg-slate-50 rounded-xl px-2 -mx-2 transition-colors">
                <div className="w-2 h-2 rounded-full bg-primary mt-1.5 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-800 hover:text-primary transition-colors">{a.title}</p>
                  <p className="text-xs text-slate-400">{(a.target_roles || []).map(libelleCible).join(", ")} • {a.created_at?.slice(0,10)}</p>
                </div>
              </div>
            ))}
            {announcements.length === 0 && <p className="text-sm text-slate-400 text-center py-4">{t("Aucune annonce")}</p>}
          </div>
        </div>
      </div>
      <AnnouncementModal announcement={selectedAnn} onClose={() => setSelectedAnn(null)} />
    </div>
  );
}