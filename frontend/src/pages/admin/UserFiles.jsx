import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Download, Search, FileText, Image, Upload, RefreshCw, X, Eye } from "lucide-react";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { userFilesAPI, authAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import Modal from "../../components/ui/Modal";
import { extractApiError } from "../../utils/errors";
import { t, dateLocale } from "../../i18n";

function FileIcon({ mime }) {
  if (!mime) return <FileText className="w-8 h-8 text-slate-400" />;
  if (mime.startsWith("image/")) return <Image className="w-8 h-8 text-blue-400" />;
  if (mime === "application/pdf") return <FileText className="w-8 h-8 text-red-400" />;
  return <FileText className="w-8 h-8 text-slate-400" />;
}

export default function AdminUserFiles() {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [filterUser, setFilterUser] = useState("");
  const [deleteItem, setDeleteItem] = useState(null);
  const [replaceItem, setReplaceItem] = useState(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [previewItem, setPreviewItem] = useState(null);
  const fileRef = useRef();
  const replaceRef = useRef();
  const { register, handleSubmit, reset } = useForm();

  const { data, isLoading } = useQuery({
    queryKey: ["user-files", filterUser, search],
    queryFn: () => userFilesAPI.list({ user: filterUser || undefined, search: search || undefined }),
    keepPreviousData: true,
  });
  const { data: usersData } = useQuery({ queryKey: ["users-list"], queryFn: () => authAPI.listUsers({}) });

  const files = data?.data?.results || data?.data || [];
  const users = usersData?.data?.results || usersData?.data || [];

  const uploadMut = useMutation({
    mutationFn: (fd) => userFilesAPI.create(fd),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["user-files"] }); toast.success(t("Fichier uploadé !")); setUploadOpen(false); reset(); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const deleteMut = useMutation({
    mutationFn: userFilesAPI.delete,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["user-files"] }); toast.success(t("Supprimé.")); setDeleteItem(null); },
  });
  const replaceMut = useMutation({
    mutationFn: ({ id, fd }) => userFilesAPI.replace(id, fd),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["user-files"] }); toast.success(t("Fichier remplacé !")); setReplaceItem(null); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const onUpload = (d) => {
    const fd = new FormData();
    fd.append("name", d.name);
    if (d.description) fd.append("description", d.description);
    if (d.user) fd.append("user", d.user);
    const file = fileRef.current?.files?.[0];
    if (!file) { toast.error(t("Sélectionnez un fichier")); return; }
    fd.append("file", file);
    uploadMut.mutate(fd);
  };

  const onReplace = () => {
    const file = replaceRef.current?.files?.[0];
    if (!file) { toast.error(t("Sélectionnez un fichier")); return; }
    const fd = new FormData();
    fd.append("file", file);
    fd.append("name", replaceItem.name);
    replaceMut.mutate({ id: replaceItem.id, fd });
  };

  const handleDownload = async (file) => {
    try {
      const res = await userFilesAPI.download(file.id);
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = file.original_filename || file.name;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error(t("Téléchargement impossible"));
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title={t("Fichiers Utilisateurs")} subtitle={t("{n} fichier(s)", { n: files.length })}
        action={
          <button onClick={() => setUploadOpen(true)} className="btn-primary flex items-center gap-2">
            <Plus className="w-4 h-4" />{t("Ajouter un fichier")}</button>
        } />

      {/* Filters */}
      <div className="card flex flex-wrap gap-3 items-center">
        <div className="flex items-center gap-2 bg-slate-100 rounded-xl px-3 py-2 flex-1 min-w-[200px]">
          <Search className="w-4 h-4 text-slate-400" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder={t("Rechercher par nom, description…")} className="bg-transparent outline-none text-sm flex-1" />
          {search && <button onClick={() => setSearch("")}><X className="w-4 h-4 text-slate-400" /></button>}
        </div>
        <select value={filterUser} onChange={e => setFilterUser(e.target.value)} className="input max-w-xs">
          <option value="">{t("Tous les utilisateurs")}</option>
          {users.map(u => <option key={u.id} value={u.id}>{u.first_name} {u.last_name} ({u.email})</option>)}
        </select>
      </div>

      {/* File grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {[...Array(8)].map((_,i) => <div key={i} className="skeleton h-40 rounded-2xl" />)}
        </div>
      ) : files.length === 0 ? (
        <div className="card text-center py-16 text-slate-400">
          <FileText className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="font-medium">{t("Aucun fichier trouvé")}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {files.map(file => (
            <div key={file.id} className="card hover:shadow-lg transition-shadow group flex flex-col gap-3">
              {/* Thumbnail */}
              <div className="h-24 bg-slate-50 rounded-xl flex items-center justify-center overflow-hidden">
                {file.mime_type?.startsWith("image/") && file.file_url ? (
                  <img src={file.file_url} alt={file.name} className="w-full h-full object-cover rounded-xl" />
                ) : (
                  <FileIcon mime={file.mime_type} />
                )}
              </div>
              {/* Info */}
              <div className="flex-1">
                <p className="font-semibold text-slate-800 text-sm truncate" title={file.name}>{file.name}</p>
                <p className="text-xs text-slate-400 mt-0.5">{file.uploader_name}</p>
                <p className="text-xs text-slate-400">{file.file_size_display} · {new Date(file.uploaded_at).toLocaleDateString(dateLocale())}</p>
              </div>
              {/* Actions */}
              <div className="flex gap-1.5">
                {file.mime_type?.startsWith("image/") && (
                  <button onClick={() => setPreviewItem(file)} title={t("Prévisualiser")}
                    className="p-1.5 rounded-lg hover:bg-blue-50 text-slate-400 hover:text-blue-500 transition-colors">
                    <Eye className="w-4 h-4" />
                  </button>
                )}
                <button onClick={() => handleDownload(file)} title={t("Télécharger")}
                  className="p-1.5 rounded-lg hover:bg-green-50 text-slate-400 hover:text-success transition-colors">
                  <Download className="w-4 h-4" />
                </button>
                <button onClick={() => setReplaceItem(file)} title={t("Remplacer")}
                  className="p-1.5 rounded-lg hover:bg-amber-50 text-slate-400 hover:text-amber-500 transition-colors">
                  <RefreshCw className="w-4 h-4" />
                </button>
                <button onClick={() => setDeleteItem(file)} title={t("Supprimer")}
                  className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger transition-colors ml-auto">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Upload modal */}
      <Modal open={uploadOpen} onClose={() => { setUploadOpen(false); reset(); }} title={t("Ajouter un fichier")} size="md">
        <form onSubmit={handleSubmit(onUpload)} className="space-y-4">
          <div>
            <label className="label">{t("Nom du fichier *")}</label>
            <input {...register("name", { required: true })} className="input" placeholder={t("Ex: Acte de naissance")} />
          </div>
          <div>
            <label className="label">{t("Description")}</label>
            <textarea {...register("description")} className="input" rows={2} placeholder={t("Description optionnelle")} />
          </div>
          <div>
            <label className="label">{t("Utilisateur cible")}</label>
            <select {...register("user")} className="input">
              <option value="">— Moi-même —</option>
              {users.map(u => <option key={u.id} value={u.id}>{u.first_name} {u.last_name} ({u.role})</option>)}
            </select>
          </div>
          <div>
            <label className="label">{t("Fichier *")}</label>
            <div className="flex items-center gap-3">
              <input ref={fileRef} type="file" className="hidden"
                accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.doc,.docx,.xls,.xlsx,.txt,.csv,.zip" />
              <button type="button" onClick={() => fileRef.current?.click()}
                className="btn-secondary flex items-center gap-2 text-sm">
                <Upload className="w-4 h-4" />{t("Choisir un fichier")}</button>
            </div>
            <p className="text-xs text-slate-400 mt-1">{t("Images, PDF, Word, Excel, CSV, ZIP — max 5 MB")}</p>
          </div>
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={() => { setUploadOpen(false); reset(); }} className="btn-secondary">{t("Annuler")}</button>
            <button type="submit" disabled={uploadMut.isPending} className="btn-primary">
              {uploadMut.isPending ? t("Upload…") : t("Enregistrer")}
            </button>
          </div>
        </form>
      </Modal>

      {/* Replace file modal */}
      {replaceItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40" onClick={() => setReplaceItem(null)} />
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-slate-800">{t("Remplacer le fichier")}</h2>
              <button onClick={() => setReplaceItem(null)} className="text-slate-400 text-2xl leading-none">×</button>
            </div>
            <p className="text-sm text-slate-500">{t("Fichier actuel :")} <strong>{replaceItem.name}</strong></p>
            <div>
              <input ref={replaceRef} type="file" className="hidden"
                accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.doc,.docx,.xls,.xlsx,.txt,.csv,.zip" />
              <button type="button" onClick={() => replaceRef.current?.click()} className="btn-secondary flex items-center gap-2 text-sm">
                <Upload className="w-4 h-4" />{t("Choisir le nouveau fichier")}</button>
            </div>
            <div className="flex gap-3 justify-end pt-2">
              <button onClick={() => setReplaceItem(null)} className="btn-secondary">{t("Annuler")}</button>
              <button onClick={onReplace} disabled={replaceMut.isPending} className="btn-primary">
                {replaceMut.isPending ? t("Remplacement…") : t("Remplacer")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Image preview */}
      {previewItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={() => setPreviewItem(null)}>
          <div className="absolute inset-0 bg-black/80" />
          <div className="relative max-w-3xl max-h-[85vh]">
            <img src={previewItem.file_url} alt={previewItem.name} className="max-w-full max-h-[85vh] rounded-2xl object-contain" />
            <button onClick={() => setPreviewItem(null)}
              className="absolute top-2 right-2 w-8 h-8 bg-white/20 rounded-full text-white flex items-center justify-center hover:bg-white/40">×</button>
          </div>
        </div>
      )}

      <ConfirmDialog open={!!deleteItem} onClose={() => setDeleteItem(null)}
        onConfirm={() => deleteMut.mutate(deleteItem?.id)} loading={deleteMut.isPending}
        message={`Supprimer "${deleteItem?.name}" ?`} />
    </div>
  );
}
