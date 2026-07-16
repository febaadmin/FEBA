import { useNavigate } from "react-router-dom";
import { Home, AlertCircle } from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { t } from "../../i18n";

/**
 * Affichée quand une URL ne correspond à aucune route connue — notamment
 * quand une notification pointe vers une ressource supprimée entre-temps,
 * ou vers une route mal formée. La session n'est JAMAIS touchée ici :
 * l'utilisateur reste connecté, seul l'écran change.
 */
export default function NotFoundPage() {
  const navigate = useNavigate();
  const { user } = useAuthStore();

  const dashboardByRole = {
    superadmin: "/superadmin/dashboard",
    admin: "/admin/dashboard",
    teacher: "/teacher/dashboard",
    parent: "/parent/home",
    student: "/student/home",
  };
  const home = dashboardByRole[user?.role] || "/";

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <div className="max-w-md w-full text-center bg-white rounded-2xl shadow-sm border border-slate-100 p-8">
        <div className="w-14 h-14 rounded-full bg-amber-50 text-amber-500 flex items-center justify-center mx-auto mb-4">
          <AlertCircle className="w-7 h-7" />
        </div>
        <h1 className="text-lg font-semibold text-slate-800 mb-2">{t("Cette page n'existe pas ou plus")}</h1>
        <p className="text-sm text-slate-500 mb-6">{t("La ressource demandée est introuvable — elle a peut-être été supprimée, ou le lien utilisé n'est plus valide. Vous êtes toujours connecté.")}</p>
        <button
          onClick={() => navigate(home, { replace: true })}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-white text-sm font-medium hover:opacity-90 transition"
        >
          <Home className="w-4 h-4" />{t("Retour au tableau de bord")}</button>
      </div>
    </div>
  );
}
