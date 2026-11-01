/**
 * Relances de paiement (P1 — octobre 2026).
 *
 * Quatre onglets :
 *   État        — le service fonctionne-t-il, et sinon pourquoi ; règles de
 *                 relance de l'académie ; suspension / reprise.
 *   Retards     — SIMULATION : échéances échues, montants calculés par le
 *                 serveur, relances qui partiraient ; anomalies bloquantes.
 *   Échéanciers — tranches de chaque tarif, abonnements, exonérations et
 *                 réductions par élève.
 *   Historique  — relances produites et exécutions du moteur.
 *
 * Aucun montant n'est calculé ici : tout vient du moteur serveur
 * (backend/apps/payments/reminders.py). L'écran affiche, il ne déduit pas.
 */
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import {
  AlertTriangle, BellRing, CalendarClock, CheckCircle2, History, Pause, Play, Plus, Trash2,
} from "lucide-react";

import { feeSchedulesAPI, remindersAPI, schoolsAPI, studentsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import Modal from "../../components/ui/Modal";
import { t } from "../../i18n";
import { extractApiError } from "../../utils/errors";
import { formatCalendarDate, formatDateTime } from "../../utils/datetime";
import { useAcademyKey } from "../../hooks/useEntityContext";

const TABS = [
  ["status", "État et règles", BellRing],
  ["preview", "Retards", AlertTriangle],
  ["schedules", "Échéanciers", CalendarClock],
  ["history", "Historique", History],
];

const PAYMENT_TYPES = [
  ["inscription", "Inscription"], ["mensualite", "Mensualité"], ["cantine", "Cantine"],
  ["transport", "Transport"], ["garderie", "Garderie"], ["other", "Autre"],
];

const REMINDER_TONE = {
  sent: "bg-emerald-50 text-emerald-700", notified: "bg-blue-50 text-blue-700",
  retry: "bg-amber-50 text-amber-700", failed: "bg-red-50 text-red-700",
  no_channel: "bg-red-50 text-red-700", pending: "bg-slate-100 text-slate-600",
};
const DUE_TONE = {
  overdue: "bg-red-50 text-red-700", partial: "bg-amber-50 text-amber-700",
  paid: "bg-emerald-50 text-emerald-700", upcoming: "bg-slate-100 text-slate-600",
  exempted: "bg-blue-50 text-blue-700",
};

function Badge({ tone, children }) {
  return <span className={`inline-block rounded-md px-2 py-0.5 text-[11px] font-semibold ${tone || "bg-slate-100 text-slate-600"}`}>{children}</span>;
}

export default function PaymentReminders() {
  const [tab, setTab] = useState("status");
  return (
    <div className="space-y-6">
      <PageHeader title={t("Relances de paiement")}
                  subtitle={t("Échéanciers, retards et relances automatiques par e-mail et notification")} />
      <div className="flex flex-wrap gap-2">
        {TABS.map(([key, label, Icon]) => (
          <button key={key} type="button" onClick={() => setTab(key)} aria-pressed={tab === key}
                  className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold ${
                    tab === key ? "bg-indigo-600 text-white" : "bg-white text-slate-600 border border-slate-200"}`}>
            <Icon className="w-4 h-4" />{t(label)}
          </button>
        ))}
      </div>
      {tab === "status" && <StatusTab />}
      {tab === "preview" && <PreviewTab />}
      {tab === "schedules" && <SchedulesTab />}
      {tab === "history" && <HistoryTab />}
    </div>
  );
}

/* ── État et règles ──────────────────────────────────────────────────── */

function StatusTab() {
  const qc = useQueryClient();
  const academyKey = useAcademyKey();
  const statusQ = useQuery({ queryKey: ["reminders-status", academyKey], queryFn: remindersAPI.status, retry: false });
  const policyQ = useQuery({ queryKey: ["reminders-policy", academyKey], queryFn: remindersAPI.policy, retry: false });
  const [draft, setDraft] = useState(null);
  const policy = draft || policyQ.data?.data;
  const status = statusQ.data?.data;

  const saveMut = useMutation({
    mutationFn: (d) => remindersAPI.updatePolicy(d),
    onSuccess: () => {
      setDraft(null);
      qc.invalidateQueries({ queryKey: ["reminders-policy", academyKey] });
      qc.invalidateQueries({ queryKey: ["reminders-status", academyKey] });
      toast.success(t("Règles enregistrées."));
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  if (statusQ.isError) return <div className="card text-sm text-red-700">{extractApiError(statusQ.error)}</div>;
  if (!status || !policy) return <div className="card text-slate-400">{t("Chargement…")}</div>;

  const set = (key) => (e) => setDraft({ ...policy, [key]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="card space-y-3">
        <h2 className="font-bold text-slate-800">{t("État du service")}</h2>
        {status.operational ? (
          <p className="flex items-center gap-2 text-emerald-700 text-sm"><CheckCircle2 className="w-4 h-4" />{t("Relances automatiques opérationnelles.")}</p>
        ) : (
          <ul className="space-y-1 text-sm text-amber-800">
            {status.issues.map((issue) => (
              <li key={issue} className="flex gap-2"><AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />{issue}</li>
            ))}
          </ul>
        )}
        <dl className="grid grid-cols-2 gap-2 text-sm">
          <dt className="text-slate-500">{t("Interrupteur serveur")}</dt><dd>{status.global_enabled ? t("Activé") : t("Désactivé")}</dd>
          <dt className="text-slate-500">{t("Serveur SMTP")}</dt><dd>{status.smtp_configured ? t("Configuré") : t("Non configuré")}</dd>
          <dt className="text-slate-500">{t("Dernière planification")}</dt>
          <dd>{status.last_beat_run ? `${formatDateTime(status.last_beat_run.started_at)} — ${t(status.last_beat_run.status_display)}` : "—"}</dd>
          <dt className="text-slate-500">{t("Dernier envoi réel")}</dt>
          <dd>{status.last_run ? formatDateTime(status.last_run.started_at) : "—"}</dd>
        </dl>
      </section>

      <section className="card space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-bold text-slate-800">{t("Règles de relance")}</h2>
          <button type="button" disabled={saveMut.isPending}
                  onClick={() => saveMut.mutate({ enabled: !policy.enabled, paused_reason: policy.enabled ? (policy.paused_reason || t("Suspendu manuellement")) : "" })}
                  className={`btn-secondary flex items-center gap-2 text-sm ${policy.enabled ? "text-danger" : "text-success"}`}>
            {policy.enabled ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            {policy.enabled ? t("Suspendre les envois automatiques") : t("Activer les envois automatiques")}
          </button>
        </div>
        <form className="grid grid-cols-2 gap-3 text-sm" onSubmit={(e) => {
          e.preventDefault();
          const { min_amount_value: minAmount, updated_at: _u, ...rest } = policy;
          saveMut.mutate({ ...rest, min_amount: policy.min_amount ?? minAmount });
        }}>
          <label>{t("Délai de grâce (jours)")}<input className="input" type="number" min="0" value={policy.grace_days} onChange={set("grace_days")} /></label>
          <label>{t("Intervalle entre relances (jours)")}<input className="input" type="number" min="1" value={policy.interval_days} onChange={set("interval_days")} /></label>
          <label>{t("Relances maximum par échéance")}<input className="input" type="number" min="1" value={policy.max_reminders} onChange={set("max_reminders")} /></label>
          <label>{t("Solde minimum relancé")}<input className="input" value={policy.min_amount ?? policy.min_amount_value} onChange={set("min_amount")} /></label>
          <label className="flex items-center gap-2"><input type="checkbox" checked={policy.send_email} onChange={set("send_email")} />{t("E-mail")}</label>
          <label className="flex items-center gap-2"><input type="checkbox" checked={policy.send_notification} onChange={set("send_notification")} />{t("Notification interne")}</label>
          <label className="col-span-2">{t("Modalités de paiement rappelées")}
            <textarea className="input" rows={3} value={policy.payment_instructions} onChange={set("payment_instructions")} /></label>
          <label className="col-span-2">{t("Coordonnées de contact")}
            <textarea className="input" rows={2} value={policy.contact_text} onChange={set("contact_text")} /></label>
          <div className="col-span-2 flex justify-end">
            <button type="submit" className="btn-primary" disabled={!draft || saveMut.isPending}>{t("Enregistrer")}</button>
          </div>
        </form>
      </section>
    </div>
  );
}

/* ── Retards (simulation) ────────────────────────────────────────────── */

function PreviewTab() {
  const qc = useQueryClient();
  const academyKey = useAcademyKey();
  const [on, setOn] = useState("");
  const [showAll, setShowAll] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const previewQ = useQuery({
    queryKey: ["reminders-preview", academyKey, on, showAll],
    queryFn: () => remindersAPI.preview({ on: on || undefined, all: showAll ? 1 : undefined }),
    retry: false,
  });
  const data = previewQ.data?.data;
  const runningRef = useRef(false);   // verrou synchrone anti double-clic
  const runMut = useMutation({
    mutationFn: remindersAPI.run,
    onSettled: () => { runningRef.current = false; },
    onSuccess: () => {
      setConfirm(false);
      toast.success(t("Relances lancées : le résultat apparaîtra dans l'historique."));
      qc.invalidateQueries({ queryKey: ["reminders-history", academyKey] });
    },
    onError: (e) => { setConfirm(false); toast.error(extractApiError(e)); },
  });

  return (
    <div className="space-y-4">
      <div className="card flex flex-wrap items-end gap-3">
        <label className="text-sm">{t("Situation au")}
          <input type="date" className="input" value={on} onChange={(e) => setOn(e.target.value)} /></label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />{t("Afficher aussi les échéances réglées et à venir")}</label>
        <div className="flex-1" />
        <button type="button" className="btn-primary flex items-center gap-2"
                disabled={!data || data.planned_count === 0 || !data.global_enabled || runMut.isPending}
                title={data && !data.global_enabled ? t("Envoi réel désactivé sur ce serveur (PAYMENT_REMINDERS_ENABLED).") : ""}
                onClick={() => setConfirm(true)}>
          <BellRing className="w-4 h-4" />{t("Envoyer les relances dues ({n})", { n: data?.planned_count ?? 0 })}
        </button>
      </div>
      <p className="text-xs text-slate-500">{t("Simulation : cet écran ne crée aucune relance et n'envoie rien.")}</p>

      {data?.anomalies?.length > 0 && (
        <div className="card border border-red-200 bg-red-50 text-sm text-red-800 space-y-1">
          <p className="font-semibold">{t("Anomalies : aucune relance n'est envoyée pour les éléments concernés :")}</p>
          {data.anomalies.map((a, i) => <p key={i}>• {a.message}</p>)}
        </div>
      )}

      <div className="card overflow-x-auto">
        {previewQ.isLoading ? <p className="text-slate-400">{t("Chargement…")}</p> : previewQ.isError ? (
          <p className="text-sm text-red-700">{extractApiError(previewQ.error)}</p>
        ) : !data?.items?.length ? (
          <p className="text-sm text-slate-400">{t("Aucune échéance en retard.")}</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500 border-b border-slate-100">
                {["Élève", "Frais", "Échéance", "Date limite", "Prévu", "Payé", "Reste dû", "Statut", "Retard", "Relance prévue"].map((h) => (
                  <th key={h} className="py-2 pr-3 font-semibold">{t(h)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.items.map((r) => (
                <tr key={`${r.student_id}-${r.installment_id}`} className="border-b border-slate-50 align-top">
                  <td className="py-2 pr-3 font-medium">{r.student_name}</td>
                  <td className="py-2 pr-3">{r.fee_label}</td>
                  <td className="py-2 pr-3">{r.installment_label}</td>
                  <td className="py-2 pr-3 whitespace-nowrap">{formatCalendarDate(r.due_date)}</td>
                  <td className="py-2 pr-3 whitespace-nowrap">{r.expected_display}</td>
                  <td className="py-2 pr-3 whitespace-nowrap">{r.paid_display}</td>
                  <td className="py-2 pr-3 whitespace-nowrap font-semibold">{r.outstanding_display}</td>
                  <td className="py-2 pr-3"><Badge tone={DUE_TONE[r.status]}>{t(r.status_label)}</Badge>
                    {r.blockers.map((b) => <div key={b} className="text-xs text-red-600 mt-1">{b}</div>)}</td>
                  <td className="py-2 pr-3 whitespace-nowrap">{r.days_overdue ? t("{n} j", { n: r.days_overdue }) : "—"}</td>
                  <td className="py-2 pr-3 text-xs">
                    {r.planned_reminders.length === 0 ? "—" : r.planned_reminders.map((p) => (
                      <div key={p.email}>{t("Relance n°{n}", { n: p.level })} → {p.recipient}</div>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Modal open={confirm} onClose={() => !runMut.isPending && setConfirm(false)} title={t("Confirmer l'envoi des relances")} size="sm">
        <p className="text-sm text-slate-600">
          {t("{n} relance(s) vont être envoyées maintenant (e-mail et notification interne). Les relances déjà envoyées ne seront pas renvoyées.", { n: data?.planned_count ?? 0 })}
        </p>
        <div className="flex gap-3 justify-end mt-6">
          <button type="button" className="btn-secondary" disabled={runMut.isPending} onClick={() => setConfirm(false)}>{t("Annuler")}</button>
          <button type="button" className="btn-primary" disabled={runMut.isPending}
                  onClick={() => { if (!runningRef.current) { runningRef.current = true; runMut.mutate(); } }}>
            {runMut.isPending ? t("Envoi…") : t("Confirmer")}
          </button>
        </div>
      </Modal>
    </div>
  );
}

/* ── Échéanciers ─────────────────────────────────────────────────────── */

const emptyFee = () => ({
  payment_type: "mensualite", label: "", school_year: "", level: "", amount: "",
  is_mandatory: true, installment_mode: "split", is_active: true,
  installments: [{ label: "", due_date: "", amount: "" }],
});

function SchedulesTab() {
  const qc = useQueryClient();
  const academyKey = useAcademyKey();
  const feesQ = useQuery({ queryKey: ["fee-schedules", academyKey], queryFn: feeSchedulesAPI.list, retry: false });
  const yearsQ = useQuery({ queryKey: ["years"], queryFn: schoolsAPI.years });
  const levelsQ = useQuery({ queryKey: ["levels"], queryFn: schoolsAPI.levels });
  const fees = feesQ.data?.data || [];
  const years = yearsQ.data?.data?.results || yearsQ.data?.data || [];
  const levels = levelsQ.data?.data?.results || levelsQ.data?.data || [];
  const [editing, setEditing] = useState(null);
  const [arrangementsFor, setArrangementsFor] = useState(null);

  const saveMut = useMutation({
    mutationFn: (fee) => {
      const body = { ...fee, school_year: fee.school_year || null, level: fee.level || null };
      return fee.id ? feeSchedulesAPI.update(fee.id, body) : feeSchedulesAPI.create(body);
    },
    onSuccess: () => { setEditing(null); qc.invalidateQueries({ queryKey: ["fee-schedules", academyKey] }); toast.success(t("Échéancier enregistré.")); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const deleteMut = useMutation({
    mutationFn: feeSchedulesAPI.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fee-schedules", academyKey] }),
    onError: (e) => toast.error(extractApiError(e)),
  });

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button type="button" className="btn-primary flex items-center gap-2" onClick={() => setEditing(emptyFee())}>
          <Plus className="w-4 h-4" />{t("Nouvel échéancier")}
        </button>
      </div>
      {feesQ.isError && <div className="card text-sm text-red-700">{extractApiError(feesQ.error)}</div>}
      {fees.length === 0 && !feesQ.isLoading && <div className="card text-sm text-slate-400">{t("Aucun tarif configuré.")}</div>}
      {fees.map((fee) => (
        <section key={fee.id} className="card space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-bold text-slate-800">{fee.label || t(fee.payment_type_label)}</h3>
            <Badge>{t(fee.payment_type_label)}</Badge>
            {fee.level_name && <Badge>{fee.level_name}</Badge>}
            {fee.school_year_name && <Badge>{fee.school_year_name}</Badge>}
            <Badge tone={fee.is_mandatory ? "bg-indigo-50 text-indigo-700" : "bg-slate-100 text-slate-600"}>
              {fee.is_mandatory ? t("Obligatoire") : t("Abonnés uniquement")}
            </Badge>
            {!fee.is_consistent && <Badge tone="bg-red-50 text-red-700">{t("Somme des tranches ≠ total")}</Badge>}
            <div className="flex-1" />
            <button type="button" className="text-xs text-primary hover:underline" onClick={() => setArrangementsFor(fee)}>{t("Élèves (abonnements, exonérations…)")}</button>
            <button type="button" className="text-xs text-primary hover:underline" onClick={() => setEditing({
              ...fee, amount: fee.amount_value, school_year: fee.school_year || "", level: fee.level || "",
              installments: fee.installments.map((i) => ({ id: i.id, label: i.label, due_date: i.due_date, amount: i.amount_value })),
            })}>{t("Modifier")}</button>
            <button type="button" aria-label={t("Supprimer")} className="text-slate-400 hover:text-danger"
                    onClick={() => window.confirm(t("Supprimer ce tarif et ses échéances ?")) && deleteMut.mutate(fee.id)}>
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
          <p className="text-sm text-slate-600">{t("Total")} : <strong>{fee.amount_display}</strong> : {t("échéances")} : {fee.installments_total_display}</p>
          <ul className="text-sm text-slate-700 grid sm:grid-cols-3 gap-1">
            {fee.installments.map((i) => <li key={i.id}>{i.label} : {formatCalendarDate(i.due_date)} : {i.amount_display}</li>)}
          </ul>
        </section>
      ))}

      {editing && (
        <FeeEditor fee={editing} years={years} levels={levels} saving={saveMut.isPending}
                   onCancel={() => setEditing(null)} onSave={(f) => saveMut.mutate(f)} />
      )}
      {arrangementsFor && <ArrangementsModal fee={arrangementsFor} onClose={() => setArrangementsFor(null)} />}
    </div>
  );
}

function FeeEditor({ fee, years, levels, saving, onCancel, onSave }) {
  const [f, setF] = useState(fee);
  const set = (key) => (e) => setF({ ...f, [key]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const setInst = (index, key, value) => setF({ ...f, installments: f.installments.map((row, i) => (i === index ? { ...row, [key]: value } : row)) });
  return (
    <Modal open onClose={onCancel} title={f.id ? t("Modifier l'échéancier") : t("Nouvel échéancier")} size="lg">
      <form className="space-y-3 text-sm" onSubmit={(e) => { e.preventDefault(); onSave(f); }}>
        <div className="grid grid-cols-2 gap-3">
          <label>{t("Type de frais")}<select className="input" value={f.payment_type} onChange={set("payment_type")}>
            {PAYMENT_TYPES.map(([v, l]) => <option key={v} value={v}>{t(l)}</option>)}</select></label>
          <label>{t("Libellé")}<input className="input" value={f.label} onChange={set("label")} /></label>
          <label>{t("Année scolaire")}<select className="input" value={f.school_year} onChange={set("school_year")}>
            <option value="">{t("Toutes les années")}</option>{years.map((y) => <option key={y.id} value={y.id}>{y.name}</option>)}</select></label>
          <label>{t("Niveau")}<select className="input" value={f.level} onChange={set("level")}>
            <option value="">{t("Tous les niveaux")}</option>{levels.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}</select></label>
          <label>{t("Montant total")}<input className="input" required value={f.amount} onChange={set("amount")} /></label>
          <label>{t("Mode")}<select className="input" value={f.installment_mode} onChange={set("installment_mode")}>
            <option value="split">{t("Tranches (somme = total)")}</option>
            <option value="recurring">{t("Récurrent (ex. mensuel)")}</option></select></label>
          <label className="flex items-center gap-2 col-span-2"><input type="checkbox" checked={f.is_mandatory} onChange={set("is_mandatory")} />
            {t("Dû par tous les élèves du périmètre (sinon : élèves abonnés uniquement)")}</label>
        </div>
        <div className="space-y-2">
          <p className="font-semibold">{t("Échéances")}</p>
          {f.installments.map((row, i) => (
            <div key={i} className="grid grid-cols-[1fr_auto_auto_auto] gap-2 items-center">
              <input className="input" placeholder={t("Libellé")} required value={row.label} onChange={(e) => setInst(i, "label", e.target.value)} />
              <input className="input" type="date" required value={row.due_date} onChange={(e) => setInst(i, "due_date", e.target.value)} />
              <input className="input w-32" placeholder={t("Montant")} required value={row.amount} onChange={(e) => setInst(i, "amount", e.target.value)} />
              <button type="button" aria-label={t("Supprimer")} className="text-slate-400 hover:text-danger"
                      onClick={() => setF({ ...f, installments: f.installments.filter((_, j) => j !== i) })}><Trash2 className="w-4 h-4" /></button>
            </div>
          ))}
          <button type="button" className="btn-secondary text-xs" onClick={() => setF({ ...f, installments: [...f.installments, { label: "", due_date: "", amount: "" }] })}>
            <Plus className="w-3 h-3 inline" /> {t("Ajouter une échéance")}
          </button>
        </div>
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={onCancel}>{t("Annuler")}</button>
          <button type="submit" className="btn-primary" disabled={saving}>{saving ? t("Enregistrement…") : t("Enregistrer")}</button>
        </div>
      </form>
    </Modal>
  );
}

function ArrangementsModal({ fee, onClose }) {
  const qc = useQueryClient();
  const academyKey = useAcademyKey();
  const listQ = useQuery({ queryKey: ["fee-arrangements", academyKey, fee.id], queryFn: () => feeSchedulesAPI.arrangements(fee.id) });
  const studentsQ = useQuery({ queryKey: ["students-all"], queryFn: () => studentsAPI.list() });
  const rows = listQ.data?.data || [];
  const students = studentsQ.data?.data?.results || studentsQ.data?.data || [];
  const [form, setForm] = useState({ student: "", kind: fee.is_mandatory ? "exemption" : "subscription", discount: "", start_date: "", end_date: "", reason: "" });
  const refresh = () => qc.invalidateQueries({ queryKey: ["fee-arrangements", academyKey, fee.id] });
  const addMut = useMutation({
    mutationFn: () => feeSchedulesAPI.createArrangement({ ...form, fee_schedule: fee.id, start_date: form.start_date || null, end_date: form.end_date || null }),
    onSuccess: () => { refresh(); toast.success(t("Enregistré.")); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const delMut = useMutation({ mutationFn: feeSchedulesAPI.deleteArrangement, onSuccess: refresh, onError: (e) => toast.error(extractApiError(e)) });
  return (
    <Modal open onClose={onClose} title={`${t("Élèves")} — ${fee.label || t(fee.payment_type_label)}`} size="lg">
      <div className="space-y-4 text-sm">
        <form className="grid grid-cols-2 gap-2" onSubmit={(e) => { e.preventDefault(); addMut.mutate(); }}>
          <select className="input col-span-2" required value={form.student} onChange={(e) => setForm({ ...form, student: e.target.value })}>
            <option value="">{t("Choisir un élève")}</option>
            {students.map((s) => <option key={s.id} value={s.id}>{s.full_name} : {s.class_name || "?"}</option>)}
          </select>
          <select className="input" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
            <option value="subscription">{t("Abonnement au service")}</option>
            <option value="exemption">{t("Exonération totale")}</option>
            <option value="discount">{t("Réduction / bourse (montant fixe)")}</option>
          </select>
          {form.kind === "discount" && <input className="input" placeholder={t("Montant de la réduction")} value={form.discount} onChange={(e) => setForm({ ...form, discount: e.target.value })} />}
          {form.kind === "subscription" && (<>
            <label>{t("Début")}<input type="date" className="input" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} /></label>
            <label>{t("Fin")}<input type="date" className="input" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} /></label>
          </>)}
          <input className="input col-span-2" placeholder={t("Motif")} value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} />
          <button type="submit" className="btn-primary col-span-2" disabled={addMut.isPending}>{t("Ajouter")}</button>
        </form>
        <ul className="divide-y divide-slate-100">
          {rows.length === 0 && <li className="py-2 text-slate-400">{t("Aucune disposition pour ce tarif.")}</li>}
          {rows.map((r) => (
            <li key={r.id} className="py-2 flex items-center justify-between gap-2">
              <span><strong>{r.student_name}</strong> : {t(r.kind_label)} {r.discount_display && `(${r.discount_display})`} {r.reason && <span className="text-slate-400">· {r.reason}</span>}</span>
              <button type="button" aria-label={t("Supprimer")} className="text-slate-400 hover:text-danger" onClick={() => delMut.mutate(r.id)}><Trash2 className="w-4 h-4" /></button>
            </li>
          ))}
        </ul>
      </div>
    </Modal>
  );
}

/* ── Historique ──────────────────────────────────────────────────────── */

function HistoryTab() {
  const academyKey = useAcademyKey();
  const historyQ = useQuery({ queryKey: ["reminders-history", academyKey], queryFn: () => remindersAPI.history(), retry: false });
  const runsQ = useQuery({ queryKey: ["reminders-runs", academyKey], queryFn: remindersAPI.runs, retry: false });
  const rows = historyQ.data?.data?.results || [];
  const runs = runsQ.data?.data?.results || [];
  return (
    <div className="space-y-6">
      <section className="card overflow-x-auto">
        <h2 className="font-bold text-slate-800 mb-3">{t("Relances envoyées")}</h2>
        {rows.length === 0 ? <p className="text-sm text-slate-400">{t("Aucune relance.")}</p> : (
          <table className="w-full text-sm">
            <thead><tr className="text-left text-slate-500 border-b border-slate-100">
              {["Date et heure", "Élève", "Destinataire", "Frais", "Échéance", "Reste dû", "N°", "Statut"].map((h) => <th key={h} className="py-2 pr-3">{t(h)}</th>)}
            </tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-slate-50 align-top">
                  <td className="py-2 pr-3 whitespace-nowrap">{formatDateTime(r.created_at)}</td>
                  <td className="py-2 pr-3">{r.student}</td>
                  <td className="py-2 pr-3">{r.recipient}<div className="text-xs text-slate-400">{r.email_to}</div></td>
                  <td className="py-2 pr-3">{r.fee_label} : {r.installment_label}</td>
                  <td className="py-2 pr-3 whitespace-nowrap">{formatCalendarDate(r.due_date)}</td>
                  <td className="py-2 pr-3 whitespace-nowrap">{r.amount_due_display}</td>
                  <td className="py-2 pr-3">{r.level}</td>
                  <td className="py-2 pr-3"><Badge tone={REMINDER_TONE[r.status]}>{t(r.status_display)}</Badge>
                    {r.error && <div className="text-xs text-red-600 mt-1 break-all">{r.error}</div>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <section className="card overflow-x-auto">
        <h2 className="font-bold text-slate-800 mb-3">{t("Exécutions du moteur")}</h2>
        <table className="w-full text-sm">
          <tbody>
            {runs.map((r) => (
              <tr key={r.id} className="border-b border-slate-50">
                <td className="py-2 pr-3 whitespace-nowrap">{formatDateTime(r.started_at)}</td>
                <td className="py-2 pr-3">{t(r.trigger_display)}</td>
                <td className="py-2 pr-3">{t(r.status_display)}</td>
                <td className="py-2 pr-3 text-xs text-slate-500">
                  {r.error || Object.entries(r.stats || {}).map(([k, v]) => `${k}: ${v}`).join(" · ")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
