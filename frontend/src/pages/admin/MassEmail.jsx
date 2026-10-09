/**
 * Envoi d'e-mails par académie et par type de profil (P1 — octobre 2026).
 *
 * Parcours : académie → profils et/ou personnes → objet et message →
 * aperçu (nombre réel de destinataires, calculé PAR LE SERVEUR) →
 * confirmation → suivi de l'envoi → rapport par destinataire.
 *
 * Garde-fous côté écran (le serveur applique les siens, qui font foi) :
 *   - le bouton d'envoi n'existe qu'après un aperçu, et confirme le nombre
 *     exact affiché ; si la liste change entre-temps, le serveur refuse ;
 *   - un jeton par brouillon : un double clic ne crée pas deux envois ;
 *   - le bouton est désactivé pendant la requête.
 */
import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import {
  AlertTriangle, CheckCircle2, Eye, Loader2, Mail, RefreshCw, Send, Users,
} from "lucide-react";

import { massEmailAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import Modal from "../../components/ui/Modal";
import { useAcademy } from "../../context/AcademyContext";
import { t } from "../../i18n";
import { extractApiError } from "../../utils/errors";
import { formatDateTime } from "../../utils/datetime";
import {
  audiencePayload, emptyAudience, hasAnyRule, isSelected, newClientToken,
  setUsers, toggleRole, toggleUser,
} from "../../utils/massEmailSelection";

const ROLE_LABELS = {
  admin: "Administrateurs", teacher: "Enseignants", parent: "Parents", student: "Élèves",
};

const STATUS_TONE = {
  sent: "bg-emerald-50 text-emerald-700",
  pending: "bg-slate-100 text-slate-600",
  sending: "bg-blue-50 text-blue-700",
  retry: "bg-amber-50 text-amber-700",
  failed: "bg-red-50 text-red-700",
  done: "bg-emerald-50 text-emerald-700",
  partial: "bg-amber-50 text-amber-700",
  queued: "bg-slate-100 text-slate-600",
};

const SKIP_REASON = {
  skipped_no_email: "Aucune adresse",
  skipped_invalid_email: "Adresse invalide",
  skipped_inactive: "Compte inactif",
  skipped_duplicate: "Adresse en double",
};

function Badge({ tone, children }) {
  return (
    <span className={`inline-block rounded-md px-2 py-0.5 text-[11px] font-semibold ${tone || "bg-slate-100 text-slate-600"}`}>
      {children}
    </span>
  );
}

export default function MassEmail() {
  const qc = useQueryClient();
  const { activeAcademy } = useAcademy();
  const [academyId, setAcademyId] = useState(activeAcademy?.id || "");
  const [audience, setAudience] = useState(emptyAudience);
  const [roleFilter, setRoleFilter] = useState("");
  const [search, setSearch] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [previewState, setPreviewState] = useState(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [clientToken, setClientToken] = useState(newClientToken);
  const [openCampaign, setOpenCampaign] = useState(null);

  const optionsQuery = useQuery({
    queryKey: ["mass-email-options", academyId],
    queryFn: () => massEmailAPI.options(academyId),
    retry: false,
  });
  const options = optionsQuery.data?.data;
  const effectiveAcademyId = academyId || options?.academy?.id || "";

  const recipientsQuery = useQuery({
    queryKey: ["mass-email-recipients", effectiveAcademyId],
    queryFn: () => massEmailAPI.recipients(effectiveAcademyId),
    enabled: !!effectiveAcademyId,
  });
  const allUsers = useMemo(() => recipientsQuery.data?.data?.results || [], [recipientsQuery.data]);

  const campaignsQuery = useQuery({
    queryKey: ["mass-email-campaigns", effectiveAcademyId],
    queryFn: () => massEmailAPI.campaigns(effectiveAcademyId),
    enabled: !!effectiveAcademyId,
    refetchInterval: (query) => {
      const rows = query.state.data?.data?.results || [];
      return rows.some((c) => ["queued", "sending"].includes(c.status)) ? 4000 : false;
    },
  });
  const campaigns = campaignsQuery.data?.data?.results || [];

  // L'aperçu n'est valable que pour le brouillon qui l'a produit : toute
  // modification (sélection, académie, objet, message) l'invalide — on ne
  // confirme jamais un nombre calculé pour une autre sélection.
  const draftSignature = JSON.stringify([effectiveAcademyId, audience, subject, body]);
  const preview = previewState?.signature === draftSignature ? previewState.data : null;

  const changeAcademy = (id) => {
    setAcademyId(id);
    setAudience(emptyAudience());
    setClientToken(newClientToken());
  };

  const visibleUsers = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return allUsers.filter((u) => (
      (!roleFilter || u.role === roleFilter)
      && (!needle || `${u.full_name} ${u.email}`.toLowerCase().includes(needle))
    ));
  }, [allUsers, roleFilter, search]);

  const selectedCount = allUsers.filter((u) => isSelected(u, audience)).length;

  const previewMut = useMutation({
    // La signature est FIGÉE à la demande : si le brouillon change pendant
    // le calcul, la réponse ne sera pas attribuée au nouveau brouillon.
    mutationFn: () => massEmailAPI.preview({ academy_id: effectiveAcademyId, ...audiencePayload(audience) }),
    onSuccess: (res, signature) => setPreviewState({ signature, data: res.data }),
    onError: (e) => toast.error(extractApiError(e)),
  });

  // Verrou SYNCHRONE : `isPending` ne désactive le bouton qu'au rendu
  // suivant ; deux clics dans le même instant partaient tous les deux.
  const sendingRef = useRef(false);
  const sendOnce = () => {
    if (sendingRef.current) return;
    sendingRef.current = true;
    sendMut.mutate();
  };
  const sendMut = useMutation({
    mutationFn: () => massEmailAPI.create({
      academy_id: effectiveAcademyId, ...audiencePayload(audience),
      subject, body, confirm: true, expected_count: preview?.count, client_token: clientToken,
    }),
    onSuccess: (res) => {
      setConfirmOpen(false);
      toast.success(t("Envoi mis en file : {n} destinataire(s).", { n: res.data.total_recipients }));
      setSubject(""); setBody(""); setAudience(emptyAudience()); setPreviewState(null);
      setClientToken(newClientToken());
      setOpenCampaign(res.data.id);
      qc.invalidateQueries({ queryKey: ["mass-email-campaigns", effectiveAcademyId] });
    },
    onError: (e) => { setConfirmOpen(false); toast.error(extractApiError(e)); },
    onSettled: () => { sendingRef.current = false; },
  });

  if (optionsQuery.isError) {
    return (
      <div className="space-y-4">
        <PageHeader title={t("E-mails groupés")} subtitle={t("Envoi par académie et par type de profil")} />
        <div className="card text-sm text-red-700">{extractApiError(optionsQuery.error)}</div>
      </div>
    );
  }

  const canPreview = hasAnyRule(audience) && subject.trim() && body.trim();

  return (
    <div className="space-y-6">
      <PageHeader title={t("E-mails groupés")} subtitle={t("Envoi par académie et par type de profil")} />

      {options && !options.provider_configured && (
        <div className="card border border-amber-200 bg-amber-50 text-sm text-amber-800 flex gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          {t("Aucun serveur de messagerie réel n'est configuré : les messages seront journalisés mais ne partiront pas sur Internet.")}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-5">
        {/* ── 1. Académie et destinataires ─────────────────────────── */}
        <section className="card lg:col-span-3 space-y-4">
          <h2 className="font-bold text-slate-800 flex items-center gap-2"><Users className="w-4 h-4" />{t("Destinataires")}</h2>

          <div>
            <label className="label" htmlFor="mass-email-academy">{t("Académie")}</label>
            {options?.academies?.length > 1 ? (
              <select id="mass-email-academy" className="input" value={effectiveAcademyId}
                      onChange={(e) => changeAcademy(e.target.value)}>
                {options.academies.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
            ) : (
              <p className="text-sm font-semibold text-slate-700">{options?.academy?.name || "…"}</p>
            )}
          </div>

          <div>
            <p className="label">{t("Types de profil")}</p>
            <div className="flex flex-wrap gap-2">
              <label className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-1.5 text-sm">
                <input type="checkbox" checked={audience.allProfiles}
                       onChange={() => setAudience((a) => ({ ...a, allProfiles: !a.allProfiles }))} />
                <span className="font-semibold">{t("Tous les profils")}</span>
              </label>
              {(options?.roles || []).map((r) => (
                <label key={r.role} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-1.5 text-sm">
                  <input type="checkbox" disabled={audience.allProfiles}
                         checked={audience.allProfiles || audience.roles.includes(r.role)}
                         onChange={() => setAudience((a) => toggleRole(a, r.role))} />
                  {t(ROLE_LABELS[r.role] || r.label)} <span className="text-slate-400">({r.active_count})</span>
                </label>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap gap-2 items-center">
            <input className="input flex-1 min-w-[12rem]" placeholder={t("Rechercher une personne…")}
                   value={search} onChange={(e) => setSearch(e.target.value)} aria-label={t("Rechercher une personne…")} />
            <select className="input w-auto" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}
                    aria-label={t("Filtrer par profil")}>
              <option value="">{t("Tous les profils")}</option>
              {Object.entries(ROLE_LABELS).map(([k, v]) => <option key={k} value={k}>{t(v)}</option>)}
            </select>
            <button type="button" className="btn-secondary text-xs"
                    onClick={() => setAudience((a) => setUsers(a, visibleUsers, true))}>
              {t("Cocher la liste affichée")} ({visibleUsers.filter((u) => u.sendable).length})
            </button>
            <button type="button" className="btn-secondary text-xs"
                    onClick={() => setAudience((a) => setUsers(a, visibleUsers, false))}>
              {t("Décocher la liste affichée")}
            </button>
          </div>

          <div className="max-h-80 overflow-y-auto rounded-xl border border-slate-100">
            {recipientsQuery.isLoading ? (
              <p className="p-4 text-sm text-slate-400">{t("Chargement…")}</p>
            ) : visibleUsers.length === 0 ? (
              <p className="p-4 text-sm text-slate-400">{t("Aucun compte pour ce filtre.")}</p>
            ) : (
              <table className="w-full text-sm">
                <tbody>
                  {visibleUsers.map((u) => (
                    <tr key={u.id} className="border-b border-slate-50">
                      <td className="px-3 py-2 w-8">
                        <input type="checkbox" disabled={!u.sendable} checked={isSelected(u, audience)}
                               onChange={() => setAudience((a) => toggleUser(a, u))}
                               aria-label={`${t("Sélectionner")} ${u.full_name}`} />
                      </td>
                      <td className="px-3 py-2">
                        <div className="font-medium text-slate-800">{u.full_name}</div>
                        <div className="text-xs text-slate-400 break-all">{u.email || "—"}</div>
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-500">{t(ROLE_LABELS[u.role] || u.role)}</td>
                      <td className="px-3 py-2 text-right">
                        {!u.sendable && <Badge tone="bg-red-50 text-red-700">{t(SKIP_REASON[u.status] || "Non joignable")}</Badge>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <p className="text-sm text-slate-600">
            {t("{n} destinataire(s) sélectionné(s)", { n: selectedCount })}
          </p>
        </section>

        {/* ── 2. Message ───────────────────────────────────────────── */}
        <section className="card lg:col-span-2 space-y-4">
          <h2 className="font-bold text-slate-800 flex items-center gap-2"><Mail className="w-4 h-4" />{t("Message")}</h2>
          <div>
            <label className="label" htmlFor="mass-email-subject">{t("Objet")}</label>
            <input id="mass-email-subject" className="input" maxLength={200} value={subject}
                   onChange={(e) => setSubject(e.target.value)} />
          </div>
          <div>
            <label className="label" htmlFor="mass-email-body">{t("Contenu")}</label>
            <textarea id="mass-email-body" className="input" rows={10} value={body}
                      onChange={(e) => setBody(e.target.value)} />
            <p className="text-xs text-slate-400 mt-1">
              {t("Chaque destinataire reçoit un message individuel : aucune adresse n'est visible des autres.")}
            </p>
          </div>
          <button type="button" className="btn-secondary w-full flex items-center justify-center gap-2"
                  disabled={!canPreview || previewMut.isPending} onClick={() => previewMut.mutate(draftSignature)}>
            {previewMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
            {t("Prévisualiser")}
          </button>

          {preview && (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-3 text-sm">
              <p className="font-semibold text-slate-800">
                {t("{n} destinataire(s) recevront ce message.", { n: preview.count })}
                {preview.skipped_count > 0 && (
                  <span className="font-normal text-slate-500"> {t("{n} ignoré(s).", { n: preview.skipped_count })}</span>
                )}
              </p>
              {preview.skipped.length > 0 && (
                <ul className="text-xs text-slate-500 list-disc pl-4">
                  {preview.skipped.slice(0, 8).map((s) => (
                    <li key={s.user_id}>{s.full_name} — {t(SKIP_REASON[s.status] || s.status)}</li>
                  ))}
                </ul>
              )}
              <div className="rounded-lg bg-white border border-slate-200 p-3">
                <p className="text-xs text-slate-400">{t("Aperçu du message")}</p>
                <p className="font-semibold text-slate-800">{subject}</p>
                <p className="whitespace-pre-wrap text-slate-700 text-wrapsafe">{body}</p>
                <p className="mt-2 border-t pt-2 text-xs text-slate-400">{preview.academy?.name}</p>
              </div>
              <button type="button" className="btn-primary w-full flex items-center justify-center gap-2"
                      disabled={preview.count === 0 || sendMut.isPending} onClick={() => setConfirmOpen(true)}>
                <Send className="w-4 h-4" />{t("Envoyer à {n} destinataire(s)", { n: preview.count })}
              </button>
            </div>
          )}
        </section>
      </div>

      {/* ── 3. Historique et rapports ──────────────────────────────── */}
      <section className="card space-y-3">
        <h2 className="font-bold text-slate-800">{t("Envois récents")}</h2>
        {campaigns.length === 0 ? (
          <p className="text-sm text-slate-400">{t("Aucun envoi groupé pour cette académie.")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-500 border-b border-slate-100">
                  <th className="py-2 pr-3">{t("Date et heure")}</th>
                  <th className="py-2 pr-3">{t("Objet")}</th>
                  <th className="py-2 pr-3">{t("Statut")}</th>
                  <th className="py-2 pr-3">{t("Remis")}</th>
                  <th className="py-2 pr-3">{t("Échecs")}</th>
                  <th className="py-2 pr-3">{t("Ignorés")}</th>
                  <th className="py-2 pr-3" />
                </tr>
              </thead>
              <tbody>
                {campaigns.map((c) => (
                  <tr key={c.id} className="border-b border-slate-50">
                    <td className="py-2 pr-3 whitespace-nowrap">{formatDateTime(c.created_at)}</td>
                    <td className="py-2 pr-3">{c.subject}</td>
                    <td className="py-2 pr-3"><Badge tone={STATUS_TONE[c.status]}>{t(c.status_display)}</Badge></td>
                    <td className="py-2 pr-3">{c.counts.sent}</td>
                    <td className="py-2 pr-3">{c.counts.failed + c.counts.retry}</td>
                    <td className="py-2 pr-3">{c.skipped_count}</td>
                    <td className="py-2 pr-3 text-right">
                      <button type="button" className="text-primary hover:underline text-xs" onClick={() => setOpenCampaign(c.id)}>
                        {t("Rapport")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <Modal open={confirmOpen} onClose={() => !sendMut.isPending && setConfirmOpen(false)}
             title={t("Confirmer l'envoi")} size="sm">
        <p className="text-sm text-slate-600">
          {t("Vous allez envoyer « {subject} » à {n} destinataire(s) de {academy}. Cette action ne peut pas être annulée.",
             { subject, n: preview?.count ?? 0, academy: preview?.academy?.name || "" })}
        </p>
        <div className="flex gap-3 justify-end mt-6">
          <button type="button" className="btn-secondary" disabled={sendMut.isPending} onClick={() => setConfirmOpen(false)}>
            {t("Annuler")}
          </button>
          <button type="button" className="btn-primary flex items-center gap-2" disabled={sendMut.isPending}
                  onClick={sendOnce}>
            {sendMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            {sendMut.isPending ? t("Envoi…") : t("Confirmer l'envoi")}
          </button>
        </div>
      </Modal>

      {openCampaign && (
        <CampaignReport id={openCampaign} academyId={effectiveAcademyId} onClose={() => setOpenCampaign(null)} />
      )}
    </div>
  );
}

function CampaignReport({ id, academyId, onClose }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["mass-email-campaign", id, academyId],
    queryFn: () => massEmailAPI.campaign(id, academyId),
    refetchInterval: (query) => (
      ["queued", "sending"].includes(query.state.data?.data?.status) ? 3000 : false
    ),
  });
  const campaign = data?.data;
  const retryMut = useMutation({
    mutationFn: () => massEmailAPI.retryFailed(id, academyId),
    onSuccess: (res) => {
      toast.success(t("{n} envoi(s) en échec remis en file.", { n: res.data.requeued }));
      qc.invalidateQueries({ queryKey: ["mass-email-campaign", id, academyId] });
      qc.invalidateQueries({ queryKey: ["mass-email-campaigns", academyId] });
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const failures = campaign ? campaign.counts.failed + campaign.counts.retry : 0;

  return (
    <Modal open onClose={onClose} title={t("Rapport d'envoi")} size="lg">
      {isLoading || !campaign ? (
        <p className="text-sm text-slate-400">{t("Chargement…")}</p>
      ) : (
        <div className="space-y-4 text-sm">
          <div className="flex flex-wrap gap-2 items-center">
            <Badge tone={STATUS_TONE[campaign.status]}>{t(campaign.status_display)}</Badge>
            <span className="text-slate-600">{campaign.subject}</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {[
              ["Remis au serveur", campaign.counts.sent, CheckCircle2],
              ["En attente", campaign.counts.pending + campaign.counts.sending, Loader2],
              ["Échecs", failures, AlertTriangle],
              ["Ignorés", campaign.skipped_count, Users],
            ].map(([label, value, Icon]) => (
              <div key={label} className="rounded-xl bg-slate-50 p-3">
                <div className="flex items-center gap-1 text-xs text-slate-500"><Icon className="w-3 h-3" />{t(label)}</div>
                <div className="text-lg font-bold text-slate-800">{value}</div>
              </div>
            ))}
          </div>
          <p className="text-xs text-slate-500">
            {t("« Remis au serveur » signifie que le serveur de messagerie a accepté le message ; la réception dans la boîte du destinataire ne peut pas être garantie.")}
          </p>
          {campaign.last_error && <p className="text-xs text-red-600">{campaign.last_error}</p>}
          {failures > 0 && (
            <button type="button" className="btn-secondary flex items-center gap-2"
                    disabled={retryMut.isPending} onClick={() => retryMut.mutate()}>
              <RefreshCw className="w-4 h-4" />{t("Relancer uniquement les échecs ({n})", { n: failures })}
            </button>
          )}
          <div className="max-h-80 overflow-y-auto rounded-xl border border-slate-100">
            <table className="w-full text-sm">
              <tbody>
                {campaign.recipients.map((r) => (
                  <tr key={r.id} className="border-b border-slate-50 align-top">
                    <td className="px-3 py-2">
                      <div className="font-medium text-slate-800">{r.full_name}</div>
                      <div className="text-xs text-slate-400 break-all">{r.email || "—"}</div>
                    </td>
                    <td className="px-3 py-2">
                      <Badge tone={STATUS_TONE[r.status]}>{t(r.status_display)}</Badge>
                      {/* Backend console/locmem : « remis » ne veut pas dire « parti ». */}
                      {r.status === "sent" && !r.used_real_provider && (
                        <div className="mt-1"><Badge tone="bg-amber-50 text-amber-700">{t("Journalisé — aucun fournisseur réel")}</Badge></div>
                      )}
                    </td>
                    <td className="px-3 py-2 text-xs text-red-600 break-all">{r.error}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Modal>
  );
}
