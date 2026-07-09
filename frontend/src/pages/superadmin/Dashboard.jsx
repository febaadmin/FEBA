import { useQuery } from "@tanstack/react-query";
import { Users, Shield, GraduationCap, UserCheck, Users2, Activity } from "lucide-react";
import { authAPI } from "../../api";
import StatCard from "../../components/ui/StatCard";
import PageHeader from "../../components/ui/PageHeader";
import { motion } from "framer-motion";

export default function SuperAdminDashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ["all-users"],
    queryFn: () => authAPI.listUsers(),
  });
  const users = data?.data?.results || data?.data || [];

  const countByRole = (role) => users.filter(u => u.role === role).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Super Admin — Vue globale"
        subtitle="Contrôle total du système FEBA"
      />

      {isLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => <div key={i} className="skeleton h-28 rounded-2xl" />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
          <StatCard title="Total utilisateurs" value={users.length} icon={Users} color="secondary" delay={0} />
          <StatCard title="Administrateurs"   value={countByRole("admin")}   icon={Shield}       color="primary"   delay={0.1} />
          <StatCard title="Enseignants"       value={countByRole("teacher")} icon={UserCheck}    color="success"   delay={0.2} />
          <StatCard title="Parents"           value={countByRole("parent")}  icon={Users2}       color="accent"    delay={0.3} />
          <StatCard title="Élèves"            value={countByRole("student")} icon={GraduationCap} color="primary"  delay={0.4} />
          <StatCard title="Comptes actifs"    value={users.filter(u => u.is_active).length} icon={Activity} color="success" delay={0.5} />
        </div>
      )}

      <div className="card">
        <h3 className="font-semibold text-slate-800 mb-4">Répartition des rôles</h3>
        {isLoading ? <div className="skeleton h-40" /> : (
          <div className="space-y-3">
            {[
              { role: "superadmin", label: "Super Admin", color: "from-purple-500 to-pink-500" },
              { role: "admin",      label: "Admin",       color: "from-primary to-primary-700" },
              { role: "teacher",    label: "Enseignant",  color: "from-emerald-500 to-teal-600" },
              { role: "parent",     label: "Parent",      color: "from-amber-500 to-orange-600" },
              { role: "student",    label: "Élève",       color: "from-sky-500 to-blue-600" },
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