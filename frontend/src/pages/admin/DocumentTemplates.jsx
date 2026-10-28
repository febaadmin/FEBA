/**
 * Gabarits des documents — diplôme et certificat officiels de l'académie active.
 *
 * Chaque type a son espace : version active, version en préparation,
 * historique. Un fichier téléversé n'est JAMAIS présenté comme prêt : il
 * l'est après « Vérifier », qui produit un document d'essai et le relit
 * (apps/documents/academy_templates.validate), puis « Activer ». Les
 * documents déjà délivrés gardent leur fichier et leur version.
 *
 * L'académie est celle du sélecteur : le serveur la résout lui-même et
 * n'accepte aucun identifiant d'académie venu de cet écran.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle, Building2, CheckCircle2, Copy, Download, Eye, FileCog, Lock, Power,
  RefreshCw, ShieldCheck, Trash2, Upload,
} from "lucide-react";
import toast from "react-hot-toast";
import { documentTemplatesAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import Modal from "../../components/ui/Modal";
import TemplateEditor from "../../components/documents/TemplateEditor";
import { useAcademy } from "../../context/AcademyContext";
import { extractApiError } from "../../utils/errors";
import { blobErrorDetail } from "../../utils/templateLayout";
import { t } from "../../i18n";

export const STATE_STYLES = {
  absent: ["Absent", "bg-slate-100 text-slate-600"],
  uploaded: ["Téléversé, non validé", "bg-amber-50 text-amber-700"],
  ready: ["Valide, prêt à être activé", "bg-blue-50 text-blue-700"],
  active: ["Actif — utilisé pour les documents", "bg-green-50 text-green-700"],
  replacing: ["Actif — remplacement en préparation", "bg-green-50 text-green-700"],
  disabled: ["Désactivé", "bg-slate-200 text-slate-700"],
  invalid: ["Invalide ou incompatible", "bg-red-50 text-red-700"],
};
const VERSION_STYLES = {
  draft: "bg-amber-50 text-amber-700", validated: "bg-blue-50 text-blue-700",
  active: "bg-green-50 text-green-700", disabled: "bg-slate-200 text-slate-700",
  archived: "bg-slate-100 text-slate-500", invalid: "bg-red-50 text-red-700",
};
const PAGE_FORMAT_LABELS = {
  auto: "Automatique (A4, selon l'orientation de l'image)",
  a4_landscape: "A4 paysage", a4_portrait: "A4 portrait",
  a5_landscape: "A5 paysage", a5_portrait: "A5 portrait",
  letter_landscape: "Lettre US paysage", letter_portrait: "Lettre US portrait",
};

/** Extension de l'original téléchargé, par format réel. */
const SOURCE_EXTENSIONS = { jpeg: "jpg", tiff: "tif" };

const fmtDate = (value) => (value ? new Date(value).toLocaleString() : "—");
const fmtSize = (bytes) => `${(bytes / 1024 / 1024).toFixed(2)} Mo`;

function openBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  if (filename) {
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
  } else {
    window.open(url, "_blank", "noopener");
  }
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

export default function DocumentTemplates() {
  const qc = useQueryClient();
  const { academyKey, isAllAcademies } = useAcademy();
  const [uploadKind, setUploadKind] = useState(null);
  const [editing, setEditing] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["document-templates", academyKey],
    queryFn: documentTemplatesAPI.list,
    enabled: !isAllAcademies,
    retry: false,
  });
  const payload = data?.data;
  const refresh = () => qc.invalidateQueries({ queryKey: ["document-templates"] });

  const action = useMutation({
    mutationFn: ({ id, name }) => documentTemplatesAPI.action(id, name),
    onSuccess: (response, { name }) => {
      const report = response.data.report;
      if (name === "validate") {
        if (report?.ok) toast.success(t("Gabarit vérifié : rendu d'essai conforme. Il peut être activé."));
        else toast.error((report?.errors || []).join(" ") || t("La vérification a échoué."));
      } else {
        toast.success({
          activate: t("Version activée : elle sert désormais à produire les documents."),
          disable: t("Gabarit désactivé. Les documents déjà délivrés restent consultables."),
          reactivate: t("Version vérifiée et réactivée."),
          duplicate: t("Nouvelle version créée à partir de celle-ci (brouillon)."),
        }[name]);
      }
      refresh();
      if (name === "duplicate") setEditing(response.data.id);
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const remove = useMutation({
    mutationFn: ({ id, confirm }) => documentTemplatesAPI.remove(id, confirm),
    onSuccess: () => { toast.success(t("Version supprimée.")); setConfirmDelete(null); refresh(); },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const previewSample = useMutation({
    mutationFn: (id) => documentTemplatesAPI.preview(id, {}),
    onSuccess: (response) => openBlob(response.data),
    onError: async (err) => toast.error((await blobErrorDetail(err)) || extractApiError(err)),
  });

  const original = useMutation({
    mutationFn: (version) => documentTemplatesAPI.original(version.id),
    onSuccess: (response, version) =>
      openBlob(response.data, `gabarit-${version.kind}-v${version.version}.${SOURCE_EXTENSIONS[version.source_format] || version.source_format}`),
    onError: (err) => toast.error(extractApiError(err)),
  });

  if (isAllAcademies) {
    return (
      <div className="space-y-6">
        <PageHeader title={t("Gabarits des documents")} subtitle={t("Diplômes et certificats officiels")} />
        <div className="card border border-amber-200 bg-amber-50/40 flex items-start gap-3">
          <Building2 className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <p className="text-sm text-slate-700">
            {t("Sélectionnez une académie dans le sélecteur en haut de page : chaque académie a ses propres gabarits, et ils ne se partagent pas.")}
          </p>
        </div>
      </div>
    );
  }

  const editingTemplate = editing && payload
    ? Object.values(payload.kinds).flatMap((k) => k.versions).find((v) => v.id === editing)
    : null;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Gabarits des documents")}
        subtitle={payload ? t("Diplôme et certificat officiels de {a}", { a: payload.academy.name })
          : t("Diplômes et certificats officiels")}
      />

      <div className="card text-sm text-slate-600 space-y-1">
        <p>
          {t("Formats acceptés, téléversés tels quels — la plateforme les convertit elle-même :")}{" "}
          <span data-testid="accepted-formats">
            {(payload?.formats || []).filter((f) => f.available).map((f) => t(f.label)).join(", ")
              || t("Chargement…")}
          </span>.
          {" "}{t("Taille maximale : {n} Mo.", { n: Math.round((payload?.limits?.max_bytes || 20971520) / 1048576) })}
        </p>
        {payload && payload.formats?.some((f) => !f.available) && (
          <p className="text-amber-700">
            {t("Conversion bureautique indisponible sur ce serveur (LibreOffice absent) : Word, OpenDocument, RTF et PowerPoint sont refusés ici.")}
          </p>
        )}
        <p>{t("Word, OpenDocument, RTF et PowerPoint sont convertis en PDF ; les marqueurs {{ nom_du_champ }} qu'ils contiennent deviennent des champs déjà placés. L'original est conservé.")}</p>
        <p>{t("Étapes : téléverser → placer les champs → vérifier → activer. Une nouvelle version ne remplace l'ancienne qu'à son activation ; les documents déjà délivrés ne changent jamais.")}</p>
      </div>

      {isLoading && <p className="text-sm text-slate-500">{t("Chargement…")}</p>}
      {error && <p className="text-sm text-red-600">{extractApiError(error)}</p>}

      {payload && (
        <div className="grid gap-6 xl:grid-cols-2">
          {["diploma", "certificate"].map((kind) => {
            const summary = payload.kinds[kind];
            const [stateLabel, stateStyle] = STATE_STYLES[summary.state];
            const { active, pending } = summary;
            return (
              <section key={kind} className="card space-y-4" data-testid={`kind-${kind}`}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold text-slate-800">
                      {kind === "diploma" ? t("Gabarit du diplôme") : t("Gabarit du certificat")}
                    </h2>
                    <span className={`inline-block mt-1 text-xs font-medium px-2 py-1 rounded-lg ${stateStyle}`}
                          data-testid={`state-${kind}`}>
                      {t(stateLabel)}
                    </span>
                  </div>
                  <button type="button" className="btn-primary flex items-center gap-2"
                          onClick={() => setUploadKind(kind)}>
                    <Upload className="w-4 h-4" />{active || pending ? t("Remplacer") : t("Téléverser")}
                  </button>
                </div>

                {active ? (
                  <VersionCard version={active} title={t("Version en service")}
                               onEdit={() => setEditing(active.id)}
                               onPreview={() => previewSample.mutate(active.id)}
                               onOriginal={() => original.mutate(active)}
                               onAction={(name) => action.mutate({ id: active.id, name })}
                               onDelete={() => setConfirmDelete(active)} busy={action.isPending} />
                ) : (
                  <p className="text-sm text-slate-600">
                    {summary.builtin?.in_use && summary.builtin.can_issue
                      ? t("Aucun gabarit téléversé actif : le gabarit intégré « {l} » (livré avec l'application) est utilisé.",
                          { l: summary.builtin.label })
                      : t("Aucun gabarit actif : aucun document de ce type ne peut être produit pour cette académie.")}
                  </p>
                )}

                {pending && (
                  <VersionCard version={pending} title={t("Version en préparation")}
                               onEdit={() => setEditing(pending.id)}
                               onPreview={() => previewSample.mutate(pending.id)}
                               onOriginal={() => original.mutate(pending)}
                               onAction={(name) => action.mutate({ id: pending.id, name })}
                               onDelete={() => setConfirmDelete(pending)} busy={action.isPending} />
                )}

                {summary.versions.length > 0 && (
                  <details className="text-sm">
                    <summary className="cursor-pointer text-slate-600">
                      {t("Historique des versions ({n})", { n: summary.versions.length })}
                    </summary>
                    <ul className="mt-2 divide-y divide-slate-100">
                      {summary.versions.map((v) => (
                        <li key={v.id} className="py-2 flex flex-wrap items-center gap-2 justify-between">
                          <span>
                            v{v.version} · {v.original_filename} · {fmtDate(v.created_at)}
                            {v.documents_count > 0 && ` · ${t("{n} document(s) produit(s)", { n: v.documents_count })}`}
                          </span>
                          <span className="flex items-center gap-2">
                            <span className={`text-xs px-2 py-0.5 rounded-lg ${VERSION_STYLES[v.status]}`}>
                              {t(v.status_display)}
                            </span>
                            {["disabled", "archived"].includes(v.status) && (
                              <button type="button" className="text-xs text-primary hover:underline"
                                      onClick={() => action.mutate({ id: v.id, name: "reactivate" })}>
                                {t("Réactiver")}
                              </button>
                            )}
                            <button type="button" className="text-xs text-primary hover:underline"
                                    onClick={() => setEditing(v.id)}>{t("Voir")}</button>
                          </span>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </section>
            );
          })}
        </div>
      )}

      {uploadKind && payload && (
        <UploadModal kind={uploadKind} summary={payload.kinds[uploadKind]}
                     formats={payload.formats} limits={payload.limits}
                     onClose={() => setUploadKind(null)}
                     onUploaded={(created) => { setUploadKind(null); refresh(); setEditing(created.id); }} />
      )}

      {editingTemplate && (
        <TemplateEditor key={`${editingTemplate.id}-${editingTemplate.page_index}`}
                        template={editingTemplate} catalog={payload.catalog}
                        rules={payload.eligibility_rules[editingTemplate.kind]}
                        onClose={() => setEditing(null)} />
      )}

      <Modal open={Boolean(confirmDelete)} onClose={() => setConfirmDelete(null)}
             title={t("Supprimer une version")} size="sm">
        {confirmDelete && (
          <div className="space-y-4">
            <div className="flex items-start gap-3 p-3 rounded-xl bg-amber-50 border border-amber-200">
              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <p className="text-sm text-slate-700">
                {confirmDelete.status === "active"
                  ? t("C'est la version ACTIVE : après suppression, plus aucun document de ce type ne pourra être produit avec un gabarit téléversé.")
                  : t("La version et son fichier seront supprimés. Une version qui a servi à des documents ne peut pas l'être : désactivez-la.")}
              </p>
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" className="btn-secondary" onClick={() => setConfirmDelete(null)}>{t("Annuler")}</button>
              <button type="button" className="btn-danger" disabled={remove.isPending}
                      onClick={() => remove.mutate({ id: confirmDelete.id, confirm: confirmDelete.status === "active" })}>
                {t("Supprimer")}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

function VersionCard({ version, title, onEdit, onPreview, onOriginal, onAction, onDelete, busy }) {
  const report = version.validation_report || {};
  return (
    <div className="rounded-xl border border-slate-200 p-4 space-y-3" data-testid={`version-${version.id}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs uppercase font-semibold text-slate-500">{title}</p>
          <p className="font-medium text-slate-800 truncate">
            v{version.version} · {version.original_filename}
          </p>
          <p className="text-xs text-slate-500" data-testid={`format-${version.id}`}>
            {t(version.source_format_display || version.file_format_display)}
            {version.converted && ` → ${t("fond normalisé {f}", { f: version.normalized_format.toUpperCase() })}`}
            {version.conversion?.seconds ? ` (${t("conversion {s} s", { s: version.conversion.seconds })})` : ""}
            {" · "}{fmtSize(version.file_size)} · {version.page_width_mm} × {version.page_height_mm} mm
            {" "}({version.orientation === "landscape" ? t("paysage") : t("portrait")})
            {version.page_count > 1 && ` · ${t("page {n} sur {c}", { n: version.page_index + 1, c: version.page_count })}`}
          </p>
          <p className="text-xs text-slate-500">
            {t("Téléversé le {d}", { d: fmtDate(version.created_at) })}
            {version.uploaded_by && ` ${t("par")} ${version.uploaded_by}`}
            {version.activated_at && ` · ${t("activé le {d}", { d: fmtDate(version.activated_at) })}`}
          </p>
        </div>
        <span className={`text-xs px-2 py-1 rounded-lg shrink-0 ${VERSION_STYLES[version.status]}`}>
          {t(version.status_display)}
        </span>
      </div>

      {version.markers && (
        <p className="text-xs text-slate-600" data-testid={`markers-${version.id}`}>
          {t("Marqueurs repérés dans le document : {m}", { m: version.markers.found.join(", ") })}
          {version.markers.auto_fields > 0
            && ` · ${t("{n} champ(s) placé(s) automatiquement", { n: version.markers.auto_fields })}`}
        </p>
      )}
      {version.dimension_warning && (
        <p className="text-xs text-amber-700 flex items-start gap-1">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />{version.dimension_warning}
        </p>
      )}
      <p className="text-xs text-slate-600">
        {t("{n} champ(s) positionné(s)", { n: version.fields.length })}
        {version.documents_count > 0 && ` · ${t("{n} document(s) produit(s)", { n: version.documents_count })}`}
      </p>

      {report.errors?.length > 0 && (
        <ul className="text-xs text-red-700 list-disc list-inside space-y-0.5">
          {report.errors.map((e, i) => <li key={i}>{e}</li>)}
        </ul>
      )}
      {report.ok && (
        <p className="text-xs text-green-700 flex items-center gap-1">
          <CheckCircle2 className="w-3.5 h-3.5" />{t("Rendu d'essai vérifié le {d}", { d: fmtDate(report.checked_at) })}
        </p>
      )}
      {report.warnings?.length > 0 && (
        <ul className="text-xs text-amber-700 list-disc list-inside">
          {report.warnings.map((w, i) => <li key={i}>{w}</li>)}
        </ul>
      )}

      <div className="flex flex-wrap gap-2 text-xs">
        <button type="button" className="btn-secondary px-2.5 py-1.5 flex items-center gap-1" onClick={onEdit}>
          {version.is_editable ? <FileCog className="w-3.5 h-3.5" /> : <Lock className="w-3.5 h-3.5" />}
          {version.is_editable ? t("Placer les champs") : t("Voir la configuration")}
        </button>
        <button type="button" className="btn-secondary px-2.5 py-1.5 flex items-center gap-1" onClick={onPreview}>
          <Eye className="w-3.5 h-3.5" />{t("Aperçu PDF")}
        </button>
        {version.is_editable && (
          <button type="button" className="btn-secondary px-2.5 py-1.5 flex items-center gap-1" disabled={busy}
                  onClick={() => onAction("validate")}>
            <ShieldCheck className="w-3.5 h-3.5" />{t("Vérifier")}
          </button>
        )}
        {version.status === "validated" && (
          <button type="button" className="btn-primary px-2.5 py-1.5 flex items-center gap-1" disabled={busy}
                  onClick={() => onAction("activate")}>
            <Power className="w-3.5 h-3.5" />{t("Activer")}
          </button>
        )}
        {version.status === "active" && (
          <>
            <button type="button" className="btn-secondary px-2.5 py-1.5 flex items-center gap-1" disabled={busy}
                    onClick={() => onAction("duplicate")}>
              <Copy className="w-3.5 h-3.5" />{t("Nouvelle version")}
            </button>
            <button type="button" className="btn-secondary px-2.5 py-1.5 flex items-center gap-1" disabled={busy}
                    onClick={() => onAction("disable")}>
              <Power className="w-3.5 h-3.5" />{t("Désactiver")}
            </button>
          </>
        )}
        {version.status === "disabled" && (
          <button type="button" className="btn-secondary px-2.5 py-1.5 flex items-center gap-1" disabled={busy}
                  onClick={() => onAction("reactivate")}>
            <RefreshCw className="w-3.5 h-3.5" />{t("Réactiver")}
          </button>
        )}
        <button type="button" className="btn-secondary px-2.5 py-1.5 flex items-center gap-1" onClick={onOriginal}>
          <Download className="w-3.5 h-3.5" />{t("Original")}
        </button>
        {version.documents_count === 0 && (
          <button type="button" className="px-2.5 py-1.5 flex items-center gap-1 text-red-600 hover:underline"
                  onClick={onDelete}>
            <Trash2 className="w-3.5 h-3.5" />{t("Supprimer")}
          </button>
        )}
      </div>
    </div>
  );
}

function UploadModal({ kind, summary, formats, limits, onClose, onUploaded }) {
  const [file, setFile] = useState(null);
  const [pageFormat, setPageFormat] = useState("auto");
  const [copy, setCopy] = useState(Boolean(summary.active));
  const isImage = file && /\.(png|jpe?g|tiff?|webp)$/i.test(file.name);
  const isOffice = file && /\.(docx?|odt|rtf|pptx?|odp)$/i.test(file.name);
  const accept = (formats || []).filter((f) => f.available).flatMap((f) => f.extensions).join(",");
  const reference = summary.active || summary.pending;

  const upload = useMutation({
    mutationFn: () => {
      const form = new FormData();
      form.append("kind", kind);
      form.append("file", file);
      if (isImage) form.append("page_format", pageFormat);
      if (copy && reference) form.append("copy_from", reference.id);
      return documentTemplatesAPI.upload(form);
    },
    onSuccess: (response) => {
      toast.success(t("Fichier accepté (version {v}). Placez les champs puis vérifiez le gabarit.",
                      { v: response.data.version }));
      onUploaded(response.data);
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  return (
    <Modal open onClose={onClose} size="sm"
           title={kind === "diploma" ? t("Téléverser le gabarit du diplôme") : t("Téléverser le gabarit du certificat")}>
      <div className="space-y-4">
        <label className="block">
          <span className="block text-xs text-slate-500 mb-1">
            {t("Fichier : {f} — {n} Mo au plus", {
              f: (formats || []).filter((x) => x.available).map((x) => x.extensions.join(" ")).join(" "),
              n: Math.round((limits?.max_bytes || 20971520) / 1048576) })}
          </span>
          <input type="file" accept={accept || undefined}
                 data-testid="template-file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        </label>
        {isImage && (
          <label className="block">
            <span className="block text-xs text-slate-500 mb-1">{t("Format de la page imprimée")}</span>
            <select className="input" value={pageFormat} onChange={(e) => setPageFormat(e.target.value)}>
              {Object.entries(PAGE_FORMAT_LABELS).map(([key, label]) => (
                <option key={key} value={key}>{t(label)}</option>
              ))}
            </select>
            <span className="block text-xs text-slate-500 mt-1">
              {t("L'image est inscrite dans la page sans être déformée.")}
            </span>
          </label>
        )}
        {isOffice && (
          <p className="text-xs text-slate-500">
            {t("Le document sera converti en PDF par le serveur (jusqu'à {s} s). Si plusieurs pages, vous choisirez celle qui sert de fond.",
               { s: limits?.conversion_timeout_s || 90 })}
          </p>
        )}
        {reference && (
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-0.5" checked={copy} onChange={(e) => setCopy(e.target.checked)} />
            <span>{t("Reprendre la configuration de la version {v} (champs, textes, règle)", { v: reference.version })}</span>
          </label>
        )}
        {summary.active && (
          <p className="text-xs text-slate-500">
            {t("La version active reste utilisée tant que la nouvelle n'est pas vérifiée puis activée.")}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={onClose}>{t("Annuler")}</button>
          <button type="button" className="btn-primary" disabled={!file || upload.isPending}
                  onClick={() => upload.mutate()}>
            {upload.isPending
              ? (isOffice ? t("Conversion en cours…") : t("Envoi…"))
              : t("Téléverser")}
          </button>
        </div>
      </div>
    </Modal>
  );
}
