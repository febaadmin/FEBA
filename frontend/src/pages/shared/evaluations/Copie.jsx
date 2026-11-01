/** Correction d'une copie : points, commentaire, validation. Le journal informe, il ne juge pas. */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import toast from "react-hot-toast";
import { evaluationsAPI } from "../../../api";
import PageHeader from "../../../components/ui/PageHeader";
import { extractApiError } from "../../../utils/errors";
import { t } from "../../../i18n";
import { STATUTS_COPIE } from "./commun";

function Ligne({ l, onSave, verrou }) {
  const [points, setPoints] = useState(l.points_manuel ?? l.points_auto ?? "");
  const [commentaire, setCommentaire] = useState(l.commentaire || "");
  const valeur = typeof l.valeur === "string" ? l.valeur : l.valeur === null ? null : JSON.stringify(l.valeur);
  return (
    <div className="border border-slate-200 rounded-lg p-3 space-y-2">
      <p className="text-sm font-medium text-slate-900">{l.enonce}</p>
      <p className="text-sm text-slate-700 whitespace-pre-wrap bg-slate-50 rounded p-2">{valeur ?? t("Sans réponse")}</p>
      {l.fichier && <a href={l.fichier} className="text-sm text-primary underline" target="_blank" rel="noreferrer">{t("Ouvrir le fichier déposé")}</a>}
      {l.criteres && <p className="text-xs text-slate-500">{t("Critères")} : {l.criteres}</p>}
      <p className="text-xs text-slate-500">{l.points_auto === null ? t("Correction manuelle") : t("Correction automatique : {p} pt", { p: l.points_auto })}</p>
      <div className="flex flex-wrap gap-2 items-end">
        <div><label className="label" htmlFor={`p-${l.version}`}>{t("Points sur {m}", { m: l.maximum })}</label><input id={`p-${l.version}`} className="input w-24" type="number" min="0" max={l.maximum} step="0.25" disabled={verrou} value={points} onChange={(e) => setPoints(e.target.value)} /></div>
        <div className="flex-1 min-w-40"><label className="label" htmlFor={`c-${l.version}`}>{t("Commentaire")}</label><input id={`c-${l.version}`} className="input" disabled={verrou} value={commentaire} onChange={(e) => setCommentaire(e.target.value)} /></div>
        <button type="button" className="btn-secondary" disabled={verrou || points === ""} onClick={() => onSave({ reponse: l.reponse, points, commentaire })}>{t("Enregistrer")}</button>
      </div>
      {l.historique.length > 0 && <p className="text-xs text-slate-500">{t("{n} correction(s) enregistrée(s)", { n: l.historique.length })}</p>}
    </div>
  );
}

export default function Copie() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { data, isLoading, isError } = useQuery({ queryKey: ["eval-copie", id], queryFn: () => evaluationsAPI.copie(id) });
  const opts = { onSuccess: () => { toast.success(t("Enregistré.")); qc.invalidateQueries({ queryKey: ["eval-copie", id] }); }, onError: (e) => toast.error(extractApiError(e)) };
  const corriger = useMutation({ mutationFn: (d) => evaluationsAPI.corriger(id, d), ...opts });
  const valider = useMutation({ mutationFn: () => evaluationsAPI.valider(id), ...opts });
  const choisir = useMutation({ mutationFn: () => evaluationsAPI.choisir(id), ...opts });
  if (isLoading) return <p className="text-sm text-slate-500">{t("Chargement")}</p>;
  if (isError) return <p className="card text-sm text-red-700">{t("Cette copie n'a pas pu être chargée.")}</p>;
  const c = data.data;
  const signaux = c.evenements.filter((e) => ["perte_connexion", "sortie_fenetre", "session_concurrente", "reprise"].includes(e.type));
  return (
    <div className="space-y-4">
      <PageHeader title={c.eleve} subtitle={`${t("tentative {n}", { n: c.numero })} - ${t(STATUTS_COPIE[c.statut])}`}
        action={<Link to={`../../${c.epreuve}`} relative="path" className="btn-secondary text-sm">{t("Retour")}</Link>} />
      <div className="card grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
        {[[t("Résultat brut"), c.score_brut], [t("Après correction"), c.score_corrige], [t("Résultat validé"), c.score_valide], [t("Total des points"), c.total_points]].map(([k, v]) => (
          <div key={k}><p className="text-xs text-slate-500">{k}</p><p className="font-semibold text-slate-900">{v ?? "-"}</p></div>
        ))}
      </div>
      {c.lignes.map((l) => <Ligne key={l.version} l={l} verrou={c.a_transfert || c.statut === "en_cours"} onSave={(d) => corriger.mutate(d)} />)}
      <div className="card flex flex-wrap gap-2">
        <button type="button" className="btn-primary" disabled={c.statut !== "corrigee" && c.statut !== "validee"} onClick={() => valider.mutate()}>{t("Valider la copie")}</button>
        <button type="button" className="btn-secondary" disabled={c.choisie} onClick={() => choisir.mutate()}>{c.choisie ? t("Tentative retenue") : t("Retenir cette tentative")}</button>
      </div>
      {signaux.length > 0 && (
        <div className="card">
          <h2 className="text-sm font-semibold text-slate-800">{t("Journal de l'épreuve")}</h2>
          <p className="text-xs text-slate-500 mb-2">{t("Ces événements signalent un contexte. Ils ne prouvent pas une fraude.")}</p>
          <ul className="text-xs text-slate-700 space-y-1">{signaux.map((e, i) => <li key={i}>{new Date(e.created_at).toLocaleString()} - {t({ perte_connexion: "Perte de connexion", sortie_fenetre: "Sortie de la fenêtre", session_concurrente: "Autre session détectée", reprise: "Reprise de l'épreuve" }[e.type])}</li>)}</ul>
        </div>
      )}
    </div>
  );
}
