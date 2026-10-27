/**
 * Boîte d'envoi — tous les e-mails émis par FEBA (octobre 2026).
 *
 * Chaque envoi est consultable : objet, destinataire, expéditeur, origine,
 * statut EXACT (« capturé par Mailpit » n'est pas « envoyé »), tentatives,
 * erreurs, texte, HTML et pièces jointes. Le périmètre (académie) est
 * décidé par le serveur ; l'écran n'affiche que ce qu'il reçoit.
 *
 * Sécurité : le HTML archivé est rendu dans un <iframe sandbox> SANS
 * `allow-scripts` — aucun script ne peut s'exécuter dans l'application. Les
 * pièces jointes sont récupérées avec le jeton de session (jamais par une
 * URL publique) puis affichées ou téléchargées depuis un objet local.
 */
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { AlertTriangle, Download, Eye, Mail, Paperclip, RefreshCw, Search, Send, X } from "lucide-react";

import { outboxAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import { t } from "../../i18n";
import { extractApiError } from "../../utils/errors";
import { formatDateTime } from "../../utils/datetime";
import { useAcademyKey } from "../../hooks/useEntityContext";

const STATUS_TONE = {
  sent: "bg-emerald-50 text-emerald-700",
  accepted: "bg-emerald-50 text-emerald-700",
  queued: "bg-slate-100 text-slate-600",
  pending: "bg-blue-50 text-blue-700",
  retry: "bg-amber-50 text-amber-700",
  failed: "bg-red-50 text-red-700",
};
const STATUS_FILTERS = [
  ["", "Tous les statuts"], ["queued", "En file d'attente"], ["pending", "Envoi en cours"],
  ["sent", "Accepté par le serveur"], ["retry", "Nouvel essai programmé"], ["failed", "Échec définitif"],
];

function Badge({ tone, children }) {
  return <span className={`inline-block rounded-md px-2 py-0.5 text-[11px] font-semibold ${tone || "bg-slate-100 text-slate-600"}`}>{children}</span>;
}

function formatBytes(n) {
  if (n < 1024) return `${n} o`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} Ko`;
  return `${(n / (1024 * 1024)).toFixed(1)} Mo`;
}

/** Statut affiché : la capture Mailpit n'est jamais présentée comme une distribution. */
function StatusCell({ row }) {
  return (
    <div className="space-y-1">
      <Badge tone={STATUS_TONE[row.status]}>{t(row.status_display)}</Badge>
      {["sent", "accepted"].includes(row.status) && !row.used_real_provider && (
        <div><Badge tone="bg-amber-50 text-amber-700">{t(row.delivery_summary)}</Badge></div>
      )}
      {row.sms && <SmsBadge sms={row.sms} />}
    </div>
  );
}

const SMS_TONE = {
  sent: "bg-emerald-50 text-emerald-700", delivered: "bg-emerald-50 text-emerald-700",
  failed: "bg-red-50 text-red-700", retry: "bg-amber-50 text-amber-700",
  skipped: "bg-slate-100 text-slate-600", captured: "bg-amber-50 text-amber-700",
  pending: "bg-blue-50 text-blue-700", sending: "bg-blue-50 text-blue-700",
};

/** Statut du SMS miroir : DISTINCT de celui de l'e-mail. */
function SmsBadge({ sms }) {
  const label = sms.status === "skipped" && sms.skip_reason_display
    ? `${t("SMS non envoyé")} — ${t(sms.skip_reason_display)}`
    : `SMS : ${t(sms.status_display)}`;
  return <div><Badge tone={SMS_TONE[sms.status] || ""}>{label}</Badge></div>;
}

export default function Outbox() {
  const academyKey = useAcademyKey();
  const [filters, setFilters] = useState({ status: "", purpose: "", to: "", q: "", date_from: "", date_to: "" });
  const [applied, setApplied] = useState(filters);
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState(null);

  const params = Object.fromEntries(Object.entries({ ...applied, page, page_size: 25 }).filter(([, v]) => v !== ""));
  const listQ = useQuery({
    queryKey: ["outbox", academyKey, params],
    queryFn: () => outboxAPI.list(params),
    keepPreviousData: true,
    refetchInterval: (q) => ((q.state.data?.data?.results || []).some((r) => ["queued", "pending"].includes(r.status)) ? 4000 : false),
  });
  const data = listQ.data?.data;
  const rows = data?.results || [];
  const pages = data ? Math.max(1, Math.ceil(data.count / data.page_size)) : 1;
  const set = (k) => (e) => setFilters((f) => ({ ...f, [k]: e.target.value }));
  const apply = (e) => { e?.preventDefault(); setApplied(filters); setPage(1); };

  return (
    <div className="space-y-6">
      <PageHeader title={t("Boîte d'envoi")} subtitle={t("Tous les e-mails envoyés depuis la plateforme, avec leur contenu et leurs pièces jointes")} />
      <SmtpPanel />

      <form className="card grid gap-2 sm:grid-cols-3 lg:grid-cols-7 items-end text-sm" onSubmit={apply}>
        <label className="lg:col-span-2">{t("Recherche")}
          <input className="input" value={filters.q} onChange={set("q")} placeholder={t("Objet, destinataire, contenu…")} /></label>
        <label>{t("Destinataire")}<input className="input" value={filters.to} onChange={set("to")} /></label>
        <label>{t("Statut")}
          <select className="input" value={filters.status} onChange={set("status")}>
            {STATUS_FILTERS.map(([v, l]) => <option key={v} value={v}>{t(l)}</option>)}
          </select></label>
        <label>{t("Origine")}
          <select className="input" value={filters.purpose} onChange={set("purpose")}>
            <option value="">{t("Toutes les origines")}</option>
            {(data?.purposes || []).map((p) => <option key={p.value} value={p.value}>{t(p.label)}</option>)}
          </select></label>
        <label>{t("Du")}<input type="date" className="input" value={filters.date_from} onChange={set("date_from")} /></label>
        <label>{t("Au")}<input type="date" className="input" value={filters.date_to} onChange={set("date_to")} /></label>
        <button type="submit" className="btn-primary flex items-center justify-center gap-2"><Search className="w-4 h-4" />{t("Filtrer")}</button>
      </form>

      <div className="card overflow-x-auto">
        {listQ.isError ? <p className="text-sm text-red-700">{extractApiError(listQ.error)}</p> : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500 border-b border-slate-100">
                {["Date et heure", "Académie", "Destinataire", "Objet", "Origine", "Statut", ""].map((h) => (
                  <th key={h} className="py-2 pr-3 font-semibold">{h ? t(h) : ""}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {listQ.isLoading && <tr><td colSpan={7} className="py-8 text-center text-slate-400">{t("Chargement…")}</td></tr>}
              {!listQ.isLoading && rows.length === 0 && <tr><td colSpan={7} className="py-8 text-center text-slate-400">{t("Aucun e-mail pour ces critères.")}</td></tr>}
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-slate-50 hover:bg-slate-50 cursor-pointer align-top" onClick={() => setOpenId(r.id)}>
                  <td className="py-2 pr-3 whitespace-nowrap">{formatDateTime(r.created_at)}</td>
                  <td className="py-2 pr-3 text-xs">{r.academy?.code || "—"}</td>
                  <td className="py-2 pr-3 break-all">{r.to_email}</td>
                  <td className="py-2 pr-3">
                    {r.subject}
                    {r.attachments_count > 0 && (
                      <span className="ml-1 inline-flex items-center gap-0.5 text-xs text-slate-400"><Paperclip className="w-3 h-3" />{r.attachments_count}</span>
                    )}
                  </td>
                  <td className="py-2 pr-3 text-xs text-slate-500">{t(r.purpose_label)}</td>
                  <td className="py-2 pr-3"><StatusCell row={r} /></td>
                  <td className="py-2 pr-3 text-right">
                    <button type="button" className="text-xs text-primary hover:underline" aria-label={`${t("Ouvrir")} ${r.subject}`}>{t("Ouvrir")}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {data && (
          <div className="flex items-center justify-between mt-3 text-sm text-slate-500">
            <span>{t("{n} e-mail(s)", { n: data.count })}</span>
            <div className="flex items-center gap-2">
              <button type="button" className="btn-secondary text-xs" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>{t("Précédent")}</button>
              <span>{t("Page")} {page} / {pages}</span>
              <button type="button" className="btn-secondary text-xs" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>{t("Suivant")}</button>
            </div>
          </div>
        )}
      </div>

      {openId && <OutboxDetail id={openId} onClose={() => setOpenId(null)} />}
    </div>
  );
}

function OutboxDetail({ id, onClose }) {
  const qc = useQueryClient();
  const academyKey = useAcademyKey();
  const { data, isLoading, isError, error } = useQuery({ queryKey: ["outbox-detail", id, academyKey], queryFn: () => outboxAPI.detail(id) });
  const d = data?.data;
  const [preview, setPreview] = useState(null);   // { url, type, name }
  const retrying = useRef(false);

  useEffect(() => () => { if (preview?.url) URL.revokeObjectURL(preview.url); }, [preview]);

  const retryMut = useMutation({
    mutationFn: () => outboxAPI.retry(id),
    onSuccess: (res) => {
      toast.success(t("Nouvelle tentative : {s}", { s: t(res.data.delivery_summary) }));
      qc.invalidateQueries({ queryKey: ["outbox-detail", id, academyKey] });
      qc.invalidateQueries({ queryKey: ["outbox", academyKey] });
    },
    onError: (e) => toast.error(extractApiError(e)),
    onSettled: () => { retrying.current = false; },
  });

  const fetchFile = async (attachment, inline) => {
    try {
      const res = await outboxAPI.attachment(id, attachment.id, inline);
      const blob = new Blob([res.data], { type: attachment.content_type });
      const url = URL.createObjectURL(blob);
      if (inline) {
        setPreview({ url, type: attachment.content_type, name: attachment.name });
      } else {
        const link = document.createElement("a");
        link.href = url; link.download = attachment.name; link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
    } catch (e) {
      toast.error(extractApiError(e));
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label={t("Détail de l'e-mail")}>
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative z-10 h-full w-full max-w-3xl overflow-y-auto bg-white p-6 space-y-4 text-sm">
        <div className="flex items-start justify-between gap-2">
          <h2 className="text-lg font-bold text-slate-800 break-words">{d?.subject || t("E-mail")}</h2>
          <button type="button" onClick={onClose} aria-label={t("Fermer")}><X className="w-5 h-5 text-slate-400" /></button>
        </div>
        {isLoading && <p className="text-slate-400">{t("Chargement…")}</p>}
        {isError && <p className="text-red-700">{extractApiError(error)}</p>}
        {d && (
          <>
            <dl className="grid grid-cols-[9rem_1fr] gap-x-3 gap-y-1">
              <dt className="text-slate-500">{t("Date et heure")}</dt><dd>{formatDateTime(d.created_at)}</dd>
              <dt className="text-slate-500">{t("Expéditeur")}</dt><dd className="break-all">{d.from_email || "—"}</dd>
              <dt className="text-slate-500">{t("Destinataire")}</dt><dd className="break-all">{d.to_email}</dd>
              <dt className="text-slate-500">{t("Académie")}</dt><dd>{d.academy?.name || "—"}</dd>
              <dt className="text-slate-500">{t("Origine")}</dt><dd>{t(d.purpose_label)} {d.reference && <span className="text-slate-400">· {d.reference}</span>}</dd>
              <dt className="text-slate-500">{t("Statut")}</dt><dd><StatusCell row={d} /></dd>
              <dt className="text-slate-500">{t("Transport")}</dt><dd>{t(d.transport_display)} {d.smtp_host && <span className="text-slate-400">({d.smtp_host})</span>}</dd>
              {d.sms && (
                <>
                  <dt className="text-slate-500">SMS</dt>
                  <dd>
                    <SmsBadge sms={d.sms} />
                    <span className="text-xs text-slate-500">
                      {d.sms.to_number} · {d.sms.encoding} · {d.sms.segments} {t("segment(s)")}
                      {d.sms.last_error && ` · ${d.sms.last_error}`}
                    </span>
                  </dd>
                </>
              )}
              <dt className="text-slate-500">{t("Tentatives")}</dt><dd>{d.attempts}{d.next_retry_at && ` · ${t("prochain essai")} ${formatDateTime(d.next_retry_at)}`}</dd>
              <dt className="text-slate-500">{t("Suivi")}</dt><dd className="break-all text-xs text-slate-500">{d.tracking_id} {d.message_id}</dd>
            </dl>
            {d.last_error && <p className="rounded-lg bg-red-50 p-2 text-xs text-red-700 break-all">{d.last_error}</p>}
            {d.retry_note && <p className="rounded-lg bg-amber-50 p-2 text-xs text-amber-800">{d.retry_note}</p>}
            {d.can_retry && (
              <button type="button" className="btn-secondary flex items-center gap-2" disabled={retryMut.isPending}
                      onClick={() => { if (!retrying.current) { retrying.current = true; retryMut.mutate(); } }}>
                <RefreshCw className="w-4 h-4" />{t("Relancer cet envoi")}
              </button>
            )}

            {d.content_note ? (
              <p className="rounded-lg bg-slate-50 p-3 text-slate-500">{t(d.content_note)}</p>
            ) : (
              <>
                {d.is_redacted && <p className="text-xs text-amber-700">{t(d.redaction_note)}</p>}
                <section>
                  <h3 className="font-semibold text-slate-700 mb-1">{t("Contenu texte")}</h3>
                  <pre className="whitespace-pre-wrap rounded-lg bg-slate-50 p-3 font-sans text-slate-700 text-wrapsafe">{d.text_body || "—"}</pre>
                </section>
                {d.html_body && (
                  <section>
                    <h3 className="font-semibold text-slate-700 mb-1">{t("Version HTML")}</h3>
                    {/* sandbox SANS allow-scripts : le HTML ne peut rien exécuter. */}
                    <iframe title={t("Version HTML")} sandbox="" srcDoc={d.html_body}
                            className="w-full h-72 rounded-lg border border-slate-200 bg-white" />
                  </section>
                )}
                <section>
                  <h3 className="font-semibold text-slate-700 mb-1">{t("Pièces jointes")} ({d.attachments.length})</h3>
                  {d.attachments.length === 0 ? <p className="text-slate-400">{t("Aucune pièce jointe.")}</p> : (
                    <ul className="divide-y divide-slate-100 rounded-xl border border-slate-100">
                      {d.attachments.map((a) => (
                        <li key={a.id} className="flex items-center justify-between gap-2 px-3 py-2">
                          <span className="break-all"><Paperclip className="inline w-3 h-3 mr-1" />{a.name}
                            <span className="text-xs text-slate-400"> ({formatBytes(a.size)})</span>
                            {!a.available && <span className="ml-1 text-xs text-red-600">{t("fichier introuvable")}</span>}
                          </span>
                          <span className="flex gap-2 shrink-0">
                            {a.previewable && a.available && (
                              <button type="button" className="text-xs text-primary hover:underline flex items-center gap-1"
                                      onClick={() => fetchFile(a, true)} aria-label={`${t("Aperçu")} ${a.name}`}>
                                <Eye className="w-3 h-3" />{t("Aperçu")}</button>
                            )}
                            {a.available && (
                              <button type="button" className="text-xs text-primary hover:underline flex items-center gap-1"
                                      onClick={() => fetchFile(a, false)} aria-label={`${t("Télécharger")} ${a.name}`}>
                                <Download className="w-3 h-3" />{t("Télécharger")}</button>
                            )}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                  {preview && (
                    <div className="mt-3 space-y-1">
                      <p className="text-xs text-slate-500">{preview.name}</p>
                      {preview.type === "application/pdf"
                        ? <iframe title={preview.name} src={preview.url} className="w-full h-96 rounded-lg border" />
                        : <img src={preview.url} alt={preview.name} className="max-h-96 rounded-lg border" />}
                    </div>
                  )}
                </section>
              </>
            )}

            {d.attempt_log?.length > 0 && (
              <section>
                <h3 className="font-semibold text-slate-700 mb-1">{t("Historique des tentatives")}</h3>
                <ul className="space-y-1 text-xs">
                  {d.attempt_log.map((a, i) => (
                    <li key={i} className="flex flex-wrap gap-2">
                      <span className="whitespace-nowrap">{formatDateTime(a.at)}</span>
                      <Badge tone={STATUS_TONE[a.outcome]}>{a.outcome}</Badge>
                      {a.manual && <span className="text-slate-500">{t("relance manuelle")}</span>}
                      {a.error && <span className="text-red-600 break-all">{a.error}</span>}
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/** Configuration effective (secrets masqués) et envoi de test. */
function SmtpPanel() {
  const [open, setOpen] = useState(false);
  const [to, setTo] = useState("");
  const sending = useRef(false);
  const configQ = useQuery({ queryKey: ["email-config", open], queryFn: () => outboxAPI.config(open), staleTime: 30000 });
  const c = configQ.data?.data;
  const testMut = useMutation({
    mutationFn: () => outboxAPI.testSend(to),
    onSuccess: (res) => toast(t(res.data.delivery_summary), { icon: res.data.status === "sent" ? "✉️" : "⚠️" }),
    onError: (e) => toast.error(extractApiError(e)),
    onSettled: () => { sending.current = false; },
  });
  if (!c) return null;
  const tone = c.real_provider ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-amber-200 bg-amber-50 text-amber-800";
  return (
    <section className={`card border ${tone} text-sm space-y-2`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-2 font-semibold">
          {c.real_provider ? <Mail className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
          {t("Transport e-mail")} : {t(c.transport_display)}
        </p>
        <button type="button" className="text-xs underline" onClick={() => setOpen((o) => !o)}>
          {open ? t("Masquer le diagnostic") : t("Diagnostic et test d'envoi")}
        </button>
      </div>
      <p>{t(c.explanation)}</p>
      {c.capture_ui_url && (
        <a href={c.capture_ui_url} target="_blank" rel="noreferrer" className="font-semibold underline">{t("Ouvrir Mailpit")} ({c.capture_ui_url})</a>
      )}
      {open && (
        <div className="space-y-2 pt-2 border-t border-current/10">
          <dl className="grid grid-cols-[10rem_1fr] gap-x-3 text-xs">
            <dt>{t("Serveur")}</dt><dd>{c.host || "—"}:{c.port}</dd>
            <dt>TLS / SSL</dt><dd>{String(c.use_tls)} / {String(c.use_ssl)}</dd>
            <dt>{t("Utilisateur")}</dt><dd>{c.user || "—"}</dd>
            <dt>{t("Mot de passe")}</dt><dd>{c.password_set ? t("défini (masqué)") : t("vide")}</dd>
            <dt>{t("Expéditeur")}</dt><dd>{c.default_from}</dd>
            {c.reachability && (<><dt>{t("Réseau")}</dt><dd>{c.reachability.detail}</dd></>)}
          </dl>
          <form className="flex flex-wrap gap-2" onSubmit={(e) => {
            e.preventDefault();
            if (sending.current) return;
            sending.current = true;
            testMut.mutate();
          }}>
            <input type="email" required className="input w-auto flex-1" placeholder={t("Adresse de test")} value={to}
                   onChange={(e) => setTo(e.target.value)} aria-label={t("Adresse de test")} />
            <button type="submit" className="btn-secondary flex items-center gap-2" disabled={testMut.isPending}>
              <Send className="w-4 h-4" />{t("Envoyer un message de test")}
            </button>
          </form>
        </div>
      )}
    </section>
  );
}
