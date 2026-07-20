import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { dashboardAPI, announcementsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import { motion } from "framer-motion";
import { TrendingUp, AlertCircle, BookOpen, Users, Megaphone } from "lucide-react";
import AnnouncementModal from "../../components/ui/AnnouncementModal";
import { t } from "../../i18n";

export default function ParentHome() {
  const [selectedAnn, setSelectedAnn] = useState(null);
  const { data, isLoading, isError } = useQuery({ queryKey: ["parent-dashboard"], queryFn: dashboardAPI.parent });
  const { data: annData } = useQuery({ queryKey: ["parent-announcements"], queryFn: () => announcementsAPI.list() });

  const children = data?.data?.children || [];
  const announcements = annData?.data?.results || annData?.data || [];

  return (
    <div className="space-y-6">
      <PageHeader title={t("Bonjour 👋")} subtitle={t("Tableau de bord — suivi de vos enfants")} />

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[...Array(2)].map((_,i) => <div key={i} className="skeleton h-40 rounded-2xl" />)}
        </div>
      ) : isError ? (
        // FIX: Parent1 issue — show helpful error instead of blank page
        <div className="card text-center py-12 text-slate-500 border border-amber-200 bg-amber-50">
          <AlertCircle className="w-12 h-12 mx-auto mb-3 text-amber-400" />
          <p className="font-semibold text-amber-700">{t("Profil parent introuvable")}</p>
          <p className="text-sm mt-1 text-amber-600">{t("Votre profil parent n'est pas encore configuré.")}<br />{t("Contactez l'administrateur pour lier votre compte.")}</p>
        </div>
      ) : children.length === 0 ? (
        <div className="card text-center py-12 text-slate-400">
          <Users className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>{t("Aucun enfant associé à votre compte.")}</p>
          <p className="text-sm mt-1">{t("Contactez l'administration pour lier vos enfants.")}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {children.map((child, i) => (
            <motion.div key={child.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }} className="card border-l-4 border-amber-500 hover:shadow-md transition-shadow">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center text-white text-xl font-bold shrink-0">
                  {child.name?.[0]}
                </div>
                <div>
                  <p className="font-bold text-slate-800">{child.name}</p>
                  <p className="text-xs text-slate-500">{child.class} • {child.level}</p>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-slate-50 rounded-xl p-2 text-center">
                  <p className="text-xs text-slate-500">{t("Moyenne générale")}</p>
                  <p className={`font-bold text-sm ${child.average >= 10 ? "text-success" : "text-danger"}`}>
                    {child.average != null ? `${Number(child.average).toFixed(2)}/20` : "—"}
                  </p>
                  {child.appreciation && (
                    <p className="text-[10px] text-slate-400">{t(child.appreciation)}</p>
                  )}
                </div>
                <div className="bg-slate-50 rounded-xl p-2 text-center">
                  <p className="text-xs text-slate-500">{t("Absences")}</p>
                  <p className={`font-bold text-sm ${child.absent_count > 3 ? "text-danger" : "text-slate-700"}`}>
                    {child.absent_count ?? 0}
                  </p>
                </div>
                <div className="bg-slate-50 rounded-xl p-2 text-center">
                  <p className="text-xs text-slate-500">{t("Devoirs")}</p>
                  <p className="font-bold text-sm text-primary">{child.pending_homework ?? 0}</p>
                </div>
              </div>
              {/* Moyennes trimestrielles (BUG N°3).
                  NE PAS nommer l'élément destructuré « t » : cela masquerait
                  la fonction de traduction t importée de ../../i18n
                  (cause du crash « t2 is not a function » / page blanche). */}
              <div className="grid grid-cols-3 gap-2 mt-2">
                {[["T1", child.average_t1], ["T2", child.average_t2], ["T3", child.average_t3]].map(([per, v]) => (
                  <div key={per} className="bg-slate-50 rounded-xl p-2 text-center">
                    <p className="text-xs text-slate-500">{t("Moy.")} {per}</p>
                    <p className={`font-bold text-sm ${
                      v == null ? "text-slate-300" : v >= 10 ? "text-success" : "text-danger"
                    }`}>
                      {v != null ? `${Number(v).toFixed(2)}` : "—"}
                    </p>
                  </div>
                ))}
              </div>
              {/* FIX (moyennes manquantes) : moyenne français / anglais /
                  par matière — auparavant totalement absentes du tableau de
                  bord parent. */}
              {child.bilingual && (child.bilingual.fr_average != null || child.bilingual.en_average != null) && (
                <div className="grid grid-cols-2 gap-2 mt-2">
                  <div className="bg-slate-50 rounded-xl p-2 text-center">
                    <p className="text-xs text-slate-500">{t("Français")}</p>
                    <p className={`font-bold text-sm ${
                      child.bilingual.fr_average == null ? "text-slate-300" : child.bilingual.fr_average >= 10 ? "text-success" : "text-danger"
                    }`}>
                      {child.bilingual.fr_average != null ? `${Number(child.bilingual.fr_average).toFixed(2)}/20` : t("Aucune note")}
                    </p>
                  </div>
                  <div className="bg-slate-50 rounded-xl p-2 text-center">
                    <p className="text-xs text-slate-500">{t("Anglais")}</p>
                    <p className={`font-bold text-sm ${
                      child.bilingual.en_average == null ? "text-slate-300" : child.bilingual.en_average >= 10 ? "text-success" : "text-danger"
                    }`}>
                      {child.bilingual.en_average != null ? `${Number(child.bilingual.en_average).toFixed(2)}/20` : t("Aucune note")}
                    </p>
                  </div>
                </div>
              )}
              {child.subject_averages && child.subject_averages.length > 0 && (
                <details className="mt-2">
                  <summary className="text-xs font-medium text-primary cursor-pointer select-none">{t("Voir le détail par matière")}</summary>
                  <div className="grid grid-cols-2 gap-2 mt-2">
                    {child.subject_averages.map((s) => (
                      <div key={s.subject_id} className="flex items-center justify-between px-2 py-1.5 rounded-lg bg-slate-50 text-xs">
                        <span className="text-slate-600 truncate pr-1">{s.subject_name}</span>
                        <span className={`font-semibold whitespace-nowrap ${
                          s.average == null ? "text-slate-400" : s.average >= 10 ? "text-success" : "text-danger"
                        }`}>
                          {s.average != null ? `${Number(s.average).toFixed(2)}` : t("Aucune note")}
                        </span>
                      </div>
                    ))}
                  </div>
                </details>
              )}
              {child.progression != null && (
                <div className={`mt-2 flex items-center gap-1.5 text-xs font-medium ${
                  child.progression >= 0 ? "text-success" : "text-danger"
                }`}>
                  <TrendingUp className={`w-3.5 h-3.5 ${child.progression < 0 ? "rotate-180" : ""}`} />
                  {t("Progression T1 → T2 :")} {child.progression >= 0 ? "+" : ""}{child.progression} pt
                </div>
              )}
            </motion.div>
          ))}
        </div>
      )}

      {announcements.length > 0 && (
        <div className="card">
          <h3 className="font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <Megaphone className="w-4 h-4 text-primary" />{t("Annonces récentes")}</h3>
          <div className="space-y-3">
            {announcements.slice(0, 3).map(a => (
              <div key={a.id} onClick={() => setSelectedAnn(a)}
                className="flex items-start gap-3 p-3 bg-primary-50/30 rounded-xl cursor-pointer hover:bg-primary-50 transition-colors">
                <div className="w-2 h-2 rounded-full bg-primary mt-1.5 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-800 hover:text-primary transition-colors">{a.title}</p>
                  <p className="text-xs text-slate-500 mt-0.5 truncate">{a.content?.slice(0, 100)}</p>
                  <p className="text-xs text-slate-400 mt-1">{a.created_at?.slice(0, 10)}</p>
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