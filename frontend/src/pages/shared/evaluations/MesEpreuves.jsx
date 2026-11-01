/** Espace de l'élève : épreuves disponibles et résultats publiés. Le parent ne voit que les résultats. */
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";
import { evaluationsAPI } from "../../../api";
import PageHeader from "../../../components/ui/PageHeader";
import { useAuth } from "../../../hooks/useAuth";
import { t } from "../../../i18n";
import { TYPES_EPREUVE, libelle } from "./commun";

const ouverte = (e) => { const m = new Date(); return e.statut === "publiee" && new Date(e.ouverture) <= m && m <= new Date(e.fermeture); };

export default function MesEpreuves() {
  const { user } = useAuth();
  const base = useLocation().pathname.replace(/\/$/, "");
  const eleve = user?.role === "student";
  const { data, isLoading } = useQuery({ queryKey: ["eval-mes"], queryFn: () => evaluationsAPI.mesEpreuves(), enabled: eleve });
  const { data: res, isError } = useQuery({ queryKey: ["eval-resultats"], queryFn: () => evaluationsAPI.resultats() });
  const epreuves = data?.data || [];
  const resultats = res?.data || [];
  return (
    <div className="space-y-4">
      <PageHeader title={eleve ? t("Mes épreuves") : t("Résultats des épreuves")} />
      {eleve && (
        <div className="card">
          {isLoading && <p className="text-sm text-slate-500">{t("Chargement")}</p>}
          {!isLoading && epreuves.length === 0 && <p className="text-sm text-slate-500">{t("Aucune épreuve pour le moment.")}</p>}
          <ul className="divide-y divide-slate-100">
            {epreuves.map((e) => {
              const reste = e.en_cours || e.tentatives < e.tentatives_max;
              return (
                <li key={e.id} className="py-3 flex flex-wrap justify-between items-center gap-2">
                  <div>
                    <p className="text-sm font-medium text-slate-900">{e.titre}</p>
                    <p className="text-xs text-slate-500">{libelle(TYPES_EPREUVE, e.type)} - {e.subject} - {t("{n} min", { n: e.duree_minutes })}</p>
                    <p className="text-xs text-slate-500">{t("Jusqu'au {d}", { d: new Date(e.fermeture).toLocaleString() })} - {t("{a} tentative(s) sur {b}", { a: e.tentatives, b: e.tentatives_max })}</p>
                  </div>
                  {ouverte(e) && reste
                    ? <Link to={`${base}/${e.id}/passer`} className="btn-primary text-sm">{e.en_cours ? t("Reprendre") : t("Commencer")}</Link>
                    : <span className="text-xs text-slate-500">{ouverte(e) ? t("Tentatives utilisées") : t("Non ouverte")}</span>}
                </li>
              );
            })}
          </ul>
        </div>
      )}
      <div className="card">
        <h2 className="text-sm font-semibold text-slate-800 mb-2">{t("Résultats publiés")}</h2>
        {isError && <p className="text-sm text-slate-500">{t("Fonctionnalité non activée")}</p>}
        {!isError && resultats.length === 0 && <p className="text-sm text-slate-500">{t("Aucun résultat publié.")}</p>}
        <ul className="divide-y divide-slate-100">
          {resultats.map((r) => (
            <li key={r.id} className="py-2 flex flex-wrap justify-between gap-2 text-sm">
              <span>{r.epreuve}{user?.role === "parent" ? ` - ${r.eleve}` : ""}</span>
              <span className="font-medium">{r.note} / {r.note_max} - {r.reussie ? t("Réussie") : t("Non réussie")}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
