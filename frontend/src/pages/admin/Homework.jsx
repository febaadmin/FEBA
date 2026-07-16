import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, CalendarClock, Paperclip, X, FileText } from "lucide-react";
import { useForm, Controller } from "react-hook-form";
import toast from "react-hot-toast";
import { homeworkAPI, classesAPI, subjectsAPI, schoolsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import Modal from "../../components/ui/Modal";
import SearchableSelect from "../../components/ui/SearchableSelect";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import { extractApiError } from "../../utils/errors";
import { t } from "../../i18n";

export default function AdminHomework() {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [deleteItem, setDeleteItem] = useState(null);
  const [attachments, setAttachments] = useState([]);
  const [viewItem, setViewItem] = useState(null);
  const fileRef = useRef();
  const { register, handleSubmit, reset, control, formState: { errors } } = useForm();

  const { data, isLoading } = useQuery({ queryKey: ["homework"], queryFn: () => homeworkAPI.list() });
  const { data: classData } = useQuery({ queryKey: ["classes"], queryFn: () => classesAPI.list() });
  const { data: subjData } = useQuery({ queryKey: ["subjects"], queryFn: () => subjectsAPI.list() });
  const { data: yearsData } = useQuery({ queryKey: ["years"], queryFn: schoolsAPI.years });

  const homework = data?.data?.results || data?.data || [];
  const classes = classData?.data?.results || classData?.data || [];
  const subjects = subjData?.data?.results || subjData?.data || [];
  const years = yearsData?.data?.results || yearsData?.data || [];
  const currentYear = years.find(y => y.is_current);

  const createMut = useMutation({
    mutationFn: (d) => {
      const fd = new FormData();
      Object.keys(d).forEach(k => { if (d[k] != null && d[k] !== "") fd.append(k, d[k]); });
      attachments.forEach(f => fd.append("attachments", f));
      return homeworkAPI.create(fd);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["homework"] }); toast.success(t("Devoir créé !")); closeModal(); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, data }) => homeworkAPI.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["homework"] }); toast.success(t("Modifié !")); closeModal(); },
  });
  const deleteMut = useMutation({
    mutationFn: homeworkAPI.delete,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["homework"] }); toast.success(t("Supprimé.")); setDeleteItem(null); },
  });

  const closeModal = () => { setModalOpen(false); setEditItem(null); setAttachments([]); reset(); };
  const openCreate = () => { reset({ school_year: currentYear?.id || "" }); setAttachments([]); setModalOpen(true); };
  const openEdit = (h) => { setEditItem(h); reset({ title: h.title, description: h.description, due_date: h.due_date }); setModalOpen(true); };
  const onSubmit = (d) => {
    if (editItem) updateMut.mutate({ id: editItem.id, data: { title: d.title, description: d.description, due_date: d.due_date } });
    else createMut.mutate(d);
  };

  const addFiles = (files) => setAttachments(prev => [...prev, ...Array.from(files)]);
  const removeFile = (i) => setAttachments(prev => prev.filter((_, idx) => idx !== i));

  const cols = [
    { key: "title", label: t("Titre"), accessor: "title" },
    { key: "class", label: t("Classe"), accessor: "class_name" },
    { key: "subject", label: t("Matière"), accessor: "subject_name" },
    { key: "teacher", label: t("Enseignant"), accessor: "teacher_name" },
    { key: "att", label: t("Pièces jointes"), sortable: false, render: r => (r.attachments?.length > 0) ? (
      <div className="flex flex-wrap gap-1">
        {r.attachments.map(a => (
          <a key={a.id} href={a.file} target="_blank" rel="noreferrer" className="text-xs text-primary underline flex items-center gap-1">
            <FileText className="w-3 h-3" />{a.name || "Fichier"}
          </a>
        ))}
      </div>
    ) : "—" },
    { key: "due", label: t("Date limite"), render: r => (
      <span className={(new Date(r.due_date) < new Date()) ? "text-danger font-medium" : "text-slate-700"}>
        <CalendarClock className="w-3 h-3 inline mr-1" />{r.due_date}
      </span>
    )},
  ];

  const bulkDeleteMut = useMutation({
    mutationFn: (ids) => homeworkAPI.bulkDelete(ids),
    onSuccess: (data) => { qc.invalidateQueries({ queryKey: ["homework"] }); toast.success(t("{n} élément(s) supprimé(s).", { n: data?.data?.deleted || "" })); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  return (
    <div className="space-y-6">
      <PageHeader title={t("Devoirs")} subtitle={t("{n} devoir(s)", { n: homework.length })}
        action={<button onClick={openCreate} className="btn-primary flex items-center gap-2"><Plus className="w-4 h-4" />{t("Nouveau devoir")}</button>} />
      <div className="card">
        {/* FIX BUG N°9 (audit) : selectable/onBulkDelete/bulkDeletePending
            étaient posées sur l'icône <Pencil> (warnings React + sélection
            groupée inopérante). Remises sur DataTable. */}
        <DataTable columns={cols} data={homework} loading={isLoading} onRowClick={row => setViewItem(row)}
          selectable
          onBulkDelete={ids => bulkDeleteMut.mutate(ids)}
          bulkDeletePending={bulkDeleteMut.isPending}
          actions={row => (
          <div className="flex items-center gap-1 justify-end">
            <button onClick={() => openEdit(row)} className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-400 hover:text-primary"><Pencil className="w-4 h-4" /></button>
            <button onClick={() => setDeleteItem(row)} className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger"><Trash2 className="w-4 h-4" /></button>
          </div>
        )} />
      </div>

      {/* Homework detail modal */}
      {viewItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40" onClick={() => setViewItem(null)} />
          <div className="relative bg-white rounded-2xl shadow-2xl max-w-lg w-full p-6 space-y-4 max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-slate-800 text-lg">{t("Détail du devoir")}</h2>
              <button onClick={() => setViewItem(null)} className="text-slate-400 hover:text-slate-600 text-2xl leading-none">×</button>
            </div>
            <div className="space-y-3 text-sm">
              <div><span className="text-slate-500 font-medium">{t("Titre")}</span><p className="mt-0.5 text-slate-800 font-semibold">{viewItem.title}</p></div>
              <div><span className="text-slate-500 font-medium">{t("Description")}</span><p className="mt-0.5 text-slate-700 whitespace-pre-wrap">{viewItem.description || "—"}</p></div>
              <div className="grid grid-cols-2 gap-3">
                <div><span className="text-slate-500 font-medium">{t("Classe")}</span><p className="mt-0.5">{viewItem.class_name || "—"}</p></div>
                <div><span className="text-slate-500 font-medium">{t("Matière")}</span><p className="mt-0.5">{viewItem.subject_name || "—"}</p></div>
                <div><span className="text-slate-500 font-medium">{t("Enseignant")}</span><p className="mt-0.5">{viewItem.teacher_name || "—"}</p></div>
                <div><span className="text-slate-500 font-medium">{t("Date limite")}</span><p className={`mt-0.5 font-medium ${new Date(viewItem.due_date) < new Date() ? "text-danger" : "text-slate-700"}`}>{viewItem.due_date}</p></div>
              </div>
              {viewItem.attachments?.length > 0 && (
                <div>
                  <span className="text-slate-500 font-medium">{t("Pièces jointes")} ({viewItem.attachments.length})</span>
                  <div className="mt-1.5 space-y-1.5">
                    {viewItem.attachments.map(a => (
                      <a key={a.id} href={a.file} target="_blank" rel="noreferrer"
                        className="flex items-center gap-2 text-xs text-primary bg-primary-50 hover:bg-primary/10 rounded-xl px-3 py-2 transition-colors">
                        <FileText className="w-3.5 h-3.5 shrink-0" />
                        <span className="truncate">{a.name || a.file?.split("/").pop() || "Fichier"}</span>
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <div className="flex gap-2 pt-2">
              <button onClick={() => { setViewItem(null); openEdit(viewItem); }} className="btn-secondary text-sm flex-1">{t("Modifier")}</button>
              <button onClick={() => setViewItem(null)} className="btn-primary text-sm flex-1">{t("Fermer")}</button>
            </div>
          </div>
        </div>
      )}

      <Modal open={modalOpen} onClose={closeModal} title={editItem ? t("Modifier le devoir") : t("Nouveau devoir")} size="md">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="label">{t("Titre*")}</label>
            <input {...register("title", { required: true })} className="input" />
            {errors.title && <p className="text-danger text-xs mt-1">{t("Requis")}</p>}
          </div>
          <div>
            <label className="label">{t("Description*")}</label>
            <textarea {...register("description", { required: true })} className="input" rows={3} />
          </div>
          {!editItem && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">{t("Classe*")}</label>
                  <Controller name="cls" control={control} rules={{ required: true }}
                    render={({ field }) => <SearchableSelect options={classes.map(c => ({value: c.id, label: c.name}))} value={field.value} onChange={field.onChange} placeholder={t("Sélectionner une classe…")} />} />
                </div>
                <div>
                  <label className="label">{t("Matière*")}</label>
                  <select {...register("subject", { required: true })} className="input">
                    <option value="">-- Sélectionner --</option>
                    {subjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="label">{t("Année scolaire")}</label>
                <select {...register("school_year")} className="input">
                  {years.map(y => <option key={y.id} value={y.id}>{y.name}{y.is_current ? " ✓" : ""}</option>)}
                </select>
              </div>
            </>
          )}
          <div>
            <label className="label">{t("Date limite*")}</label>
            <input {...register("due_date", { required: true })} type="date" className="input" />
          </div>
          {/* Attachments */}
          {!editItem && (
            <div>
              <label className="label">{t("Pièces jointes (doc, pdf, image…)")}</label>
              <input ref={fileRef} type="file" className="hidden" multiple
                accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.gif,.xlsx,.pptx,.zip"
                onChange={e => addFiles(e.target.files)} />
              <button type="button" onClick={() => fileRef.current?.click()}
                className="btn-secondary flex items-center gap-2 text-sm">
                <Paperclip className="w-4 h-4" />{t("Ajouter des fichiers")}</button>
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
          )}
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={closeModal} className="btn-secondary">{t("Annuler")}</button>
            <button type="submit" disabled={createMut.isPending || updateMut.isPending} className="btn-primary">
              {(createMut.isPending || updateMut.isPending) ? t("Enregistrement…") : t("Enregistrer")}
            </button>
          </div>
        </form>
      </Modal>
      <ConfirmDialog open={!!deleteItem} onClose={() => setDeleteItem(null)} onConfirm={() => deleteMut.mutate(deleteItem?.id)} loading={deleteMut.isPending} message={`Supprimer "${deleteItem?.title}" ?`} />
    </div>
  );
}
