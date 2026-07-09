import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, CalendarClock, Paperclip, X, FileText } from "lucide-react";
import { useForm, Controller } from "react-hook-form";
import toast from "react-hot-toast";
import { homeworkAPI, classesAPI, teachersAPI, schoolsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import Modal from "../../components/ui/Modal";
import SearchableSelect from "../../components/ui/SearchableSelect";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import { extractApiError } from "../../utils/errors";

export default function TeacherHomework() {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [deleteItem, setDeleteItem] = useState(null);
  const [attachments, setAttachments] = useState([]);
  const fileRef = useRef();
  const { register, handleSubmit, reset, control, formState: { errors } } = useForm();

  const { data, isLoading } = useQuery({ queryKey: ["homework"], queryFn: () => homeworkAPI.list() });
  // BUG FIX: Teacher only sees their own classes and subjects
  const { data: classData } = useQuery({ queryKey: ["my-classes"], queryFn: teachersAPI.myClasses });
  const { data: subjData } = useQuery({ queryKey: ["my-subjects"], queryFn: teachersAPI.mySubjects });
  const { data: yearsData } = useQuery({ queryKey: ["years"], queryFn: schoolsAPI.years });

  const homework = data?.data?.results || data?.data || [];
  // BUG FIX: Use teacher's own classes/subjects only
  const classes = classData?.data?.results || classData?.data || [];
  const subjects = subjData?.data?.results || subjData?.data || [];
  const years = yearsData?.data?.results || yearsData?.data || [];
  const currentYear = years.find(y => y.is_current);

  const createMut = useMutation({
    mutationFn: (d) => {
      const fd = new FormData();
      Object.keys(d).forEach(k => { if (d[k] != null && d[k] !== "") fd.append(k, d[k]); });
      // BUG FIX: always use FormData so backend gets correct content-type
      attachments.forEach(f => fd.append("attachments", f));
      return homeworkAPI.create(fd);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["homework"] }); toast.success("Devoir créé !"); closeModal(); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, data }) => {
      if (attachments.length > 0) {
        const fd = new FormData();
        Object.keys(data).forEach(k => { if (data[k] != null && data[k] !== "") fd.append(k, data[k]); });
        attachments.forEach(f => fd.append("attachments", f));
        return homeworkAPI.update(id, fd);
      }
      return homeworkAPI.update(id, data);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["homework"] }); toast.success("Modifié !"); closeModal(); },
  });
  const deleteMut = useMutation({
    mutationFn: homeworkAPI.delete,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["homework"] }); toast.success("Supprimé."); setDeleteItem(null); },
  });

  const closeModal = () => { setModalOpen(false); setEditItem(null); setAttachments([]); reset(); };
  const openCreate = () => { reset({ school_year: currentYear?.id || "" }); setAttachments([]); setModalOpen(true); };
  const openEdit = (h) => {
    setEditItem(h);
    reset({ title: h.title, description: h.description, due_date: h.due_date });
    setAttachments([]);
    setModalOpen(true);
  };
  const onSubmit = (d) => {
    if (editItem) updateMut.mutate({ id: editItem.id, data: { title: d.title, description: d.description, due_date: d.due_date } });
    else createMut.mutate(d);
  };

  const addFiles = (files) => setAttachments(prev => [...prev, ...Array.from(files)]);
  const removeFile = (i) => setAttachments(prev => prev.filter((_, idx) => idx !== i));

  const cols = [
    { key: "title", label: "Titre", accessor: "title" },
    { key: "class", label: "Classe", accessor: "class_name" },
    { key: "subject", label: "Matière", accessor: "subject_name" },
    { key: "att", label: "Pièces jointes", sortable: false, render: r => (r.attachments?.length > 0) ? (
      <div className="flex flex-wrap gap-1">
        {r.attachments.map(a => (
          <a key={a.id} href={a.file} target="_blank" rel="noreferrer" className="text-xs text-primary underline flex items-center gap-1">
            <FileText className="w-3 h-3" />{a.name || "Fichier"}
          </a>
        ))}
      </div>
    ) : "—" },
    { key: "due", label: "Date limite", render: r => (
      <span className={(new Date(r.due_date) < new Date()) ? "text-danger font-medium" : "text-slate-700"}>
        <CalendarClock className="w-3 h-3 inline mr-1" />{r.due_date}
      </span>
    )},
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Devoirs" subtitle={`${homework.length} devoir(s) — matières de votre profil uniquement`}
        action={<button onClick={openCreate} className="btn-primary flex items-center gap-2"><Plus className="w-4 h-4" />Nouveau devoir</button>} />
      <div className="card">
        <DataTable columns={cols} data={homework} loading={isLoading} actions={row => (
          <div className="flex items-center gap-1 justify-end">
            <button onClick={() => openEdit(row)} className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-400 hover:text-primary"><Pencil className="w-4 h-4" /></button>
            <button onClick={() => setDeleteItem(row)} className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger"><Trash2 className="w-4 h-4" /></button>
          </div>
        )} />
      </div>

      <Modal open={modalOpen} onClose={closeModal} title={editItem ? "Modifier le devoir" : "Nouveau devoir"} size="md">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="label">Titre*</label>
            <input {...register("title", { required: true })} className="input" />
            {errors.title && <p className="text-danger text-xs mt-1">Requis</p>}
          </div>
          <div>
            <label className="label">Description*</label>
            <textarea {...register("description", { required: true })} className="input" rows={3} />
          </div>
          {!editItem && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Classe* (vos classes)</label>
                  <Controller name="cls" control={control} rules={{ required: true }}
                    render={({ field }) => (
                      <SearchableSelect
                        options={classes.map(c => ({ value: c.id, label: c.name }))}
                        value={field.value}
                        onChange={field.onChange}
                        placeholder="Sélectionner une classe…"
                      />
                    )} />
                  {errors.cls && <p className="text-danger text-xs mt-1">Requis</p>}
                </div>
                <div>
                  {/* BUG FIX: Only teacher's own subjects shown here */}
                  <label className="label">Matière* (vos matières)</label>
                  <Controller name="subject" control={control} rules={{ required: true }}
                    render={({ field }) => (
                      <SearchableSelect
                        options={subjects.map(s => ({ value: s.id, label: s.name }))}
                        value={field.value}
                        onChange={field.onChange}
                        placeholder="Sélectionner une matière…"
                      />
                    )} />
                  {errors.subject && <p className="text-danger text-xs mt-1">Requis</p>}
                </div>
              </div>
              <div>
                <label className="label">Année scolaire</label>
                <select {...register("school_year")} className="input">
                  {years.map(y => <option key={y.id} value={y.id}>{y.name}{y.is_current ? " ✓" : ""}</option>)}
                </select>
              </div>
            </>
          )}
          <div>
            <label className="label">Date limite*</label>
            <input {...register("due_date", { required: true })} type="date" className="input" />
          </div>
          <div>
            <label className="label">Pièces jointes (doc, pdf, image…)</label>
            <input ref={fileRef} type="file" className="hidden" multiple
              accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.gif,.xlsx,.pptx,.zip"
              onChange={e => addFiles(e.target.files)} />
            <button type="button" onClick={() => fileRef.current?.click()}
              className="btn-secondary flex items-center gap-2 text-sm">
              <Paperclip className="w-4 h-4" />Ajouter des fichiers
            </button>
            {/* Show existing attachments on edit */}
            {editItem?.attachments?.length > 0 && (
              <div className="mt-2">
                <p className="text-xs text-slate-500 mb-1">Fichiers existants :</p>
                <div className="flex flex-wrap gap-2">
                  {editItem.attachments.map(a => (
                    <a key={a.id} href={a.file} target="_blank" rel="noreferrer"
                      className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 text-slate-600 text-xs rounded-lg px-2.5 py-1.5 hover:bg-primary-50">
                      <FileText className="w-3.5 h-3.5" />{a.name || "Fichier"}
                    </a>
                  ))}
                </div>
              </div>
            )}
            {attachments.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {attachments.map((f, i) => (
                  <div key={i} className="flex items-center gap-1.5 bg-primary-50 text-primary text-xs rounded-xl px-2.5 py-1.5">
                    <FileText className="w-3.5 h-3.5" />
                    <span className="max-w-[150px] truncate">{f.name}</span>
                    <button type="button" onClick={() => removeFile(i)}><X className="w-3.5 h-3.5" /></button>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={closeModal} className="btn-secondary">Annuler</button>
            <button type="submit" disabled={createMut.isPending || updateMut.isPending} className="btn-primary">
              {(createMut.isPending || updateMut.isPending) ? "Enregistrement…" : "Enregistrer"}
            </button>
          </div>
        </form>
      </Modal>
      <ConfirmDialog open={!!deleteItem} onClose={() => setDeleteItem(null)} onConfirm={() => deleteMut.mutate(deleteItem?.id)} loading={deleteMut.isPending} message={`Supprimer "${deleteItem?.title}" ?`} />
    </div>
  );
}
