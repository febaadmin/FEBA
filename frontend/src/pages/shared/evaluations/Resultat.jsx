/** Résultat publié, avec le corrigé si l'enseignant l'a prévu et que l'épreuve est terminée. */
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { evaluationsAPI } from "../../../api";
import { AnneauProgression, CompteurAnime, Squelette } from "../../../components/ui/anime";
import { extractApiError } from "../../../utils/errors";
import { t } from "../../../i18n";

export default function Resultat() {
  const { id } = useParams();
  const { data, isLoading, error } = useQuery({ queryKey: ["eval-resultat", id], queryFn: () => evaluationsAPI.resultat(id) });
  if (isLoading) return <Squelette />;
  if (error) return <div className="card text-sm text-slate-700">{extractApiError(error)} <Link className="text-primary underline" to="../.." relative="path">{t("Retour")}</Link></div>;
  const r = data.data;
  const pct = Number(r.pourcentage);
  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div className="card flex flex-wrap items-center gap-5">
        <AnneauProgression valeur={pct} couleur={r.reussie ? "#15803d" : "#d97706"}><span className="text-lg font-bold text-slate-900"><CompteurAnime valeur={pct} suffixe=" %" /></span></AnneauProgression>
        <div className="flex-1 min-w-48">
          <h1 className="text-xl font-bold text-slate-900">{r.epreuve}</h1>
          <p className="text-2xl font-semibold mt-1">{r.note} / {r.note_max}</p>
          <p className={`text-sm ${r.reussie ? "text-green-700" : "text-amber-800"}`}>{r.reussie ? t("Réussie") : t("Non réussie")}</p>
        </div>
        <Link to="../.." relative="path" className="btn-secondary">{t("Retour")}</Link>
      </div>
      {!r.correction_visible && <p className="text-xs text-slate-500">{t("Le corrigé n'est pas affiché : l'enseignant ne l'a pas prévu, ou l'épreuve n'est pas terminée.")}</p>}
      {r.lignes.map((l, i) => (
        <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.03 }} className="card space-y-1">
          <div className="flex justify-between gap-3"><p className="text-sm font-medium text-slate-900 whitespace-pre-wrap">{l.enonce}</p><span className="text-sm font-semibold whitespace-nowrap">{l.points ?? "-"} / {l.maximum}</span></div>
          <p className="text-xs text-slate-600">{t("Votre réponse")} : {l.reponse || t("Sans réponse")}</p>
          {l.corrige && <p className="text-xs text-green-800">{t("Bonne réponse")} : {l.corrige}</p>}
          {l.explication && <p className="text-xs text-slate-600">{l.explication}</p>}
          {l.commentaire && <p className="text-xs text-slate-700">{t("Commentaire")} : {l.commentaire}</p>}
        </motion.div>
      ))}
    </div>
  );
}
