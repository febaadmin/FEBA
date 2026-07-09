import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, Paperclip, X, FileText } from "lucide-react";
import { useForm, Controller } from "react-hook-form";
import toast from "react-hot-toast";
import { attendanceAPI, studentsAPI, schoolsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import StatusBadge from "../../components/ui/StatusBadge";
import SearchableSelect from "../../components/ui/SearchableSelect";
import { extractApiError } from "../../utils/errors";

export default function TeacherAttendance() {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [deleteItem, setDeleteItem] = useState(null);
  const [justFile, setJustFile] = useState(null);
  const fileRef = useRef();
  const { register, handleSubmit, reset, control } = useForm();

  const { data: yearsData } = useQuery({ queryKey: ["years"], queryFn: schoolsAPI.years });
  const years = yearsData?.data?.results || yearsData?.data || [];
  const currentYear = years.find(y => y.is_current);

  const { data, isLoading } = useQuery({
    queryKey: ["teacher-attendance", currentYear?.id],
    queryFn: () => attendanceAPI.list({ school_year: currentYear?.id }),
    enabled: true,
  });
  const { data: studData } = useQuery({ queryKey: ["my-students"], queryFn: () => studentsAPI.list() });
  const records = data?.data?.results || data?.data || [];
  const students = studData?.data?.results || studData?.data || [];
  const studentOpts = students.map(s => ({ value: s.id, label: `${s.full_name} — ${s.class_name || "?"}` }));

  const buildPayload = (d) => {
    if (justFile) {
      const fd = new FormData();
      Object.keys(d).forEach(k => { if (d[k] != null && d[k] !== "") fd.append(k, d[k]); });
      fd.append("justification_file", justFile);
      return fd;
    }
    return d;
  };

  const createMut = useMutation({
    mutationFn: (d) => attendanceAPI.create(buildPayload(d)),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["teacher-attendance"] }); toast.success("Présence enregistrée !"); closeModal(); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, data }) => attendanceAPI.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["teacher-attendance"] }); toast.success("Modifiée !"); closeModal(); },
  });
  const deleteMut = useMutation({
    mutationFn: attendanceAPI.delete,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["teacher-attendance"] }); toast.success("Supprimée."); setDeleteItem(null); },
  });

  const closeModal = () => { setModalOpen(false); setEditItem(null); setJustFile(null); reset(); };
  const openCreate = () => { reset({ date: new Date().toISOString().slice(0, 10), status: "present", school_year: currentYear?.id || "" }); setJustFile(null); setModalOpen(true); };
  const openEdit = (r) => { setEditItem(r); reset({ status: r.status, justification: r.justification }); setModalOpen(true); };
  const onSubmit = (d) => { if (editItem) updateMut.mutate({ id: editItem.id, data: d }); else createMut.mutate(d); };

  const cols = [
    { key: "student", label: "Élève", accessor: "student_name" },
    { key: "date", label: "Date", accessor: "date" },
    { key: "status", label: "Statut", render: r => <StatusBadge status={r.status} /> },
    { key: "justification", label: "Justification", render: r => r.justification || "—" },
    { key: "file", label: "Justificatif", sortable: false, render: r => r.justification_file ? (
      <a href={r.justification_file} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-xs text-primary hover:underline">
        <FileText className="w-3 h-3" />Voir
      </a>
    ) : "—" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Présences & Absences" subtitle={`${records.length} enregistrement(s)`}
        action={<button onClick={openCreate} className="btn-primary flex items-center gap-2"><Plus className="w-4 h-4" />Enregistrer</button>} />
      <div className="card">
        <DataTable columns={cols} data={records} loading={isLoading} actions={row => (
          <div className="flex items-center gap-1 justify-end">
            <button onClick={() => openEdit(row)} className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-400 hover:text-primary"><Pencil className="w-4 h-4" /></button>
            <button onClick={() => setDeleteItem(row)} className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger"><Trash2 className="w-4 h-4" /></button>
          </div>
        )} />
      </div>
      <Modal open={modalOpen} onClose={closeModal} title={editItem ? "Modifier" : "Nouvelle présence"} size="md">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {!editItem && (
            <div>
              <label className="label">Élève*</label>
              <Controller name="student" control={control} rules={{ required: true }}
                render={({ field }) => (
                  <SearchableSelect options={studentOpts} value={field.value} onChange={field.onChange} placeholder="Rechercher un élève…" />
                )} />
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <div><label className="label">Date*</label><input {...register("date", { required: true })} type="date" className="input" /></div>
            <div>
              <label className="label">Statut*</label>
              <select {...register("status", { required: true })} className="input">
                <option value="present">Présent</option>
                <option value="absent">Absent</option>
                <option value="late">En retard</option>
                <option value="excused">Excusé</option>
              </select>
            </div>
          </div>
          <div><label className="label">Justification</label><textarea {...register("justification")} className="input" rows={2} /></div>
          <div>
            <label className="label">Justificatif (image, PDF…)</label>
            <div className="flex items-center gap-3">
              <input ref={fileRef} type="file" className="hidden" accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
                onChange={e => setJustFile(e.target.files[0] || null)} />
              <button type="button" onClick={() => fileRef.current?.click()} className="btn-secondary flex items-center gap-2 text-sm">
                <Paperclip className="w-4 h-4" />{justFile ? "Changer" : "Joindre un justificatif"}
              </button>
              {justFile && (
                <div className="flex items-center gap-1.5 bg-primary-50 text-primary text-xs rounded-xl px-2.5 py-1.5">
                  <FileText className="w-3.5 h-3.5" />
                  <span className="truncate max-w-[160px]">{justFile.name}</span>
                  <button type="button" onClick={() => { setJustFile(null); if (fileRef.current) fileRef.current.value = ""; }}><X className="w-3.5 h-3.5" /></button>
                </div>
              )}
            </div>
          </div>
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={closeModal} className="btn-secondary">Annuler</button>
            <button type="submit" disabled={createMut.isPending || updateMut.isPending} className="btn-primary">
              {(createMut.isPending || updateMut.isPending) ? "Enregistrement…" : "Enregistrer"}
            </button>
          </div>
        </form>
      </Modal>
      <ConfirmDialog open={!!deleteItem} onClose={() => setDeleteItem(null)} onConfirm={() => deleteMut.mutate(deleteItem?.id)} loading={deleteMut.isPending} message="Supprimer cet enregistrement ?" />
    </div>
  );
}
