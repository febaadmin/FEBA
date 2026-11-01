/** Une épreuve : composition, publication, copies, statistiques, transfert vers les notes. */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useParams } from "react-router-dom";
import toast from "react-hot-toast";
import { evaluationsAPI } from "../../../api";
import ConfirmDialog from "../../../components/ui/ConfirmDialog";
import PageHeader from "../../../components/ui/PageHeader";
import { extractApiError } from "../../../utils/errors";
import { t } from "../../../i18n";
import { STATUTS_COPIE, STATUTS_EPREUVE, TYPES_QUESTION, libelle, telecharger } from "./commun";

const vide = (v) => (v === null || v === undefined ? "-" : v);

export default function EpreuveDetail() {
  const { id } = useParams();
  const base = useLocation().pathname.replace(/\/\d+\/?$/, "");
  const qc = useQueryClient();
  const [confirmer, setConfirmer] = useState(null);
  const { data, isLoading, isError } = useQuery({ queryKey: ["eval-epreuve", id], queryFn: () => evaluationsAPI.epreuve(id) });
  const e = data?.data;
  const brouillon = e?.statut === "brouillon";
  const { data: banque } = useQuery({ queryKey: ["eval-questions", { archive: "false" }], queryFn: () => evaluationsAPI.questions({ archive: "false" }), enabled: brouillon });
  const { data: copies } = useQuery({ queryKey: ["eval-copies", id], queryFn: () => evaluationsAPI.copies(id), enabled: !!e && !brouillon });
  const { data: stats } = useQuery({ queryKey: ["eval-stats", id], queryFn: () => evaluationsAPI.statistiques(id), enabled: !!e && !brouillon });
  const rafraichir = () => ["eval-epreuve", "eval-copies", "eval-stats"].forEach((k) => qc.invalidateQueries({ queryKey: [k, id] }));
  const action = useMutation({
    mutationFn: (fn) => fn(),
    onSuccess: () => { toast.success(t("Enregistré.")); setConfirmer(null); rafraichir(); },
    onError: (x) => { toast.error(extractApiError(x)); setConfirmer(null); },
  });
  const transfert = useMutation({
    mutationFn: () => evaluationsAPI.transferer(id, {}),
    onSuccess: (r) => {
      setConfirmer(null);
      toast.success(t("{c} note(s) créée(s), {d} déjà transférée(s).", { c: r.data.crees, d: r.data.deja_transferes }));
      r.data.erreurs.forEach((x) => toast.error(x.detail));
      rafraichir();
    },
    onError: (x) => { toast.error(extractApiError(x)); setConfirmer(null); },
  });
  if (isLoading) return <p className="text-sm text-slate-500">{t("Chargement")}</p>;
  if (isError) return <p className="card text-sm text-red-700">{t("Cette épreuve n'a pas pu être chargée.")}</p>;
  const lignesCopies = copies?.data || [];
  const s = stats?.data;
  const dejaLa = new Set(e.questions.map((q) => q.version));
  const proposees = (banque?.data?.results || []).filter((q) => !dejaLa.has(q.version?.id));

  return (
    <div className="space-y-4">
      <PageHeader title={e.titre} subtitle={`${e.subject_name} - ${e.class_name} - ${t(STATUTS_EPREUVE[e.statut])}`}
        action={<Link to={base} className="btn-secondary text-sm">{t("Retour")}</Link>} />
      <div className="card flex flex-wrap gap-2">
        {brouillon && <button type="button" className="btn-primary" onClick={() => action.mutate(() => evaluationsAPI.publier(id))}>{t("Publier l'épreuve")}</button>}
        {e.statut === "publiee" && <button type="button" className="btn-secondary" onClick={() => setConfirmer("fermer")}>{t("Clore l'épreuve")}</button>}
        {!brouillon && <button type="button" className="btn-secondary" onClick={() => (e.resultats_publies ? action.mutate(() => evaluationsAPI.publierResultats(id, false)) : setConfirmer("resultats"))}>{e.resultats_publies ? t("Retirer les résultats") : t("Publier les résultats")}</button>}
        {!brouillon && e.produit_note && <button type="button" className="btn-secondary" onClick={() => setConfirmer("transfert")}>{t("Transférer vers les notes")}</button>}
        {!brouillon && <button type="button" className="btn-secondary" onClick={async () => telecharger((await evaluationsAPI.exporterResultats(id)).data, `resultats-${id}.csv`)}>{t("Exporter les résultats")}</button>}
        {brouillon && <Link to={`${base}/banque`} className="btn-secondary">{t("Banque de questions")}</Link>}
      </div>
      <div className="card space-y-2">
        <h2 className="text-sm font-semibold text-slate-800">{t("Questions")} ({e.questions.length})</h2>
        {e.questions.length === 0 && <p className="text-sm text-slate-500">{t("Ajoutez des questions depuis la banque.")}</p>}
        <ul className="divide-y divide-slate-100">
          {e.questions.map((q) => (
            <li key={q.id} className="py-2 flex flex-wrap justify-between gap-2 text-sm">
              <span className="flex-1 min-w-0">{q.enonce} <span className="text-xs text-slate-500">({libelle(TYPES_QUESTION, q.type)}, {q.points} pt)</span></span>
              {brouillon && <button type="button" className="text-xs text-primary underline" onClick={() => action.mutate(() => evaluationsAPI.retirerQuestion(id, q.id))}>{t("Retirer")}</button>}
            </li>
          ))}
        </ul>
        {brouillon && proposees.length > 0 && (
          <div className="pt-3 border-t border-slate-100">
            <h3 className="text-xs font-medium text-slate-600 mb-1">{t("Depuis la banque")}</h3>
            <ul className="divide-y divide-slate-100 max-h-64 overflow-y-auto">
              {proposees.map((q) => (
                <li key={q.id} className="py-2 flex flex-wrap justify-between gap-2 text-sm">
                  <span className="flex-1 min-w-0">{q.version?.enonce}</span>
                  <button type="button" className="text-xs text-primary underline" onClick={() => action.mutate(() => evaluationsAPI.ajouterQuestion(id, { question: q.id }))}>{t("Ajouter")}</button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      {!brouillon && s && (
        <div className="card space-y-3">
          <h2 className="text-sm font-semibold text-slate-800">{t("Statistiques")}</h2>
          {s.corrigees === 0 ? <p className="text-sm text-slate-500">{t("Aucune copie corrigée pour le moment.")}</p> : (
            <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
              {[[t("Participation"), s.taux_participation === null ? "-" : `${s.participants} / ${s.inscrits}`], [t("Moyenne"), `${s.moyenne} %`], [t("Médiane"), `${s.mediane} %`], [t("Réussite"), `${s.taux_reussite} %`], [t("Meilleur résultat"), `${s.meilleur} %`], [t("Résultat le plus faible"), `${s.plus_faible} %`], [t("À corriger"), s.a_corriger]].map(([k, v]) => (
                <div key={k}><dt className="text-xs text-slate-500">{k}</dt><dd className="font-semibold text-slate-900">{v}</dd></div>
              ))}
            </dl>
          )}
          {s.questions.length > 0 && (
            <div>
              <h3 className="text-xs font-medium text-slate-600 mb-1">{t("Réussite par question, de la plus difficile à la plus réussie")}</h3>
              <ul className="space-y-1">{s.questions.map((q) => (
                <li key={q.version} className="text-xs flex justify-between gap-3"><span className="truncate">{q.enonce}</span><span className="whitespace-nowrap font-medium">{q.reussite === null ? t("À corriger") : `${q.reussite} %`}</span></li>
              ))}</ul>
            </div>
          )}
        </div>
      )}
      {!brouillon && (
        <div className="card">
          <h2 className="text-sm font-semibold text-slate-800 mb-2">{t("Copies")}</h2>
          {lignesCopies.length === 0 && <p className="text-sm text-slate-500">{t("Aucune copie pour le moment.")}</p>}
          <ul className="divide-y divide-slate-100">
            {lignesCopies.map((c) => (
              <li key={c.id}><Link to={`${base}/copies/${c.id}`} className="py-2 px-2 flex flex-wrap justify-between gap-2 text-sm hover:bg-slate-50 rounded-lg">
                <span>{c.eleve} <span className="text-xs text-slate-500">({t("tentative {n}", { n: c.numero })})</span></span>
                <span className="text-slate-700">{t(STATUTS_COPIE[c.statut])} - {vide(c.note_echelle)} / {e.note_max}{c.a_transfert ? ` - ${t("Note transférée")}` : ""}</span>
              </Link></li>
            ))}
          </ul>
        </div>
      )}
      <ConfirmDialog open={!!confirmer} onClose={() => setConfirmer(null)} loading={action.isPending || transfert.isPending}
        onConfirm={() => (confirmer === "fermer" ? action.mutate(() => evaluationsAPI.fermer(id)) : confirmer === "resultats" ? action.mutate(() => evaluationsAPI.publierResultats(id, true)) : transfert.mutate())}
        message={confirmer === "fermer" ? t("Clore l'épreuve ? Les tentatives en cours seront remises.") : confirmer === "resultats" ? t("Publier les résultats validés aux élèves ?") : t("Créer une note officielle sur 20 pour chaque élève validé ? Ces notes entreront dans les moyennes et les bulletins.")} />
    </div>
  );
}
