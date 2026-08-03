/**
 * AdminWebsite — gestion du contenu du site vitrine public (P4 v4).
 *
 * Onglets :
 *  - Messages reçus (formulaire de contact) : lecture, marquage lu, suppression ;
 *  - Préinscriptions : suivi de statut (nouvelle / en traitement / clôturée) ;
 *  - Actualités & événements : CRUD complet avec publication ;
 *  - Paramètres du site : coordonnées, réseaux sociaux, SEO, statistiques.
 * Les slides du carrousel et la galerie se gèrent via la même API
 * (/api/website/admin/) ou l'admin Django (/django-admin/).
 */
import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import {
  Download, Eye, FileText, Inbox, ClipboardList, Newspaper, RefreshCw,
  Settings2, Trash2, Pencil, Plus, MailOpen, Mail, ExternalLink,
} from "lucide-react";
import toast from "react-hot-toast";
import { websiteAdminAPI } from "../../api";
import { extractApiError } from "../../utils/errors";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import Modal from "../../components/ui/Modal";
import LongText from "../../components/ui/LongText";
import DetailField from "../../components/ui/DetailField";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import { t } from "../../i18n";
import { useAcademyKey, useEntityContext } from "../../hooks/useEntityContext";

const TABS = [
  { key: "messages", label: "Messages reçus", icon: Inbox },
  // P2 : les préinscriptions de cet onglet sont celles de FEBA
  // (modèle PreRegistration). FEBA French Heritage Academy traite ses
  // inscriptions dans le module « Admissions FEBA FHA », avec ses propres
  // modèles. Afficher cet onglet pour FHA donnerait une liste
  // systématiquement vide, laissant croire que les dossiers sont perdus.
  //
  // `campusOnly` masque l'onglet ET rend sa vue inatteignable — le
  // masquage seul ne suffirait pas.
  { key: "prereg", label: "Préinscriptions", icon: ClipboardList, campusOnly: true },
  { key: "news", label: "Actualités", icon: Newspaper },
  { key: "settings", label: "Paramètres du site", icon: Settings2 },
];

const PREREG_STATUS = [
  ["new", "Nouvelle"], ["processing", "En traitement"], ["closed", "Clôturée"],
];

function rows(data) {
  const d = data?.data;
  return d?.results || d || [];
}

/* ── Étiquette d'académie ────────────────────────────────────────────────── */
/**
 * P5 — En vue consolidée, l'académie doit se lire sur la ligne elle-même.
 * Le code interne est stable ; le libellé affiché vient du serveur et suit
 * un éventuel renommage.
 */
function AcademyBadge({ code, name }) {
  if (!code && !name) return <span className="text-slate-400">—</span>;
  const isOnline = code === "FEBA_FHA";
  return (
    <span className={`badge whitespace-nowrap ${isOnline
      ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
      : "bg-indigo-50 text-indigo-700 border border-indigo-200"}`}>
      {name || code}
    </span>
  );
}

/* ── Détail d'un message reçu ────────────────────────────────────────────── */
/**
 * P5 — TOUT ce que le visiteur a saisi est affiché.
 *
 * Le détail montrait le nom, l'e-mail, le téléphone et le message. Le
 * numéro WhatsApp, le pays, l'État, le fuseau, la langue préférée et la
 * catégorie étaient enregistrés en base et ne s'affichaient nulle part :
 * une famille qui laissait son WhatsApp pouvait légitimement croire qu'on
 * la rappellerait dessus.
 *
 * Un champ vide n'est pas affiché plutôt que rempli d'un tiret : la liste
 * reste lisible, et l'absence se distingue d'une valeur.
 */
function ContactMessageDetail({ message: m }) {
  const rows = [
    [t("Nom complet"), m.name],
    [t("Email"), m.email],
    [t("Téléphone"), m.phone],
    [t("WhatsApp"), m.whatsapp],
    [t("Pays"), m.country],
    [t("État / Province"), m.state_province],
    [t("Fuseau horaire"), m.timezone],
    [t("Langue préférée"), m.preferred_language_display || m.preferred_language],
    [t("Catégorie"), m.category_display || m.category],
    [t("Sujet"), m.subject],
    [t("Reçu le"), m.created_at?.slice(0, 16).replace("T", " ")],
    [t("Consentement"), m.consent ? t("Accordé") : t("Non accordé")],
  ].filter(([, value]) => value !== null && value !== undefined && `${value}` !== "");

  return (
    <div className="space-y-4 text-sm">
      <div className="flex items-center gap-2 flex-wrap">
        <AcademyBadge code={m.entity_code} name={m.entity_short_name || m.entity_name} />
        {!m.is_read && <span className="badge bg-amber-50 text-amber-700">{t("Nouveau")}</span>}
      </div>

      <dl className="grid sm:grid-cols-2 gap-x-6 gap-y-2">
        {rows.map(([label, value]) => (
          <div key={label} className="min-w-0">
            <dt className="text-xs uppercase tracking-wide text-slate-400">{label}</dt>
            {/* `break-words` : un e-mail ou une URL très longue se replie
                au lieu d'élargir la colonne hors de la fenêtre. */}
            <dd className="text-slate-700 font-medium break-words">{value}</dd>
          </div>
        ))}
      </dl>

      <div>
        <p className="text-xs uppercase tracking-wide text-slate-400 mb-1.5">{t("Message")}</p>
        <LongText value={m.message} />
      </div>

      <div className="flex justify-end gap-2 flex-wrap">
        {m.whatsapp && (
          <a href={`https://wa.me/${String(m.whatsapp).replace(/[^0-9]/g, "")}`}
            target="_blank" rel="noopener noreferrer"
            className="btn-secondary inline-flex items-center gap-2">
            <ExternalLink className="w-4 h-4" /> {t("Répondre sur WhatsApp")}
          </a>
        )}
        <a href={`mailto:${m.email}?subject=Re: ${encodeURIComponent(m.subject || "")}`}
          className="btn-primary inline-flex items-center gap-2">
          <ExternalLink className="w-4 h-4" /> {t("Répondre par email")}
        </a>
      </div>
    </div>
  );
}

/* ── Onglet Messages ─────────────────────────────────────────────────────── */
function MessagesTab() {
  // P0 : l'académie entre dans les clés de cache de cet onglet.
  const academyKey = useAcademyKey();
  const { allEntitiesMode } = useEntityContext();
  const qc = useQueryClient();
  const [view, setView] = useState(null);
  const [del, setDel] = useState(null);
  const { data, isLoading } = useQuery({
    queryKey: ["site-admin-contact", academyKey], queryFn: websiteAdminAPI.contactMessages,
  });
  const readMut = useMutation({
    mutationFn: ({ id, is_read }) => websiteAdminAPI.updateContact(id, { is_read }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["site-admin-contact", academyKey] }),
  });
  const delMut = useMutation({
    mutationFn: websiteAdminAPI.deleteContact,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["site-admin-contact", academyKey] });
      toast.success(t("Message supprimé."));
      setDel(null);
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  // P5 — En mode « Toutes les Académies », chaque ligne DOIT dire de quelle
  // académie elle vient. Deux messages voisins peuvent venir de deux
  // établissements différents : sans étiquette, on répond au nom du mauvais.
  const cols = [
    { key: "date", label: t("Reçu le"), render: r => r.created_at?.slice(0, 16).replace("T", " ") },
    ...(allEntitiesMode ? [{
      key: "academy", label: t("Académie"), sortable: false,
      render: r => <AcademyBadge code={r.entity_code} name={r.entity_short_name} />,
    }] : []),
    { key: "name", label: t("Nom"), accessor: "name" },
    { key: "subject", label: t("Sujet"), accessor: "subject" },
    { key: "email", label: t("Email"), accessor: "email" },
    { key: "read", label: t("Statut"), render: r => r.is_read
        ? <span className="badge bg-slate-100 text-slate-500">{t("Lu")}</span>
        : <span className="badge bg-amber-50 text-amber-700">{t("Nouveau")}</span> },
  ];

  return (
    <div className="card">
      <DataTable columns={cols} data={rows(data)} loading={isLoading}
        onRowClick={(r) => { setView(r); if (!r.is_read) readMut.mutate({ id: r.id, is_read: true }); }}
        actions={(r) => (
          <div className="flex items-center gap-1 justify-end">
            <button onClick={() => readMut.mutate({ id: r.id, is_read: !r.is_read })}
              className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400"
              title={r.is_read ? t("Marquer non lu") : t("Marquer lu")}>
              {r.is_read ? <Mail className="w-4 h-4" /> : <MailOpen className="w-4 h-4" />}
            </button>
            <button onClick={() => setDel(r)}
              className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger" title={t("Supprimer")}>
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        )} />
      <Modal open={!!view} onClose={() => setView(null)}
        title={t("Message reçu")} size="lg">
        {view && <ContactMessageDetail message={view} />}
      </Modal>
      <ConfirmDialog open={!!del} onClose={() => setDel(null)}
        onConfirm={() => delMut.mutate(del?.id)} loading={delMut.isPending}
        message={`Supprimer le message de ${del?.name} ?`} />
    </div>
  );
}

/* ── Onglet Préinscriptions ──────────────────────────────────────────────── */
function PreregTab() {
  // P0 : l'académie entre dans les clés de cache de cet onglet.
  const academyKey = useAcademyKey();
  const qc = useQueryClient();
  const [del, setDel] = useState(null);
  const [detail, setDetail] = useState(null);
  const { data, isLoading } = useQuery({
    queryKey: ["site-admin-prereg", academyKey], queryFn: websiteAdminAPI.preregistrations,
  });
  const statusMut = useMutation({
    mutationFn: ({ id, status }) => websiteAdminAPI.updatePrereg(id, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["site-admin-prereg", academyKey] }),
    onError: (e) => toast.error(extractApiError(e)),
  });
  const delMut = useMutation({
    mutationFn: websiteAdminAPI.deletePrereg,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["site-admin-prereg", academyKey] });
      toast.success(t("Demande supprimée."));
      setDel(null);
    },
  });

  const sheetMut = useMutation({
    mutationFn: async (row) => {
      const response = await websiteAdminAPI.preregSheet(row.id);
      downloadBlob(`${row.reference || row.id}-fiche-preinscription.pdf`, response.data);
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const regenMut = useMutation({
    mutationFn: (row) => websiteAdminAPI.regeneratePreregSheet(row.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["site-admin-prereg", academyKey] });
      toast.success(t("Fiche régénérée."));
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const exportMut = useMutation({
    mutationFn: async () => {
      const response = await websiteAdminAPI.exportPreregs();
      downloadBlob("preinscriptions-feba.csv", response.data);
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  /*
   * P2 — LE TABLEAU RESTE LISIBLE, LA FICHE PORTE TOUT.
   *
   * La demande compte une vingtaine de champs. Les faire tous entrer dans
   * le tableau donnerait une grille illisible où l'essentiel se perd —
   * et où l'on ne remarquerait toujours rien. Le tableau garde donc les
   * huit colonnes de travail du secrétariat ; « Voir le dossier » ouvre
   * la fiche complète, sans exception et sans troncature.
   */
  const cols = [
    { key: "date", label: t("Reçue le"), render: r => r.created_at?.slice(0, 10) },
    { key: "reference", label: t("Dossier"), accessor: "reference" },
    { key: "child", label: t("Enfant"), render: r => `${r.child_name}${r.child_age ? ` (${r.child_age} ans)` : ""}` },
    { key: "level", label: t("Niveau"), accessor: "desired_level_display" },
    { key: "parent", label: t("Parent"), accessor: "parent_name" },
    { key: "phone", label: t("Téléphone"), accessor: "phone" },
    { key: "academy", label: t("Académie"), sortable: false, render: r => (
        <AcademyBadge code={r.academy_code} name={r.academy_name} />
      ) },
    { key: "status", label: t("Statut"), sortable: false, render: r => (
        <select value={r.status}
          onChange={(e) => statusMut.mutate({ id: r.id, status: e.target.value })}
          onClick={(e) => e.stopPropagation()}
          className="text-xs border border-slate-200 rounded-lg px-2 py-1 bg-white">
          {PREREG_STATUS.map(([v, l]) => <option key={v} value={v}>{t(l)}</option>)}
        </select>
      ) },
  ];

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button onClick={() => exportMut.mutate()} disabled={exportMut.isPending}
          className="btn-secondary inline-flex items-center gap-2">
          <Download className="w-4 h-4" aria-hidden="true" />
          {t("Exporter en CSV")}
        </button>
      </div>

      <div className="card">
        <DataTable columns={cols} data={rows(data)} loading={isLoading}
          actions={(r) => (
            <div className="flex items-center gap-1">
              <button onClick={() => setDetail(r.id)}
                className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700"
                title={t("Voir le dossier")}>
                <Eye className="w-4 h-4" aria-hidden="true" />
              </button>
              <button onClick={() => sheetMut.mutate(r)} disabled={sheetMut.isPending}
                className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700"
                title={t("Télécharger la fiche PDF")}>
                <FileText className="w-4 h-4" aria-hidden="true" />
              </button>
              <button onClick={() => setDel(r)}
                className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger"
                title={t("Supprimer")}>
                <Trash2 className="w-4 h-4" aria-hidden="true" />
              </button>
            </div>
          )} />
      </div>

      {detail !== null && (
        <PreregDetail id={detail} onClose={() => setDetail(null)}
          onDownload={sheetMut.mutate} onRegenerate={regenMut.mutate}
          busy={sheetMut.isPending || regenMut.isPending} />
      )}

      <ConfirmDialog open={!!del} onClose={() => setDel(null)}
        onConfirm={() => delMut.mutate(del?.id)} loading={delMut.isPending}
        message={`Supprimer la demande pour ${del?.child_name} ?`} />
    </div>
  );
}

/**
 * P2 — La fiche complète d'une demande de préinscription.
 *
 * LE DÉFAUT CORRIGÉ
 * -----------------
 * Le tableau affichait six colonnes. L'e-mail, le WhatsApp, l'âge, la date
 * de naissance, l'année scolaire, le message, l'adresse et le second
 * téléphone n'apparaissaient NULLE PART — ni ici, ni ailleurs. Ils étaient
 * collectés, enregistrés, et invisibles.
 *
 * Cette vue affiche chaque champ, texte long compris, sans troncature.
 * Elle recharge le dossier depuis le serveur plutôt que de réutiliser la
 * ligne du tableau : la ligne vient d'une liste qui peut dater, et une
 * fiche officielle doit montrer l'état actuel.
 */
function PreregDetail({ id, onClose, onDownload, onRegenerate, busy }) {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["site-admin-prereg-detail", id],
    queryFn: () => websiteAdminAPI.prereg(id),
  });
  const row = data?.data;

  return (
    <Modal open onClose={onClose} title={t("Dossier de préinscription")} size="lg">
      {isLoading && <p className="text-sm text-slate-500">{t("Chargement…")}</p>}
      {isError && (
        <p className="text-sm text-danger">{extractApiError(error)}</p>
      )}
      {row && (
        <div className="space-y-4 text-sm min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <AcademyBadge code={row.academy_code} name={row.academy_name} />
            <span className="badge bg-slate-100 text-slate-600">{row.reference}</span>
            <span className="badge bg-sky-50 text-sky-700">{row.status_display}</span>
            {/* L'état RÉEL de la fiche, tel que le serveur le constate sur
                le disque — pas déduit de la présence d'un chemin en base. */}
            {row.sheet_available
              ? <span className="badge bg-emerald-50 text-emerald-700">{t("Fiche PDF disponible")}</span>
              : <span className="badge bg-amber-50 text-amber-700">{t("Fiche PDF absente")}</span>}
          </div>

          {row.sheet_error && (
            <div className="rounded-xl bg-red-50 border border-red-100 p-3">
              <p className="text-xs font-semibold text-red-700 mb-1">
                {t("Dernier échec de production de la fiche")}
              </p>
              <LongText value={row.sheet_error} plain copyable={false}
                        maxHeight="none" className="text-xs text-red-700" />
            </div>
          )}

          <Section title={t("Dossier")}>
            <DetailField label={t("Numéro de dossier")} value={row.reference} />
            <DetailField label={t("Reçue le")}
                         value={row.created_at?.slice(0, 16).replace("T", " ")} />
            <DetailField label={t("Statut")} value={row.status_display} />
            <DetailField label={t("Année scolaire souhaitée")} value={row.school_year}
                         emptyLabel={t("Non renseignée")} />
          </Section>

          <Section title={t("Enfant")}>
            <DetailField label={t("Nom et prénoms")} value={row.child_name} />
            <DetailField label={t("Date de naissance")} value={row.child_birth_date}
                         emptyLabel={t("Non renseignée")} />
            <DetailField label={t("Âge déclaré")}
                         value={row.child_age ? `${row.child_age} ans` : ""}
                         emptyLabel={t("Non renseigné")} />
            <DetailField label={t("Niveau demandé")} value={row.desired_level_display} />
          </Section>

          <Section title={t("Parent ou tuteur")}>
            <DetailField label={t("Nom et prénoms")} value={row.parent_name} />
            <DetailField label={t("Téléphone principal")} value={row.phone} />
            <DetailField label={t("Téléphone secondaire")} value={row.phone_secondary}
                         emptyLabel={t("Non renseigné")} />
            <DetailField label={t("WhatsApp")} value={row.whatsapp}
                         emptyLabel={t("Non renseigné")} />
            <DetailField label={t("Adresse électronique")} value={row.email}
                         emptyLabel={t("Non renseignée")} />
          </Section>

          <Section title={t("Domicile")}>
            <DetailField label={t("Adresse")} value={row.address}
                         emptyLabel={t("Non renseignée")} copyable />
          </Section>

          <Section title={t("Message de la famille")}>
            <DetailField label={t("Message")} value={row.message}
                         emptyLabel={t("Aucun message")} copyable />
          </Section>

          <div className="flex justify-end gap-2 flex-wrap pt-2">
            {row.whatsapp && (
              <a href={`https://wa.me/${String(row.whatsapp).replace(/[^0-9]/g, "")}`}
                target="_blank" rel="noopener noreferrer"
                className="btn-secondary inline-flex items-center gap-2">
                <ExternalLink className="w-4 h-4" aria-hidden="true" />
                {t("Répondre sur WhatsApp")}
              </a>
            )}
            <button type="button" onClick={() => onRegenerate(row)} disabled={busy}
              className="btn-secondary inline-flex items-center gap-2">
              <RefreshCw className="w-4 h-4" aria-hidden="true" />
              {t("Régénérer la fiche")}
            </button>
            <button type="button" onClick={() => onDownload(row)} disabled={busy}
              className="btn-primary inline-flex items-center gap-2">
              <Download className="w-4 h-4" aria-hidden="true" />
              {t("Télécharger la fiche PDF")}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}

function Section({ title, children }) {
  return (
    <section className="min-w-0">
      <h3 className="text-xs font-bold uppercase tracking-wide text-slate-400 mb-2">
        {title}
      </h3>
      <div className="space-y-1 min-w-0">{children}</div>
    </section>
  );
}

/**
 * Téléchargement d'un contenu produit PAR LE SERVEUR.
 *
 * Le fichier arrive dans la réponse d'une requête authentifiée, et l'objet
 * URL temporaire est révoqué aussitôt : une fiche de préinscription
 * contient l'adresse et le téléphone d'une famille, et un lien qui
 * resterait valide serait partageable par mégarde.
 */
function downloadBlob(filename, data) {
  const blob = data instanceof Blob ? data : new Blob([data]);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

/* ── Onglet Actualités ───────────────────────────────────────────────────── */
function NewsTab() {
  // P0 : l'académie entre dans les clés de cache de cet onglet.
  const academyKey = useAcademyKey();
  const qc = useQueryClient();
  const [modal, setModal] = useState(false);
  const [edit, setEdit] = useState(null);
  const [del, setDel] = useState(null);
  const { register, handleSubmit, reset } = useForm();
  const { data, isLoading } = useQuery({
    queryKey: ["site-admin-news", academyKey], queryFn: websiteAdminAPI.news,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["site-admin-news", academyKey] });
    qc.invalidateQueries({ queryKey: ["site-news"] });
    qc.invalidateQueries({ queryKey: ["site-news-home"] });
  };
  const saveMut = useMutation({
    mutationFn: (d) => edit
      ? websiteAdminAPI.updateNews(edit.id, d)
      : websiteAdminAPI.createNews(d),
    onSuccess: () => {
      invalidate();
      toast.success(edit ? t("Publication modifiée !") : t("Publication créée !"));
      close();
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const delMut = useMutation({
    mutationFn: websiteAdminAPI.deleteNews,
    onSuccess: () => { invalidate(); toast.success(t("Publication supprimée.")); setDel(null); },
  });

  const close = () => { setModal(false); setEdit(null); reset(); };
  const openCreate = () => { setEdit(null); reset({ kind: "news", is_published: true }); setModal(true); };
  const openEdit = (r) => {
    setEdit(r);
    reset({
      kind: r.kind, title: r.title, excerpt: r.excerpt, body: r.body,
      event_date: r.event_date ? r.event_date.slice(0, 16) : "",
      location: r.location, image_path: r.image_path, is_published: r.is_published,
    });
    setModal(true);
  };
  const onSubmit = (d) => {
    const payload = { ...d, event_date: d.event_date || null };
    saveMut.mutate(payload);
  };

  const cols = [
    { key: "title", label: t("Titre"), accessor: "title" },
    { key: "kind", label: t("Type"), render: r => r.kind === "event"
        ? <span className="badge bg-amber-50 text-amber-700">{t("Événement")}</span>
        : <span className="badge bg-sky-50 text-sky-700">{t("Actualité")}</span> },
    { key: "pub", label: t("Publication"), render: r => r.is_published
        ? <span className="badge bg-emerald-50 text-emerald-700">{t("Publiée")}</span>
        : <span className="badge bg-slate-100 text-slate-500">{t("Brouillon")}</span> },
    { key: "date", label: t("Date"), render: r => (r.published_at || r.created_at)?.slice(0, 10) },
  ];

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button onClick={openCreate} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" /> {t("Nouvelle publication")}
        </button>
      </div>
      <div className="card">
        <DataTable columns={cols} data={rows(data)} loading={isLoading}
          actions={(r) => (
            <div className="flex items-center gap-1 justify-end">
              <button onClick={() => openEdit(r)}
                className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-400 hover:text-primary" title={t("Modifier")}>
                <Pencil className="w-4 h-4" />
              </button>
              <button onClick={() => setDel(r)}
                className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger" title={t("Supprimer")}>
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          )} />
      </div>

      <Modal open={modal} onClose={close}
        title={edit ? t("Modifier la publication") : t("Nouvelle publication")} size="lg">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">{t("Type *")}</label>
              <select {...register("kind", { required: true })} className="input">
                <option value="news">{t("Actualité")}</option>
                <option value="event">{t("Événement")}</option>
              </select>
            </div>
            <div className="flex items-end pb-2">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" {...register("is_published")} className="rounded border-slate-300" />
                {t("Publier sur le site")}
              </label>
            </div>
          </div>
          <div>
            <label className="label">{t("Titre *")}</label>
            <input {...register("title", { required: true })} className="input" />
          </div>
          <div>
            <label className="label">{t("Résumé (affiché dans les listes)")}</label>
            <input {...register("excerpt")} className="input" maxLength={300} />
          </div>
          <div>
            <label className="label">{t("Contenu")}</label>
            <textarea {...register("body")} rows={6} className="input" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">{t("Date de l'événement")}</label>
              <input type="datetime-local" {...register("event_date")} className="input" />
            </div>
            <div>
              <label className="label">{t("Lieu")}</label>
              <input {...register("location")} className="input" />
            </div>
          </div>
          <div>
            <label className="label">{t("Image (chemin ou URL)")}</label>
            <input {...register("image_path")} className="input"
              placeholder="/site/img/activite-expression-1600.webp" />
            <p className="text-xs text-slate-400 mt-1">
              {t("Chemins des visuels packagés : voir MEDIA_INVENTORY.md (ex. /site/img/hero-campus-1600.webp).")}
            </p>
          </div>
          <div className="flex gap-3 justify-end pt-2 border-t border-slate-100">
            <button type="button" onClick={close} className="btn-secondary">{t("Annuler")}</button>
            <button type="submit" disabled={saveMut.isPending} className="btn-primary">
              {saveMut.isPending ? t("Enregistrement...") : t("Enregistrer")}
            </button>
          </div>
        </form>
      </Modal>
      <ConfirmDialog open={!!del} onClose={() => setDel(null)}
        onConfirm={() => delMut.mutate(del?.id)} loading={delMut.isPending}
        message={`Supprimer « ${del?.title} » ?`} />
    </div>
  );
}

/* ── Onglet Paramètres ───────────────────────────────────────────────────── */
function SettingsTab() {
  // P0 : l'académie entre dans les clés de cache de cet onglet.
  const academyKey = useAcademyKey();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["site-admin-settings", academyKey], queryFn: websiteAdminAPI.settings,
  });
  const { register, handleSubmit } = useForm({ values: data?.data });
  const saveMut = useMutation({
    mutationFn: websiteAdminAPI.updateSettings,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["site-admin-settings", academyKey] });
      qc.invalidateQueries({ queryKey: ["site-settings"] });
      toast.success(t("Paramètres du site enregistrés."));
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  if (isLoading) return <div className="card p-8 text-center text-slate-400">{t("Chargement…")}</div>;

  const numeric = (v) => (v === "" || v === null || v === undefined ? null : Number(v));
  const onSubmit = (d) => saveMut.mutate({
    ...d,
    stat_students: numeric(d.stat_students),
    stat_teachers: numeric(d.stat_teachers),
    stat_years: numeric(d.stat_years),
    stat_success_rate: numeric(d.stat_success_rate),
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="card p-6 space-y-6">
      <div>
        <h3 className="font-bold text-slate-800 mb-3">{t("Identité")}</h3>
        <div className="grid sm:grid-cols-2 gap-4">
          <div><label className="label">{t("Nom de l'école")}</label><input {...register("school_name")} className="input" /></div>
          <div><label className="label">{t("Slogan")}</label><input {...register("tagline")} className="input" /></div>
        </div>
      </div>
      <div>
        <h3 className="font-bold text-slate-800 mb-3">{t("Coordonnées (vides = masquées sur le site)")}</h3>
        <div className="grid sm:grid-cols-2 gap-4">
          <div><label className="label">{t("Adresse")}</label><input {...register("address")} className="input" /></div>
          <div><label className="label">{t("Téléphone")}</label><input {...register("phone")} className="input" placeholder="+229 ..." /></div>
          <div><label className="label">{t("WhatsApp")}</label><input {...register("whatsapp")} className="input" placeholder="+229 ..." /></div>
          <div><label className="label">{t("Email")}</label><input {...register("email")} type="email" className="input" /></div>
          <div className="sm:col-span-2"><label className="label">{t("Horaires")}</label><input {...register("opening_hours")} className="input" placeholder="Lun–Ven 7h30–17h30" /></div>
        </div>
      </div>
      <div>
        <h3 className="font-bold text-slate-800 mb-3">{t("Réseaux sociaux")}</h3>
        <div className="grid sm:grid-cols-3 gap-4">
          <div><label className="label">Facebook</label><input {...register("facebook_url")} className="input" /></div>
          <div><label className="label">Instagram</label><input {...register("instagram_url")} className="input" /></div>
          <div><label className="label">YouTube</label><input {...register("youtube_url")} className="input" /></div>
        </div>
      </div>
      <div>
        <h3 className="font-bold text-slate-800 mb-3">{t("Statistiques (vides = section masquée)")}</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div><label className="label">{t("Élèves")}</label><input type="number" {...register("stat_students")} className="input" /></div>
          <div><label className="label">{t("Enseignants")}</label><input type="number" {...register("stat_teachers")} className="input" /></div>
          <div><label className="label">{t("Années d'expérience")}</label><input type="number" {...register("stat_years")} className="input" /></div>
          <div><label className="label">{t("Taux de réussite (%)")}</label><input type="number" {...register("stat_success_rate")} className="input" /></div>
        </div>
      </div>
      <div>
        <h3 className="font-bold text-slate-800 mb-3">{t("SEO")}</h3>
        <div className="space-y-4">
          <div><label className="label">{t("Titre par défaut")}</label><input {...register("meta_title")} className="input" /></div>
          <div><label className="label">{t("Méta-description")}</label><textarea {...register("meta_description")} rows={2} className="input" /></div>
        </div>
      </div>
      <div className="flex justify-end pt-2 border-t border-slate-100">
        <button type="submit" disabled={saveMut.isPending} className="btn-primary">
          {saveMut.isPending ? t("Enregistrement...") : t("Enregistrer les paramètres")}
        </button>
      </div>
    </form>
  );
}

export default function AdminWebsite() {
  // Académie active : détermine les onglets réellement disponibles.
  const { activeEntity, allEntitiesMode, isLoading: contextLoading } = useEntityContext();
  // Une académie EN LIGNE (FEBA FHA) n'a pas de préinscriptions FEBA.
  // En mode « Toutes les Académies », l'onglet reste visible : il porte
  // alors explicitement le libellé « Préinscriptions FEBA ».
  // Le contexte d'académie arrive de façon ASYNCHRONE. Tant qu'il n'est
  // pas chargé, `activeEntity` est indéfini : filtrer à ce moment-là
  // afficherait l'onglet « Préinscriptions » pour FEBA FHA, puis le
  // retirerait — un clignotement trompeur. On attend donc le contexte.
  const isOnlineAcademy = activeEntity?.entity_type === "online";
  const visibleTabs = contextLoading
    ? []
    : TABS.filter((item) => !(item.campusOnly && isOnlineAcademy));

  const [tab, setTab] = useState("messages");
  return (
    <div className="space-y-6">
      <PageHeader title={t("Site vitrine")}
        subtitle={t("Contenu public : messages, préinscriptions, actualités et paramètres")} />
      <div className="flex gap-2 flex-wrap">
        {contextLoading && (
          <div className="h-10 w-96 rounded-xl bg-slate-100 animate-pulse" aria-hidden="true" />
        )}
        {visibleTabs.map((tb) => (
          <button key={tb.key} onClick={() => setTab(tb.key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
              tab === tb.key
                ? "bg-primary text-white shadow-md"
                : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
            }`}>
            <tb.icon className="w-4 h-4" />{" "}
            {/* Libellé explicite en toutes circonstances : cet onglet ne
                montre QUE les préinscriptions FEBA (modèle PreRegistration).
                Les dossiers FEBA FHA vivent dans « Admissions FEBA FHA ». */}
            {tb.key === "prereg" ? t("Préinscriptions FEBA") : t(tb.label)}
          </button>
        ))}
      </div>
      {tab === "messages" && <MessagesTab />}
      {tab === "prereg" && !isOnlineAcademy && <PreregTab />}
      {tab === "news" && <NewsTab />}
      {tab === "settings" && <SettingsTab />}
      <p className="text-xs text-slate-400">
        {t("Slides du carrousel et galerie : gérables via l'admin Django (/django-admin/) ou l'API /api/website/admin/.")}
      </p>
    </div>
  );
}
