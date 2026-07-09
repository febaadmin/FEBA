import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { authAPI } from "../../api";
import AvatarUpload from "../../components/ui/AvatarUpload";
import PageHeader from "../../components/ui/PageHeader";
import { Save, Lock, Eye, EyeOff } from "lucide-react";
import { extractApiError } from "../../utils/errors";

export default function TeacherProfile() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["me"], queryFn: authAPI.me });
  const user = data?.data;
  const { register, handleSubmit, reset } = useForm();
  const { register: regPwd, handleSubmit: hsPwd, reset: resetPwd } = useForm();
  const [showOldPwd, setShowOldPwd] = useState(false);
  const [showNewPwd, setShowNewPwd] = useState(false);

  useEffect(() => {
    if (user) reset({ first_name: user.first_name, last_name: user.last_name, phone: user.phone || "" });
  }, [user, reset]);

  // ✅ Fixed: actually calls PATCH /api/auth/me/
  const updateMut = useMutation({
    mutationFn: (d) => authAPI.updateMe(d),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["me"] });
      toast.success("Profil mis à jour!");
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const pwdMut = useMutation({
    mutationFn: authAPI.changePassword,
    onSuccess: () => { toast.success("Mot de passe changé!"); resetPwd(); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  if (isLoading) return <div className="skeleton h-48 rounded-2xl" />;

  return (
    <div className="space-y-6">
      <PageHeader title="Mon Profil" subtitle={user?.email} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card flex flex-col items-center pb-6 border-b border-slate-100 mb-4">
          <AvatarUpload user={user} onUpdate={() => qc.invalidateQueries({ queryKey: ["me"] })} size="lg" />
          <h2 className="mt-3 font-bold text-slate-800 text-lg">{user?.first_name} {user?.last_name}</h2>
          <p className="text-sm text-slate-500">{user?.email}</p>
          <span className="mt-1 text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full">Enseignant</span>
        </div>
        <div className="card">
          <h3 className="font-semibold text-slate-800 mb-4">Informations personnelles</h3>
          <form onSubmit={handleSubmit(d => updateMut.mutate(d))} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div><label className="label">Prénom</label><input {...register("first_name")} className="input" /></div>
              <div><label className="label">Nom</label><input {...register("last_name")} className="input" /></div>
            </div>
            <div><label className="label">Téléphone</label><input {...register("phone")} className="input" /></div>
            <div>
              <label className="label">Email</label>
              <input value={user?.email || ""} disabled className="input bg-slate-50 text-slate-400 cursor-not-allowed" />
              <p className="text-xs text-slate-400 mt-1">L'email ne peut pas être modifié ici.</p>
            </div>
            <button type="submit" disabled={updateMut.isPending} className="btn-primary flex items-center gap-2">
              <Save className="w-4 h-4" />{updateMut.isPending ? "Enregistrement..." : "Enregistrer"}
            </button>
          </form>
        </div>
        <div className="card">
          <h3 className="font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <Lock className="w-4 h-4" />Changer le mot de passe
          </h3>
          <form onSubmit={hsPwd(d => pwdMut.mutate(d))} className="space-y-4">
            <div><label className="label">Ancien mot de passe*</label><div className="relative"><input {...regPwd("old_password", { required: true })} type={showOldPwd ? "text" : "password"} className="input pr-10" /><button type="button" onClick={() => setShowOldPwd(v => !v)} className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600">{showOldPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}</button></div></div>
            <div><label className="label">Nouveau mot de passe*</label><div className="relative"><input {...regPwd("new_password", { required: true })} type={showNewPwd ? "text" : "password"} className="input pr-10" /><button type="button" onClick={() => setShowNewPwd(v => !v)} className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600">{showNewPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}</button></div></div>
            <button type="submit" disabled={pwdMut.isPending} className="btn-primary">
              {pwdMut.isPending ? "Modification..." : "Modifier le mot de passe"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}