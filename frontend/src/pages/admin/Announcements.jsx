import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, Megaphone, Paperclip, X, FileText, Eye } from "lucide-react";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { announcementsAPI, schoolsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import { extractApiError } from "../../utils/errors";

const TARGET_OPTIONS = [
  { value: "all", label: "Tous les profils" },
  { value: "parent", label: "Parents" },
  { value: "teacher", label: "Enseignants" },
  { value: "student", label: "Élèves" },
  { value: "admin", label: "Administrateurs" },
];

export default function AdminAnnouncements() {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [deleteItem, setDeleteItem] = useState(null);
  const [viewItem, setViewItem] = useState(null);
  const [attachedFile, setAttachedFile] = useState(null);
  const fileRef = useRef();
  const { register, handleSubmit, reset } = useForm({ defaultValues: { is_published: true } });

  const { data: yearsData } = useQuery({ queryKey: ["years"], queryFn: schoolsAPI.years });
  const years = yearsData?.data?.results || yearsData?.data || [];
  const currentYear = years.find(y => y.is_current);
  const [filterYear, setFilterYear] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["announcements", filterYear || currentYear?.id],
    queryFn: () => announcementsAPI.list({ school_year: filterYear || currentYear?.id }),
  });
  const announcements = data?.data?.results || data?.data || [];

  const buildPayload = (d, file) => {
    if (file) {
      const fd = new FormData();
      fd.append("title", d.title);
      fd.append("content", d.content);
      fd.append("is_published", d.is_published ? "true" : "false");
      fd.append("target_roles", JSON.stringify([d.target_roles || "all"]));
      fd.append("attachment", file);
      return { data: fd, isFile: true };
    }
    return { data: { ...d, target_roles: [d.target_roles || "all"] }, isFile: false };
  };

  const createMut = useMutation({
    mutationFn: (d) => {
      const { data, isFile } = buildPayload(d, attachedFile);
      return announcementsAPI.create(data, isFile);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["announcements"] }); toast.success("Annonce publiée !"); closeModal(); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, data: d }) => {
      const { data, isFile } = buildPayload(d, attachedFile);
      return announcementsAPI.update(id, data, isFile);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["announcements"] }); toast.success("Modifiée !"); closeModal(); },
  });
  const deleteMut = useMutation({
    mutationFn: announcementsAPI.delete,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["announcements"] }); toast.success("Supprimée."); setDeleteItem(null); },
  });

  const closeModal = () => { setModalOpen(false); setEditItem(null); setAttachedFile(null); reset({ is_published: true }); };
  const openCreate = () => { closeModal(); reset({ is_published: true, school_year: currentYear?.id || "" }); setModalOpen(true); };
  const openEdit = (a) => {
    setEditItem(a);
    reset({ title: a.title, content: a.content, is_published: a.is_published, target_roles: a.target_roles?.[0] || "all" });
    setModalOpen(true);
  };
  const onSubmit = (d) => {
    if (editItem) updateMut.mutate({ id: editItem.id, data: d });
    else createMut.mutate(d);
  };

  const cols = [
    { key: "title", label: "Titre", accessor: "title" },
    { key: "targets", label: "Destinataires", render: r => (r.target_roles || []).join(", ") },
    { key: "attachment", label: "Pièce jointe", sortable: false, render: r => r.has_attachment ? (
      <a href={r.attachment} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-xs text-primary hover:underline">
        <FileText className="w-3 h-3" />{r.attachment_name || "Fichier"}
      </a>
    ) : <span className="text-slate-300">—</span> },
    { key: "status", label: "Statut", render: r => (
      <span className={`badge ${r.is_published ? "bg-success-50 text-success" : "bg-slate-100 text-slate-500"}`}>
        {r.is_published ? "Publiée" : "Brouillon"}
      </span>
    )},
    { key: "date", label: "Date", render: r => r.created_at?.slice(0,10) },
  ];

  const bulkDeleteMut = useMutation({
    mutationFn: (ids) => announcementsAPI.bulkDelete(ids),
    onSuccess: (data) => { qc.invalidateQueries({ queryKey: ["announcements"] }); toast.success(`${data?.data?.deleted || ""} élément(s) supprimé(s).`); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Annonces" subtitle={`${announcements.length} annonce(s)`}
        action={<button onClick={openCreate} className="btn-primary flex items-center gap-2"><Plus className="w-4 h-4" />Nouvelle annonce</button>} />
      <div className="flex items-center gap-3">
        <label className="text-sm font-semibold text-slate-600">Année scolaire :</label>
        <select value={filterYear} onChange={e => setFilterYear(e.target.value)} className="input w-auto text-sm">
          <option value="">— Toutes ({currentYear?.name || "actuelle"}) —</option>
          {years.map(y => <option key={y.id} value={y.id}>{y.name}{y.is_current ? " ✓" : ""}</option>)}
        </select>
      </div>
      <div className="card">
        {/* FIX BUG N°9 (audit) : selectable/onBulkDelete/bulkDeletePending
            étaient posées sur l'icône <Eye> (warnings React + sélection
            groupée inopérante). Remises sur DataTable. */}
        <DataTable columns={cols} data={announcements} loading={isLoading}
          onRowClick={(row) => setViewItem(row)}
          selectable
          onBulkDelete={ids => bulkDeleteMut.mutate(ids)}
          bulkDeletePending={bulkDeleteMut.isPending}
          actions={row => (
            <div className="flex items-center gap-1 justify-end">
              <button onClick={e => { e.stopPropagation(); setViewItem(row); }} className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-400 hover:text-primary"><Eye className="w-4 h-4" /></button>
              <button onClick={e => { e.stopPropagation(); openEdit(row); }} className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-400 hover:text-primary"><Pencil className="w-4 h-4" /></button>
              <button onClick={e => { e.stopPropagation(); setDeleteItem(row); }} className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger"><Trash2 className="w-4 h-4" /></button>
            </div>
          )} />
      </div>

      {/* View detail modal */}
      <Modal open={!!viewItem} onClose={() => setViewItem(null)} title={viewItem?.title || "Annonce"} size="lg">
        {viewItem && (
          <div className="space-y-4">
            <div className="flex gap-2 flex-wrap">
              {(viewItem.target_roles || []).map(r => (
                <span key={r} className="badge bg-primary-50 text-primary text-xs px-2 py-0.5 rounded-full">{r}</span>
              ))}
              <span className={`badge text-xs px-2 py-0.5 rounded-full ${viewItem.is_published ? "bg-success-50 text-success" : "bg-slate-100 text-slate-500"}`}>
                {viewItem.is_published ? "Publiée" : "Brouillon"}
              </span>
            </div>
            <p className="text-sm text-slate-400">{viewItem.created_at?.slice(0,10)} — {viewItem.author?.first_name} {viewItem.author?.last_name}</p>
            <div className="bg-slate-50 rounded-xl p-4 text-slate-700 text-sm whitespace-pre-wrap leading-relaxed">
              {viewItem.content}
            </div>
            {viewItem.has_attachment && (
              <a href={viewItem.attachment} target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-2 bg-primary-50 text-primary px-4 py-2 rounded-xl text-sm font-medium hover:bg-primary-100 transition-colors">
                <FileText className="w-4 h-4" />{viewItem.attachment_name || "Télécharger la pièce jointe"}
              </a>
            )}
          </div>
        )}
      </Modal>

      {/* Create / Edit modal */}
      <Modal open={modalOpen} onClose={closeModal} title={editItem ? "Modifier l'annonce" : "Nouvelle annonce"} size="lg">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div><label className="label">Titre*</label><input {...register("title", { required: true })} className="input" /></div>
          <div><label className="label">Contenu*</label><textarea {...register("content", { required: true })} className="input" rows={5} /></div>
          <div>
            <label className="label">Destinataires</label>
            <select {...register("target_roles")} className="input">
              {TARGET_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Pièce jointe (PDF, Word, image, vidéo…)</label>
            <div className="flex items-center gap-3">
              <input ref={fileRef} type="file" className="hidden"
                accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.gif,.mp4,.avi,.xlsx,.pptx"
                onChange={e => setAttachedFile(e.target.files[0] || null)} />
              <button type="button" onClick={() => fileRef.current?.click()}
                className="btn-secondary flex items-center gap-2 text-sm">
                <Paperclip className="w-4 h-4" />{attachedFile ? "Changer le fichier" : "Joindre un fichier"}
              </button>
              {attachedFile && (
                <div className="flex items-center gap-2 bg-primary-50 rounded-xl px-3 py-1.5 text-xs text-primary">
                  <FileText className="w-3.5 h-3.5" />
                  <span className="truncate max-w-[200px]">{attachedFile.name}</span>
                  <button type="button" onClick={() => { setAttachedFile(null); if (fileRef.current) fileRef.current.value = ""; }}>
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </div>
          </div>
          <div>
            <label className="label">Année scolaire</label>
            <select {...register("school_year")} className="input">
              <option value="">-- Sélectionner --</option>
              {years.map(y => <option key={y.id} value={y.id}>{y.name}{y.is_current ? " (active)" : ""}</option>)}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <input {...register("is_published")} type="checkbox" id="pub" className="w-4 h-4 accent-primary" />
            <label htmlFor="pub" className="text-sm font-medium text-slate-700">Publier immédiatement</label>
          </div>
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={closeModal} className="btn-secondary">Annuler</button>
            <button type="submit" disabled={createMut.isPending || updateMut.isPending} className="btn-primary">
              {(createMut.isPending || updateMut.isPending) ? "Publication…" : editItem ? "Mettre à jour" : "Publier"}
            </button>
          </div>
        </form>
      </Modal>
      <ConfirmDialog open={!!deleteItem} onClose={() => setDeleteItem(null)} onConfirm={() => deleteMut.mutate(deleteItem?.id)} loading={deleteMut.isPending} message={`Supprimer "${deleteItem?.title}" ?`} />
    </div>
  );
}
