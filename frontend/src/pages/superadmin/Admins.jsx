import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, ToggleLeft, ToggleRight, Eye, EyeOff} from "lucide-react";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { authAPI, schoolsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import StatusBadge from "../../components/ui/StatusBadge";
import { extractApiError } from "../../utils/errors";

export default function SuperAdminAdmins() {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [deleteItem, setDeleteItem] = useState(null);
  const [showPwd, setShowPwd] = useState(false);
  const [showPwd2, setShowPwd2] = useState(false);
  const { register, handleSubmit, reset } = useForm();

  const { data, isLoading } = useQuery({
    queryKey: ["admins"],
    queryFn: () => authAPI.listUsers({ role: "admin" }),
  });
  const admins = data?.data?.results || data?.data || [];
  const { data: schoolsData } = useQuery({ queryKey: ["schools"], queryFn: schoolsAPI.list });
  const schools = schoolsData?.data?.results || schoolsData?.data || [];

  const createMut = useMutation({
    mutationFn: (d) => authAPI.createUser({ ...d, role: "admin" }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["admins"] }); toast.success("Administrateur créé!"); closeModal(); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, data }) => authAPI.updateUser(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["admins"] }); toast.success("Modifié!"); closeModal(); },
  });
  const deleteMut = useMutation({
    mutationFn: authAPI.deleteUser,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["admins"] }); toast.success("Supprimé."); setDeleteItem(null); },
  });
  const toggleMut = useMutation({
    mutationFn: authAPI.toggleActive,
    onSuccess: (d) => { qc.invalidateQueries({ queryKey: ["admins"] }); toast.success(d.data.detail); },
  });

  const closeModal = () => { setModalOpen(false); setEditItem(null); reset(); };
  const openCreate = () => { reset({}); setModalOpen(true); };
  const openEdit = (u) => { setEditItem(u); reset({ first_name: u.first_name, last_name: u.last_name, email: u.email, phone: u.phone, school: u.school || "" }); setModalOpen(true); };

  const onSubmit = (data) => {
    const payload = { ...data, school: data.school ? Number(data.school) : null };
    if (editItem) updateMut.mutate({ id: editItem.id, data: payload });
    else createMut.mutate(payload);
  };

  const cols = [
    { key: "name",  label: "Nom",   accessor: "first_name", render: r => `${r.first_name} ${r.last_name}` },
    { key: "email", label: "Email", accessor: "email" },
    { key: "phone", label: "Tél",   accessor: "phone" },
    { key: "status", label: "Statut", accessor: "is_active", sortable: false, render: r => <StatusBadge status={r.is_active ? "active" : "inactive"} /> },
    { key: "date",  label: "Créé le", accessor: "created_at", render: r => r.created_at?.slice(0,10) },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Gestion des Administrateurs" subtitle="Seul le Super Admin peut gérer les admins"
        action={<button onClick={openCreate} className="btn-primary flex items-center gap-2"><Plus className="w-4 h-4" />Nouvel admin</button>} />

      <div className="card">
        <DataTable columns={cols} data={admins} loading={isLoading} actions={(row) => (
          <div className="flex items-center gap-1 justify-end">
            <button onClick={() => toggleMut.mutate(row.id)} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400">
              {row.is_active ? <ToggleRight className="w-4 h-4 text-success" /> : <ToggleLeft className="w-4 h-4" />}
            </button>
            <button onClick={() => openEdit(row)} className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-400 hover:text-primary"><Pencil className="w-4 h-4" /></button>
            <button onClick={() => setDeleteItem(row)} className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger"><Trash2 className="w-4 h-4" /></button>
          </div>
        )} />
      </div>

      <Modal open={modalOpen} onClose={closeModal} title={editItem ? "Modifier l'admin" : "Nouvel administrateur"} size="md">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Prénom*</label><input {...register("first_name", { required: true })} className="input" /></div>
            <div><label className="label">Nom*</label><input {...register("last_name", { required: true })} className="input" /></div>
          </div>
          <div><label className="label">Email*</label><input {...register("email", { required: true })} type="email" className="input" /></div>
          <div><label className="label">Téléphone</label><input {...register("phone")} className="input" /></div>
          <div>
            <label className="label">Établissement*</label>
            <select {...register("school", { required: true })} className="input">
              <option value="">-- Sélectionner un établissement --</option>
              {schools.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          {!editItem && (
            <div className="grid grid-cols-2 gap-4">
              <div><label className="label">Mot de passe*</label><div className="relative"><input {...register("password", { required: true })} type={showPwd ? "text" : "password"} className="input pr-10" /><button type="button" onClick={() => setShowPwd(v => !v)} className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600">{showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}</button></div></div>
              <div><label className="label">Confirmer*</label><div className="relative"><input {...register("password2", { required: true })} type={showPwd2 ? "text" : "password"} className="input pr-10" /><button type="button" onClick={() => setShowPwd2(v => !v)} className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600">{showPwd2 ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}</button></div></div>
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

      <ConfirmDialog open={!!deleteItem} onClose={() => setDeleteItem(null)}
        onConfirm={() => deleteMut.mutate(deleteItem?.id)} loading={deleteMut.isPending}
        message={`Supprimer l'administrateur ${deleteItem?.email} ?`} />
    </div>
  );
}