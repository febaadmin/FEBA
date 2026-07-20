import { useAuthStore } from "../store/authStore";
import { authAPI } from "../api";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { getLang, setLang, translate } from "../i18n";
import toast from "react-hot-toast";

export function useAuth() {
  const { user, accessToken, setAuth, clearAuth } = useAuthStore();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const login = async (email, password) => {
    // Clear all cached data from any previous user session
    queryClient.clear();
    const { data } = await authAPI.login({ email, password });
    setAuth(null, data.access, data.refresh);
    const me = await authAPI.me();
    setAuth(me.data, data.access, data.refresh);
    // La préférence enregistrée dans le profil est PRIORITAIRE à la
    // reconnexion (exigence bilinguisme) : elle écrase le choix local.
    if (me.data.preferred_language && me.data.preferred_language !== getLang()) {
      setLang(me.data.preferred_language);
    }
    // P2 : mot de passe réinitialisé par un administrateur → l'utilisateur
    // doit d'abord choisir son propre mot de passe (parcours obligatoire).
    if (me.data.must_change_password) {
      navigate("/change-password-required");
      toast(translate("Veuillez définir votre nouveau mot de passe."), { icon: "🔑" });
      return;
    }
    const role = me.data.role;
    if (role === "superadmin") navigate("/superadmin/dashboard");
    else if (role === "admin")   navigate("/admin/dashboard");
    else if (role === "teacher") navigate("/teacher/dashboard");
    else if (role === "parent")  navigate("/parent/home");
    else navigate("/student/home");
    toast.success(translate("Bienvenue, {name}!", { name: me.data.first_name }));
  };

  const logout = async () => {
    try {
      const { refreshToken } = useAuthStore.getState();
      if (refreshToken) await authAPI.logout(refreshToken);
    } catch { /* déconnexion best-effort : le token local est purgé quoi qu'il arrive */ }
    // Clear ALL cached queries so next user sees fresh data
    queryClient.clear();
    clearAuth();
    navigate("/login");
    toast.success(translate("Déconnexion réussie."));
  };

  return { user, isAuthenticated: !!accessToken, login, logout };
}
