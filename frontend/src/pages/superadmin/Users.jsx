import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, ToggleLeft, ToggleRight, Shield, Eye, EyeOff} from "lucide-react";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { authAPI, schoolsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import StatusBadge from "../../components/ui/StatusBadge";
import { extractApiError } from "../../utils/errors";

const ROLE_OPTIONS = [
  { value: "superadmin", label: "Super Admin" },
  { value: "admin",      label: "Administrateur" },
  { value: "teacher",    label: "Enseignant" },
  { value: "parent",     label: "Parent" },
  { value: "student",    label: "Élève" },
];

export default function SuperAdminUsers() {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [deleteItem, setDeleteItem] = useState(null);
  const [roleFilter, setRoleFilter] = useState("");
  const [viewItem, setViewItem] = useState(null);
  const [showPwd, setShowPwd] = useState(false);
  const [showPwd2, setShowPwd2] = useState(false);
  const { register, handleSubmit, reset, watch, formState: { errors } } = useForm();

  const { data, isLoading } = useQuery({
    queryKey: ["all-users", roleFilter],
    queryFn: () => authAPI.listUsers(roleFilter ? { role: roleFilter } : {}),
  });
  const users = data?.data?.results || data?.data || [];

  // Établissements : requis pour tout rôle autre que superadmin
  const { data: schoolsData } = useQuery({ queryKey: ["schools"], queryFn: schoolsAPI.list });
  const schools = schoolsData?.data?.results || schoolsData?.data || [];
  const watchedRole = watch("role");
  const needsSchool = watchedRole && watchedRole !== "superadmin";

  const createMut = useMutation({
    mutationFn: authAPI.createUser,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["all-users"] }); toast.success("Utilisateur créé!"); closeModal(); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, data }) => authAPI.updateUser(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["all-users"] }); toast.success("Modifié!"); closeModal(); },
  });
  const deleteMut = useMutation({
    mutationFn: authAPI.deleteUser,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["all-users"] }); toast.success("Supprimé."); setDeleteItem(null); },
  });
  const toggleMut = useMutation({
    mutationFn: authAPI.toggleActive,
    onSuccess: (d) => { qc.invalidateQueries({ queryKey: ["all-users"] }); toast.success(d.data.detail); },
  });

  const closeModal = () => { setModalOpen(false); setEditItem(null); reset(); };
  const openCreate = () => { setEditItem(null); reset({}); setModalOpen(true); };
  const openEdit = (u) => {
    setEditItem(u);
    reset({ first_name: u.first_name, last_name: u.last_name, email: u.email, phone: u.phone, role: u.role, school: u.school || "" });
    setModalOpen(true);
  };

  const onSubmit = (data) => {
    const payload = { ...data, school: data.school ? Number(data.school) : null };
    if (payload.role === "superadmin") payload.school = null;
    if (editItem) updateMut.mutate({ id: editItem.id, data: payload });
    else createMut.mutate(payload);
  };

  const roleBadge = (role) => {
    const map = {
      superadmin: "bg-purple-100 text-purple-700",
      admin:   "bg-primary-50 text-primary",
      teacher: "bg-emerald-50 text-emerald-700",
      parent:  "bg-amber-50 text-amber-700",
      student: "bg-sky-50 text-sky-700",
    };
    const labels = { superadmin: "Super Admin", admin: "Admin", teacher: "Enseignant", parent: "Parent", student: "Élève" };
    return <span className={`badge ${map[role] || "bg-slate-100 text-slate-600"}`}>{labels[role] || role}</span>;
  };

  const cols = [
    { key: "name",  label: "Nom",   accessor: "first_name", render: r => `${r.first_name} ${r.last_name}` },
    { key: "email", label: "Email", accessor: "email" },
    { key: "role",  label: "Rôle",  accessor: "role", render: r => roleBadge(r.role) },
    { key: "level", label: "Niveau", accessor: "role_level", render: r => <span className="font-mono text-xs bg-slate-100 px-2 py-0.5 rounded">{r.role_level}</span> },
    { key: "status", label: "Statut", accessor: "is_active", sortable: false, render: r => <StatusBadge status={r.is_active ? "active" : "inactive"} /> },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Tous les utilisateurs" subtitle="Gestion complète — accès Super Admin"
        action={<button onClick={openCreate} className="btn-primary flex items-center gap-2"><Plus className="w-4 h-4" />Nouvel utilisateur</button>} />

      {/* Role filter */}
      <div className="flex gap-2 flex-wrap">
        {[{ value: "", label: "Tous" }, ...ROLE_OPTIONS].map(opt => (
          <button key={opt.value} onClick={() => setRoleFilter(opt.value)}
            className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${roleFilter === opt.value ? "bg-primary text-white shadow-md" : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"}`}>
            {opt.label}
          </button>
        ))}
      </div>

      <div className="card">
        <DataTable columns={cols} data={users} loading={isLoading} onRowClick={row => setViewItem(row)} actions={(row) => (
          <div className="flex items-center gap-1 justify-end">
            <button onClick={() => toggleMut.mutate(row.id)} title={row.is_active ? "Désactiver" : "Activer"}
              className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700">
              {row.is_active ? <ToggleRight className="w-4 h-4 text-success" /> : <ToggleLeft className="w-4 h-4" />}
            </button>
            <button onClick={() => openEdit(row)} className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-400 hover:text-primary"><Pencil className="w-4 h-4" /></button>
            <button onClick={() => setDeleteItem(row)} className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger"><Trash2 className="w-4 h-4" /></button>
          </div>
        )} />
      </div>

      <Modal open={modalOpen} onClose={closeModal} title={editItem ? "Modifier l'utilisateur" : "Nouvel utilisateur"} size="md">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Prénom*</label><input {...register("first_name", { required: true })} className="input" />{errors.first_name && <p className="text-danger text-xs mt-1">Requis</p>}</div>
            <div><label className="label">Nom*</label><input {...register("last_name", { required: true })} className="input" />{errors.last_name && <p className="text-danger text-xs mt-1">Requis</p>}</div>
          </div>
          <div><label className="label">Email*</label><input {...register("email", { required: true })} type="email" className="input" /></div>
          <div><label className="label">Téléphone</label><input {...register("phone")} className="input" /></div>
          <div><label className="label">Rôle*</label>
            <select {...register("role", { required: true })} className="input">
              {ROLE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          {needsSchool && (
            <div>
              <label className="label">Établissement*</label>
              <select {...register("school", { required: needsSchool })} className="input">
                <option value="">-- Sélectionner un établissement --</option>
                {schools.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
              {errors.school && <p className="text-danger text-xs mt-1">Un établissement est requis pour ce rôle</p>}
            </div>
          )}
          {!editItem && (
            <div className="grid grid-cols-2 gap-4">
              <div><label className="label">Mot de passe*</label><div className="relative"><input {...register("password", { required: !editItem })} type={showPwd ? "text" : "password"} className="input pr-10" /><button type="button" onClick={() => setShowPwd(v => !v)} className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600">{showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}</button></div></div>
              <div><label className="label">Confirmer*</label><div className="relative"><input {...register("password2", { required: !editItem })} type={showPwd2 ? "text" : "password"} className="input pr-10" /><button type="button" onClick={() => setShowPwd2(v => !v)} className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600">{showPwd2 ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}</button></div></div>
            </div>
          )}
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={closeModal} className="btn-secondary">Annuler</button>
            <button type="submit" disabled={createMut.isPending || updateMut.isPending} className="btn-primary">
              {(createMut.isPending || updateMut.isPending) ? "Enregistrement..." : "Enregistrer"}
            </button>
          </div>
        </form>
      </Modal>


      {viewItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40" onClick={() => setViewItem(null)} />
          <div className="relative bg-white rounded-2xl shadow-2xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-slate-800 text-lg">Détail utilisateur</h2>
              <button onClick={() => setViewItem(null)} className="text-slate-400 hover:text-slate-600 text-2xl leading-none">×</button>
            </div>
            <div className="flex items-center gap-4">
              {viewItem.avatar ? (
                <img src={viewItem.avatar} className="w-16 h-16 rounded-xl object-cover" alt="" />
              ) : (
                <div className="w-16 h-16 rounded-xl bg-primary-50 flex items-center justify-center text-primary text-xl font-bold">
                  {viewItem.first_name?.[0]}{viewItem.last_name?.[0]}
                </div>
              )}
              <div>
                <p className="font-bold text-slate-800 text-lg">{viewItem.first_name} {viewItem.last_name}</p>
                <p className="text-sm text-slate-500">{viewItem.email}</p>
              </div>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between py-2 border-b border-slate-50"><span className="text-slate-500">Rôle</span><span className="font-medium capitalize">{viewItem.role}</span></div>
              <div className="flex justify-between py-2 border-b border-slate-50"><span className="text-slate-500">Téléphone</span><span>{viewItem.phone || "—"}</span></div>
              <div className="flex justify-between py-2 border-b border-slate-50"><span className="text-slate-500">Statut</span><span className={viewItem.is_active ? "text-success font-medium" : "text-danger font-medium"}>{viewItem.is_active ? "Actif" : "Inactif"}</span></div>
              <div className="flex justify-between py-2"><span className="text-slate-500">Créé le</span><span>{viewItem.created_at?.slice(0,10)}</span></div>
            </div>
          </div>
        </div>
      )}
      <ConfirmDialog open={!!deleteItem} onClose={() => setDeleteItem(null)}
        onConfirm={() => deleteMut.mutate(deleteItem?.id)} loading={deleteMut.isPending}
        message={`Supprimer définitivement ${deleteItem?.email} (${deleteItem?.role}) ?`} />
    </div>
  );
}