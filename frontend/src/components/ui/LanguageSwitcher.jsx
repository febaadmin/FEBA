import { useI18n } from "../../i18n";
import { useAuthStore } from "../../store/authStore";
import { authAPI } from "../../api";
import { clsx } from "clsx";

/**
 * Sélecteur de langue FR | EN.
 *  - Application immédiate (tous les composants abonnés à useI18n re-rendent).
 *  - Persistance locale (localStorage) gérée par setLang().
 *  - Si l'utilisateur est connecté, la préférence est aussi enregistrée dans
 *    son profil (PATCH /auth/me/) pour être restaurée à la reconnexion.
 *
 * variant="dark"  : en-têtes sombres (sidebar) — texte clair.
 * variant="light" : en-têtes clairs — texte sombre (défaut).
 */
export default function LanguageSwitcher({ variant = "light", className }) {
  const { lang, setLang } = useI18n();
  const { user, accessToken } = useAuthStore();

  const choose = (next) => {
    if (next === lang) return;
    setLang(next);
    // Persistance côté profil (best-effort : le choix local reste appliqué
    // même si la requête échoue — il sera resynchronisé au prochain login).
    if (accessToken && user) {
      authAPI.updateMe({ preferred_language: next }).then(({ data }) => {
        useAuthStore.getState().setAuth(
          { ...useAuthStore.getState().user, preferred_language: data.preferred_language },
          useAuthStore.getState().accessToken,
          useAuthStore.getState().refreshToken,
        );
      }).catch(() => {});
    }
  };

  const base = "px-2 py-1 rounded-md text-xs font-semibold transition-colors";
  const activeCls = variant === "dark"
    ? "bg-yellow-400 text-blue-950"
    : "bg-blue-800 text-white";
  const idleCls = variant === "dark"
    ? "text-slate-300 hover:text-white hover:bg-white/10"
    : "text-slate-500 hover:text-slate-800 hover:bg-slate-100";

  return (
    <div
      className={clsx(
        "flex items-center gap-0.5 rounded-lg p-0.5",
        variant === "dark" ? "bg-white/10" : "bg-slate-50 border border-slate-200",
        className,
      )}
      role="group"
      aria-label="Langue / Language"
    >
      <button type="button" lang="fr" aria-pressed={lang === "fr"}
        aria-label="Français"
        className={clsx(base, lang === "fr" ? activeCls : idleCls)}
        onClick={() => choose("fr")}>
        FR
      </button>
      <button type="button" lang="en" aria-pressed={lang === "en"}
        aria-label="English"
        className={clsx(base, lang === "en" ? activeCls : idleCls)}
        onClick={() => choose("en")}>
        EN
      </button>
    </div>
  );
}
