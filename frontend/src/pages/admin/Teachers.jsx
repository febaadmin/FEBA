/**
 * AdminTeachers — v26 CORRIGÉ
 *
 * CORRECTIONS :
 *  1. CRITIQUE: `bulkDeleteMut` déplacé dans AdminTeachers (était dans MultiSelect
 *     sans `qc` en scope → ReferenceError → page blanche)
 *  2. JSX malformé corrigé (props selectable/onBulkDelete collées dans <Eye />)
 *  3. DataTable correctement structuré
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, Eye, BookOpen, Users } from "lucide-react";
import StatusBadge from "../../components/ui/StatusBadge";
import { useForm, Controller } from "react-hook-form";
import toast from "react-hot-toast";
import { teachersAPI, authAPI, classesAPI, subjectsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import SearchableSelect from "../../components/ui/SearchableSelect";
import { extractApiError } from "../../utils/errors";
import { resolveMediaUrl } from "../../utils/media";

/* ── MultiSelect simple (sans mutation — ne référence plus qc) ────────────── */
function MultiSelect({ options, value = [], onChange, placeholder }) {
  const selectedSet = new Set((value || []).map(Number));
  const remaining = options.filter(o => !selectedSet.has(Number(o.value)));
  const selected  = options.filter(o =>  selectedSet.has(Number(o.value)));
  const add    = (v) => { if (v != null) onChange([...(value || []), Number(v)]); };
  const remove = (v) => onChange((value || []).filter(x => Number(x) !== Number(v)));
  return (
    <div className="space-y-2">
      <SearchableSelect options={remaining} value={null} onChange={add} placeholder={placeholder} />
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selected.map(o => (
            <span key={o.value} className="inline-flex items-center gap-1 bg-primary-50 text-primary text-xs font-medium px-2.5 py-1 rounded-full">
              {o.label}
              <button type="button" onClick={() => remove(o.value)} className="text-primary/60 hover:text-primary font-bold">×</button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AdminTeachers() {
  const qc = useQueryClient();
  const [modalOpen,  setModalOpen]  = useState(false);
  const [editItem,   setEditItem]   = useState(null);
  const [deleteItem, setDeleteItem] = useState(null);
  const [viewItem,   setViewItem]   = useState(null);
  const { register, handleSubmit, reset, control } = useForm();

  const { data, isLoading } = useQuery({ queryKey: ["teachers"], queryFn: () => teachersAPI.list() });
  const { data: usersData } = useQuery({ queryKey: ["teacher-users"], queryFn: () => authAPI.listUsers({ role: "teacher", is_active: "true" }) });
  const { data: classData } = useQuery({ queryKey: ["classes"],  queryFn: () => classesAPI.list() });
  const { data: subjData  } = useQuery({ queryKey: ["subjects"], queryFn: () => subjectsAPI.list() });

  const teachers     = data?.data?.results     || data?.data     || [];
  const teacherUsers = usersData?.data?.results|| usersData?.data|| [];
  const classes      = classData?.data?.results|| classData?.data|| [];
  const subjects     = subjData?.data?.results || subjData?.data || [];

  const userOptions    = teacherUsers.map(u => ({ value: u.id, label: `${u.first_name} ${u.last_name} (${u.email})` }));
  const classOptions   = classes.map(c => ({ value: c.id, label: c.name }));
  const subjectOptions = subjects.map(s => ({ value: s.id, label: `${s.name} (coeff ${s.coefficient})` }));

  const createMut = useMutation({
    mutationFn: (d) => teachersAPI.create(d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["teachers"] }); toast.success("Enseignant créé !"); closeModal(); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, data }) => teachersAPI.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["teachers"] }); toast.success("Modifié !"); closeModal(); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const deleteMut = useMutation({
    mutationFn: teachersAPI.delete,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["teachers"] }); toast.success("Supprimé."); setDeleteItem(null); },
  });
  /* FIX: bulkDeleteMut CORRECT dans AdminTeachers (non dans MultiSelect) */
  const bulkDeleteMut = useMutation({
    mutationFn: (ids) => teachersAPI.bulkDelete(ids),
    onSuccess: (data) => { qc.invalidateQueries({ queryKey: ["teachers"] }); toast.success(`${data?.data?.deleted || ""} enseignant(s) supprimé(s).`); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const closeModal = () => { setModalOpen(false); setEditItem(null); reset(); };
  const openCreate = () => { reset({ contract_type: "permanent", class_ids: [], subject_ids: [] }); setModalOpen(true); };
  const openEdit = (t) => {
    setEditItem(t);
    reset({
      specialization: t.specialization, hire_date: t.hire_date,
      contract_type: t.contract_type, bio: t.bio,
      class_ids:   (t.classes_detail  || []).map(c => c.id),
      subject_ids: (t.subjects_detail || []).map(s => s.id),
    });
    setModalOpen(true);
  };

  const onSubmit = (d) => {
    const payload = { ...d };
    if (!payload.hire_date) delete payload.hire_date;
    if (editItem) updateMut.mutate({ id: editItem.id, data: payload });
    else          createMut.mutate(payload);
  };

  const cols = [
    { key: "id",       label: "ID employé",  accessor: "employee_id" },
    { key: "name",     label: "Nom",         render: r => `${r.user_first_name || ""} ${r.user_last_name || ""}`.trim() || "—" },
    { key: "email",    label: "Email",       accessor: "user_email" },
    { key: "spec",     label: "Spécialité",  accessor: "specialization" },
    { key: "contract", label: "Contrat",     accessor: "contract_type" },
    { key: "classes",  label: "Classes",     render: r => (r.classes_detail || []).map(c => c.name).join(", ") || "—" },
    { key: "status",   label: "Statut",      render: r => <StatusBadge status={r.user_is_active === false ? "inactive" : "active"} /> },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Enseignants" subtitle={`${teachers.length} enseignant(s)`}
        action={<button onClick={openCreate} className="btn-primary flex items-center gap-2"><Plus className="w-4 h-4" />Ajouter</button>} />

      <div className="card">
        <DataTable
          columns={cols}
          data={teachers}
          loading={isLoading}
          onRowClick={(row) => setViewItem(row)}
          selectable
          onBulkDelete={(ids) => bulkDeleteMut.mutate(ids)}
          bulkDeletePending={bulkDeleteMut.isPending}
          actions={row => (
            <div className="flex items-center gap-1 justify-end">
              <button onClick={(e) => { e.stopPropagation(); setViewItem(row); }}
                className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600" title="Voir le détail">
                <Eye className="w-4 h-4" />
              </button>
              <button onClick={(e) => { e.stopPropagation(); openEdit(row); }}
                className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-400 hover:text-primary">
                <Pencil className="w-4 h-4" />
              </button>
              <button onClick={(e) => { e.stopPropagation(); setDeleteItem(row); }}
                className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          )}
        />
      </div>

      {/* Modal détail enseignant */}
      {viewItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40" onClick={() => setViewItem(null)} />
          <div className="relative bg-white rounded-2xl shadow-2xl max-w-lg w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-slate-800 text-lg">Fiche Enseignant</h2>
              <button onClick={() => setViewItem(null)} className="text-slate-400 hover:text-slate-600 text-2xl leading-none">×</button>
            </div>
            <div className="flex items-center gap-4">
              {viewItem.user_avatar ? (
                <img src={resolveMediaUrl(viewItem.user_avatar)} className="w-20 h-20 rounded-xl object-cover border border-slate-100" alt="" />
              ) : (
                <div className="w-20 h-20 rounded-xl bg-emerald-50 flex items-center justify-center text-emerald-600 text-2xl font-bold">
                  {viewItem.user_first_name?.[0]}{viewItem.user_last_name?.[0]}
                </div>
              )}
              <div>
                <p className="font-bold text-slate-800 text-xl">{viewItem.user_first_name} {viewItem.user_last_name}</p>
                <p className="text-sm text-slate-500">{viewItem.user_email}</p>
                <p className="text-xs text-slate-400 font-mono mt-0.5">ID: {viewItem.employee_id}</p>
              </div>
            </div>
            <div className="space-y-2 text-sm divide-y divide-slate-50">
              <div className="flex justify-between py-2"><span className="text-slate-500">Spécialité</span><span className="font-medium">{viewItem.specialization || "—"}</span></div>
              <div className="flex justify-between py-2"><span className="text-slate-500">Téléphone</span><span className="font-medium">{viewItem.user_phone || "—"}</span></div>
              <div className="flex justify-between py-2"><span className="text-slate-500">Type de contrat</span><span className="capitalize">{viewItem.contract_type || "—"}</span></div>
              <div className="flex justify-between py-2"><span className="text-slate-500">Date d'embauche</span><span>{viewItem.hire_date || "—"}</span></div>
              <div className="py-2">
                <div className="flex items-center gap-1 text-slate-500 mb-1"><BookOpen className="w-3.5 h-3.5" />Matières enseignées</div>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {(viewItem.subjects_detail || []).length > 0
                    ? (viewItem.subjects_detail || []).map(s => (
                        <span key={s.id} className="bg-emerald-50 text-emerald-700 text-xs px-2 py-0.5 rounded-full">{s.name}</span>
                      ))
                    : <span className="text-slate-400 text-xs">—</span>}
                </div>
              </div>
              <div className="py-2">
                <div className="flex items-center gap-1 text-slate-500 mb-1"><Users className="w-3.5 h-3.5" />Classes assignées</div>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {(viewItem.classes_detail || []).length > 0
                    ? (viewItem.classes_detail || []).map(c => (
                        <span key={c.id} className="bg-primary-50 text-primary text-xs px-2 py-0.5 rounded-full">{c.name}</span>
                      ))
                    : <span className="text-slate-400 text-xs">—</span>}
                </div>
              </div>
              {viewItem.bio && (
                <div className="py-2"><span className="text-slate-500 block mb-1">Bio</span><p className="text-slate-700 text-sm">{viewItem.bio}</p></div>
              )}
            </div>
            <div className="flex justify-end pt-2">
              <button onClick={() => { setViewItem(null); openEdit(viewItem); }} className="btn-primary text-sm">
                <Pencil className="w-4 h-4 inline mr-1" />Modifier
              </button>
            </div>
          </div>
        </div>
      )}

      <Modal open={modalOpen} onClose={closeModal} title={editItem ? "Modifier l'enseignant" : "Nouvel enseignant"} size="md">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {!editItem && (
            <div>
              <label className="label">Compte utilisateur (rôle teacher)*</label>
              <Controller name="user_write" control={control} rules={{ required: !editItem }}
                render={({ field }) => (
                  <SearchableSelect options={userOptions} value={field.value} onChange={field.onChange}
                    placeholder="Rechercher un utilisateur enseignant…" />
                )} />
            </div>
          )}
          <div><label className="label">Spécialité</label><input {...register("specialization")} className="input" /></div>
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Date d'embauche</label><input {...register("hire_date")} type="date" className="input" /></div>
            <div>
              <label className="label">Type de contrat</label>
              <select {...register("contract_type")} className="input">
                <option value="permanent">Permanent</option>
                <option value="contractuel">Contractuel</option>
                <option value="vacataire">Vacataire</option>
              </select>
            </div>
          </div>
          <div>
            <label className="label">Classes assignées</label>
            <Controller name="class_ids" control={control}
              render={({ field }) => <MultiSelect options={classOptions} value={field.value} onChange={field.onChange} placeholder="Ajouter une classe…" />} />
          </div>
          <div>
            <label className="label">Matières assignées</label>
            <Controller name="subject_ids" control={control}
              render={({ field }) => <MultiSelect options={subjectOptions} value={field.value} onChange={field.onChange} placeholder="Ajouter une matière…" />} />
          </div>
          <div><label className="label">Bio</label><textarea {...register("bio")} className="input" rows={2} /></div>
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={closeModal} className="btn-secondary">Annuler</button>
            <button type="submit" disabled={createMut.isPending || updateMut.isPending} className="btn-primary">
              {(createMut.isPending || updateMut.isPending) ? "Enregistrement…" : "Enregistrer"}
            </button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog open={!!deleteItem} onClose={() => setDeleteItem(null)}
        onConfirm={() => deleteMut.mutate(deleteItem?.id)} loading={deleteMut.isPending}
        message="Supprimer cet enseignant ?" />
    </div>
  );
}
