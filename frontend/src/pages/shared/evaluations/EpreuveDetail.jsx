/** Une épreuve : composition, publication, copies, statistiques, transfert vers les notes. */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { Reorder, motion } from "framer-motion";
import { GripVertical } from "lucide-react";
import toast from "react-hot-toast";
import { evaluationsAPI } from "../../../api";
import ConfirmDialog from "../../../components/ui/ConfirmDialog";
import Modal from "../../../components/ui/Modal";
import PageHeader from "../../../components/ui/PageHeader";
import { extractApiError } from "../../../utils/errors";
import { t } from "../../../i18n";
import { STATUTS_COPIE, STATUTS_EPREUVE, TYPES_QUESTION, libelle, telecharger } from "./commun";

function OrdreQuestions({ questions, id, retirer }) {
  const [ordre, setOrdre] = useState(questions);
  const cle = questions.map((q) => q.id).join();
  const [cleVue, setCleVue] = useState(cle);
  if (cle !== cleVue) { setCleVue(cle); setOrdre(questions); }
  const enregistrer = () => evaluationsAPI.reordonner(id, ordre.map((q) => q.id)).catch((x) => toast.error(extractApiError(x)));
  const decaler = (i, d) => {
    const n = [...ordre];
    [n[i], n[i + d]] = [n[i + d], n[i]];
    setOrdre(n);
    evaluationsAPI.reordonner(id, n.map((q) => q.id)).catch((x) => toast.error(extractApiError(x)));
  };
  return (
    <Reorder.Group axis="y" values={ordre} onReorder={setOrdre} className="space-y-1">
      {ordre.map((q, i) => (
        <Reorder.Item key={q.id} value={q} onDragEnd={enregistrer} whileDrag={{ scale: 1.01, boxShadow: "0 8px 24px rgba(15,23,42,.15)" }}
          className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-2 text-sm cursor-grab active:cursor-grabbing">
          <GripVertical className="w-4 h-4 text-slate-400" aria-hidden="true" />
          <span className="flex-1 min-w-0">{i + 1}. {q.enonce} <span className="text-xs text-slate-500">({libelle(TYPES_QUESTION, q.type)}, {q.points} pt)</span></span>
          <button type="button" className="text-xs text-primary underline" disabled={i === 0} aria-label={t("Monter {x}", { x: q.enonce })} onClick={() => decaler(i, -1)}>{t("Monter")}</button>
          <button type="button" className="text-xs text-primary underline" disabled={i === ordre.length - 1} aria-label={t("Descendre {x}", { x: q.enonce })} onClick={() => decaler(i, 1)}>{t("Descendre")}</button>
          <button type="button" className="text-xs text-primary underline" onClick={() => retirer(q.id)}>{t("Retirer")}</button>
        </Reorder.Item>
      ))}
    </Reorder.Group>
  );
}

export default function EpreuveDetail() {
  const { id } = useParams();
  const base = useLocation().pathname.replace(/\/\d+\/?$/, "");
  const qc = useQueryClient();
  const nav = useNavigate();
  const [confirmer, setConfirmer] = useState(null);
  const [apercu, setApercu] = useState(false);
  const { data, isLoading, isError } = useQuery({ queryKey: ["eval-epreuve", id], queryFn: () => evaluationsAPI.epreuve(id) });
  const e = data?.data;
  const brouillon = e?.statut === "brouillon";
  const { data: banque } = useQuery({ queryKey: ["eval-questions", { archive: "false" }], queryFn: () => evaluationsAPI.questions({ archive: "false" }), enabled: brouillon });
  const { data: apercuData } = useQuery({ queryKey: ["eval-apercu", id], queryFn: () => evaluationsAPI.apercu(id), enabled: apercu });
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
  const ouvertureFuture = new Date(e.ouverture) > new Date();
  const lignesCopies = copies?.data || [];
  const s = stats?.data;
  const dejaLa = new Set(e.questions.map((q) => q.version));
  const proposees = (banque?.data?.results || []).filter((q) => !dejaLa.has(q.version?.id));

  return (
    <div className="space-y-4">
      <PageHeader title={e.titre} subtitle={`${e.subject_name} - ${e.class_name} - ${t(STATUTS_EPREUVE[e.statut])}`}
        action={<Link to={base} className="btn-secondary text-sm">{t("Retour")}</Link>} />
      <p className="rounded-xl border border-blue-100 bg-primary-50 p-3 text-sm text-slate-700" role="status">
        {t("Prochaine étape")} : {brouillon ? (e.questions.length ? t("publiez l'épreuve pour l'ouvrir aux élèves. Elle ne se modifiera plus.") : t("ajoutez des questions depuis la banque.")) : s?.a_corriger ? t("corrigez les copies en attente.") : lignesCopies.some((c) => c.statut === "corrigee") ? t("validez les copies corrigées.") : lignesCopies.length === 0 ? t("attendez les premières copies, à partir de l'ouverture.") : !e.resultats_publies ? t("publiez les résultats pour les rendre visibles aux élèves.") : e.produit_note ? t("transférez les copies validées vers les notes si ce n'est pas déjà fait.") : t("rien à faire, l'épreuve est terminée.")}
      </p>
      {!brouillon && ouvertureFuture && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 flex flex-wrap items-center justify-between gap-2" role="status">
          <span>{t("Les élèves voient cette épreuve, mais ne pourront la commencer qu'à partir du {d}.", { d: new Date(e.ouverture).toLocaleString() })}</span>
          <button type="button" className="btn-secondary text-sm" disabled={action.isPending} onClick={() => action.mutate(() => evaluationsAPI.ajusterDates(id, { ouverture: new Date().toISOString() }))}>{t("Ouvrir maintenant")}</button>
        </div>
      )}
      {e.statut === "publiee" && !ouvertureFuture && new Date(e.fermeture) < new Date() && (
        <p className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{t("La date de fermeture est passée : plus aucun élève ne peut commencer.")}</p>
      )}
      <div className="card flex flex-wrap gap-2">
        {brouillon && <button type="button" className="btn-primary" onClick={() => action.mutate(() => evaluationsAPI.publier(id))}>{t("Publier l'épreuve")}</button>}
        {e.statut === "publiee" && <button type="button" className="btn-secondary" onClick={() => setConfirmer("fermer")}>{t("Clore l'épreuve")}</button>}
        {!brouillon && <button type="button" className="btn-secondary" onClick={() => (e.resultats_publies ? action.mutate(() => evaluationsAPI.publierResultats(id, false)) : setConfirmer("resultats"))}>{e.resultats_publies ? t("Retirer les résultats") : t("Publier les résultats")}</button>}
        {!brouillon && e.produit_note && <button type="button" className="btn-secondary" onClick={() => setConfirmer("transfert")}>{t("Transférer vers les notes")}</button>}
        <button type="button" className="btn-secondary" onClick={() => setApercu(true)}>{t("Aperçu de l'épreuve")}</button>
        {!brouillon && <button type="button" className="btn-secondary" onClick={async () => telecharger((await evaluationsAPI.exporterResultats(id)).data, `resultats-${id}.csv`)}>{t("Exporter en CSV")}</button>}
        {!brouillon && <button type="button" className="btn-secondary" onClick={async () => telecharger((await evaluationsAPI.resultatsPdf(id)).data, `resultats-${id}.pdf`)}>{t("Exporter en PDF")}</button>}
        {brouillon && <Link to={`${base}/banque`} className="btn-secondary">{t("Banque de questions")}</Link>}
        {brouillon && <button type="button" className="btn-secondary" onClick={() => setConfirmer("supprimer")}>{t("Supprimer le brouillon")}</button>}
      </div>
      <div className="card space-y-2">
        <h2 className="text-sm font-semibold text-slate-800">{t("Questions")} ({e.questions.length})</h2>
        {e.questions.length === 0 && <p className="text-sm text-slate-500">{t("Ajoutez des questions depuis la banque.")}</p>}
        {brouillon && e.questions.length > 1 && <p className="text-xs text-slate-500">{t("Faites glisser une question pour changer l'ordre.")}</p>}
        {brouillon ? <OrdreQuestions questions={e.questions} id={id} retirer={(l) => action.mutate(() => evaluationsAPI.retirerQuestion(id, l))} /> : (
          <ol className="divide-y divide-slate-100">
            {e.questions.map((q) => (
              <li key={q.id} className="py-2 text-sm">{q.enonce} <span className="text-xs text-slate-500">({libelle(TYPES_QUESTION, q.type)}, {q.points} pt)</span></li>
            ))}
          </ol>
        )}
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
              <ul className="space-y-2">{s.questions.map((q) => (
                <li key={q.version} className="text-xs">
                  <span className="flex justify-between gap-3"><span className="truncate">{q.enonce}</span><span className="whitespace-nowrap font-medium">{q.reussite === null ? t("À corriger") : `${q.reussite} %`}</span></span>
                  <span className="block h-2 rounded-full bg-slate-100 overflow-hidden mt-0.5" aria-hidden="true"><motion.span className="block h-full rounded-full bg-primary" initial={{ width: 0 }} animate={{ width: `${q.reussite ?? 0}%` }} transition={{ duration: 0.7 }} /></span>
                </li>
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
                <span className="text-slate-700">{t(STATUTS_COPIE[c.statut])} - {c.note_echelle === null ? "-" : Number(c.note_echelle)} / {Number(e.note_max)}{c.a_transfert ? ` - ${t("Note transférée")}` : ""}</span>
              </Link></li>
            ))}
          </ul>
        </div>
      )}
      <Modal open={apercu} onClose={() => setApercu(false)} title={t("Aperçu de l'épreuve")} size="lg">
        <div className="space-y-3">
          {apercuData?.data?.consignes && <p className="text-sm text-slate-700 whitespace-pre-wrap">{apercuData.data.consignes}</p>}
          {(apercuData?.data?.lignes || []).map((q, i) => (
            <div key={i} className="rounded-xl border border-slate-200 p-3 space-y-1">
              <p className="text-sm font-medium text-slate-900 whitespace-pre-wrap">{i + 1}. {q.enonce} <span className="text-xs font-normal text-slate-500">({Number(q.points)} pt)</span></p>
              {q.media && q.media_type === "image" && <img src={q.media} alt={t("Illustration de la question")} className="max-w-full rounded" />}
              {(q.contenu?.choix || q.contenu?.elements || []).map((c) => <p key={c.id} className="text-xs text-slate-600">- {c.texte}</p>)}
              {q.corrige && <p className="text-xs text-green-800">{t("Bonne réponse")} : {q.corrige}</p>}
            </div>
          ))}
        </div>
      </Modal>
      <ConfirmDialog open={!!confirmer} onClose={() => setConfirmer(null)} loading={action.isPending || transfert.isPending}
        title={confirmer === "supprimer" ? undefined : "Confirmer"} libelle={{ fermer: "Clore l'épreuve", resultats: "Publier les résultats", transfert: "Créer les notes" }[confirmer]}
        onConfirm={() => (confirmer === "supprimer" ? evaluationsAPI.supprimerEpreuve(id).then(() => nav(base)).catch((x) => toast.error(extractApiError(x))) : confirmer === "fermer" ? action.mutate(() => evaluationsAPI.fermer(id)) : confirmer === "resultats" ? action.mutate(() => evaluationsAPI.publierResultats(id, true)) : transfert.mutate())}
        message={confirmer === "supprimer" ? t("Supprimer ce brouillon d'épreuve ?") : confirmer === "fermer" ? t("Clore l'épreuve ? Les tentatives en cours seront remises.") : confirmer === "resultats" ? t("Publier les résultats validés aux élèves ?") : t("Créer une note officielle sur 20 pour chaque élève validé ? Ces notes entreront dans les moyennes et les bulletins.")} />
    </div>
  );
}
