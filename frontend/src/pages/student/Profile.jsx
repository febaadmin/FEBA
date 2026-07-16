import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { authAPI, studentsAPI, gradesAPI, attendanceAPI, homeworkAPI, schoolsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import AvatarUpload from "../../components/ui/AvatarUpload";
import { Save, Lock, Eye, EyeOff, BookOpen, AlertCircle, ClipboardList } from "lucide-react";
import { extractApiError } from "../../utils/errors";
import { t } from "../../i18n";

export default function StudentProfile() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["me"], queryFn: authAPI.me });
  const user = data?.data;

  const { data: studData } = useQuery({
    queryKey: ["student-profile"],
    queryFn: () => studentsAPI.list({ user: user?.id }),
    enabled: !!user?.id,
  });
  const student = studData?.data?.results?.[0] || studData?.data?.[0];

  // Current year
  const { data: yearsData } = useQuery({ queryKey: ["years"], queryFn: schoolsAPI.years });
  const years = yearsData?.data?.results || yearsData?.data || [];
  const currentYear = years.find(y => y.is_current);

  // Year-filtered data
  const { data: gradesData } = useQuery({
    queryKey: ["student-grades-profile", student?.id, currentYear?.id],
    queryFn: () => gradesAPI.list({ student: student.id, school_year: currentYear?.id }),
    enabled: !!(student?.id && currentYear?.id),
  });
  const { data: attendData } = useQuery({
    queryKey: ["student-attend-profile", student?.id, currentYear?.id],
    queryFn: () => attendanceAPI.list({ student: student.id, school_year: currentYear?.id }),
    enabled: !!(student?.id && currentYear?.id),
  });
  const { data: homeworkData } = useQuery({
    queryKey: ["student-hw-profile", student?.id, currentYear?.id],
    queryFn: () => homeworkAPI.list({ school_year: currentYear?.id }),
    enabled: !!(student?.id && currentYear?.id),
  });

  const grades = gradesData?.data?.results || gradesData?.data || [];
  const attendRecords = attendData?.data?.results || attendData?.data || [];
  const homework = homeworkData?.data?.results || homeworkData?.data || [];

  const absences = attendRecords.filter(r => r.status === "absent" || r.status === "late");
  const avgGrade = grades.length > 0
    ? (grades.reduce((sum, g) => sum + parseFloat(g.value || 0), 0) / grades.length).toFixed(2)
    : null;

  const { register: regPwd, handleSubmit: hsPwd, reset: resetPwd } = useForm();
  const [showOldPwd, setShowOldPwd] = useState(false);
  const [showNewPwd, setShowNewPwd] = useState(false);
  const [showConfirmPwd, setShowConfirmPwd] = useState(false);

  const pwdMut = useMutation({
    mutationFn: authAPI.changePassword,
    onSuccess: () => { toast.success(t("Mot de passe changé !")); resetPwd(); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  if (isLoading) return <div className="skeleton h-48 rounded-2xl" />;

  return (
    <div className="space-y-6">
      <PageHeader title={t("Mon Profil")} subtitle={t("Année scolaire {y}", { y: currentYear?.name || "" })} />

      {/* Avatar card */}
      <div className="card flex flex-col items-center gap-3 py-6">
        <AvatarUpload user={user} onUpdate={() => qc.invalidateQueries({ queryKey: ["me"] })} size="lg" />
        <div className="text-center">
          <p className="font-bold text-slate-800 text-xl">{user?.first_name} {user?.last_name}</p>
          <p className="text-sm text-slate-500 mt-0.5">{user?.email}</p>
          <span className="mt-2 inline-block text-xs bg-sky-50 text-sky-700 px-3 py-0.5 rounded-full font-medium">{t("Élève")}</span>
        </div>
      </div>

      {/* Academic year summary stats */}
      {currentYear && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="card text-center py-4">
            <ClipboardList className="w-6 h-6 mx-auto mb-2 text-blue-500" />
            <p className="text-2xl font-bold text-slate-800">{grades.length}</p>
            <p className="text-xs text-slate-500 mt-0.5">{t("Notes cette année")}</p>
            {avgGrade && <p className="text-sm font-semibold text-blue-600 mt-1">{t("Moy.")} {avgGrade}/20</p>}
          </div>
          <div className="card text-center py-4">
            <AlertCircle className="w-6 h-6 mx-auto mb-2 text-amber-500" />
            <p className="text-2xl font-bold text-slate-800">{absences.length}</p>
            <p className="text-xs text-slate-500 mt-0.5">{t("Absences / retards")}</p>
          </div>
          <div className="card text-center py-4">
            <BookOpen className="w-6 h-6 mx-auto mb-2 text-green-500" />
            <p className="text-2xl font-bold text-slate-800">{homework.length}</p>
            <p className="text-xs text-slate-500 mt-0.5">{t("Devoirs assignés")}</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Account info */}
        <div className="card">
          <h3 className="font-semibold text-slate-800 mb-4">{t("Compte utilisateur")}</h3>
          <dl className="space-y-3 text-sm">
            {[
              ["Prénom", user?.first_name],
              ["Nom", user?.last_name],
              ["Email", user?.email],
              ["Téléphone", user?.phone || "—"],
              ["Rôle", "Élève"],
              ["Compte créé le", user?.created_at?.slice(0, 10) || "—"],
            ].map(([label, val]) => (
              <div key={label} className="flex justify-between py-2 border-b border-slate-50 last:border-0">
                <dt className="text-slate-500 font-medium">{label}</dt>
                <dd className="text-slate-800 font-semibold text-right">{val}</dd>
              </div>
            ))}
          </dl>
        </div>

        {/* Student-specific info */}
        {student && (
          <div className="card">
            <h3 className="font-semibold text-slate-800 mb-4">{t("Dossier scolaire")}</h3>
            <dl className="space-y-3 text-sm">
              {[
                ["Matricule", student.matricule],
                ["Classe", student.class_name || student.current_class?.name || "—"],
                ["Année scolaire", currentYear?.name || "—"],
                ["Date de naissance", student.date_of_birth || "—"],
                ["Genre", student.gender === "M" ? "Masculin" : student.gender === "F" ? t("Féminin") : "—"],
                ["Adresse", student.address || "—"],
                ["Statut", student.is_active ? t("Actif") : t("Inactif")],
                ["Inscrit le", student.enrollment_date || "—"],
              ].map(([label, val]) => (
                <div key={label} className="flex justify-between py-2 border-b border-slate-50 last:border-0">
                  <dt className="text-slate-500 font-medium">{label}</dt>
                  <dd className="text-slate-800 font-semibold text-right">{val}</dd>
                </div>
              ))}
            </dl>
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
              <Save className="w-4 h-4" />{pwdMut.isPending ? t("Enregistrement…") : t("Changer le mot de passe")}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
