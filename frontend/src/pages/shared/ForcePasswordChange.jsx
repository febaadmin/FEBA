/**
 * ForcePasswordChange — P2 v4
 *
 * Écran obligatoire affiché après connexion quand un administrateur a
 * réinitialisé le mot de passe (must_change_password=true) : l'utilisateur
 * doit choisir SON propre mot de passe (l'ancien = mot de passe temporaire
 * communiqué par l'administrateur) avant de retrouver son espace.
 * Le backend lève le drapeau à la réussite de /auth/change-password/.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { Eye, EyeOff, KeyRound, Loader2, ShieldAlert } from "lucide-react";
import toast from "react-hot-toast";
import { authAPI } from "../../api";
import { useAuthStore } from "../../store/authStore";
import { useAuth } from "../../hooks/useAuth";
import { extractApiErrors } from "../../utils/errors";
import { t } from "../../i18n";

const HOME_BY_ROLE = {
  superadmin: "/superadmin/dashboard",
  admin: "/admin/dashboard",
  teacher: "/teacher/dashboard",
  parent: "/parent/home",
  student: "/student/home",
};

export default function ForcePasswordChange() {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const { user, accessToken, refreshToken, setAuth } = useAuthStore();
  const [show, setShow] = useState({ old: false, new1: false, new2: false });
  const [apiErrors, setApiErrors] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const { register, handleSubmit, watch, formState: { errors } } = useForm({ mode: "onChange" });
  const newPassword = watch("new_password");

  const toggle = (k) => setShow((s) => ({ ...s, [k]: !s[k] }));

  const onSubmit = async (d) => {
    setApiErrors([]);
    setSubmitting(true);
    try {
      await authAPI.changePassword({
        old_password: d.old_password,
        new_password: d.new_password,
      });
      // Drapeau levé côté backend — synchroniser le store local.
      setAuth({ ...user, must_change_password: false }, accessToken, refreshToken);
      toast.success(t("Mot de passe modifié. Bienvenue !"));
      navigate(HOME_BY_ROLE[user?.role] || "/", { replace: true });
    } catch (e) {
      const errs = extractApiErrors(e);
      setApiErrors(errs);
      toast.error(errs[0]);
    } finally {
      setSubmitting(false);
    }
  };

  const eyeBtn = (key, visible) => (
    <button type="button" onClick={() => toggle(key)} tabIndex={-1}
      aria-label={visible ? t("Masquer le mot de passe") : t("Afficher le mot de passe")}
      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
      {visible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
    </button>
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-950 via-blue-900 to-blue-800 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-2xl p-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center">
            <KeyRound className="w-5 h-5 text-amber-600" />
          </div>
          <h1 className="text-lg font-bold text-slate-800">
            {t("Nouveau mot de passe requis")}
          </h1>
        </div>
        <div className="flex gap-2 rounded-xl bg-amber-50 border border-amber-200 p-3 text-xs text-amber-800 mb-5">
          <ShieldAlert className="w-4 h-4 mt-0.5 shrink-0" />
          <p>
            {t("Votre mot de passe a été réinitialisé par un administrateur. Pour sécuriser votre compte, choisissez maintenant votre propre mot de passe.")}
          </p>
        </div>

        {apiErrors.length > 0 && (
          <div className="rounded-xl bg-red-50 border border-red-200 p-3 space-y-1 mb-4">
            {apiErrors.map((err, i) => (
              <p key={i} className="text-sm text-red-700">{err}</p>
            ))}
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div>
            <label className="label" htmlFor="fpc-old">{t("Mot de passe temporaire *")}</label>
            <div className="relative">
              <input id="fpc-old"
                {...register("old_password", { required: t("Le mot de passe temporaire est obligatoire.") })}
                type={show.old ? "text" : "password"} autoComplete="current-password"
                className={`input pr-10 ${errors.old_password ? "border-red-400" : ""}`} placeholder="••••••••" />
              {eyeBtn("old", show.old)}
            </div>
            {errors.old_password && <p className="mt-1 text-xs text-red-600">{errors.old_password.message}</p>}
          </div>

          <div>
            <label className="label" htmlFor="fpc-new">{t("Nouveau mot de passe *")}</label>
            <div className="relative">
              <input id="fpc-new"
                {...register("new_password", {
                  required: t("Le nouveau mot de passe est obligatoire."),
                  minLength: { value: 8, message: t("Minimum {n} caractères.").replace("{n}", 8) },
                })}
                type={show.new1 ? "text" : "password"} autoComplete="new-password"
                className={`input pr-10 ${errors.new_password ? "border-red-400" : ""}`} placeholder="••••••••" />
              {eyeBtn("new1", show.new1)}
            </div>
            {errors.new_password && <p className="mt-1 text-xs text-red-600">{errors.new_password.message}</p>}
          </div>

          <div>
            <label className="label" htmlFor="fpc-new2">{t("Confirmer le nouveau mot de passe *")}</label>
            <div className="relative">
              <input id="fpc-new2"
                {...register("confirm_password", {
                  required: t("La confirmation est obligatoire."),
                  validate: (v) => v === newPassword || t("Les mots de passe ne correspondent pas."),
                })}
                type={show.new2 ? "text" : "password"} autoComplete="new-password"
                className={`input pr-10 ${errors.confirm_password ? "border-red-400" : ""}`} placeholder="••••••••" />
              {eyeBtn("new2", show.new2)}
            </div>
            {errors.confirm_password && <p className="mt-1 text-xs text-red-600">{errors.confirm_password.message}</p>}
          </div>

          <ul className="text-xs text-slate-500 list-disc pl-5 space-y-0.5">
            <li>{t("Au moins 8 caractères.")}</li>
            <li>{t("Pas uniquement des chiffres.")}</li>
            <li>{t("Différent des informations personnelles (nom, email).")}</li>
            <li>{t("Pas un mot de passe trop courant.")}</li>
          </ul>

          <button type="submit" disabled={submitting}
            className="w-full bg-blue-800 hover:bg-blue-900 text-white font-semibold py-2.5 rounded-lg transition flex items-center justify-center gap-2 disabled:opacity-60">
            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
            {submitting ? t("Enregistrement...") : t("Définir mon nouveau mot de passe")}
          </button>
        </form>

        <button onClick={logout} className="w-full text-center text-xs text-slate-400 hover:text-slate-600 mt-4">
          {t("Se déconnecter")}
        </button>
      </div>
    </div>
  );
}
