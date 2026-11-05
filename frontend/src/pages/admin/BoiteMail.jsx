/**
 * Boîte mail contact@globalfeba.com — vraie boîte professionnelle (Hostinger, IMAP).
 *
 * Trois zones sur ordinateur : dossiers, liste, lecture ; un panneau à la fois sur mobile.
 * Toutes les données viennent du serveur, qui synchronise la boîte réelle et applique
 * chaque action CHEZ LE FOURNISSEUR avant de la refléter ici. L'onglet « Journal
 * technique des envois » conserve l'ancienne boîte d'envoi (diagnostic SMTP, relances).
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import {
  AlertTriangle, Archive, ArrowLeft, FileText, Forward, Image as ImageIcon, Inbox, Loader2, Mail, MailOpen,
  Paperclip, PenSquare, RefreshCw, Reply, ReplyAll, RotateCcw, Search, Send, ShieldCheck, Star, Trash2, X,
} from "lucide-react";
import { boiteMailAPI } from "../../api";
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import EditeurMessage from "../../components/email/EditeurMessage";
import { useDiffere } from "../../hooks/useDiffere";
import { dateLocale, t, useI18n } from "../../i18n";
import { extractApiError } from "../../utils/errors";
import Outbox from "./Outbox";

const DOSSIERS = [
  ["reception", "Boîte de réception", Inbox], ["envoyes", "Messages envoyés", Send], ["brouillons", "Brouillons", FileText],
  ["importants", "Importants", Star], ["archives", "Archivés", Archive], ["corbeille", "Corbeille", Trash2],
  ["indesirables", "Indésirables", AlertTriangle],
];

export function dateListe(iso, maintenant = new Date()) {
  const d = new Date(iso);
  if (d.toDateString() === maintenant.toDateString()) return d.toLocaleTimeString(dateLocale(), { hour: "2-digit", minute: "2-digit" });
  return d.toLocaleDateString(dateLocale(), { day: "2-digit", month: "short", ...(d.getFullYear() !== maintenant.getFullYear() ? { year: "numeric" } : {}) });
}
const personne = (p) => (p?.nom ? `${p.nom} <${p.email}>` : p?.email || "");
const taille = (n) => (n < 1024 ? `${n} o` : n < 1048576 ? `${Math.round(n / 1024)} Ko` : `${(n / 1048576).toFixed(1)} Mo`);

function telecharger(blob, nom) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nom;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function Composer({ ouvert, contexte, onFermer }) {
  // contexte : { mode, origine (détail du message) } ; mode = nouveau | repondre | repondre_tous | transferer
  const qc = useQueryClient();
  const [cle, setCle] = useState(null);
  const [a, setA] = useState("");
  const [cc, setCc] = useState("");
  const [cci, setCci] = useState("");
  const [sujet, setSujet] = useState("");
  const [format, setFormat] = useState("texte");
  const [texte, setTexte] = useState("");
  const [html, setHtml] = useState("");
  const [fichiers, setFichiers] = useState([]);
  const nouvelleCle = ouvert ? `${contexte?.mode}:${contexte?.origine?.id ?? ""}` : null;
  if (nouvelleCle !== cle) {
    setCle(nouvelleCle);
    const o = contexte?.origine;
    const mode = contexte?.mode;
    const prefixe = mode === "transferer" ? "Tr: " : mode && mode !== "nouveau" ? "Re: " : "";
    const citation = o ? `\n\n----- ${t("Message d'origine")} -----\n${t("De")} : ${personne(o.expediteur)}\n${t("Date")} : ${new Date(o.date).toLocaleString(dateLocale())}\n${t("Objet")} : ${o.sujet}\n\n${o.texte || ""}` : "";
    const adresse = (x) => x?.email;
    setA(mode === "repondre" || mode === "repondre_tous" ? (o.repondre_a || o.expediteur?.email || "") : "");
    setCc(mode === "repondre_tous" ? [...(o.a || []), ...(o.cc || [])].map(adresse).filter((e) => e && e !== contexte?.adresse).join(", ") : "");
    setCci(""); setSujet(o ? (o.sujet.startsWith(prefixe.trim()) ? o.sujet : `${prefixe}${o.sujet}`) : "");
    setFormat("texte"); setTexte(citation); setHtml(""); setFichiers([]);
  }
  const envoi = useMutation({
    mutationFn: () => {
      const fd = new FormData();
      fd.append("mode", contexte?.mode || "nouveau");
      if (contexte?.origine) fd.append("origine", contexte.origine.id);
      const decoupe = (v) => v.split(/[,;\s]+/).filter(Boolean);
      decoupe(a).forEach((x) => fd.append("a", x));
      decoupe(cc).forEach((x) => fd.append("cc", x));
      decoupe(cci).forEach((x) => fd.append("cci", x));
      fd.append("sujet", sujet);
      if (format === "html") fd.append("html", html); else fd.append("texte", texte);
      fichiers.forEach((f) => fd.append("attachments", f));
      return boiteMailAPI.envoyer(fd);
    },
    onSuccess: (rep) => {
      if (rep.status === 202) toast(t("Le serveur d'envoi n'a pas encore accepté le message : nouvel essai automatique."));
      else toast.success(t("Message envoyé depuis contact@globalfeba.com."));
      qc.invalidateQueries({ queryKey: ["boite-mail"] });
      onFermer();
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const titre = { nouveau: "Nouveau message", repondre: "Répondre", repondre_tous: "Répondre à tous", transferer: "Transférer" }[contexte?.mode || "nouveau"];
  const pret = a.trim() && sujet.trim() && (format === "html" ? html.replace(/<[^>]*>/g, "").trim() : texte.trim());
  return (
    <Modal open={ouvert} onClose={() => !envoi.isPending && onFermer()} title={t(titre)} size="xl">
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (pret) envoi.mutate(); }} data-testid="bm-composer">
        <p className="text-xs text-slate-500">{t("Depuis")} <strong>contact@globalfeba.com</strong></p>
        {[["À", a, setA, "bm-a"], ["Cc", cc, setCc, "bm-cc"], ["Cci", cci, setCci, "bm-cci"]].map(([n, v, set, id]) => (
          <label key={id} className="flex items-center gap-2 border-b border-slate-100 pb-1">
            <span className="w-10 text-sm text-slate-500">{t(n)}</span>
            <input className="flex-1 bg-transparent text-sm outline-none py-1" value={v} onChange={(e) => set(e.target.value)}
              placeholder={t("adresses séparées par des virgules")} data-testid={id} />
          </label>
        ))}
        <div>
          <label className="label" htmlFor="bm-sujet">{t("Objet")}</label>
          <input id="bm-sujet" className="input" value={sujet} maxLength={250} onChange={(e) => setSujet(e.target.value)} />
        </div>
        <EditeurMessage id="bm-corps" format={format} onFormat={setFormat} texte={texte} onTexte={setTexte} html={html} onHtml={setHtml} />
        {contexte?.mode === "transferer" && contexte?.origine?.pieces?.length > 0 && (
          <p className="text-xs text-slate-500">{t("Pièces jointes transférées")} : {contexte.origine.pieces.map((p) => p.nom).join(", ")}</p>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <label className="btn-secondary text-sm cursor-pointer inline-flex items-center gap-1">
            <Paperclip className="w-4 h-4" />{t("Joindre")}
            <input type="file" multiple className="sr-only" onChange={(e) => { setFichiers([...fichiers, ...e.target.files]); e.target.value = ""; }} />
          </label>
          {fichiers.map((f, i) => (
            <span key={`${f.name}-${i}`} className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs">
              {f.name} <button type="button" onClick={() => setFichiers(fichiers.filter((_, j) => j !== i))} aria-label={t("Retirer {n}", { n: f.name })}><X className="w-3 h-3" /></button>
            </span>
          ))}
          <button type="submit" className="btn-primary ml-auto inline-flex items-center gap-2" disabled={!pret || envoi.isPending} data-testid="bm-envoyer">
            {envoi.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            {envoi.isPending ? t("Envoi…") : t("Envoyer")}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function Acces({ ouvert, onFermer }) {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["boite-mail", "acces"], queryFn: boiteMailAPI.acces, enabled: ouvert });
  const maj = useMutation({
    mutationFn: boiteMailAPI.majAcces,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["boite-mail", "acces"] }),
    onError: (e) => toast.error(extractApiError(e)),
  });
  const lignes = data?.data || [];
  return (
    <Modal open={ouvert} onClose={onFermer} title={t("Accès à la boîte contact")} size="lg">
      <p className="text-sm text-slate-600 mb-3">{t("Le super administrateur a tous les droits. Seuls des administrateurs d'académie peuvent recevoir un accès ; chaque action sensible est journalisée.")}</p>
      {lignes.length === 0 ? <p className="text-sm text-slate-400">{t("Aucun administrateur.")}</p> : (
        <table className="w-full text-sm" data-testid="bm-acces">
          <thead><tr className="text-left text-xs text-slate-500"><th className="py-1">{t("Administrateur")}</th><th>{t("Lire")}</th><th>{t("Écrire / répondre")}</th><th>{t("Supprimer")}</th></tr></thead>
          <tbody>
            {lignes.map((u) => (
              <tr key={u.id} className="border-t border-slate-100">
                <td className="py-1.5">{u.nom}<span className="block text-xs text-slate-400">{u.email} · {u.academie}</span></td>
                {["lire", "envoyer", "supprimer"].map((d) => (
                  <td key={d}><input type="checkbox" checked={u[d]} disabled={d !== "lire" && !u.lire} aria-label={`${t(d)} ${u.nom}`}
                    onChange={(e) => maj.mutate({ utilisateur: u.id, ...u, [d]: e.target.checked, ...(d === "lire" && !e.target.checked ? { envoyer: false, supprimer: false } : {}) })} /></td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Modal>
  );
}

function Lecture({ id, droits, onRetour, onComposer }) {
  const qc = useQueryClient();
  const [images, setImages] = useState(false);
  const [supprimer, setSupprimer] = useState(false);
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["boite-mail", "message", id, images], queryFn: () => boiteMailAPI.message(id, images), staleTime: 0,
  });
  const m = data?.data;
  const action = useMutation({
    mutationFn: (a) => boiteMailAPI.action(id, a),
    onSuccess: (_r, a) => {
      qc.invalidateQueries({ queryKey: ["boite-mail"] });
      if (["archiver", "corbeille", "restaurer", "supprimer_definitivement"].includes(a)) {
        toast.success({ archiver: t("Message archivé."), corbeille: t("Message placé dans la corbeille."), restaurer: t("Message restauré."),
          supprimer_definitivement: t("Message supprimé définitivement.") }[a]);
        onRetour();
      }
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  // Ouvrir un message non lu le marque comme lu CHEZ LE FOURNISSEUR (comme un logiciel de messagerie).
  const marque = useRef(null);
  const { mutate } = action;
  useEffect(() => {
    if (m && !m.lu && marque.current !== m.id) {
      marque.current = m.id;
      mutate("lu");
    }
  }, [m, mutate]);
  if (isLoading) return <div className="flex-1 grid place-items-center"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>;
  if (isError) return <div className="flex-1 grid place-items-center text-sm text-red-700" role="alert">{extractApiError(error)}</div>;
  const btn = "p-2 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-800 transition-colors disabled:opacity-40";
  const corbeille = m.dossier === "corbeille";
  return (
    <article className="flex-1 flex flex-col min-w-0 animate-apparition" data-testid="bm-lecture">
      <header className="border-b border-slate-100 px-4 py-3 space-y-2">
        <div className="flex items-start gap-2">
          <button type="button" className={`${btn} lg:hidden`} onClick={onRetour} aria-label={t("Retour à la liste")}><ArrowLeft className="w-4 h-4" /></button>
          <h2 className="flex-1 min-w-0 text-lg font-semibold text-slate-900 break-words" data-testid="bm-sujet-lu">{m.sujet}</h2>
          <div className="flex flex-wrap gap-0.5" role="toolbar" aria-label={t("Actions")}>
            {droits.envoyer && m.dossier !== "envoyes" && <>
              <button type="button" className={btn} title={t("Répondre")} aria-label={t("Répondre")} onClick={() => onComposer("repondre", m)} data-testid="bm-repondre"><Reply className="w-4 h-4" /></button>
              <button type="button" className={btn} title={t("Répondre à tous")} aria-label={t("Répondre à tous")} onClick={() => onComposer("repondre_tous", m)}><ReplyAll className="w-4 h-4" /></button>
            </>}
            {droits.envoyer && <button type="button" className={btn} title={t("Transférer")} aria-label={t("Transférer")} onClick={() => onComposer("transferer", m)} data-testid="bm-transferer"><Forward className="w-4 h-4" /></button>}
            <button type="button" className={btn} title={m.important ? t("Retirer des importants") : t("Marquer comme important")} aria-pressed={m.important}
              onClick={() => action.mutate(m.important ? "non_important" : "important")} data-testid="bm-important">
              <Star className={`w-4 h-4 ${m.important ? "fill-amber-400 text-amber-500" : ""}`} />
            </button>
            <button type="button" className={btn} title={t("Marquer comme non lu")} aria-label={t("Marquer comme non lu")} onClick={() => { action.mutate("non_lu"); onRetour(); }}><Mail className="w-4 h-4" /></button>
            {m.dossier === "reception" && <button type="button" className={btn} title={t("Archiver")} aria-label={t("Archiver")} onClick={() => action.mutate("archiver")} data-testid="bm-archiver"><Archive className="w-4 h-4" /></button>}
            {["archives", "corbeille", "indesirables"].includes(m.dossier) && (
              <button type="button" className={btn} title={t("Restaurer")} aria-label={t("Restaurer")} onClick={() => action.mutate("restaurer")} data-testid="bm-restaurer"><RotateCcw className="w-4 h-4" /></button>
            )}
            {droits.supprimer && (corbeille
              ? <button type="button" className={`${btn} hover:text-red-700`} title={t("Supprimer définitivement")} aria-label={t("Supprimer définitivement")} onClick={() => setSupprimer(true)}><Trash2 className="w-4 h-4" /></button>
              : <button type="button" className={`${btn} hover:text-red-700`} title={t("Placer dans la corbeille")} aria-label={t("Placer dans la corbeille")} onClick={() => action.mutate("corbeille")} data-testid="bm-corbeille"><Trash2 className="w-4 h-4" /></button>)}
          </div>
        </div>
        <dl className="text-xs text-slate-600 grid grid-cols-[auto,1fr] gap-x-2 gap-y-0.5">
          <dt className="text-slate-400">{t("De")}</dt><dd className="break-all">{personne(m.expediteur)}</dd>
          <dt className="text-slate-400">{t("À")}</dt><dd className="break-all">{(m.a || []).map(personne).join(", ") || "-"}</dd>
          {m.cc?.length > 0 && <><dt className="text-slate-400">{t("Cc")}</dt><dd className="break-all">{m.cc.map(personne).join(", ")}</dd></>}
          {m.cci?.length > 0 && <><dt className="text-slate-400">{t("Cci")}</dt><dd className="break-all">{m.cci.map(personne).join(", ")}</dd></>}
          <dt className="text-slate-400">{t("Date")}</dt><dd>{new Date(m.date).toLocaleString(dateLocale(), { dateStyle: "full", timeStyle: "short" })}</dd>
          {m.source === "feba" && <><dt className="text-slate-400">{t("Origine")}</dt><dd>{t("Envoyé depuis FEBA")}{m.origine ? ` (${m.origine})` : ""}{m.statut_envoi ? ` · ${m.statut_envoi}` : ""}</dd></>}
        </dl>
      </header>
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {m.a_images_distantes && (
          <button type="button" className="mb-3 inline-flex items-center gap-1.5 rounded-lg bg-amber-50 border border-amber-200 px-3 py-1.5 text-xs text-amber-900"
            onClick={() => setImages(true)} data-testid="bm-images">
            <ImageIcon className="w-3.5 h-3.5" />{t("Images distantes masquées (protection contre le pistage). Les afficher")}
          </button>
        )}
        {m.html
          // HTML nettoyé par le serveur (liste blanche nh3) : aucun script ni gestionnaire d'événement.
          ? <div className="prose-sm max-w-none text-slate-800 text-wrapsafe [&_a]:text-primary [&_a]:underline [&_img]:max-w-full [&_table]:max-w-full"
            dangerouslySetInnerHTML={{ __html: m.html }} data-testid="bm-html" />
          : <pre className="whitespace-pre-wrap font-sans text-sm text-slate-800 text-wrapsafe" data-testid="bm-texte">{m.texte}</pre>}
        {m.pieces?.length > 0 && (
          <ul className="mt-4 flex flex-wrap gap-2" aria-label={t("Pièces jointes")}>
            {m.pieces.map((p) => (
              <li key={p.id}>
                <button type="button" disabled={p.non_copiee} data-testid="bm-piece"
                  title={p.non_copiee ? t("Pièce trop volumineuse : consultable dans la boîte du fournisseur.") : t("Télécharger")}
                  onClick={async () => { try { telecharger((await boiteMailAPI.piece(p.id)).data, p.nom); } catch (e) { toast.error(extractApiError(e)); } }}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50">
                  <Paperclip className="w-3.5 h-3.5" />{p.nom}<span className="text-slate-400">{taille(p.taille)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <ConfirmDialog open={supprimer} onClose={() => setSupprimer(false)} loading={action.isPending}
        onConfirm={() => { setSupprimer(false); action.mutate("supprimer_definitivement"); }}
        message={t("Supprimer définitivement ce message de la boîte contact@globalfeba.com ? Cette action est irréversible.")} />
    </article>
  );
}

function Boite({ etat }) {
  useI18n();
  const qc = useQueryClient();
  const droits = etat.droits;
  const [dossier, setDossier] = useState("reception");
  const [ouvert, setOuvert] = useState(null);
  const [saisie, setSaisie] = useState("");
  const q = useDiffere(saisie, 300);
  const [nonLus, setNonLus] = useState(false);
  const [pieces, setPieces] = useState(false);
  const [page, setPage] = useState(1);
  const [choisis, setChoisis] = useState([]);
  const [composer, setComposer] = useState(null);
  const [acces, setAcces] = useState(false);
  const params = Object.fromEntries(Object.entries({ dossier, q: q.trim(), non_lus: nonLus ? 1 : "", pieces: pieces ? 1 : "", page }).filter(([, v]) => v));
  const liste = useQuery({ queryKey: ["boite-mail", "liste", params], queryFn: () => boiteMailAPI.messages(params),
    placeholderData: keepPreviousData, staleTime: 0, refetchInterval: 60000 });
  const r = liste.data?.data;
  const lignes = r?.results || [];
  const synchro = useMutation({
    mutationFn: boiteMailAPI.synchroniser,
    onSuccess: (rep) => { qc.invalidateQueries({ queryKey: ["boite-mail"] }); toast.success(t("Boîte actualisée : {n} nouveau(x) message(s).", { n: rep.data.nouveaux ?? 0 })); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const groupe = useMutation({
    mutationFn: (a) => boiteMailAPI.actions(choisis, a),
    onSuccess: () => { setChoisis([]); qc.invalidateQueries({ queryKey: ["boite-mail"] }); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const changerDossier = (d) => { setDossier(d); setOuvert(null); setPage(1); setChoisis([]); };
  const compteur = (d) => (d === "importants" ? null : etat.non_lus?.[d]);
  const derniere = useMemo(() => etat.synchro?.map((s) => s.derniere_synchro).filter(Boolean).sort().at(-1), [etat]);
  const erreurSynchro = etat.synchro?.find((s) => s.derniere_erreur);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm text-slate-600 flex items-center gap-1.5"><ShieldCheck className="w-4 h-4 text-emerald-600" />
          <strong>{etat.adresse}</strong> · {etat.fournisseur}{derniere ? ` · ${t("synchronisée le {d}", { d: new Date(derniere).toLocaleString(dateLocale()) })}` : ""}</p>
        <div className="ml-auto flex gap-2">
          {droits.gerer && <button type="button" className="btn-secondary text-sm" onClick={() => setAcces(true)} data-testid="bm-gerer">{t("Gérer les accès")}</button>}
          <button type="button" className="btn-secondary text-sm inline-flex items-center gap-1.5" onClick={() => synchro.mutate()} disabled={synchro.isPending} data-testid="bm-actualiser">
            <RefreshCw className={`w-4 h-4 ${synchro.isPending ? "animate-spin" : ""}`} />{t("Actualiser")}
          </button>
          {droits.envoyer && <button type="button" className="btn-primary text-sm inline-flex items-center gap-1.5" onClick={() => setComposer({ mode: "nouveau" })} data-testid="bm-nouveau">
            <PenSquare className="w-4 h-4" />{t("Nouveau message")}</button>}
        </div>
      </div>
      {erreurSynchro && <p className="text-xs text-amber-800" role="status">{t("Dernière synchronisation incomplète")} ({erreurSynchro.dossier_imap}).</p>}
      <div className="card !p-0 overflow-hidden flex h-[calc(100vh-15rem)] min-h-[32rem]" data-testid="boite-mail">
        <nav className="hidden lg:flex w-56 shrink-0 flex-col gap-0.5 border-r border-slate-100 p-2" aria-label={t("Dossiers")}>
          {DOSSIERS.map(([v, n, Icone]) => (
            <button key={v} type="button" onClick={() => changerDossier(v)} aria-current={dossier === v ? "page" : undefined} data-testid={`bm-dossier-${v}`}
              className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${dossier === v ? "bg-feba-navy/10 text-feba-navy font-semibold" : "text-slate-600 hover:bg-slate-50"}`}>
              <Icone className="w-4 h-4" aria-hidden="true" /><span className="flex-1 text-left">{t(n)}</span>
              {compteur(v) > 0 && <span className="rounded-full bg-feba-navy text-white text-[11px] px-1.5 min-w-[1.25rem] text-center">{compteur(v)}</span>}
            </button>
          ))}
        </nav>
        <section className={`${ouvert ? "hidden lg:flex" : "flex"} w-full lg:w-[26rem] shrink-0 flex-col border-r border-slate-100 min-w-0`} aria-label={t("Messages")}>
          <div className="lg:hidden flex gap-1.5 overflow-x-auto px-3 pt-3" role="tablist">
            {DOSSIERS.map(([v, n]) => (
              <button key={v} type="button" role="tab" aria-selected={dossier === v} onClick={() => changerDossier(v)}
                className={`whitespace-nowrap rounded-full px-3 py-1 text-xs ${dossier === v ? "bg-feba-navy text-white" : "bg-slate-100 text-slate-600"}`}>{t(n)}</button>
            ))}
          </div>
          <div className="p-3 space-y-2 border-b border-slate-100">
            <label className="relative block">
              <span className="sr-only">{t("Rechercher")}</span>
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input type="search" className="input pl-9 !py-1.5 text-sm" value={saisie} onChange={(e) => { setSaisie(e.target.value); setPage(1); }}
                placeholder={t("Expéditeur, destinataire, objet, contenu…")} data-testid="bm-recherche" />
            </label>
            <div className="flex flex-wrap items-center gap-1.5 text-xs">
              <button type="button" onClick={() => { setNonLus((x) => !x); setPage(1); }} aria-pressed={nonLus} data-testid="bm-non-lus"
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 ${nonLus ? "bg-feba-navy text-white" : "bg-slate-100 text-slate-600"}`}><MailOpen className="w-3 h-3" />{t("Non lus")}</button>
              <button type="button" onClick={() => { setPieces((x) => !x); setPage(1); }} aria-pressed={pieces}
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 ${pieces ? "bg-feba-navy text-white" : "bg-slate-100 text-slate-600"}`}><Paperclip className="w-3 h-3" />{t("Avec pièces jointes")}</button>
              <span className="ml-auto text-slate-400">{r ? t("{n} message(s)", { n: r.count }) : ""}</span>
            </div>
            {choisis.length > 0 && (
              <div className="flex flex-wrap gap-1.5 text-xs" data-testid="bm-groupe">
                <span className="text-slate-500">{t("{n} sélectionné(s)", { n: choisis.length })}</span>
                {[["lu", "Marquer lus"], ["non_lu", "Marquer non lus"], ["archiver", "Archiver"], ...(droits.supprimer ? [["corbeille", "Corbeille"]] : [])].map(([a, n]) => (
                  <button key={a} type="button" className="rounded-full bg-slate-100 px-2 py-0.5 hover:bg-slate-200" onClick={() => groupe.mutate(a)} disabled={groupe.isPending}>{t(n)}</button>
                ))}
              </div>
            )}
          </div>
          <div className="flex-1 overflow-y-auto">
            {liste.isLoading ? <ul className="p-3 space-y-3">{[0, 1, 2, 3].map((i) => <li key={i} className="h-14 rounded-xl bg-slate-100 animate-pulse" />)}</ul>
              : liste.isError ? <p className="p-4 text-sm text-red-700" role="alert">{extractApiError(liste.error)}</p>
                : lignes.length === 0 ? (
                  <div className="flex flex-col items-center gap-2 py-16 text-center text-sm text-slate-400" data-testid="bm-vide">
                    <Inbox className="w-8 h-8 text-slate-300" />{q || nonLus || pieces ? t("Aucun message ne correspond.") : t("Ce dossier est vide.")}
                  </div>
                ) : (
                  <ul className="divide-y divide-slate-50" data-testid="bm-liste">
                    {lignes.map((m) => (
                      <li key={m.id} className={`flex items-start gap-2 px-3 py-2.5 ${ouvert === m.id ? "bg-feba-navy/5" : "hover:bg-slate-50"}`}>
                        <input type="checkbox" className="mt-1" checked={choisis.includes(m.id)} aria-label={t("Sélectionner")}
                          onChange={() => setChoisis((c) => (c.includes(m.id) ? c.filter((x) => x !== m.id) : [...c, m.id]))} />
                        <button type="button" className="flex-1 min-w-0 text-left" onClick={() => setOuvert(m.id)} data-testid={`bm-message-${m.id}`}>
                          <span className="flex items-center gap-1">
                            <span className={`flex-1 truncate text-sm ${m.lu ? "text-slate-700" : "font-semibold text-slate-900"}`}>
                              {dossier === "envoyes" ? `${t("À")} : ${(m.a || []).map((p) => p.nom || p.email).join(", ")}` : (m.expediteur.nom || m.expediteur.email)}
                            </span>
                            <span className={`text-[11px] whitespace-nowrap ${m.lu ? "text-slate-400" : "text-feba-navy font-semibold"}`}>{dateListe(m.date)}</span>
                          </span>
                          <span className="flex items-center gap-1">
                            <span className={`flex-1 truncate text-sm ${m.lu ? "text-slate-600" : "font-semibold text-slate-800"}`}>{m.sujet}</span>
                            {m.important && <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-500" aria-label={t("Important")} />}
                            {m.nb_pieces > 0 && <Paperclip className="w-3.5 h-3.5 text-slate-400" aria-label={t("Pièces jointes")} />}
                            {!m.lu && <span className="w-2 h-2 rounded-full bg-feba-navy" aria-label={t("Non lu")} data-testid="bm-non-lu" />}
                          </span>
                          <span className="block truncate text-xs text-slate-400">{m.extrait}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
          </div>
          {r && r.pages > 1 && (
            <div className="flex items-center justify-between border-t border-slate-100 px-3 py-2 text-xs text-slate-600">
              <button type="button" className="btn-secondary !py-1 !px-2" disabled={page <= 1} onClick={() => setPage(page - 1)}>{t("Précédent")}</button>
              <span>{page} / {r.pages}</span>
              <button type="button" className="btn-secondary !py-1 !px-2" disabled={page >= r.pages} onClick={() => setPage(page + 1)}>{t("Suivant")}</button>
            </div>
          )}
        </section>
        <section className={`${ouvert ? "flex" : "hidden lg:flex"} flex-1 min-w-0`} aria-label={t("Lecture")}>
          {ouvert ? <Lecture key={ouvert} id={ouvert} droits={droits} onRetour={() => setOuvert(null)}
            onComposer={(mode, origine) => setComposer({ mode, origine })} />
            : <div className="flex-1 flex flex-col items-center justify-center gap-2 text-sm text-slate-400"><Mail className="w-8 h-8 text-slate-300" />{t("Sélectionnez un message pour le lire.")}</div>}
        </section>
      </div>
      <Composer ouvert={composer !== null} contexte={composer ? { ...composer, adresse: etat.adresse } : null} onFermer={() => setComposer(null)} />
      <Acces ouvert={acces} onFermer={() => setAcces(false)} />
    </div>
  );
}

export default function BoiteMail() {
  useI18n();
  const [onglet, setOnglet] = useState("boite");
  const { data, isLoading } = useQuery({ queryKey: ["boite-mail", "etat"], queryFn: boiteMailAPI.etat, refetchInterval: 60000 });
  const etat = data?.data;
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">{t("Boîte mail contact")}</h1>
        <p className="text-sm text-slate-500">{t("Messages reçus et envoyés par l'adresse officielle contact@globalfeba.com")}</p>
      </div>
      <div className="flex gap-1 border-b border-slate-200" role="tablist">
        {[["boite", "Boîte mail"], ["journal", "Journal technique des envois"]].map(([v, n]) => (
          <button key={v} type="button" role="tab" aria-selected={onglet === v} onClick={() => setOnglet(v)} data-testid={`bm-onglet-${v}`}
            className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px ${onglet === v ? "border-feba-navy text-feba-navy" : "border-transparent text-slate-500 hover:text-slate-800"}`}>{t(n)}</button>
        ))}
      </div>
      {onglet === "journal" ? <Outbox integre /> : isLoading ? (
        <div className="h-64 rounded-xl bg-slate-100 animate-pulse" />
      ) : !etat?.acces ? (
        <div className="card text-sm text-slate-600" data-testid="bm-sans-acces">{t("Vous n'avez pas accès à la boîte contact@globalfeba.com. Le super administrateur peut vous l'accorder.")}</div>
      ) : !etat.configuree ? (
        <div className="card text-sm text-amber-800 bg-amber-50 border-amber-200" data-testid="bm-non-configuree">{t("La connexion à la boîte contact n'est pas configurée sur ce serveur.")}</div>
      ) : <Boite etat={etat} />}
    </div>
  );
}
