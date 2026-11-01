/**
 * Passage d'une épreuve. Le serveur tient l'heure : le compte à rebours se recale
 * sur sa réponse. Chaque réponse est sauvegardée, et réessayée après une coupure.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { CheckCircle2, CloudOff } from "lucide-react";
import { evaluationsAPI } from "../../../api";
import ConfirmDialog from "../../../components/ui/ConfirmDialog";
import { extractApiError } from "../../../utils/errors";
import { t } from "../../../i18n";

const format = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
const remplie = (v) => v !== null && v !== undefined && v !== "" && !(Array.isArray(v) && (v.length === 0 || v.every((x) => !x))) && !(typeof v === "object" && !Array.isArray(v) && Object.keys(v).length === 0);

function Champ({ q, valeur, changer }) {
  const c = q.contenu || {};
  if (q.type === "qcm_unique") {
    return c.choix.map((o) => <label key={o.id} className="flex items-center gap-2 text-sm py-1"><input type="radio" name={`q${q.version}`} checked={valeur === o.id} onChange={() => changer(o.id)} />{o.texte}</label>);
  }
  if (q.type === "qcm_multiple") {
    const liste = valeur || [];
    return c.choix.map((o) => <label key={o.id} className="flex items-center gap-2 text-sm py-1"><input type="checkbox" checked={liste.includes(o.id)} onChange={(e) => changer(e.target.checked ? [...liste, o.id] : liste.filter((x) => x !== o.id))} />{o.texte}</label>);
  }
  if (q.type === "vrai_faux") {
    return [[true, t("Vrai")], [false, t("Faux")]].map(([v, l]) => <label key={l} className="flex items-center gap-2 text-sm py-1"><input type="radio" name={`q${q.version}`} checked={valeur === v} onChange={() => changer(v)} />{l}</label>);
  }
  if (q.type === "ouverte") return <textarea aria-label={t("Votre réponse")} className="input" rows={8} value={valeur || ""} onChange={(e) => changer(e.target.value)} />;
  if (q.type === "courte" || q.type === "numerique") return <input aria-label={t("Votre réponse")} className="input" inputMode={q.type === "numerique" ? "decimal" : "text"} value={valeur ?? ""} onChange={(e) => changer(e.target.value)} />;
  if (q.type === "trous") {
    const liste = valeur || [];
    return Array.from({ length: c.nombre_trous || 0 }, (_, i) => (
      <div key={i} className="py-1"><label className="label" htmlFor={`t${q.version}-${i}`}>{t("Trou {n}", { n: i + 1 })}</label>
        <input id={`t${q.version}-${i}`} className="input" value={liste[i] || ""} onChange={(e) => { const n = [...liste]; n[i] = e.target.value; changer(n); }} /></div>
    ));
  }
  if (q.type === "association") {
    const paires = valeur || {};
    return c.gauche.map((g) => (
      <div key={g.id} className="flex flex-wrap items-center gap-2 py-1 text-sm"><label className="flex-1 min-w-32" htmlFor={`a${g.id}`}>{g.texte}</label>
        <select id={`a${g.id}`} className="input w-auto" value={paires[g.id] || ""} onChange={(e) => changer({ ...paires, [g.id]: e.target.value })}>
          <option value="">{t("Choisir")}</option>{c.droite.map((d) => <option key={d.id} value={d.id}>{d.texte}</option>)}
        </select></div>
    ));
  }
  if (q.type === "classement") {
    const ids = valeur?.length ? valeur : c.elements.map((e) => e.id);
    const texte = Object.fromEntries(c.elements.map((e) => [e.id, e.texte]));
    const bouger = (i, d) => { const n = [...ids]; [n[i], n[i + d]] = [n[i + d], n[i]]; changer(n); };
    return <ol className="space-y-1">{ids.map((id, i) => (
      <li key={id} className="flex items-center gap-2 text-sm border border-slate-200 rounded p-2"><span className="flex-1">{i + 1}. {texte[id]}</span>
        <button type="button" className="btn-secondary text-xs" disabled={i === 0} aria-label={t("Monter {x}", { x: texte[id] })} onClick={() => bouger(i, -1)}>{t("Monter")}</button>
        <button type="button" className="btn-secondary text-xs" disabled={i === ids.length - 1} aria-label={t("Descendre {x}", { x: texte[id] })} onClick={() => bouger(i, 1)}>{t("Descendre")}</button></li>
    ))}</ol>;
  }
  return null;
}

export default function Passage() {
  const { id } = useParams();
  const nav = useNavigate();
  const [etat, setEtat] = useState(null);
  const [erreur, setErreur] = useState("");
  const [valeurs, setValeurs] = useState({});
  const [indice, setIndice] = useState(0);
  const [restant, setRestant] = useState(0);
  const [hors, setHors] = useState(0);
  const [confirmer, setConfirmer] = useState(false);
  const attente = useRef({});
  const minuteur = useRef(null);
  const tentativeId = etat?.id;
  const jeton = etat?.jeton;

  const vider = useCallback(async () => {
    if (!tentativeId) return;
    for (const [version, valeur] of Object.entries(attente.current)) {
      try {
        const r = await evaluationsAPI.repondre(tentativeId, { version: Number(version), valeur, jeton });
        if (attente.current[version] === valeur) delete attente.current[version];
        setRestant(r.data.secondes_restantes);
      } catch (x) {
        if (x?.response?.status === 400) { delete attente.current[version]; }
      }
    }
    setHors(Object.keys(attente.current).length);
  }, [tentativeId, jeton]);

  useEffect(() => {
    let actif = true;
    evaluationsAPI.demarrer(id).then((r) => {
      if (!actif) return;
      setEtat(r.data);
      setRestant(r.data.secondes_restantes);
      setValeurs(Object.fromEntries(r.data.questions.map((q) => [q.version, q.valeur])));
    }).catch((x) => setErreur(extractApiError(x)));
    return () => { actif = false; };
  }, [id]);

  const remis = !!etat?.remise_le || (etat && etat.statut !== "en_cours");

  useEffect(() => {
    if (!tentativeId || remis) return undefined;
    const seconde = setInterval(() => setRestant((s) => Math.max(0, s - 1)), 1000);
    const recalage = setInterval(async () => {
      await vider();
      try {
        const r = await evaluationsAPI.tentative(tentativeId);
        setRestant(r.data.secondes_restantes);
        if (r.data.statut !== "en_cours") setEtat((e) => ({ ...e, ...r.data }));
      } catch { /* hors ligne : on réessaie au prochain passage */ }
    }, 20000);
    const signal = (type) => () => { evaluationsAPI.evenement(tentativeId, type).catch(() => {}); };
    const horsLigne = signal("perte_connexion");
    const enLigne = () => { signal("reconnexion")(); vider(); };
    const visible = () => signal(document.hidden ? "sortie_fenetre" : "retour_fenetre")();
    window.addEventListener("offline", horsLigne);
    window.addEventListener("online", enLigne);
    document.addEventListener("visibilitychange", visible);
    return () => {
      clearInterval(seconde); clearInterval(recalage);
      window.removeEventListener("offline", horsLigne);
      window.removeEventListener("online", enLigne);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [tentativeId, remis, vider]);

  const fin = restant === 0 && !!etat && !remis;
  useEffect(() => {
    if (!fin) return;
    evaluationsAPI.tentative(tentativeId).then((r) => setEtat((e) => ({ ...e, ...r.data }))).catch(() => {});
  }, [fin, tentativeId]);

  const changer = (version, valeur) => {
    setValeurs((v) => ({ ...v, [version]: valeur }));
    attente.current[version] = valeur;
    setHors(Object.keys(attente.current).length);
    clearTimeout(minuteur.current);
    minuteur.current = setTimeout(vider, 800);
  };
  const remettre = async () => {
    await vider();
    try {
      const r = await evaluationsAPI.remettre(tentativeId);
      setEtat((e) => ({ ...e, ...r.data }));
    } catch (x) { setErreur(extractApiError(x)); }
    setConfirmer(false);
  };

  if (erreur) return <div className="card text-sm text-red-700">{erreur}</div>;
  if (!etat) return <p className="text-sm text-slate-500">{t("Chargement")}</p>;
  if (remis) {
    return (
      <div className="card max-w-xl mx-auto text-center space-y-3">
        <CheckCircle2 className="w-10 h-10 text-green-700 mx-auto" />
        <h1 className="text-lg font-semibold text-slate-900">{t("Épreuve remise")}</h1>
        <p className="text-sm text-slate-600">{t("Votre copie est enregistrée. Le résultat sera visible après sa publication.")}</p>
        {etat.recu && <p className="text-xs text-slate-500 break-all">{t("Reçu de remise")} : {etat.recu}</p>}
        <button type="button" className="btn-secondary" onClick={() => nav("..", { relative: "path" })}>{t("Retour")}</button>
      </div>
    );
  }
  const q = etat.questions[indice];
  const repondues = etat.questions.filter((x) => remplie(valeurs[x.version])).length;
  return (
    <div className="max-w-3xl mx-auto space-y-3">
      <div className="card sticky top-2 z-10 flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm text-slate-700">{t("{a} réponse(s) sur {b}", { a: repondues, b: etat.questions.length })}</span>
        <span className="text-xs flex items-center gap-1 text-slate-600" role="status">
          {hors > 0 ? <><CloudOff className="w-3 h-3" />{t("Sauvegarde en attente")}</> : t("Réponses sauvegardées")}
        </span>
        <span className={`font-mono text-lg font-semibold ${restant < 300 ? "text-red-700" : "text-slate-900"}`} role="timer" aria-label={t("Temps restant")}>{format(restant)}</span>
      </div>
      <div className="card flex flex-wrap gap-1" aria-label={t("Questions")}>
        {etat.questions.map((x, i) => (
          <button key={x.version} type="button" disabled={!etat.retour_autorise && i < indice} onClick={() => setIndice(i)} aria-current={i === indice}
            aria-label={t("Question {n}{r}", { n: i + 1, r: remplie(valeurs[x.version]) ? `, ${t("répondue")}` : "" })}
            className={`w-8 h-8 rounded text-xs border ${i === indice ? "border-primary font-bold" : "border-slate-200"} ${remplie(valeurs[x.version]) ? "bg-slate-800 text-white" : "bg-white text-slate-700"}`}>{i + 1}</button>
        ))}
      </div>
      <div className="card space-y-3">
        <p className="text-xs text-slate-500">{t("Question {n} sur {m}", { n: indice + 1, m: etat.questions.length })} - {q.points} pt</p>
        <p className="text-base text-slate-900 whitespace-pre-wrap">{q.enonce}</p>
        {q.media && q.media_type === "image" && <img src={q.media} alt={t("Illustration de la question")} className="max-w-full rounded" />}
        {q.media && q.media_type === "audio" && <audio controls src={q.media} className="w-full" />}
        {q.media && q.media_type === "video" && <video controls src={q.media} className="w-full rounded" />}
        {q.media && q.media_type === "document" && <a href={q.media} target="_blank" rel="noreferrer" className="text-sm text-primary underline">{t("Ouvrir le document")}</a>}
        {q.type === "fichier" ? (
          <div><label className="label" htmlFor="q-fichier">{t("Votre fichier")}</label>
            <input id="q-fichier" type="file" className="input" onChange={async (e) => {
              const f = e.target.files[0];
              if (!f) return;
              const d = new FormData();
              d.append("version", q.version); d.append("fichier", f); d.append("jeton", jeton);
              try { await evaluationsAPI.repondre(tentativeId, d); setValeurs((v) => ({ ...v, [q.version]: f.name })); } catch (x) { setErreur(extractApiError(x)); }
            }} />
            {valeurs[q.version] && <p className="text-xs text-green-700 mt-1">{t("Fichier reçu")}</p>}
          </div>
        ) : <Champ key={q.version} q={q} valeur={valeurs[q.version]} changer={(v) => changer(q.version, v)} />}
      </div>
      <div className="flex flex-wrap justify-between gap-2">
        <button type="button" className="btn-secondary" disabled={indice === 0 || !etat.retour_autorise} onClick={() => setIndice(indice - 1)}>{t("Précédente")}</button>
        {indice < etat.questions.length - 1
          ? <button type="button" className="btn-primary" onClick={() => setIndice(indice + 1)}>{t("Suivante")}</button>
          : <button type="button" className="btn-primary" onClick={() => setConfirmer(true)}>{t("Remettre ma copie")}</button>}
      </div>
      <ConfirmDialog open={confirmer} onClose={() => setConfirmer(false)} onConfirm={remettre}
        message={t("Remettre votre copie ? {a} réponse(s) sur {b}. Vous ne pourrez plus la modifier.", { a: repondues, b: etat.questions.length })} />
    </div>
  );
}
