import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { authAPI, parentsAPI, schoolsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import AvatarUpload from "../../components/ui/AvatarUpload";
import { Save, Lock, User, Eye, EyeOff, GraduationCap, Calendar } from "lucide-react";
import { extractApiError } from "../../utils/errors";
import { t } from "../../i18n";

export default function ParentProfile() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["me"], queryFn: authAPI.me });
  const user = data?.data;

  const { data: parentData } = useQuery({
    queryKey: ["parent-profile"],
    queryFn: () => parentsAPI.list({ user: user?.id }),
    enabled: !!user?.id,
  });
  const { data: yearsData } = useQuery({ queryKey: ["years"], queryFn: schoolsAPI.years });
  const years = yearsData?.data?.results || yearsData?.data || [];
  const currentYear = years.find(y => y.is_current);
  const parent = parentData?.data?.results?.[0] || parentData?.data?.[0];
  const children = parent?.children_links || [];

  const { register, handleSubmit, reset } = useForm();
  const { register: regPwd, handleSubmit: hsPwd, reset: resetPwd } = useForm();
  const [showOldPwd, setShowOldPwd] = useState(false);
  const [showNewPwd, setShowNewPwd] = useState(false);
  const [showConfirmPwd, setShowConfirmPwd] = useState(false);

  useEffect(() => {
    if (user) reset({ first_name: user.first_name, last_name: user.last_name, phone: user.phone || "" });
  }, [user, reset]);

  const updateMut = useMutation({
    mutationFn: (d) => authAPI.updateMe(d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["me"] }); toast.success(t("Profil mis à jour !")); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const pwdMut = useMutation({
    mutationFn: authAPI.changePassword,
    onSuccess: () => { toast.success(t("Mot de passe changé !")); resetPwd(); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  if (isLoading) return <div className="skeleton h-48 rounded-2xl" />;

  return (
    <div className="space-y-6">
      <PageHeader title={t("Mon Profil")} subtitle={t("Année scolaire {y}", { y: currentYear?.name || "" })} />

      {/* Avatar */}
      <div className="card flex flex-col items-center gap-3 py-6">
        <AvatarUpload user={user} onUpdate={() => qc.invalidateQueries({ queryKey: ["me"] })} size="lg" />
        <div className="text-center">
          <p className="font-bold text-slate-800 text-xl">{user?.first_name} {user?.last_name}</p>
          <p className="text-sm text-slate-500 mt-0.5">{user?.email}</p>
          <span className="mt-2 inline-block text-xs bg-amber-50 text-amber-700 px-3 py-0.5 rounded-full font-medium">{t("Parent")}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Edit info */}
        <div className="card">
          <h3 className="font-semibold text-slate-800 mb-4">{t("Informations personnelles")}</h3>
          <form onSubmit={handleSubmit(d => updateMut.mutate(d))} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div><label className="label">{t("Prénom")}</label><input {...register("first_name")} className="input" /></div>
              <div><label className="label">{t("Nom")}</label><input {...register("last_name")} className="input" /></div>
            </div>
            <div><label className="label">{t("Téléphone")}</label><input {...register("phone")} className="input" /></div>
            <div>
              <label className="label">{t("Email")}</label>
              <input value={user?.email || ""} disabled className="input bg-slate-50 text-slate-400 cursor-not-allowed" />
            </div>
            {parent && (
              <>
                <div><label className="label">{t("Profession")}</label><input value={parent.profession || "—"} disabled className="input bg-slate-50 text-slate-400" /></div>
                <div><label className="label">{t("Adresse")}</label><input value={parent.address || "—"} disabled className="input bg-slate-50 text-slate-400" /></div>
              </>
            )}
            <button type="submit" disabled={updateMut.isPending} className="btn-primary flex items-center gap-2">
              <Save className="w-4 h-4" />{updateMut.isPending ? t("Enregistrement…") : t("Enregistrer")}
            </button>
          </form>
        </div>

        {/* Children */}
        {children.length > 0 && (
          <div className="card">
            <h3 className="font-semibold text-slate-800 mb-4 flex items-center gap-2">
              <GraduationCap className="w-4 h-4 text-amber-500" />
              Mes enfants — {currentYear?.name || "année en cours"} ({children.length})
            </h3>
            <div className="space-y-3">
              {children.map(link => (
                <div key={link.id || link.student} className="flex items-center gap-3 bg-slate-50 rounded-xl p-3 border border-slate-100">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-violet-600 flex items-center justify-center text-white text-sm font-bold shrink-0">
                    {(link.student_name || "?")[0]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-slate-800">{link.student_name || `Élève #${link.student}`}</p>
                    <div className="flex items-center gap-3 mt-0.5 flex-wrap">
                      <span className="text-xs text-slate-400">{link.relation_label || link.relation || "—"}</span>
                      {link.class_name && (
                        <span className="text-xs bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded-md font-medium">
                          📚 {link.class_name}
                        </span>
                      )}
                      {currentYear && (
                        <span className="text-xs bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded-md font-medium flex items-center gap-1">
                          <Calendar className="w-3 h-3" />{currentYear.name}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Change password */}
        <div className="card">
          <h3 className="font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <Lock className="w-4 h-4" />{t("Changer le mot de passe")}</h3>
          <form onSubmit={hsPwd(d => pwdMut.mutate(d))} className="space-y-4">
            <div><label className="label">{t("Mot de passe actuel")}</label><div className="relative"><input {...regPwd("old_password", { required: true })} type={showOldPwd ? "text" : "password"} className="input pr-10" /><button type="button" onClick={() => setShowOldPwd(v => !v)} className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600">{showOldPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}</button></div></div>
            <div><label className="label">{t("Nouveau mot de passe")}</label><div className="relative"><input {...regPwd("new_password", { required: true, minLength: 8 })} type={showNewPwd ? "text" : "password"} className="input pr-10" /><button type="button" onClick={() => setShowNewPwd(v => !v)} className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600">{showNewPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}</button></div></div>
            <div><label className="label">{t("Confirmer")}</label><div className="relative"><input {...regPwd("confirm_password", { required: true })} type={showConfirmPwd ? "text" : "password"} className="input pr-10" /><button type="button" onClick={() => setShowConfirmPwd(v => !v)} className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600">{showConfirmPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}</button></div></div>
            <button type="submit" disabled={pwdMut.isPending} className="btn-primary flex items-center gap-2">
              <Save className="w-4 h-4" />{pwdMut.isPending ? t("Enregistrement…") : t("Changer")}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
