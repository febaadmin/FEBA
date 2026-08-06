import { useQuery } from "@tanstack/react-query";
import { Users, Shield, GraduationCap, UserCheck, Users2, Activity } from "lucide-react";
import { authAPI } from "../../api";
import { isCanceledError } from "../../api/academyScope";
import { useAcademy } from "../../context/AcademyContext";
import StatCard from "../../components/ui/StatCard";
import PageHeader from "../../components/ui/PageHeader";
import { motion } from "framer-motion";
import { t } from "../../i18n";

export default function SuperAdminDashboard() {
  /* La clé inclut la portée : deux académies ne peuvent plus partager la
     même entrée de cache, et une bascule ne réaffiche jamais les chiffres
     de l'académie quittée. */
  const { academyKey, businessDataEnabled } = useAcademy();

  const { data, isPending, isError, error, isFetching } = useQuery({
    queryKey: ["all-users", academyKey],
    queryFn: () => authAPI.listUsers(),
    // Ceinture et bretelles : même si un garde amont disparaissait, la
    // requête ne peut pas partir avec une portée indéterminée.
    enabled: businessDataEnabled,
  });

  /**
   * P1 — NE JAMAIS FABRIQUER DE ZÉRO.
   *
   * `data?.data?.results || []` traitait indifféremment « aucun utilisateur »
   * et « données pas encore là ». Une requête annulée rendait donc un
   * tableau de bord entièrement à zéro, chiffres parfaitement crédibles et
   * pourtant faux. On distingue désormais explicitement les trois états :
   * en attente, en erreur, et chargé.
   */
  const loaded = Boolean(data);
  const users = loaded ? data?.data?.results || data?.data || [] : null;

  // Une annulation n'est pas une erreur à afficher : la requête sera relancée
  // par le remontage. On reste en état d'attente plutôt que d'alarmer.
  const canceled = isCanceledError(error);
  const showSkeleton = isPending || !loaded || (canceled && isFetching);
  const showError = isError && !canceled && !loaded;

  const countByRole = (role) => (users || []).filter(u => u.role === role).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Super Admin — Vue globale")}
        subtitle={t("Contrôle total du système FEBA")}
      />

      {showError ? (
        <div role="alert" className="card text-sm text-red-600">
          {t("Les statistiques n'ont pas pu être chargées. Rechargez la page.")}
        </div>
      ) : showSkeleton ? (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => <div key={i} className="skeleton h-28 rounded-2xl" />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
          <StatCard title={t("Total utilisateurs")} value={users.length} icon={Users} color="secondary" delay={0} />
          <StatCard title={t("Administrateurs")}   value={countByRole("admin")}   icon={Shield}       color="primary"   delay={0.1} />
          <StatCard title={t("Enseignants")}       value={countByRole("teacher")} icon={UserCheck}    color="success"   delay={0.2} />
          <StatCard title={t("Parents")}           value={countByRole("parent")}  icon={Users2}       color="accent"    delay={0.3} />
          <StatCard title={t("Élèves")}            value={countByRole("student")} icon={GraduationCap} color="primary"  delay={0.4} />
          <StatCard title={t("Comptes actifs")}    value={users.filter(u => u.is_active).length} icon={Activity} color="success" delay={0.5} />
        </div>
      )}

      <div className="card">
        <h3 className="font-semibold text-slate-800 mb-4">{t("Répartition des rôles")}</h3>
        {showSkeleton || showError ? <div className="skeleton h-40" /> : (
          <div className="space-y-3">
            {[
              { role: "superadmin", label: t("Super Admin"), color: "from-purple-500 to-pink-500" },
              { role: "admin",      label: t("Admin"),       color: "from-primary to-primary-700" },
              { role: "teacher",    label: t("Enseignant"),  color: "from-emerald-500 to-teal-600" },
              { role: "parent",     label: t("Parent"),      color: "from-amber-500 to-orange-600" },
              { role: "student",    label: t("Élève"),       color: "from-sky-500 to-blue-600" },
            ].map(({ role, label, color }) => {
              const count = countByRole(role);
              const pct = users.length ? Math.round(count / users.length * 100) : 0;
              return (
                <div key={role}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="font-medium text-slate-700">{label}</span>
                    <span className="text-slate-500">{count} ({pct}%)</span>
                  </div>
                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }} animate={{ width: `${pct}%` }}
                      transition={{ duration: 0.8, delay: 0.2 }}
                      className={`h-full bg-gradient-to-r ${color} rounded-full`}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}