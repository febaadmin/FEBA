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
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import {
  AlertTriangle, CheckCircle2, Eye, FileText, Loader2, Mail, Paperclip, PenSquare, RefreshCw, Save, Search, Send, Users,
} from "lucide-react";

import { massEmailAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import ChampAdresses from "../../components/email/ChampAdresses";
import EditeurMessage from "../../components/email/EditeurMessage";
import { useDiffere } from "../../hooks/useDiffere";
import { useAcademy } from "../../context/AcademyContext";
import { t } from "../../i18n";
import { extractApiError } from "../../utils/errors";
import { formatDateTime } from "../../utils/datetime";
import {
  audiencePayload, champsVides, depuisAudience, emptyAudience, hasAnyRule, isSelected, MODES, newClientToken,
  setUsers, toggleRole, toggleUser,
} from "../../utils/massEmailSelection";

const ROLE_LABELS = {
  admin: "Administrateurs", teacher: "Enseignants", parent: "Parents", student: "Élèves",
};

const STATUS_TONE = {
  sent: "bg-emerald-50 text-emerald-700",
  pending: "bg-slate-100 text-slate-600",
  sending: "bg-primary-50 text-primary-700",
  retry: "bg-amber-50 text-amber-700",
  failed: "bg-red-50 text-red-700",
  done: "bg-emerald-50 text-emerald-700",
  partial: "bg-amber-50 text-amber-700",
  queued: "bg-slate-100 text-slate-600",
  rejected: "bg-red-50 text-red-700",
};
const CHAMP_LIBELLE = { a: "À", cc: "Cc", cci: "Cci", groupe: "Individuel" };

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
  const { isAllAcademies } = useAcademy();
  const [onglet, setOnglet] = useState("nouveau");
  const [aReprendre, setAReprendre] = useState(null);       // brouillon chargé dans le compositeur
  const [rapport, setRapport] = useState(null);             // envoi tout juste créé : son rapport s'ouvre
  if (isAllAcademies) {
    return (
      <div className="space-y-4">
        <PageHeader title={t("Espace d'envoi d'e-mails")} subtitle={t("Envoi par académie et par type de profil")} />
        <div className="card text-sm text-amber-800 bg-amber-50 border-amber-200" role="status">
          {t("Sélectionnez une académie en haut de la page : chaque envoi part au nom d'une seule académie.")}
        </div>
      </div>
    );
  }
  return (
    <div className="space-y-6">
      <PageHeader title={t("Espace d'envoi d'e-mails")} subtitle={t("Composer, enregistrer et suivre les e-mails envoyés au nom de l'académie")} />
      <div className="flex gap-1 border-b border-slate-200" role="tablist" aria-label={t("E-mails")}>
        {[["nouveau", "Nouveau message", PenSquare], ["brouillons", "Brouillons", FileText], ["envoyes", "Envoyés", Send]].map(([v, n, Icone]) => (
          <button key={v} type="button" role="tab" aria-selected={onglet === v} onClick={() => setOnglet(v)} data-testid={`onglet-${v}`}
            className={`inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${onglet === v ? "border-feba-navy text-feba-navy" : "border-transparent text-slate-500 hover:text-slate-800"}`}>
            <Icone className="w-4 h-4" aria-hidden="true" />{t(n)}
          </button>
        ))}
      </div>
      {/* Le compositeur reste monté : changer d'onglet ne perd pas la rédaction en cours. */}
      <div hidden={onglet !== "nouveau"}>
        <Compositeur aReprendre={aReprendre} onEnvoye={(id) => { setRapport(id); setOnglet("envoyes"); }} />
      </div>
      {onglet === "brouillons" && <ListeBrouillons onReprendre={(b) => { setAReprendre({ ...b, jeton: newClientToken() }); setOnglet("nouveau"); }} />}
      {onglet === "envoyes" && <Envoyes rapportInitial={rapport} />}
    </div>
  );
}

function useAcademie() {
  const { activeAcademy } = useAcademy();
  const [academyId, setAcademyId] = useState(activeAcademy?.id || "");
  const optionsQuery = useQuery({
    queryKey: ["mass-email-options", academyId],
    queryFn: () => massEmailAPI.options(academyId),
    retry: false,
  });
  const options = optionsQuery.data?.data;
  return { academyId, setAcademyId, options, optionsQuery, effectiveAcademyId: academyId || options?.academy?.id || "" };
}

function Compositeur({ aReprendre, onEnvoye }) {
  const qc = useQueryClient();
  const { setAcademyId, options, optionsQuery, effectiveAcademyId } = useAcademie();
  const [audience, setAudience] = useState(emptyAudience);
  const [champs, setChamps] = useState(champsVides);
  const [mode, setMode] = useState(MODES.individuel);
  const [voirCopies, setVoirCopies] = useState(false);
  const [groupes, setGroupes] = useState(false);
  const [roleFilter, setRoleFilter] = useState("");
  const [search, setSearch] = useState("");
  const [subject, setSubject] = useState("");
  const [format, setFormat] = useState("html");
  const [body, setBody] = useState("");
  const [html, setHtml] = useState("");
  const [files, setFiles] = useState([]);
  const [brouillon, setBrouillon] = useState(null);         // { id, pieces }
  const [previewState, setPreviewState] = useState(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [annulerOpen, setAnnulerOpen] = useState(false);
  const [signatureOpen, setSignatureOpen] = useState(false);
  const [clientToken, setClientToken] = useState(newClientToken);
  const [repris, setRepris] = useState(null);

  const recipientsQuery = useQuery({
    queryKey: ["mass-email-recipients", effectiveAcademyId],
    queryFn: () => massEmailAPI.recipients(effectiveAcademyId),
    enabled: !!effectiveAcademyId,
  });
  const allUsers = useMemo(() => recipientsQuery.data?.data?.results || [], [recipientsQuery.data]);
  const signatureQuery = useQuery({ queryKey: ["mass-email-signature"], queryFn: massEmailAPI.signature });
  const signature = signatureQuery.data?.data?.texte || "";

  // Reprise d'un brouillon (une fois par demande, repérée par son jeton).
  if (aReprendre && repris !== aReprendre.jeton) {
    setRepris(aReprendre.jeton);
    const etat = depuisAudience(aReprendre.audience, allUsers);
    setAudience(etat.audience); setChamps(etat.champs); setMode(etat.mode);
    setVoirCopies(etat.champs.cc.length > 0 || etat.champs.cci.length > 0);
    setGroupes(hasAnyRule(etat.audience));
    setSubject(aReprendre.objet || ""); setFormat(aReprendre.format || "texte");
    setBody(aReprendre.corps || ""); setHtml(aReprendre.corps_html || "");
    setFiles([]); setBrouillon({ id: aReprendre.id, pieces: aReprendre.pieces || [] });
    setClientToken(newClientToken()); setPreviewState(null);
  }

  const contenuPresent = format === "html" ? html.replace(/<[^>]*>|&nbsp;/g, "").trim() : body.trim();
  // L'aperçu n'est valable que pour la rédaction qui l'a produit : toute modification l'invalide.
  const draftSignature = JSON.stringify([effectiveAcademyId, audience, champs, mode, subject, format, body, html,
    files.map((f) => [f.name, f.size, f.lastModified]), brouillon?.pieces?.map((p) => p.id)]);
  const preview = previewState?.signature === draftSignature ? previewState.data : null;

  const visibleUsers = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return allUsers.filter((u) => (!roleFilter || u.role === roleFilter)
      && (!needle || `${u.full_name} ${u.email}`.toLowerCase().includes(needle)));
  }, [allUsers, roleFilter, search]);
  const selectedCount = allUsers.filter((u) => isSelected(u, audience)).length;
  const payload = () => ({
    academy_id: effectiveAcademyId, ...audiencePayload(audience, champs, mode),
    body_format: format, body: format === "texte" ? body : "", body_html: format === "html" ? html : "",
  });

  const reinitialiser = () => {
    setAudience(emptyAudience()); setChamps(champsVides()); setMode(MODES.individuel); setSubject("");
    setBody(""); setHtml(""); setFiles([]); setBrouillon(null); setPreviewState(null); setVoirCopies(false);
    setClientToken(newClientToken());
  };
  const changeAcademy = (id) => { setAcademyId(id); reinitialiser(); };

  const previewMut = useMutation({
    mutationFn: () => massEmailAPI.preview(payload()),
    onSuccess: (res, sig) => setPreviewState({ signature: sig, data: res.data }),
    onError: (e) => toast.error(extractApiError(e)),
  });

  // Verrou SYNCHRONE : deux clics dans le même instant ne partent pas tous les deux.
  const sendingRef = useRef(false);
  const sendOnce = () => {
    if (sendingRef.current) return;
    sendingRef.current = true;
    sendMut.mutate();
  };
  const sendMut = useMutation({
    mutationFn: () => massEmailAPI.create({
      ...payload(), subject, body: format === "texte" ? body : (preview?.texte || ""), confirm: true,
      expected_count: preview?.count, client_token: clientToken, brouillon_id: brouillon?.id || undefined,
    }, files),
    onSuccess: (res) => {
      setConfirmOpen(false);
      toast.success(t("Envoi mis en file : {n} destinataire(s).", { n: res.data.total_recipients }));
      reinitialiser();
      qc.invalidateQueries({ queryKey: ["mass-email-campaigns"] });
      qc.invalidateQueries({ queryKey: ["mass-email-brouillons"] });
      onEnvoye?.(res.data.id);
    },
    onError: (e) => { setConfirmOpen(false); toast.error(extractApiError(e)); },
    onSettled: () => { sendingRef.current = false; },
  });

  const brouillonMut = useMutation({
    mutationFn: async () => {
      const d = { objet: subject, corps: body, corps_html: html, format, audience: audiencePayload(audience, champs, mode) };
      const rep = brouillon?.id
        ? await massEmailAPI.majBrouillon(brouillon.id, effectiveAcademyId, d)
        : await massEmailAPI.creerBrouillon(effectiveAcademyId, d);
      if (files.length) return massEmailAPI.ajouterPieces(rep.data.id, effectiveAcademyId, files);
      return rep;
    },
    onSuccess: (rep) => {
      setBrouillon({ id: rep.data.id, pieces: rep.data.pieces });
      setFiles([]);
      toast.success(t("Brouillon enregistré."));
      qc.invalidateQueries({ queryKey: ["mass-email-brouillons"] });
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const retirerPieceMut = useMutation({
    mutationFn: (pieceId) => massEmailAPI.retirerPiece(brouillon.id, pieceId, effectiveAcademyId),
    onSuccess: (rep) => setBrouillon({ id: rep.data.id, pieces: rep.data.pieces }),
    onError: (e) => toast.error(extractApiError(e)),
  });

  const insererSignature = () => {
    if (!signature) { setSignatureOpen(true); return; }
    if (format === "html") {
      const bloc = `<p>--<br>${signature.split("\n").map((l) => l.replace(/[<>&]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" })[c])).join("<br>")}</p>`;
      setHtml((h) => `${h}${bloc}`);
    } else {
      setBody((b) => `${b.replace(/\s+$/, "")}\n\n-- \n${signature}`);
    }
  };

  if (optionsQuery.isError) {
    return <div className="card text-sm text-red-700">{extractApiError(optionsQuery.error)}</div>;
  }
  const canPreview = hasAnyRule(audience, champs) && subject.trim() && contenuPresent;
  const nbPieces = files.length + (brouillon?.pieces?.length || 0);

  return (
    <div className="space-y-4">
      {options && options.transport === "capture" && (
        <div className="card border border-amber-200 bg-amber-50 text-sm text-amber-800 flex gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>
            {t("Mode test : les messages sont capturés par Mailpit et n'atteignent aucune boîte réelle.")}{" "}
            {options.capture_ui_url && (
              <a href={options.capture_ui_url} target="_blank" rel="noreferrer" className="font-semibold underline">{t("Ouvrir Mailpit")}</a>
            )}
          </span>
        </div>
      )}
      {options && !options.provider_configured && options.transport !== "capture" && (
        <div className="card border border-amber-200 bg-amber-50 text-sm text-amber-800 flex gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          {t("Aucun serveur de messagerie réel n'est configuré : les messages seront journalisés mais ne partiront pas sur Internet.")}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-5">
        <section className="card lg:col-span-3 space-y-3" aria-label={t("Message")} data-testid="compositeur">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-bold text-slate-800 flex items-center gap-2"><Mail className="w-4 h-4" />
              {brouillon ? t("Brouillon") : t("Nouveau message")}</h2>
            {options?.academies?.length > 1 ? (
              <select aria-label={t("Académie")} className="input w-auto text-sm" value={effectiveAcademyId}
                onChange={(e) => changeAcademy(e.target.value)}>
                {options.academies.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
            ) : <span className="text-sm font-semibold text-slate-600">{options?.academy?.name || "…"}</span>}
          </div>

          <div className="rounded-xl border border-slate-100 px-3">
            <ChampAdresses libelle={t("À")} entrees={champs.a} onChange={(a) => setChamps((c) => ({ ...c, a }))}
              comptes={allUsers} testid="champ-a" />
            {voirCopies ? (
              <>
                <ChampAdresses libelle={t("Cc")} entrees={champs.cc} onChange={(cc) => setChamps((c) => ({ ...c, cc }))}
                  comptes={allUsers} testid="champ-cc" />
                <ChampAdresses libelle={t("Cci")} entrees={champs.cci} onChange={(cci) => setChamps((c) => ({ ...c, cci }))}
                  comptes={allUsers} testid="champ-cci" aide={t("Copie cachée : invisible des autres destinataires")} />
              </>
            ) : null}
            <div className="flex flex-wrap items-center gap-3 py-1.5 text-xs">
              {!voirCopies && (
                <button type="button" className="font-medium text-primary hover:underline" onClick={() => setVoirCopies(true)}
                  data-testid="voir-copies">{t("Ajouter Cc / Cci")}</button>
              )}
              <button type="button" className="font-medium text-primary hover:underline" onClick={() => setGroupes((x) => !x)}
                aria-expanded={groupes} data-testid="voir-groupes">
                {groupes ? t("Masquer les profils") : t("Ajouter des profils ou des membres")}
                {selectedCount > 0 && ` (${selectedCount})`}
              </button>
            </div>
          </div>

          <fieldset className="rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600 space-y-1">
            <legend className="sr-only">{t("Mode d'envoi")}</legend>
            <label className="flex items-start gap-2">
              <input type="radio" name="mode" checked={mode === MODES.individuel} onChange={() => setMode(MODES.individuel)} data-testid="mode-individuel" />
              <span><strong>{t("Message individuel")}</strong> - {t("chaque destinataire reçoit son propre message ; aucune adresse n'est visible des autres (recommandé pour les familles).")}</span>
            </label>
            <label className="flex items-start gap-2">
              <input type="radio" name="mode" checked={mode === MODES.commun} onChange={() => setMode(MODES.commun)} data-testid="mode-commun" />
              <span><strong>{t("Message commun")}</strong> - {t("les destinataires « À » et « Cc » voient leurs adresses respectives ; « Cci » reste invisible. Les profils et membres ajoutés reçoivent toujours un message individuel.")}</span>
            </label>
          </fieldset>

          <div>
            <label className="label" htmlFor="mass-email-subject">{t("Objet")}</label>
            <input id="mass-email-subject" className="input" maxLength={200} value={subject} onChange={(e) => setSubject(e.target.value)} />
          </div>
          <EditeurMessage id="mass-email-body" format={format} onFormat={setFormat} texte={body} onTexte={setBody} html={html} onHtml={setHtml} />
          <div className="flex flex-wrap gap-3 text-xs">
            <button type="button" className="font-medium text-primary hover:underline" onClick={insererSignature} data-testid="inserer-signature">
              {t("Insérer ma signature")}</button>
            <button type="button" className="font-medium text-slate-500 hover:underline" onClick={() => setSignatureOpen(true)}>
              {t("Modifier ma signature")}</button>
          </div>

          {brouillon?.pieces?.length > 0 && (
            <ul className="divide-y divide-slate-100 rounded-xl border border-slate-100 text-sm" aria-label={t("Pièces jointes du brouillon")}>
              {brouillon.pieces.map((p) => (
                <li key={p.id} className="flex items-center justify-between gap-2 px-3 py-1.5">
                  <span className="break-all"><Paperclip className="inline w-3.5 h-3.5 mr-1 text-slate-400" aria-hidden="true" />{p.nom} <span className="text-xs text-slate-400">({formatBytes(p.taille)})</span></span>
                  <button type="button" className="text-xs text-danger hover:underline" onClick={() => retirerPieceMut.mutate(p.id)}
                    aria-label={`${t("Retirer")} ${p.nom}`}>{t("Retirer")}</button>
                </li>
              ))}
            </ul>
          )}
          <AttachmentPicker files={files} onChange={setFiles} limits={options?.attachments} dejaJointes={brouillon?.pieces?.length || 0} />

          <div className="flex flex-wrap gap-2 pt-1">
            <button type="button" className="btn-primary flex items-center gap-2" disabled={!canPreview || previewMut.isPending}
              onClick={() => previewMut.mutate(draftSignature)} data-testid="previsualiser">
              {previewMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}{t("Prévisualiser")}
            </button>
            <button type="button" className="btn-secondary flex items-center gap-2" disabled={brouillonMut.isPending || !effectiveAcademyId}
              onClick={() => brouillonMut.mutate()} data-testid="enregistrer-brouillon">
              {brouillonMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}{t("Enregistrer le brouillon")}
            </button>
            <button type="button" className="btn-secondary text-danger ml-auto" onClick={() => setAnnulerOpen(true)}
              disabled={!subject && !contenuPresent && !hasAnyRule(audience, champs) && !nbPieces} data-testid="annuler-redaction">
              {t("Annuler la rédaction")}
            </button>
          </div>

          {preview && (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 space-y-3 text-sm animate-apparition" data-testid="apercu-email">
              <p className="font-semibold text-slate-800">
                {t("{n} destinataire(s) recevront ce message.", { n: preview.count })}
                {preview.skipped_count > 0 && <span className="font-normal text-slate-500"> {t("{n} ignoré(s).", { n: preview.skipped_count })}</span>}
              </p>
              <p className="text-xs text-slate-600" data-testid="apercu-champs">
                {[["a", "À"], ["cc", "Cc"], ["cci", "Cci"], ["groupe", "Profils et membres (message individuel)"]]
                  .filter(([k]) => preview.par_champ?.[k]).map(([k, n]) => `${t(n)} : ${preview.par_champ[k]}`).join(" · ")}
              </p>
              {preview.skipped.length > 0 && (
                <ul className="text-xs text-slate-500 list-disc pl-4">
                  {preview.skipped.slice(0, 8).map((s, i) => <li key={`${s.email}-${i}`}>{s.full_name} : {t(SKIP_REASON[s.status] || s.status)}</li>)}
                </ul>
              )}
              <div className="rounded-lg bg-white border border-slate-200 p-3">
                <p className="text-xs text-slate-400">{t("Aperçu du message")}</p>
                <p className="font-semibold text-slate-800">{subject}</p>
                {preview.html_nettoye
                  // HTML NETTOYÉ PAR LE SERVEUR (liste blanche nh3) : exactement ce qui sera envoyé.
                  ? <div className="text-slate-700 text-wrapsafe [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_a]:text-primary [&_a]:underline"
                    dangerouslySetInnerHTML={{ __html: preview.html_nettoye }} data-testid="apercu-html" />
                  : <p className="whitespace-pre-wrap text-slate-700 text-wrapsafe">{body}</p>}
                {nbPieces > 0 && (
                  <p className="mt-2 text-xs text-slate-500">
                    {t("Pièces jointes")} : {[...(brouillon?.pieces || []).map((p) => p.nom), ...files.map((f) => f.name)].join(", ")}
                  </p>
                )}
                <p className="mt-2 border-t pt-2 text-xs text-slate-400">{preview.academy?.name}</p>
              </div>
              <button type="button" className="btn-primary w-full flex items-center justify-center gap-2"
                disabled={preview.count === 0 || sendMut.isPending} onClick={() => setConfirmOpen(true)}>
                <Send className="w-4 h-4" />{t("Envoyer à {n} destinataire(s)", { n: preview.count })}
              </button>
            </div>
          )}
        </section>

        {groupes && (
          <section className="card lg:col-span-2 space-y-3" aria-label={t("Profils et membres")} data-testid="panneau-groupes">
            <h2 className="font-bold text-slate-800 flex items-center gap-2"><Users className="w-4 h-4" />{t("Profils et membres")}</h2>
            <p className="text-xs text-slate-500">{t("Chaque personne ajoutée ici reçoit un message individuel.")}</p>
            <div className="flex flex-wrap gap-2">
              <label className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-1.5 text-sm">
                <input type="checkbox" checked={audience.allProfiles} onChange={() => setAudience((a) => ({ ...a, allProfiles: !a.allProfiles }))} />
                <span className="font-semibold">{t("Tous les profils")}</span>
              </label>
              {(options?.roles || []).map((r) => (
                <label key={r.role} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-1.5 text-sm">
                  <input type="checkbox" disabled={audience.allProfiles} checked={audience.allProfiles || audience.roles.includes(r.role)}
                    onChange={() => setAudience((a) => toggleRole(a, r.role))} />
                  {t(ROLE_LABELS[r.role] || r.label)} <span className="text-slate-400">({r.active_count})</span>
                </label>
              ))}
            </div>
            <div className="flex flex-wrap gap-2 items-center">
              <input className="input flex-1 min-w-[10rem]" placeholder={t("Rechercher une personne…")} value={search}
                onChange={(e) => setSearch(e.target.value)} aria-label={t("Rechercher une personne…")} />
              <select className="input w-auto" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} aria-label={t("Filtrer par profil")}>
                <option value="">{t("Tous les profils")}</option>
                {Object.entries(ROLE_LABELS).map(([k, v]) => <option key={k} value={k}>{t(v)}</option>)}
              </select>
            </div>
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn-secondary text-xs" onClick={() => setAudience((a) => setUsers(a, visibleUsers, true))}>
                {t("Cocher la liste affichée")} ({visibleUsers.filter((u) => u.sendable).length})</button>
              <button type="button" className="btn-secondary text-xs" onClick={() => setAudience((a) => setUsers(a, visibleUsers, false))}>
                {t("Décocher la liste affichée")}</button>
            </div>
            <div className="max-h-96 overflow-y-auto rounded-xl border border-slate-100">
              {recipientsQuery.isLoading ? (
                <p className="p-4 text-sm text-slate-400">{t("Chargement…")}</p>
              ) : visibleUsers.length === 0 ? (
                <p className="p-4 text-sm text-slate-400">{t("Aucun compte pour ce filtre.")}</p>
              ) : (
                <table className="w-full text-sm"><tbody>
                  {visibleUsers.map((u) => (
                    <tr key={u.id} className="border-b border-slate-50">
                      <td className="px-3 py-2 w-8">
                        <input type="checkbox" disabled={!u.sendable} checked={isSelected(u, audience)}
                          onChange={() => setAudience((a) => toggleUser(a, u))} aria-label={`${t("Sélectionner")} ${u.full_name}`} />
                      </td>
                      <td className="px-3 py-2">
                        <div className="font-medium text-slate-800">{u.full_name}</div>
                        <div className="text-xs text-slate-400 break-all">{u.email || "-"}</div>
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-500">{t(ROLE_LABELS[u.role] || u.role)}</td>
                      <td className="px-3 py-2 text-right">
                        {!u.sendable && <Badge tone="bg-red-50 text-red-700">{t(SKIP_REASON[u.status] || "Non joignable")}</Badge>}
                      </td>
                    </tr>
                  ))}
                </tbody></table>
              )}
            </div>
            <p className="text-sm text-slate-600">{t("{n} destinataire(s) sélectionné(s)", { n: selectedCount })}</p>
          </section>
        )}
      </div>

      <Modal open={confirmOpen} onClose={() => !sendMut.isPending && setConfirmOpen(false)} title={t("Confirmer l'envoi")} size="sm">
        <p className="text-sm text-slate-600">
          {t("Vous allez envoyer « {subject} » à {n} destinataire(s) de {academy}. Cette action ne peut pas être annulée.",
            { subject, n: preview?.count ?? 0, academy: preview?.academy?.name || "" })}
        </p>
        <div className="flex gap-3 justify-end mt-6">
          <button type="button" className="btn-secondary" disabled={sendMut.isPending} onClick={() => setConfirmOpen(false)}>{t("Annuler")}</button>
          <button type="button" className="btn-primary flex items-center gap-2" disabled={sendMut.isPending} onClick={sendOnce}>
            {sendMut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            {sendMut.isPending ? t("Envoi…") : t("Confirmer l'envoi")}
          </button>
        </div>
      </Modal>
      <Modal open={annulerOpen} onClose={() => setAnnulerOpen(false)} title={t("Annuler la rédaction")} size="sm">
        <p className="text-sm text-slate-600">
          {brouillon ? t("Les modifications non enregistrées seront perdues ; le brouillon enregistré est conservé.")
            : t("Le message en cours de rédaction sera effacé.")}
        </p>
        <div className="flex gap-3 justify-end mt-6">
          <button type="button" className="btn-secondary" onClick={() => setAnnulerOpen(false)}>{t("Continuer la rédaction")}</button>
          <button type="button" className="btn-primary bg-danger" onClick={() => { reinitialiser(); setAnnulerOpen(false); }}
            data-testid="confirmer-annulation">{t("Effacer")}</button>
        </div>
      </Modal>
      {signatureOpen && <SignatureModal initiale={signature} onClose={() => setSignatureOpen(false)} />}
    </div>
  );
}

function SignatureModal({ initiale, onClose }) {
  const qc = useQueryClient();
  const [texte, setTexte] = useState(initiale);
  const mut = useMutation({
    mutationFn: () => massEmailAPI.majSignature(texte),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["mass-email-signature"] }); toast.success(t("Signature enregistrée.")); onClose(); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  return (
    <Modal open onClose={onClose} title={t("Ma signature")} size="sm">
      <label className="label" htmlFor="signature-email">{t("Signature (texte)")}</label>
      <textarea id="signature-email" className="input" rows={5} maxLength={2000} value={texte} onChange={(e) => setTexte(e.target.value)}
        placeholder={t("Ex. : La direction - Faith & Excellence Bilingual Academy")} />
      <div className="flex gap-3 justify-end mt-4">
        <button type="button" className="btn-secondary" onClick={onClose}>{t("Annuler")}</button>
        <button type="button" className="btn-primary" disabled={mut.isPending} onClick={() => mut.mutate()}>{t("Enregistrer")}</button>
      </div>
    </Modal>
  );
}

function ListeBrouillons({ onReprendre }) {
  const qc = useQueryClient();
  const { effectiveAcademyId } = useAcademie();
  const [aSupprimer, setASupprimer] = useState(null);
  const q = useQuery({ queryKey: ["mass-email-brouillons", effectiveAcademyId], queryFn: () => massEmailAPI.brouillons(effectiveAcademyId), enabled: !!effectiveAcademyId });
  const lignes = q.data?.data?.results || [];
  const supprimer = useMutation({
    mutationFn: (id) => massEmailAPI.supprimerBrouillon(id, effectiveAcademyId),
    onSuccess: () => { setASupprimer(null); toast.success(t("Brouillon supprimé.")); qc.invalidateQueries({ queryKey: ["mass-email-brouillons"] }); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const nbDest = (a) => ["a", "cc", "cci"].reduce((n, k) => n + (a?.adresses?.[k]?.length || 0), 0) + (a?.include_ids?.length || 0);
  return (
    <section className="card space-y-3" data-testid="liste-brouillons">
      <h2 className="font-bold text-slate-800">{t("Mes brouillons")}</h2>
      <p className="text-xs text-slate-500">{t("Un brouillon n'est visible que par vous. Les destinataires sont vérifiés de nouveau au moment de l'envoi.")}</p>
      {q.isLoading ? <p className="text-sm text-slate-400">{t("Chargement…")}</p> : lignes.length === 0 ? (
        <p className="text-sm text-slate-400 py-6 text-center">{t("Aucun brouillon.")}</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {lignes.map((b) => (
            <li key={b.id} className="flex flex-wrap items-center gap-3 py-2" data-testid={`brouillon-${b.id}`}>
              <div className="min-w-0 flex-1">
                <p className="font-medium text-slate-800 truncate">{b.objet || t("(sans objet)")}</p>
                <p className="text-xs text-slate-500">
                  {t("Modifié le {d}", { d: formatDateTime(b.modifie_le) })}
                  {" · "}{t("{n} destinataire(s) saisi(s)", { n: nbDest(b.audience) })}
                  {b.audience?.roles?.length || b.audience?.all_profiles ? ` · ${t("profils")}` : ""}
                  {b.pieces.length > 0 && ` · ${t("{n} pièce(s) jointe(s)", { n: b.pieces.length })}`}
                </p>
              </div>
              <button type="button" className="btn-secondary text-xs" onClick={() => onReprendre(b)} data-testid={`reprendre-${b.id}`}>{t("Reprendre")}</button>
              <button type="button" className="text-xs text-danger hover:underline" onClick={() => setASupprimer(b)}>{t("Supprimer")}</button>
            </li>
          ))}
        </ul>
      )}
      <ConfirmDialog open={!!aSupprimer} onClose={() => setASupprimer(null)} loading={supprimer.isPending}
        onConfirm={() => supprimer.mutate(aSupprimer.id)} message={t("Supprimer le brouillon « {o} » ?", { o: aSupprimer?.objet || t("(sans objet)") })} />
    </section>
  );
}

const STATUTS_ENVOI = [["queued", "En attente"], ["sending", "En cours d'envoi"], ["done", "Envoyé au fournisseur"],
  ["partial", "Envoyé avec des échecs"], ["failed", "Échec"]];

function Envoyes({ rapportInitial }) {
  const { effectiveAcademyId } = useAcademie();
  const [saisie, setSaisie] = useState("");
  const q = useDiffere(saisie, 350);
  const [statut, setStatut] = useState("");
  const [du, setDu] = useState("");
  const [au, setAu] = useState("");
  const [ouvert, setOuvert] = useState(rapportInitial || null);
  const params = Object.fromEntries(Object.entries({ q: q.trim(), statut, du, au }).filter(([, v]) => v));
  const campaignsQuery = useQuery({
    queryKey: ["mass-email-campaigns", effectiveAcademyId, params],
    queryFn: () => massEmailAPI.campaigns(effectiveAcademyId, params),
    enabled: !!effectiveAcademyId,
    placeholderData: keepPreviousData,
    refetchInterval: (query) => ((query.state.data?.data?.results || []).some((c) => ["queued", "sending"].includes(c.status)) ? 4000 : false),
  });
  const campaigns = campaignsQuery.data?.data?.results || [];
  const filtre = Object.keys(params).length > 0;
  return (
    <section className="card space-y-3" data-testid="envoyes">
      <div className="flex flex-wrap gap-2 items-end">
        <label className="relative flex-1 min-w-[14rem]">
          <span className="sr-only">{t("Rechercher dans les envois")}</span>
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true" />
          <input type="search" className="input pl-9" value={saisie} onChange={(e) => setSaisie(e.target.value)}
            placeholder={t("Objet, nom ou adresse d'un destinataire…")} data-testid="envois-recherche" />
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-600">{t("Statut")}
          <select className="input !py-1 text-sm" value={statut} onChange={(e) => setStatut(e.target.value)} data-testid="envois-statut">
            <option value="">{t("Tous")}</option>
            {STATUTS_ENVOI.map(([v, n]) => <option key={v} value={v}>{t(n)}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-600">{t("Du")}<input type="date" className="input !py-1 text-sm" value={du} onChange={(e) => setDu(e.target.value)} /></label>
        <label className="flex flex-col gap-1 text-xs text-slate-600">{t("Au")}<input type="date" className="input !py-1 text-sm" value={au} onChange={(e) => setAu(e.target.value)} /></label>
        {filtre && <button type="button" className="text-xs font-medium text-red-700 hover:underline" onClick={() => { setSaisie(""); setStatut(""); setDu(""); setAu(""); }}>{t("Réinitialiser les filtres")}</button>}
      </div>
      {campaigns.length === 0 ? (
        <p className="text-sm text-slate-400 py-6 text-center">{filtre ? t("Aucun envoi ne correspond à ces critères.") : t("Aucun envoi groupé pour cette académie.")}</p>
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
                <tr key={c.id} className="border-b border-slate-50 hover:bg-slate-50 cursor-pointer" onClick={() => setOuvert(c.id)} data-testid={`envoi-${c.id}`}>
                  <td className="py-2 pr-3 whitespace-nowrap">{formatDateTime(c.created_at)}</td>
                  <td className="py-2 pr-3">{c.subject}{c.attachments?.length > 0 && <Paperclip className="inline w-3.5 h-3.5 ml-1 text-slate-400" aria-label={t("Pièces jointes")} />}</td>
                  <td className="py-2 pr-3"><Badge tone={STATUS_TONE[c.status]}>{t(c.status_display)}</Badge></td>
                  <td className="py-2 pr-3">{c.counts.sent}</td>
                  <td className="py-2 pr-3">{c.counts.failed + c.counts.retry + (c.counts.rejected || 0)}</td>
                  <td className="py-2 pr-3">{c.skipped_count}</td>
                  <td className="py-2 pr-3 text-right"><span className="text-primary text-xs">{t("Rapport")}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {ouvert && <CampaignReport id={ouvert} academyId={effectiveAcademyId} onClose={() => setOuvert(null)} />}
    </section>
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
  const failures = campaign ? campaign.counts.failed + campaign.counts.retry + (campaign.counts.rejected || 0) : 0;

  return (
    <Modal open onClose={onClose} title={t("Rapport d'envoi")} size="lg">
      {isLoading || !campaign ? (
        <p className="text-sm text-slate-400">{t("Chargement…")}</p>
      ) : (
        <div className="space-y-4 text-sm">
          <div className="flex flex-wrap gap-2 items-center">
            <Badge tone={STATUS_TONE[campaign.status]}>{t(campaign.status_display)}</Badge>
            <span className="text-slate-600">{campaign.subject}</span>
            <span className="text-xs text-slate-400">· {formatDateTime(campaign.created_at)} · {campaign.created_by}</span>
          </div>
          <details className="rounded-xl border border-slate-100 p-3">
            <summary className="cursor-pointer text-xs font-medium text-slate-600">{t("Contenu du message")}</summary>
            <p className="mt-2 whitespace-pre-wrap text-slate-700 text-wrapsafe">{campaign.body}</p>
            {campaign.attachments?.length > 0 && (
              <p className="mt-2 text-xs text-slate-500">{t("Pièces jointes")} : {campaign.attachments.map((a) => `${a.name} (${formatBytes(a.size)})`).join(", ")}</p>
            )}
          </details>
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
                      <div className="text-xs text-slate-400 break-all">{r.email || "-"}</div>
                    </td>
                    <td className="px-3 py-2 text-xs text-slate-500" title={t(r.champ_display || "")}>{t(CHAMP_LIBELLE[r.champ] || "Individuel")}</td>
                    <td className="px-3 py-2">
                      <Badge tone={STATUS_TONE[r.status]}>{t(r.status_display)}</Badge>
                      {/* Backend console/locmem : « remis » ne veut pas dire « parti ». */}
                      {r.status === "sent" && !r.used_real_provider && (
                        <div className="mt-1"><Badge tone="bg-amber-50 text-amber-700">
                          {t(r.delivery_summary || "Journalisé : aucun fournisseur réel")}
                        </Badge></div>
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

function formatBytes(n) {
  if (n < 1024) return `${n} o`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} Ko`;
  return `${(n / (1024 * 1024)).toFixed(1)} Mo`;
}

/**
 * Pièces jointes : sélection multiple, liste (nom, taille), retrait.
 * Le contrôle ici n'est qu'un CONFORT : le serveur revalide extension,
 * signature binaire et tailles, et refuse l'envoi entier en cas d'erreur.
 */
export function AttachmentPicker({ files, onChange, limits, dejaJointes = 0 }) {
  const [error, setError] = useState("");
  const allowed = limits?.allowed_extensions || [];
  const maxFile = (limits?.max_file_mb || 10) * 1024 * 1024;
  const maxTotal = (limits?.max_total_mb || 20) * 1024 * 1024;
  const maxFiles = limits?.max_files || 10;

  const add = (list) => {
    setError("");
    const next = [...files];
    for (const file of list) {
      const ext = (file.name.split(".").pop() || "").toLowerCase();
      if (allowed.length && !allowed.includes(ext)) {
        setError(t("« {name} » : format non autorisé.", { name: file.name })); continue;
      }
      if (file.size > maxFile) {
        setError(t("« {name} » dépasse {n} Mo.", { name: file.name, n: limits?.max_file_mb || 10 })); continue;
      }
      if (next.some((f) => f.name === file.name && f.size === file.size)) continue;
      next.push(file);
    }
    if (next.length + dejaJointes > maxFiles) { setError(t("Au plus {n} pièces jointes.", { n: maxFiles })); return; }
    if (next.reduce((sum, f) => sum + f.size, 0) > maxTotal) {
      setError(t("Taille totale supérieure à {n} Mo.", { n: limits?.max_total_mb || 20 })); return;
    }
    onChange(next);
  };

  return (
    <div className="space-y-2">
      <label className="label" htmlFor="mass-email-files">{t("Pièces jointes")}</label>
      <input id="mass-email-files" type="file" multiple className="block text-sm"
             accept={allowed.map((e) => `.${e}`).join(",")}
             onChange={(e) => { add([...e.target.files]); e.target.value = ""; }} />
      {allowed.length > 0 && (
        <p className="text-xs text-slate-400">
          {t("Formats acceptés : {list}. Au plus {n} Mo par fichier, {total} Mo au total.",
             { list: allowed.join(", "), n: limits?.max_file_mb, total: limits?.max_total_mb })}
        </p>
      )}
      {error && <p className="text-xs text-red-600" role="alert">{error}</p>}
      {files.length > 0 && (
        <ul className="divide-y divide-slate-100 rounded-xl border border-slate-100 text-sm">
          {files.map((file, i) => (
            <li key={`${file.name}-${file.size}`} className="flex items-center justify-between gap-2 px-3 py-1.5">
              <span className="break-all">{file.name} <span className="text-xs text-slate-400">({formatBytes(file.size)})</span></span>
              <button type="button" className="text-xs text-danger hover:underline"
                      aria-label={`${t("Retirer")} ${file.name}`}
                      onClick={() => onChange(files.filter((_, j) => j !== i))}>
                {t("Retirer")}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
