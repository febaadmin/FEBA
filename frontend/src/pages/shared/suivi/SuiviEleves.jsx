/** Liste des élèves visibles. Le serveur décide du périmètre selon le rôle. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";
import { suiviAPI } from "../../../api";
import PageHeader from "../../../components/ui/PageHeader";
import { useAuth } from "../../../hooks/useAuth";
import { t } from "../../../i18n";

export default function SuiviEleves() {
  const { pathname } = useLocation();
  const { user } = useAuth();
  const [recherche, setRecherche] = useState("");
  const { data, isLoading, isError } = useQuery({ queryKey: ["suivi-eleves"], queryFn: () => suiviAPI.eleves() });
  const eleves = (data?.data?.results || []).filter((e) => e.nom.toLowerCase().includes(recherche.toLowerCase()));
  const base = pathname.replace(/\/$/, "");
  const gere = user?.role !== "student" && user?.role !== "parent";

  return (
    <div>
      <PageHeader title={t("Suivi pédagogique")} subtitle={t("Progression, compétences et objectifs de chaque élève")}
        action={gere ? <div className="flex gap-2"><Link to={`${base}/alertes`} className="btn-secondary">{t("Alertes")}</Link><Link to={`${base}/referentiels`} className="btn-secondary">{t("Référentiels")}</Link></div> : null} />
      <div className="card">
        <input className="input mb-4 max-w-sm" placeholder={t("Rechercher un élève")} aria-label={t("Rechercher un élève")}
          value={recherche} onChange={(e) => setRecherche(e.target.value)} />
        {isLoading && <p className="text-sm text-slate-500">{t("Chargement")}</p>}
        {isError && <p className="text-sm text-red-700">{t("Le suivi n'a pas pu être chargé.")}</p>}
        {!isLoading && !isError && eleves.length === 0 && (
          <p className="text-sm text-slate-500">{t("Aucun élève dans votre périmètre.")}</p>
        )}
        <ul className="divide-y divide-slate-100">
          {eleves.map((e) => (
            <li key={e.id}>
              <Link to={`${base}/${e.id}`} className="flex items-center justify-between gap-3 py-3 hover:bg-slate-50 px-2 rounded-lg">
                <span>
                  <span className="block text-sm font-medium text-slate-900">{e.nom}</span>
                  <span className="block text-xs text-slate-500">{e.classe_nom || t("Sans classe")}</span>
                </span>
                <span className="text-sm text-slate-700 whitespace-nowrap">
                  {e.progression === null ? t("Données insuffisantes") : `${e.progression} %`}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
