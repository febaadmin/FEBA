/**
 * ResetPasswordModal — P2 v4
 *
 * Réinitialisation du mot de passe d'un utilisateur par un administrateur
 * autorisé. Les permissions réelles sont appliquées côté BACKEND
 * (/api/auth/users/<id>/reset-password/) — ce composant n'est qu'une
 * interface : identité de la cible, avertissement de sécurité, nouveau mot
 * de passe + confirmation avec affichage/masquage, règles de complexité,
 * confirmation explicite avant l'envoi.
 */
import { useState, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { Eye, EyeOff, KeyRound, ShieldAlert } from "lucide-react";
import toast from "react-hot-toast";
import { authAPI } from "../../api";
import { extractApiErrors } from "../../utils/errors";
import Modal from "./Modal";
import { t } from "../../i18n";

const MIN_PASSWORD_LENGTH = 8;

const ROLE_LABELS = {
  superadmin: "Super Administrateur",
  admin: "Administrateur",
  teacher: "Enseignant",
  parent: "Parent",
  student: "Élève",
};

export default function ResetPasswordModal({ user, onClose }) {
  const [showPwd, setShowPwd] = useState(false);
  const [showPwd2, setShowPwd2] = useState(false);
  const [apiErrors, setApiErrors] = useState([]);
  const {
    register, handleSubmit, watch, reset,
    formState: { errors },
  } = useForm({ mode: "onChange" });

  const newPassword = watch("new_password");

  useEffect(() => {
    if (user) {
      reset({ new_password: "", confirm_password: "", confirm_action: false });
      setApiErrors([]);
      setShowPwd(false);
      setShowPwd2(false);
    }
  }, [user, reset]);

  const resetMut = useMutation({
    mutationFn: (d) =>
      authAPI.adminResetPassword(user.id, {
        new_password: d.new_password,
        confirm_password: d.confirm_password,
      }),
    onSuccess: (resp) => {
      toast.success(resp.data?.detail || t("Mot de passe réinitialisé."));
      onClose();
    },
    onError: (e) => {
      const errs = extractApiErrors(e);
      setApiErrors(errs);
      toast.error(errs[0]);
    },
  });

  if (!user) return null;

  return (
    <Modal open onClose={onClose} title={t("Réinitialiser le mot de passe")} size="md">
      <form onSubmit={handleSubmit((d) => resetMut.mutate(d))} className="space-y-4" noValidate>
        {/* Identité de l'utilisateur concerné */}
        <div className="flex items-center gap-3 rounded-xl bg-slate-50 border border-slate-200 p-3">
          <div className="w-11 h-11 rounded-xl bg-primary-50 flex items-center justify-center text-primary font-bold">
            {user.first_name?.[0]}{user.last_name?.[0]}
          </div>
          <div className="min-w-0">
            <p className="font-semibold text-slate-800 truncate">
              {user.first_name} {user.last_name}
            </p>
            <p className="text-xs text-slate-500 truncate">{user.email}</p>
          </div>
          <span className="ml-auto badge bg-primary-50 text-primary shrink-0">
            {t(ROLE_LABELS[user.role] || user.role)}
          </span>
        </div>

        {/* Avertissement de sécurité */}
        <div className="flex gap-2 rounded-xl bg-amber-50 border border-amber-200 p-3 text-xs text-amber-800">
          <ShieldAlert className="w-4 h-4 mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold">{t("Action sensible")}</p>
            <p>{t("Les sessions actives de cet utilisateur seront déconnectées et il devra choisir un nouveau mot de passe à sa prochaine connexion. Cette opération est journalisée.")}</p>
          </div>
        </div>

        {apiErrors.length > 0 && (
          <div className="rounded-xl bg-red-50 border border-red-200 p-3 space-y-1">
            {apiErrors.map((err, i) => (
              <p key={i} className="text-sm text-red-700">{err}</p>
            ))}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">{t("Nouveau mot de passe *")}</label>
            <div className="relative">
              <input
                {...register("new_password", {
                  required: t("Le nouveau mot de passe est obligatoire."),
                  minLength: {
                    value: MIN_PASSWORD_LENGTH,
                    message: t("Minimum {n} caractères.").replace("{n}", MIN_PASSWORD_LENGTH),
                  },
                })}
                type={showPwd ? "text" : "password"}
                autoComplete="new-password"
                className={`input pr-10 ${errors.new_password ? "border-red-400" : ""}`}
                placeholder="••••••••"
              />
              <button type="button" onClick={() => setShowPwd(v => !v)} tabIndex={-1}
                aria-label={showPwd ? t("Masquer le mot de passe") : t("Afficher le mot de passe")}
                className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600">
                {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {errors.new_password && (
              <p className="mt-1 text-xs text-red-600">{errors.new_password.message}</p>
            )}
          </div>
          <div>
            <label className="label">{t("Confirmer *")}</label>
            <div className="relative">
              <input
                {...register("confirm_password", {
                  required: t("La confirmation est obligatoire."),
                  validate: (v) => v === newPassword || t("Les mots de passe ne correspondent pas."),
                })}
                type={showPwd2 ? "text" : "password"}
                autoComplete="new-password"
                className={`input pr-10 ${errors.confirm_password ? "border-red-400" : ""}`}
                placeholder="••••••••"
              />
              <button type="button" onClick={() => setShowPwd2(v => !v)} tabIndex={-1}
                aria-label={showPwd2 ? t("Masquer le mot de passe") : t("Afficher le mot de passe")}
                className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600">
                {showPwd2 ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {errors.confirm_password && (
              <p className="mt-1 text-xs text-red-600">{errors.confirm_password.message}</p>
            )}
          </div>
        </div>

        {/* Règles de complexité (validées aussi côté backend par Django) */}
        <ul className="text-xs text-slate-500 list-disc pl-5 space-y-0.5">
          <li>{t("Au moins 8 caractères.")}</li>
          <li>{t("Pas uniquement des chiffres.")}</li>
          <li>{t("Différent des informations personnelles (nom, email).")}</li>
          <li>{t("Pas un mot de passe trop courant.")}</li>
        </ul>

        {/* Confirmation explicite */}
        <label className="flex items-start gap-2 text-sm text-slate-700 cursor-pointer">
          <input
            type="checkbox"
            {...register("confirm_action", { required: true })}
            className="mt-0.5 rounded border-slate-300"
          />
          <span>
            {t("Je confirme vouloir réinitialiser le mot de passe de")}{" "}
            <strong>{user.first_name} {user.last_name}</strong>.
          </span>
        </label>
        {errors.confirm_action && (
          <p className="text-xs text-red-600">{t("Veuillez cocher la case de confirmation.")}</p>
        )}

        <div className="flex gap-3 justify-end pt-2 border-t border-slate-100">
          <button type="button" onClick={onClose} className="btn-secondary">{t("Annuler")}</button>
          <button type="submit" disabled={resetMut.isPending}
            className="btn-primary min-w-[160px] flex items-center justify-center gap-2">
            <KeyRound className="w-4 h-4" />
            {resetMut.isPending ? t("Réinitialisation…") : t("Réinitialiser")}
          </button>
        </div>
      </form>
    </Modal>
  );
}
