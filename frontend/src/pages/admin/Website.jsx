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
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import {
  Inbox, ClipboardList, Newspaper, Settings2, Trash2, Pencil, Plus,
  MailOpen, Mail, ExternalLink,
} from "lucide-react";
import toast from "react-hot-toast";
import { websiteAdminAPI } from "../../api";
import { extractApiError } from "../../utils/errors";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import { t } from "../../i18n";

const TABS = [
  { key: "messages", label: "Messages reçus", icon: Inbox },
  { key: "prereg", label: "Préinscriptions", icon: ClipboardList },
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

/* ── Onglet Messages ─────────────────────────────────────────────────────── */
function MessagesTab() {
  const qc = useQueryClient();
  const [view, setView] = useState(null);
  const [del, setDel] = useState(null);
  const { data, isLoading } = useQuery({
    queryKey: ["site-admin-contact"], queryFn: websiteAdminAPI.contactMessages,
  });
  const readMut = useMutation({
    mutationFn: ({ id, is_read }) => websiteAdminAPI.updateContact(id, { is_read }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["site-admin-contact"] }),
  });
  const delMut = useMutation({
    mutationFn: websiteAdminAPI.deleteContact,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["site-admin-contact"] });
      toast.success(t("Message supprimé."));
      setDel(null);
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const cols = [
    { key: "date", label: t("Reçu le"), render: r => r.created_at?.slice(0, 16).replace("T", " ") },
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
      <Modal open={!!view} onClose={() => setView(null)} title={view?.subject || ""} size="md">
        {view && (
          <div className="space-y-3 text-sm">
            <p><span className="text-slate-500">{t("De")} :</span> <strong>{view.name}</strong> — {view.email}{view.phone ? ` — ${view.phone}` : ""}</p>
            <p className="text-slate-400 text-xs">{view.created_at?.slice(0, 16).replace("T", " ")}</p>
            <p className="whitespace-pre-line bg-slate-50 rounded-xl p-4">{view.message}</p>
            <div className="flex justify-end">
              <a href={`mailto:${view.email}?subject=Re: ${encodeURIComponent(view.subject)}`}
                className="btn-primary inline-flex items-center gap-2">
                <ExternalLink className="w-4 h-4" /> {t("Répondre par email")}
              </a>
            </div>
          </div>
        )}
      </Modal>
      <ConfirmDialog open={!!del} onClose={() => setDel(null)}
        onConfirm={() => delMut.mutate(del?.id)} loading={delMut.isPending}
        message={`Supprimer le message de ${del?.name} ?`} />
    </div>
  );
}

/* ── Onglet Préinscriptions ──────────────────────────────────────────────── */
function PreregTab() {
  const qc = useQueryClient();
  const [del, setDel] = useState(null);
  const { data, isLoading } = useQuery({
    queryKey: ["site-admin-prereg"], queryFn: websiteAdminAPI.preregistrations,
  });
  const statusMut = useMutation({
    mutationFn: ({ id, status }) => websiteAdminAPI.updatePrereg(id, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["site-admin-prereg"] }),
    onError: (e) => toast.error(extractApiError(e)),
  });
  const delMut = useMutation({
    mutationFn: websiteAdminAPI.deletePrereg,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["site-admin-prereg"] });
      toast.success(t("Demande supprimée."));
      setDel(null);
    },
  });

  const cols = [
    { key: "date", label: t("Reçue le"), render: r => r.created_at?.slice(0, 10) },
    { key: "child", label: t("Enfant"), render: r => `${r.child_name}${r.child_age ? ` (${r.child_age} ans)` : ""}` },
    { key: "level", label: t("Niveau"), accessor: "desired_level_display" },
    { key: "parent", label: t("Parent"), accessor: "parent_name" },
    { key: "phone", label: t("Téléphone"), accessor: "phone" },
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
    <div className="card">
      <DataTable columns={cols} data={rows(data)} loading={isLoading}
        actions={(r) => (
          <button onClick={() => setDel(r)}
            className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger" title={t("Supprimer")}>
            <Trash2 className="w-4 h-4" />
          </button>
        )} />
      <ConfirmDialog open={!!del} onClose={() => setDel(null)}
        onConfirm={() => delMut.mutate(del?.id)} loading={delMut.isPending}
        message={`Supprimer la demande pour ${del?.child_name} ?`} />
    </div>
  );
}

/* ── Onglet Actualités ───────────────────────────────────────────────────── */
function NewsTab() {
  const qc = useQueryClient();
  const [modal, setModal] = useState(false);
  const [edit, setEdit] = useState(null);
  const [del, setDel] = useState(null);
  const { register, handleSubmit, reset } = useForm();
  const { data, isLoading } = useQuery({
    queryKey: ["site-admin-news"], queryFn: websiteAdminAPI.news,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["site-admin-news"] });
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
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["site-admin-settings"], queryFn: websiteAdminAPI.settings,
  });
  const { register, handleSubmit } = useForm({ values: data?.data });
  const saveMut = useMutation({
    mutationFn: websiteAdminAPI.updateSettings,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["site-admin-settings"] });
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
  const [tab, setTab] = useState("messages");
  return (
    <div className="space-y-6">
      <PageHeader title={t("Site vitrine")}
        subtitle={t("Contenu public : messages, préinscriptions, actualités et paramètres")} />
      <div className="flex gap-2 flex-wrap">
        {TABS.map((tb) => (
          <button key={tb.key} onClick={() => setTab(tb.key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
              tab === tb.key
                ? "bg-primary text-white shadow-md"
                : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
            }`}>
            <tb.icon className="w-4 h-4" /> {t(tb.label)}
          </button>
        ))}
      </div>
      {tab === "messages" && <MessagesTab />}
      {tab === "prereg" && <PreregTab />}
      {tab === "news" && <NewsTab />}
      {tab === "settings" && <SettingsTab />}
      <p className="text-xs text-slate-400">
        {t("Slides du carrousel et galerie : gérables via l'admin Django (/django-admin/) ou l'API /api/website/admin/.")}
      </p>
    </div>
  );
}
