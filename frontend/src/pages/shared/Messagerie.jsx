/**
 * Messagerie interne FEBA (tous les profils).
 *
 * Ordinateur : trois colonnes — dossiers, conversations, lecture.
 * Mobile : un panneau à la fois (dossiers en pastilles, liste, puis lecture avec retour).
 *
 * Tout ce qui touche aux droits est décidé par le serveur : destinataires
 * autorisés, accès aux conversations (participants seulement), pièces jointes
 * (liens signés), dossiers personnels. L'écran ne fait qu'afficher et demander.
 * Actualisation automatique sans rechargement : liste, fil ouvert et compteurs.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import {
  Archive, ArrowLeft, FileText, Inbox, Loader2, MailOpen, Mail, Paperclip, PenSquare, Reply, ReplyAll,
  RotateCcw, Search, Send, Star, Trash2, X,
} from "lucide-react";
import { authAPI, conversationsAPI, messageDraftsAPI } from "../../api";
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import { useDiffere } from "../../hooks/useDiffere";
import { extractApiError } from "../../utils/errors";
import { dateLocale, t, useI18n } from "../../i18n";

export const DOSSIERS = [
  ["reception", "Boîte de réception", Inbox], ["envoyes", "Envoyés", Send], ["brouillons", "Brouillons", FileText],
  ["importants", "Importants", Star], ["archives", "Archivés", Archive], ["corbeille", "Corbeille", Trash2],
];
const ROLES = { superadmin: "Super administrateur", admin: "Administration", teacher: "Enseignant", parent: "Parent", student: "Élève" };
const TEINTES = ["bg-sky-100 text-sky-800", "bg-amber-100 text-amber-800", "bg-emerald-100 text-emerald-800",
  "bg-violet-100 text-violet-800", "bg-rose-100 text-rose-800", "bg-teal-100 text-teal-800"];
const MAX_PIECES = 5;

const initiales = (nom) => (nom || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((m) => m[0]).join("").toUpperCase();

export function Avatar({ personne, taille = "w-9 h-9" }) {
  const teinte = TEINTES[(personne?.id || 0) % TEINTES.length];
  return personne?.avatar
    ? <img src={personne.avatar} alt="" className={`${taille} rounded-full object-cover shrink-0`} />
    : <span className={`${taille} rounded-full grid place-items-center text-xs font-semibold shrink-0 ${teinte}`} aria-hidden="true">{initiales(personne?.full_name)}</span>;
}

/** Date courte : heure aujourd'hui, jour de semaine cette semaine, sinon date. */
export function dateCourte(iso, maintenant = new Date()) {
  if (!iso) return "";
  const d = new Date(iso);
  const jours = (new Date(maintenant.toDateString()) - new Date(d.toDateString())) / 86400000;
  if (jours === 0) return d.toLocaleTimeString(dateLocale(), { hour: "2-digit", minute: "2-digit" });
  if (jours < 7) return d.toLocaleDateString(dateLocale(), { weekday: "short" });
  return d.toLocaleDateString(dateLocale(), { day: "2-digit", month: "short", ...(d.getFullYear() !== maintenant.getFullYear() ? { year: "numeric" } : {}) });
}

const taille = (n) => (n == null ? "" : n < 1024 ? `${n} o` : n < 1048576 ? `${Math.round(n / 1024)} Ko` : `${(n / 1048576).toFixed(1)} Mo`);
const noms = (personnes) => personnes.map((p) => p.full_name).join(", ");

function Pieces({ fichiers, onRetirer }) {
  if (!fichiers.length) return null;
  return (
    <ul className="flex flex-wrap gap-1.5">
      {fichiers.map((f, i) => (
        <li key={`${f.name}-${i}`} className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-700">
          <Paperclip className="w-3 h-3" aria-hidden="true" />{f.name} <span className="text-slate-400">{taille(f.size)}</span>
          <button type="button" onClick={() => onRetirer(i)} aria-label={t("Retirer {n}", { n: f.name })}><X className="w-3 h-3" /></button>
        </li>
      ))}
    </ul>
  );
}

function ChoixFichiers({ fichiers, onChange, id }) {
  const entree = useRef(null);
  return (
    <>
      <input ref={entree} id={id} type="file" multiple className="sr-only" aria-label={t("Joindre des fichiers")}
        onChange={(e) => {
          const tous = [...fichiers, ...e.target.files];
          if (tous.length > MAX_PIECES) toast.error(t("Au plus {n} pièces jointes.", { n: MAX_PIECES }));
          onChange(tous.slice(0, MAX_PIECES));
          e.target.value = "";
        }} />
      <button type="button" onClick={() => entree.current?.click()} className="p-2 rounded-lg text-slate-500 hover:bg-slate-100"
        title={t("Joindre des fichiers")} aria-label={t("Joindre des fichiers")} data-testid={`${id}-bouton`}>
        <Paperclip className="w-4 h-4" />
      </button>
    </>
  );
}

/** Choix de destinataires (liste autorisée par le serveur), en pastilles. */
function ChoixDestinataires({ comptes, valeurs, onChange }) {
  const [saisie, setSaisie] = useState("");
  const suggestions = useMemo(() => {
    const n = saisie.trim().toLowerCase();
    return comptes.filter((c) => !valeurs.includes(c.id) && (!n || `${c.full_name} ${c.email || ""} ${t(ROLES[c.role] || c.role)}`.toLowerCase().includes(n))).slice(0, 8);
  }, [saisie, comptes, valeurs]);
  const choisis = valeurs.map((id) => comptes.find((c) => c.id === id) || { id, full_name: `#${id}` });
  return (
    <div className="space-y-2">
      <label className="label" htmlFor="messagerie-destinataires">{t("Destinataires")}</label>
      <div className="flex flex-wrap gap-1.5">
        {choisis.map((c) => (
          <span key={c.id} className="inline-flex items-center gap-1 rounded-full bg-primary-50 text-primary-700 px-2 py-0.5 text-xs" data-testid="destinataire-pastille">
            {c.full_name}
            <button type="button" onClick={() => onChange(valeurs.filter((v) => v !== c.id))} aria-label={t("Retirer {n}", { n: c.full_name })}><X className="w-3 h-3" /></button>
          </span>
        ))}
      </div>
      <input id="messagerie-destinataires" className="input" value={saisie} onChange={(e) => setSaisie(e.target.value)}
        placeholder={t("Rechercher une personne (nom, profil)…")} autoComplete="off" data-testid="destinataires-recherche" />
      {suggestions.length > 0 && (
        <ul className="max-h-48 overflow-y-auto rounded-xl border border-slate-100 divide-y divide-slate-50" role="listbox" aria-label={t("Suggestions")}>
          {suggestions.map((c) => (
            <li key={c.id}>
              <button type="button" role="option" aria-selected="false" onClick={() => { onChange([...valeurs, c.id]); setSaisie(""); }}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-slate-50" data-testid={`destinataire-${c.id}`}>
                <Avatar personne={c} taille="w-7 h-7" />
                <span className="flex-1 min-w-0 truncate">{c.full_name}</span>
                <span className="text-xs text-slate-400">{t(ROLES[c.role] || c.role)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Composition({ ouvert, brouillon, onFermer }) {
  const qc = useQueryClient();
  const { data: rd } = useQuery({ queryKey: ["recipients"], queryFn: authAPI.recipients, enabled: ouvert });
  const comptes = rd?.data || [];
  const [dest, setDest] = useState([]);
  const [objet, setObjet] = useState("");
  const [corps, setCorps] = useState("");
  const [fichiers, setFichiers] = useState([]);
  const [brouillonId, setBrouillonId] = useState(null);
  const [initialise, setInitialise] = useState(null);
  const cle = ouvert ? (brouillon?.id ?? "nouveau") : null;
  if (cle !== initialise) {
    setInitialise(cle);
    setDest(brouillon?.destinataires || []); setObjet(brouillon?.objet || ""); setCorps(brouillon?.corps || "");
    setFichiers([]); setBrouillonId(brouillon?.id || null);
  }
  const envoi = useMutation({
    mutationFn: () => {
      const fd = new FormData();
      for (const id of dest) fd.append("recipient_ids", id);
      fd.append("subject", objet);
      fd.append("body", corps);
      for (const f of fichiers) fd.append("attachments", f);
      if (brouillonId) fd.append("brouillon_id", brouillonId);
      return conversationsAPI.create(fd);
    },
    onSuccess: (rep) => {
      toast.success(t("Message envoyé !"));
      qc.invalidateQueries({ queryKey: ["messagerie"] });
      onFermer(rep.data.id);
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const sauver = useMutation({
    mutationFn: () => (brouillonId
      ? messageDraftsAPI.update(brouillonId, { destinataires: dest, objet, corps })
      : messageDraftsAPI.create({ destinataires: dest, objet, corps })),
    onSuccess: (rep) => {
      setBrouillonId(rep.data.id);
      toast.success(fichiers.length ? t("Brouillon enregistré (les pièces jointes seront à joindre à l'envoi).") : t("Brouillon enregistré."));
      qc.invalidateQueries({ queryKey: ["messagerie"] });
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const envoyable = dest.length > 0 && corps.trim() && !envoi.isPending;
  return (
    <Modal open={ouvert} onClose={() => !envoi.isPending && onFermer()} title={brouillonId ? t("Brouillon") : t("Nouveau message")} size="lg">
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (envoyable) envoi.mutate(); }} data-testid="composition">
        <ChoixDestinataires comptes={comptes} valeurs={dest} onChange={setDest} />
        <div>
          <label className="label" htmlFor="messagerie-objet">{t("Objet")}</label>
          <input id="messagerie-objet" className="input" maxLength={200} value={objet} onChange={(e) => setObjet(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="messagerie-corps">{t("Message")}</label>
          <textarea id="messagerie-corps" className="input min-h-[10rem]" value={corps} onChange={(e) => setCorps(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && envoyable) envoi.mutate(); }} />
        </div>
        <Pieces fichiers={fichiers} onRetirer={(i) => setFichiers(fichiers.filter((_, j) => j !== i))} />
        <div className="flex flex-wrap items-center gap-2">
          <ChoixFichiers fichiers={fichiers} onChange={setFichiers} id="composition-fichiers" />
          <button type="button" className="btn-secondary text-sm" onClick={() => sauver.mutate()} disabled={sauver.isPending}
            data-testid="composition-brouillon">{t("Enregistrer le brouillon")}</button>
          <span className="text-xs text-slate-400 ml-auto hidden sm:inline">{t("Ctrl + Entrée pour envoyer")}</span>
          <button type="submit" className="btn-primary flex items-center gap-2" disabled={!envoyable} data-testid="composition-envoyer">
            {envoi.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}{t("Envoyer")}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function Fil({ id, onRetour, onOuvrir }) {
  const qc = useQueryClient();
  const [corps, setCorps] = useState("");
  const [fichiers, setFichiers] = useState([]);
  const [aTous, setATous] = useState(true);
  const [supprimer, setSupprimer] = useState(false);
  const fin = useRef(null);
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["messagerie", "fil", id], queryFn: () => conversationsAPI.get(id), refetchInterval: 8000, retry: false, staleTime: 0,
  });
  const fil = data?.data;
  const lu = useRef(null);
  useEffect(() => {
    if (fil && fil.unread_count > 0 && lu.current !== `${id}:${fil.nb_messages}`) {
      lu.current = `${id}:${fil.nb_messages}`;
      conversationsAPI.markRead(id).then(() => qc.invalidateQueries({ queryKey: ["messagerie", "liste"] })).catch(() => {});
    }
  }, [fil, id, qc]);
  useEffect(() => { fin.current?.scrollIntoView?.({ block: "end" }); }, [fil?.messages?.length]);
  const rafraichir = () => qc.invalidateQueries({ queryKey: ["messagerie"] });
  const action = useMutation({
    mutationFn: ([nom, corpsAction]) => (corpsAction === undefined ? conversationsAPI[nom](id) : conversationsAPI[nom](id, corpsAction)),
    onSuccess: (_r, [nom, corpsAction]) => {
      rafraichir();
      if (nom === "deplacer") {
        toast.success({ archives: t("Conversation archivée."), corbeille: t("Conversation placée dans la corbeille."), reception: t("Conversation restaurée.") }[corpsAction.dossier]);
        onRetour();
      }
      if (nom === "supprimerDefinitivement") { toast.success(t("Conversation supprimée de votre messagerie.")); onRetour(); }
      if (nom === "marquer") { toast.success(t("Marquée comme non lue.")); onRetour(); }
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const reponse = useMutation({
    mutationFn: () => {
      const fd = new FormData();
      fd.append("body", corps);
      fd.append("a_tous", aTous ? "true" : "false");
      for (const f of fichiers) fd.append("attachments", f);
      return conversationsAPI.reply(id, fd);
    },
    onSuccess: (rep) => {
      setCorps(""); setFichiers([]);
      rafraichir();
      if (rep.data.conversation !== id) { toast.success(t("Réponse envoyée à l'expéditeur seul (nouvelle conversation).")); onOuvrir(rep.data.conversation); }
      else toast.success(t("Réponse envoyée !"));
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  if (isLoading) return <div className="flex-1 grid place-items-center"><Loader2 className="w-6 h-6 animate-spin text-primary" aria-label={t("Chargement…")} /></div>;
  if (isError) return <div className="flex-1 grid place-items-center p-6 text-sm text-slate-500" role="alert">{error?.response?.status === 404 ? t("Conversation introuvable ou inaccessible.") : extractApiError(error)}</div>;
  const groupe = fil.correspondants.length > 1;
  const enCorbeille = fil.dossier === "corbeille";
  const bouton = "p-2 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors";
  return (
    <div className="flex-1 flex flex-col min-w-0 animate-apparition" data-testid="fil">
      <header className="flex items-start gap-2 border-b border-slate-100 px-4 py-3">
        <button type="button" onClick={onRetour} className={`${bouton} lg:hidden`} aria-label={t("Retour à la liste")} data-testid="fil-retour"><ArrowLeft className="w-4 h-4" /></button>
        <div className="flex-1 min-w-0">
          <h2 className="font-semibold text-slate-900 truncate" data-testid="fil-objet">{fil.subject}</h2>
          <p className="text-xs text-slate-500 truncate">{t("Avec")} {noms(fil.correspondants)}</p>
        </div>
        <div className="flex items-center gap-0.5" role="toolbar" aria-label={t("Actions")}>
          <button type="button" className={bouton} onClick={() => action.mutate(["important", { important: !fil.important }])}
            aria-pressed={fil.important} title={fil.important ? t("Retirer des importants") : t("Marquer comme important")}
            aria-label={fil.important ? t("Retirer des importants") : t("Marquer comme important")} data-testid="fil-important">
            <Star className={`w-4 h-4 ${fil.important ? "fill-amber-400 text-amber-500" : ""}`} />
          </button>
          <button type="button" className={bouton} onClick={() => action.mutate(["marquer", { lu: false }])} title={t("Marquer comme non lu")} aria-label={t("Marquer comme non lu")} data-testid="fil-non-lu">
            <Mail className="w-4 h-4" />
          </button>
          {fil.dossier === "reception" && (
            <button type="button" className={bouton} onClick={() => action.mutate(["deplacer", { dossier: "archives" }])} title={t("Archiver")} aria-label={t("Archiver")} data-testid="fil-archiver">
              <Archive className="w-4 h-4" />
            </button>
          )}
          {fil.dossier !== "reception" && (
            <button type="button" className={bouton} onClick={() => action.mutate(["deplacer", { dossier: "reception" }])} title={t("Restaurer dans la boîte de réception")} aria-label={t("Restaurer dans la boîte de réception")} data-testid="fil-restaurer">
              <RotateCcw className="w-4 h-4" />
            </button>
          )}
          {enCorbeille ? (
            <button type="button" className={`${bouton} hover:text-red-700`} onClick={() => setSupprimer(true)} title={t("Supprimer définitivement")} aria-label={t("Supprimer définitivement")} data-testid="fil-supprimer">
              <Trash2 className="w-4 h-4" />
            </button>
          ) : (
            <button type="button" className={`${bouton} hover:text-red-700`} onClick={() => action.mutate(["deplacer", { dossier: "corbeille" }])} title={t("Placer dans la corbeille")} aria-label={t("Placer dans la corbeille")} data-testid="fil-corbeille">
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </header>
      <ol className="flex-1 overflow-y-auto px-4 py-4 space-y-4 bg-slate-50/50" aria-label={t("Messages")}>
        {fil.messages.map((m) => (
          <li key={m.id} className={`flex gap-2 ${m.is_mine ? "flex-row-reverse" : ""} animate-apparition`}>
            {!m.is_mine && <Avatar personne={m.sender} taille="w-8 h-8" />}
            <div className={`max-w-[85%] sm:max-w-[75%] ${m.is_mine ? "items-end" : "items-start"} flex flex-col`}>
              <p className="text-xs text-slate-500 mb-0.5">
                {m.is_mine ? t("Vous") : m.sender.full_name}
                {!m.is_mine && <span className="text-slate-400"> · {t(ROLES[m.sender.role] || m.sender.role)}</span>}
                {" · "}<time dateTime={m.sent_at}>{new Date(m.sent_at).toLocaleString(dateLocale(), { dateStyle: "medium", timeStyle: "short" })}</time>
              </p>
              <div className={`rounded-2xl px-3.5 py-2.5 text-sm whitespace-pre-wrap text-wrapsafe shadow-sm ${m.is_mine ? "bg-feba-navy text-white rounded-tr-sm" : "bg-white text-slate-800 border border-slate-100 rounded-tl-sm"}`}>
                {m.body}
              </div>
              {m.pieces.length > 0 && (
                <ul className="mt-1.5 flex flex-wrap gap-1.5">
                  {m.pieces.map((p, i) => (
                    <li key={p.id ?? `l${i}`}>
                      <a href={p.url} target="_blank" rel="noopener noreferrer" download={p.nom}
                        className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs text-slate-700 hover:bg-slate-50" data-testid="piece-jointe">
                        <Paperclip className="w-3 h-3" aria-hidden="true" />{p.nom}{p.taille ? <span className="text-slate-400"> {taille(p.taille)}</span> : null}
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </li>
        ))}
        <li ref={fin} aria-hidden="true" />
      </ol>
      {!enCorbeille && (
        <form className="border-t border-slate-100 p-3 space-y-2" onSubmit={(e) => { e.preventDefault(); if (corps.trim()) reponse.mutate(); }} data-testid="reponse">
          {groupe && (
            <div className="flex gap-1 text-xs" role="group" aria-label={t("Destinataires de la réponse")}>
              <button type="button" onClick={() => setATous(true)} aria-pressed={aTous} data-testid="repondre-tous"
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 ${aTous ? "bg-feba-navy text-white" : "bg-slate-100 text-slate-600"}`}>
                <ReplyAll className="w-3 h-3" />{t("Répondre à tous")}
              </button>
              <button type="button" onClick={() => setATous(false)} aria-pressed={!aTous} data-testid="repondre-expediteur"
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 ${!aTous ? "bg-feba-navy text-white" : "bg-slate-100 text-slate-600"}`}>
                <Reply className="w-3 h-3" />{t("Répondre à l'expéditeur")}
              </button>
            </div>
          )}
          <Pieces fichiers={fichiers} onRetirer={(i) => setFichiers(fichiers.filter((_, j) => j !== i))} />
          <div className="flex items-end gap-2">
            <label htmlFor="messagerie-reponse" className="sr-only">{t("Votre réponse")}</label>
            <textarea id="messagerie-reponse" rows={2} className="input flex-1 resize-none max-h-40" value={corps} onChange={(e) => setCorps(e.target.value)}
              placeholder={t("Écrire une réponse… (Ctrl + Entrée pour envoyer)")} data-testid="reponse-texte"
              onKeyDown={(e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && corps.trim()) reponse.mutate(); }} />
            <ChoixFichiers fichiers={fichiers} onChange={setFichiers} id="reponse-fichiers" />
            <button type="submit" className="btn-primary !px-3 flex items-center gap-1.5" disabled={!corps.trim() || reponse.isPending}
              aria-label={t("Envoyer")} data-testid="reponse-envoyer">
              {reponse.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              <span className="hidden sm:inline">{t("Envoyer")}</span>
            </button>
          </div>
        </form>
      )}
      <ConfirmDialog open={supprimer} onClose={() => setSupprimer(false)} loading={action.isPending}
        onConfirm={() => { setSupprimer(false); action.mutate(["supprimerDefinitivement"]); }}
        message={t("Supprimer définitivement cette conversation de VOTRE messagerie ? Les autres participants la conservent.")} />
    </div>
  );
}

function ListeBrouillons({ onOuvrir }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["messagerie", "brouillons"], queryFn: messageDraftsAPI.list });
  const [aSupprimer, setASupprimer] = useState(null);
  const supprimer = useMutation({
    mutationFn: (id) => messageDraftsAPI.delete(id),
    onSuccess: () => { setASupprimer(null); qc.invalidateQueries({ queryKey: ["messagerie"] }); toast.success(t("Brouillon supprimé.")); },
  });
  const lignes = data?.data || [];
  if (isLoading) return <p className="p-4 text-sm text-slate-400">{t("Chargement…")}</p>;
  if (!lignes.length) return <Vide icone={FileText} texte={t("Aucun brouillon.")} />;
  return (
    <>
      <ul className="divide-y divide-slate-50">
        {lignes.map((b) => (
          <li key={b.id} className="flex items-start gap-2 px-3 py-2.5 hover:bg-slate-50" data-testid={`brouillon-${b.id}`}>
            <button type="button" className="flex-1 min-w-0 text-left" onClick={() => onOuvrir(b)}>
              <p className="text-sm font-medium text-slate-800 truncate">{b.objet || t("(sans objet)")}</p>
              <p className="text-xs text-slate-500 truncate">{b.destinataires_detail.length ? noms(b.destinataires_detail) : t("Aucun destinataire")}</p>
              <p className="text-xs text-slate-400 truncate">{b.corps}</p>
            </button>
            <span className="text-[11px] text-slate-400 whitespace-nowrap">{dateCourte(b.modifie_le)}</span>
            <button type="button" className="p-1 text-slate-400 hover:text-red-700" onClick={() => setASupprimer(b)} aria-label={t("Supprimer le brouillon")}><Trash2 className="w-3.5 h-3.5" /></button>
          </li>
        ))}
      </ul>
      <ConfirmDialog open={!!aSupprimer} onClose={() => setASupprimer(null)} loading={supprimer.isPending}
        onConfirm={() => supprimer.mutate(aSupprimer.id)} message={t("Supprimer ce brouillon ?")} />
    </>
  );
}

function Vide({ icone: Icone, texte }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-center text-sm text-slate-400" data-testid="messagerie-vide">
      <Icone className="w-8 h-8 text-slate-300" aria-hidden="true" />{texte}
    </div>
  );
}

const VIDES = {
  reception: "Aucune conversation dans la boîte de réception.", envoyes: "Aucun message envoyé.",
  importants: "Aucune conversation marquée comme importante.", archives: "Aucune conversation archivée.",
  corbeille: "La corbeille est vide.",
};

export default function Messagerie() {
  useI18n();
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const ouverteUrl = Number(params.get("conversation")) || null;
  const [dossier, setDossier] = useState("reception");
  const [ouverte, setOuverte] = useState(ouverteUrl);
  const [saisie, setSaisie] = useState("");
  const q = useDiffere(saisie, 300);
  const [nonLus, setNonLus] = useState(false);
  const [correspondant, setCorrespondant] = useState("");
  const [composer, setComposer] = useState(null);          // null | { brouillon? }

  const filtres = Object.fromEntries(Object.entries({ dossier, q: q.trim(), non_lus: nonLus ? 1 : "", correspondant }).filter(([, v]) => v));
  const liste = useQuery({
    queryKey: ["messagerie", "liste", filtres], queryFn: () => conversationsAPI.list(filtres),
    enabled: dossier !== "brouillons", refetchInterval: 15000, refetchOnWindowFocus: true, placeholderData: keepPreviousData,
    // Toujours relue en changeant de dossier : un message arrivé entre-temps doit apparaître.
    staleTime: 0,
  });
  const compteurs = useQuery({ queryKey: ["messagerie", "compteurs"], queryFn: conversationsAPI.compteurs, refetchInterval: 15000, staleTime: 0 });
  const correspondants = useQuery({ queryKey: ["messagerie", "correspondants"], queryFn: conversationsAPI.correspondants });
  const conversations = liste.data?.data || [];
  const c = compteurs.data?.data || {};
  const badge = { reception: c.reception_non_lus, brouillons: c.brouillons };

  const ouvrir = (id) => {
    setOuverte(id);
    const suivant = new URLSearchParams(params);
    if (id) suivant.set("conversation", id); else suivant.delete("conversation");
    setParams(suivant, { replace: true });
  };
  const changerDossier = (d) => { setDossier(d); ouvrir(null); };
  const filtreActif = q || nonLus || correspondant;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{t("Messages")}</h1>
          <p className="text-sm text-slate-500">{t("Messagerie interne de l'académie")}</p>
        </div>
        <button type="button" className="btn-primary flex items-center gap-2" onClick={() => setComposer({})} data-testid="nouveau-message">
          <PenSquare className="w-4 h-4" />{t("Nouveau message")}
        </button>
      </div>

      <div className="card !p-0 overflow-hidden flex h-[calc(100vh-13rem)] min-h-[32rem]" data-testid="messagerie">
        {/* Colonne 1 : dossiers (ordinateur) */}
        <nav className="hidden lg:flex w-56 shrink-0 flex-col gap-0.5 border-r border-slate-100 p-2" aria-label={t("Dossiers")}>
          {DOSSIERS.map(([v, n, Icone]) => (
            <button key={v} type="button" onClick={() => changerDossier(v)} aria-current={dossier === v ? "page" : undefined} data-testid={`dossier-${v}`}
              className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${dossier === v ? "bg-feba-navy/10 text-feba-navy font-semibold" : "text-slate-600 hover:bg-slate-50"}`}>
              <Icone className="w-4 h-4" aria-hidden="true" /><span className="flex-1 text-left">{t(n)}</span>
              {badge[v] > 0 && <span className="rounded-full bg-feba-navy text-white text-[11px] px-1.5 min-w-[1.25rem] text-center" data-testid={`badge-${v}`}>{badge[v]}</span>}
            </button>
          ))}
        </nav>

        {/* Colonne 2 : conversations */}
        <section className={`${ouverte ? "hidden lg:flex" : "flex"} w-full lg:w-96 shrink-0 flex-col border-r border-slate-100 min-w-0`} aria-label={t("Conversations")}>
          <div className="lg:hidden flex gap-1.5 overflow-x-auto px-3 pt-3 pb-1" role="tablist" aria-label={t("Dossiers")}>
            {DOSSIERS.map(([v, n]) => (
              <button key={v} type="button" role="tab" aria-selected={dossier === v} onClick={() => changerDossier(v)}
                className={`whitespace-nowrap rounded-full px-3 py-1 text-xs ${dossier === v ? "bg-feba-navy text-white" : "bg-slate-100 text-slate-600"}`}>
                {t(n)}{badge[v] > 0 ? ` (${badge[v]})` : ""}
              </button>
            ))}
          </div>
          {dossier !== "brouillons" && (
            <div className="p-3 space-y-2 border-b border-slate-100">
              <label className="relative block">
                <span className="sr-only">{t("Rechercher dans les messages")}</span>
                <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true" />
                <input type="search" className="input pl-9 !py-1.5 text-sm" value={saisie} onChange={(e) => setSaisie(e.target.value)}
                  placeholder={t("Rechercher (objet, contenu, personne)…")} data-testid="messagerie-recherche" />
              </label>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <button type="button" onClick={() => setNonLus((x) => !x)} aria-pressed={nonLus} data-testid="filtre-non-lus"
                  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 ${nonLus ? "bg-feba-navy text-white" : "bg-slate-100 text-slate-600"}`}>
                  <MailOpen className="w-3 h-3" />{t("Non lus")}
                </button>
                <select className="input !py-0.5 !text-xs w-auto max-w-[12rem]" value={correspondant} onChange={(e) => setCorrespondant(e.target.value)}
                  aria-label={t("Correspondant")} data-testid="filtre-correspondant">
                  <option value="">{t("Tous les correspondants")}</option>
                  {(correspondants.data?.data || []).map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
                </select>
                {filtreActif && <button type="button" className="text-red-700 hover:underline" onClick={() => { setSaisie(""); setNonLus(false); setCorrespondant(""); }}>{t("Effacer")}</button>}
              </div>
            </div>
          )}
          <div className="flex-1 overflow-y-auto">
            {dossier === "brouillons" ? (
              <ListeBrouillons onOuvrir={(b) => setComposer({ brouillon: b })} />
            ) : liste.isLoading ? (
              <ul className="p-3 space-y-3" aria-label={t("Chargement…")}>{[0, 1, 2, 3].map((i) => <li key={i} className="h-14 rounded-xl bg-slate-100 animate-pulse" />)}</ul>
            ) : liste.isError ? (
              <p className="p-4 text-sm text-red-700" role="alert">{extractApiError(liste.error)}</p>
            ) : conversations.length === 0 ? (
              <Vide icone={Inbox} texte={filtreActif ? t("Aucune conversation ne correspond à cette recherche.") : t(VIDES[dossier])} />
            ) : (
              <ul className="divide-y divide-slate-50" data-testid="conversations">
                {conversations.map((cv) => {
                  const nonLu = cv.unread_count > 0;
                  return (
                    <li key={cv.id}>
                      <button type="button" onClick={() => ouvrir(cv.id)} aria-current={ouverte === cv.id ? "true" : undefined}
                        className={`w-full flex gap-3 px-3 py-2.5 text-left transition-colors ${ouverte === cv.id ? "bg-feba-navy/5" : "hover:bg-slate-50"}`}
                        data-testid={`conversation-${cv.id}`}>
                        <Avatar personne={cv.correspondants[0]} />
                        <span className="flex-1 min-w-0">
                          <span className="flex items-center gap-1">
                            <span className={`flex-1 truncate text-sm ${nonLu ? "font-semibold text-slate-900" : "text-slate-700"}`}>
                              {noms(cv.correspondants) || t("Vous")}{cv.correspondants.length > 1 ? ` (${cv.correspondants.length})` : ""}
                            </span>
                            <span className={`text-[11px] whitespace-nowrap ${nonLu ? "text-feba-navy font-semibold" : "text-slate-400"}`}>{dateCourte(cv.latest_message?.sent_at || cv.updated_at)}</span>
                          </span>
                          <span className="flex items-center gap-1">
                            <span className={`flex-1 truncate text-sm ${nonLu ? "font-semibold text-slate-800" : "text-slate-600"}`}>{cv.subject}</span>
                            {cv.important && <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-500" aria-label={t("Important")} />}
                            {cv.a_pieces && <Paperclip className="w-3.5 h-3.5 text-slate-400" aria-label={t("Pièces jointes")} />}
                            {nonLu && <span className="w-2 h-2 rounded-full bg-feba-navy" aria-label={t("{n} non lu(s)", { n: cv.unread_count })} data-testid="non-lu" />}
                          </span>
                          <span className="block truncate text-xs text-slate-400">
                            {cv.latest_message?.is_mine ? `${t("Vous")} : ` : ""}{cv.latest_message?.body}
                          </span>
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </section>

        {/* Colonne 3 : lecture */}
        <section className={`${ouverte ? "flex" : "hidden lg:flex"} flex-1 min-w-0`} aria-label={t("Lecture")}>
          {ouverte ? (
            <Fil key={ouverte} id={ouverte} onRetour={() => ouvrir(null)} onOuvrir={ouvrir} />
          ) : (
            <div className="flex-1"><Vide icone={Mail} texte={t("Sélectionnez une conversation pour la lire.")} /></div>
          )}
        </section>
      </div>

      <Composition ouvert={composer !== null} brouillon={composer?.brouillon}
        onFermer={(id) => { setComposer(null); qc.invalidateQueries({ queryKey: ["messagerie"] }); if (id) { setDossier("envoyes"); ouvrir(id); } }} />
    </div>
  );
}
