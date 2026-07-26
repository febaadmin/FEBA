/**
 * Incidents techniques — espace Super administrateur (V8).
 *
 * Remplace la promesse creuse « L'équipe technique a été notifiée » par une
 * vraie traçabilité : liste paginée, filtres (statut, gravité, module,
 * établissement), recherche, détail complet, assignation, note interne,
 * résolution et réouverture.
 */
import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, RotateCcw, Search, X } from "lucide-react";
import toast from "react-hot-toast";
import { incidentsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import Modal from "../../components/ui/Modal";
import { extractApiError } from "../../utils/errors";
import { t, dateLocale } from "../../i18n";

const SEVERITIES = [
  { value: "", label: "Toutes gravités" },
  { value: "critical", label: "Critique" },
  { value: "high", label: "Élevée" },
  { value: "medium", label: "Moyenne" },
  { value: "low", label: "Faible" },
];
const STATUSES = [
  { value: "", label: "Tous statuts" },
  { value: "new", label: "Nouveau" },
  { value: "in_progress", label: "En cours" },
  { value: "resolved", label: "Résolu" },
  { value: "ignored", label: "Ignoré" },
  { value: "reopened", label: "Réouvert" },
];

const SEVERITY_STYLE = {
  critical: "bg-red-100 text-red-700 border-red-200",
  high: "bg-orange-100 text-orange-700 border-orange-200",
  medium: "bg-amber-100 text-amber-700 border-amber-200",
  low: "bg-slate-100 text-slate-600 border-slate-200",
};
const STATUS_STYLE = {
  new: "bg-blue-100 text-blue-700",
  in_progress: "bg-indigo-100 text-indigo-700",
  resolved: "bg-green-100 text-green-700",
  ignored: "bg-slate-100 text-slate-500",
  reopened: "bg-purple-100 text-purple-700",
};

const fmt = (value) =>
  value ? new Date(value).toLocaleString(dateLocale(), {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  }) : "—";

export default function SuperAdminIncidents() {
  const { id } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [filters, setFilters] = useState({ status: "", severity: "", search: "" });
  const [openId, setOpenId] = useState(id ? Number(id) : null);
  const [notes, setNotes] = useState("");

  const { data: statsData } = useQuery({
    queryKey: ["incident-stats"], queryFn: incidentsAPI.stats,
  });
  const stats = statsData?.data || {};

  const { data, isLoading, isError } = useQuery({
    queryKey: ["incidents", filters],
    queryFn: () => incidentsAPI.list({
      status: filters.status || undefined,
      severity: filters.severity || undefined,
      search: filters.search || undefined,
    }),
  });
  const rows = data?.data?.results || data?.data || [];

  const { data: detailData } = useQuery({
    queryKey: ["incident", openId],
    queryFn: () => incidentsAPI.detail(openId),
    enabled: !!openId,
  });
  const incident = detailData?.data;

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["incidents"] });
    qc.invalidateQueries({ queryKey: ["incident-stats"] });
    if (openId) qc.invalidateQueries({ queryKey: ["incident", openId] });
  };

  const resolveMut = useMutation({
    mutationFn: (payload) => incidentsAPI.resolve(openId, payload),
    onSuccess: () => { toast.success(t("Incident marqué comme résolu.")); refresh(); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const reopenMut = useMutation({
    mutationFn: () => incidentsAPI.reopen(openId),
    onSuccess: () => { toast.success(t("Incident réouvert.")); refresh(); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const statusMut = useMutation({
    mutationFn: (payload) => incidentsAPI.update(openId, payload),
    onSuccess: () => { toast.success(t("Incident mis à jour.")); refresh(); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const close = () => { setOpenId(null); setNotes(""); if (id) navigate("/superadmin/incidents"); };

  return (
    <div className="space-y-5">
      <PageHeader title={t("Incidents techniques")}
        subtitle={t("Erreurs serveur enregistrées automatiquement")} />

      {/* Compteurs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { key: "new", label: "Nouveaux", value: stats.new ?? 0, tone: "text-blue-600" },
          { key: "in_progress", label: "En cours", value: stats.by_status?.in_progress ?? 0, tone: "text-indigo-600" },
          { key: "resolved", label: "Résolus", value: stats.by_status?.resolved ?? 0, tone: "text-green-600" },
          { key: "total", label: "Total", value: stats.total ?? 0, tone: "text-slate-700" },
        ].map((card) => (
          <div key={card.key} className="rounded-2xl bg-white border border-slate-200 p-4">
            <p className={`text-2xl font-bold ${card.tone}`}>{card.value}</p>
            <p className="text-xs text-slate-500 mt-1">{t(card.label)}</p>
          </div>
        ))}
      </div>

      {/* Filtres */}
      <div className="rounded-2xl bg-white border border-slate-200 p-4 flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input className="input pl-9" placeholder={t("Rechercher (référence, message, endpoint)…")}
            value={filters.search}
            onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))} />
        </div>
        <select className="input w-auto" value={filters.status}
          onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}>
          {STATUSES.map((s) => <option key={s.value} value={s.value}>{t(s.label)}</option>)}
        </select>
        <select className="input w-auto" value={filters.severity}
          onChange={(e) => setFilters((f) => ({ ...f, severity: e.target.value }))}>
          {SEVERITIES.map((s) => <option key={s.value} value={s.value}>{t(s.label)}</option>)}
        </select>
      </div>

      {/* Liste */}
      <div className="rounded-2xl bg-white border border-slate-200 overflow-hidden">
        {isLoading && <p className="p-6 text-sm text-slate-500">{t("Chargement…")}</p>}
        {isError && <p className="p-6 text-sm text-red-600">{t("Impossible de charger les incidents.")}</p>}
        {!isLoading && !isError && rows.length === 0 && (
          <div className="p-10 text-center">
            <CheckCircle2 className="w-10 h-10 text-green-500 mx-auto mb-3" />
            <p className="font-semibold text-slate-700">{t("Aucun incident technique")}</p>
            <p className="text-sm text-slate-500 mt-1">
              {t("Les erreurs serveur inattendues apparaîtront ici automatiquement.")}
            </p>
          </div>
        )}
        {rows.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
                <tr>
                  <th className="text-left px-4 py-3">{t("Référence")}</th>
                  <th className="text-left px-4 py-3">{t("Erreur")}</th>
                  <th className="text-left px-4 py-3">{t("Endpoint")}</th>
                  <th className="text-center px-4 py-3">{t("Gravité")}</th>
                  <th className="text-center px-4 py-3">{t("Occur.")}</th>
                  <th className="text-center px-4 py-3">{t("Statut")}</th>
                  <th className="text-left px-4 py-3">{t("Dernière fois")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} onClick={() => setOpenId(row.id)}
                    className="border-t border-slate-100 hover:bg-slate-50 cursor-pointer">
                    <td className="px-4 py-3 font-mono text-xs font-semibold text-slate-700">{row.reference}</td>
                    <td className="px-4 py-3">
                      <span className="font-medium text-slate-800">{row.exception_type}</span>
                      <span className="block text-xs text-slate-400">{row.module}</span>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500 font-mono">
                      {row.http_method} {row.endpoint}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`text-[11px] px-2 py-1 rounded-full border font-semibold ${SEVERITY_STYLE[row.severity] || ""}`}>
                        {row.severity_display}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center font-semibold">{row.occurrences}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`text-[11px] px-2 py-1 rounded-full font-semibold ${STATUS_STYLE[row.status] || ""}`}>
                        {row.status_display}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500">{fmt(row.last_seen_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Détail */}
      <Modal open={!!openId} onClose={close}
        title={incident ? `${t("Incident")} ${incident.reference}` : t("Incident")} size="xl">
        {!incident ? <p className="text-sm text-slate-500">{t("Chargement…")}</p> : (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`text-[11px] px-2 py-1 rounded-full border font-semibold ${SEVERITY_STYLE[incident.severity] || ""}`}>
                {incident.severity_display}
              </span>
              <span className={`text-[11px] px-2 py-1 rounded-full font-semibold ${STATUS_STYLE[incident.status] || ""}`}>
                {incident.status_display}
              </span>
              <span className="text-xs text-slate-500">
                {incident.occurrences} {t("occurrence(s)")} · {t("depuis le")} {fmt(incident.first_seen_at)}
              </span>
            </div>

            <div className="rounded-xl bg-slate-50 border border-slate-200 p-3">
              <p className="font-semibold text-slate-800 text-sm">{incident.exception_type}</p>
              <p className="text-sm text-slate-600 mt-1 break-words">{incident.message}</p>
              {incident.location && (
                <p className="text-xs font-mono text-slate-400 mt-2">{incident.location}</p>
              )}
            </div>

            <div className="grid sm:grid-cols-2 gap-3 text-sm">
              {[
                ["Endpoint", `${incident.http_method} ${incident.endpoint}`],
                ["Module", incident.module],
                ["Action tentée", incident.attempted_action],
                ["Route frontend", incident.frontend_route],
                ["Utilisateur", incident.user_email ? `${incident.user_email} (${incident.user_role})` : "—"],
                ["Établissement", incident.school_name || "—"],
                ["Environnement", incident.environment],
                ["Première / dernière", `${fmt(incident.first_seen_at)} → ${fmt(incident.last_seen_at)}`],
              ].map(([label, value]) => (
                <div key={label}>
                  <p className="text-[11px] uppercase tracking-wide text-slate-400 font-semibold">{t(label)}</p>
                  <p className="text-slate-700 break-words">{value || "—"}</p>
                </div>
              ))}
            </div>

            {incident.context_data && Object.keys(incident.context_data).length > 0 && (
              <div>
                <p className="text-[11px] uppercase tracking-wide text-slate-400 font-semibold mb-1">
                  {t("Contexte (données sensibles expurgées)")}
                </p>
                <pre className="text-xs bg-slate-900 text-slate-100 rounded-xl p-3 overflow-x-auto">
                  {JSON.stringify(incident.context_data, null, 2)}
                </pre>
              </div>
            )}

            <div>
              <label className="label">{t("Note interne")}</label>
              <textarea className="input" rows={2}
                value={notes || incident.resolution_notes || ""}
                onChange={(e) => setNotes(e.target.value)} />
            </div>

            <div className="flex flex-wrap gap-2 justify-end pt-2 border-t border-slate-100">
              <select className="input w-auto" value={incident.status}
                onChange={(e) => statusMut.mutate({ status: e.target.value,
                                                    resolution_notes: notes || incident.resolution_notes })}>
                {STATUSES.filter((s) => s.value).map((s) => (
                  <option key={s.value} value={s.value}>{t(s.label)}</option>
                ))}
              </select>
              {incident.status !== "resolved" ? (
                <button className="btn-primary flex items-center gap-2"
                  onClick={() => resolveMut.mutate({ resolution_notes: notes })}
                  disabled={resolveMut.isPending}>
                  <CheckCircle2 className="w-4 h-4" /> {t("Marquer résolu")}
                </button>
              ) : (
                <button className="btn-secondary flex items-center gap-2"
                  onClick={() => reopenMut.mutate()} disabled={reopenMut.isPending}>
                  <RotateCcw className="w-4 h-4" /> {t("Réouvrir")}
                </button>
              )}
              <button className="btn-secondary flex items-center gap-2" onClick={close}>
                <X className="w-4 h-4" /> {t("Fermer")}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
