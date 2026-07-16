import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { authAPI } from "../../api";
import AvatarUpload from "../../components/ui/AvatarUpload";
import PageHeader from "../../components/ui/PageHeader";
import { Save, Lock, Eye, EyeOff } from "lucide-react";
import { extractApiError } from "../../utils/errors";
import { t } from "../../i18n";

/**
 * FIX (mot de passe administrateur/super administrateur) : les rôles
 * enseignant, parent et élève disposaient déjà d'un formulaire de
 * changement de mot de passe (voir pages/&lt;role&gt;/Profile.jsx), mais admin et
 * superadmin n'avaient AUCUNE page pour y accéder — alors que l'endpoint
 * backend POST /api/auth/change-password/ fonctionnait déjà pour tout
 * utilisateur authentifié (ChangePasswordView n'est pas restreint par
 * rôle). Le bug était donc uniquement côté frontend : absence de route et
 * de formulaire. Ce composant est partagé par /admin/profile et
 * /superadmin/profile pour éviter la duplication.
 *
 * Ajouts par rapport au formulaire existant (teacher/parent/student) :
 *  - confirmation du nouveau mot de passe (absente jusqu'ici, explicitement
 *    demandée dans les corrections prioritaires) ;
 *  - message de succès et remise à zéro du formulaire ;
 *  - les erreurs backend (ancien mot de passe incorrect, règles de
 *    complexité Django validate_password) sont affichées telles quelles.
 */
export default function AccountProfile({ roleLabel }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["me"], queryFn: authAPI.me });
  const user = data?.data;
  const { register, handleSubmit, reset } = useForm();
  const {
    register: regPwd,
    handleSubmit: hsPwd,
    reset: resetPwd,
    watch: watchPwd,
    formState: { errors: pwdErrors },
  } = useForm();
  const [showOldPwd, setShowOldPwd] = useState(false);
  const [showNewPwd, setShowNewPwd] = useState(false);
  const [showConfirmPwd, setShowConfirmPwd] = useState(false);

  useEffect(() => {
    if (user) reset({ first_name: user.first_name, last_name: user.last_name, phone: user.phone || "" });
  }, [user, reset]);

  const updateMut = useMutation({
    mutationFn: (d) => authAPI.updateMe(d),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me"] });
      toast.success(t("Profil mis à jour !"));
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const pwdMut = useMutation({
    mutationFn: (d) => authAPI.changePassword({ old_password: d.old_password, new_password: d.new_password }),
    onSuccess: () => {
      toast.success(t("Mot de passe modifié avec succès."));
      resetPwd();
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  if (isLoading) return <div className="skeleton h-48 rounded-2xl" />;

  const newPwdValue = watchPwd("new_password");

  return (
    <div className="space-y-6">
      <PageHeader title={t("Mon profil")} subtitle={user?.email} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card flex flex-col items-center pb-6 border-b border-slate-100 mb-4">
          <AvatarUpload user={user} onUpdate={() => qc.invalidateQueries({ queryKey: ["me"] })} size="lg" />
          <h2 className="mt-3 font-bold text-slate-800 text-lg">{user?.first_name} {user?.last_name}</h2>
          <p className="text-sm text-slate-500">{user?.email}</p>
          <span className="mt-1 text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full">{roleLabel}</span>
        </div>

        <div className="card">
          <h3 className="font-semibold text-slate-800 mb-4">{t("Informations personnelles")}</h3>
          <form onSubmit={handleSubmit((d) => updateMut.mutate(d))} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div><label className="label">{t("Prénom")}</label><input {...register("first_name")} className="input" /></div>
              <div><label className="label">{t("Nom")}</label><input {...register("last_name")} className="input" /></div>
            </div>
            <div><label className="label">{t("Téléphone")}</label><input {...register("phone")} className="input" /></div>
            <div>
              <label className="label">{t("Email")}</label>
              <input value={user?.email || ""} disabled className="input bg-slate-50 text-slate-400 cursor-not-allowed" />
              <p className="text-xs text-slate-400 mt-1">{t("L'email ne peut pas être modifié ici.")}</p>
            </div>
            <button type="submit" disabled={updateMut.isPending} className="btn-primary flex items-center gap-2">
              <Save className="w-4 h-4" />{updateMut.isPending ? t("Enregistrement...") : t("Enregistrer")}
            </button>
          </form>
        </div>

        <div className="card lg:col-span-2">
          <h3 className="font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <Lock className="w-4 h-4" />{t("Changer le mot de passe")}</h3>
          <form onSubmit={hsPwd((d) => pwdMut.mutate(d))} className="space-y-4 max-w-md">
            <div>
              <label className="label">{t("Mot de passe actuel*")}</label>
              <div className="relative">
                <input
                  {...regPwd("old_password", { required: "Le mot de passe actuel est requis." })}
                  type={showOldPwd ? "text" : "password"}
                  className="input pr-10"
                />
                <button type="button" onClick={() => setShowOldPwd((v) => !v)} className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600">
                  {showOldPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {pwdErrors.old_password && <p className="text-xs text-red-500 mt-1">{pwdErrors.old_password.message}</p>}
            </div>
            <div>
              <label className="label">{t("Nouveau mot de passe*")}</label>
              <div className="relative">
                <input
                  {...regPwd("new_password", { required: "Le nouveau mot de passe est requis.", minLength: { value: 8, message: "8 caractères minimum." } })}
                  type={showNewPwd ? "text" : "password"}
                  className="input pr-10"
                />
                <button type="button" onClick={() => setShowNewPwd((v) => !v)} className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600">
                  {showNewPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {pwdErrors.new_password && <p className="text-xs text-red-500 mt-1">{pwdErrors.new_password.message}</p>}
            </div>
            <div>
              <label className="label">{t("Confirmer le nouveau mot de passe*")}</label>
              <div className="relative">
                <input
                  {...regPwd("confirm_password", {
                    required: "Merci de confirmer le nouveau mot de passe.",
                    validate: (v) => v === newPwdValue || "Les mots de passe ne correspondent pas.",
                  })}
                  type={showConfirmPwd ? "text" : "password"}
                  className="input pr-10"
                />
                <button type="button" onClick={() => setShowConfirmPwd((v) => !v)} className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600">
                  {showConfirmPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {pwdErrors.confirm_password && <p className="text-xs text-red-500 mt-1">{pwdErrors.confirm_password.message}</p>}
            </div>
            <button type="submit" disabled={pwdMut.isPending} className="btn-primary">
              {pwdMut.isPending ? t("Modification...") : t("Modifier le mot de passe")}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
