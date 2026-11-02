/** Liste des élèves visibles. Le serveur décide du périmètre selon le rôle. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";
import { suiviAPI } from "../../../api";
import { motion } from "framer-motion";
import { AnneauProgression, apparition, cascade } from "../../../components/ui/anime";
import { useAcademy } from "../../../context/AcademyContext";
import AideModule from "../../../components/ui/AideModule";
import PageHeader from "../../../components/ui/PageHeader";
import { useAuth } from "../../../hooks/useAuth";
import { t } from "../../../i18n";

export default function SuiviEleves() {
  const { pathname } = useLocation();
  const { user } = useAuth();
  const { isAllAcademies } = useAcademy();
  const [recherche, setRecherche] = useState("");
  const { data, isLoading, isError } = useQuery({ queryKey: ["suivi-eleves"], queryFn: () => suiviAPI.eleves() });
  const eleves = (data?.data?.results || []).filter((e) => e.nom.toLowerCase().includes(recherche.toLowerCase()));
  const base = pathname.replace(/\/$/, "");
  const gere = user?.role !== "student" && user?.role !== "parent";

  return (
    <div>
      <PageHeader title={t("Suivi pédagogique")} subtitle={t("Progression, compétences et objectifs de chaque élève")}
        action={gere ? <div className="flex gap-2"><Link to={`${base}/alertes`} className="btn-secondary">{t("Alertes")}</Link><Link to={`${base}/evaluer`} className="btn-secondary">{t("Évaluer une classe")}</Link><Link to={`${base}/referentiels`} className="btn-secondary">{t("Compétences")}</Link></div> : null} />
      <AideModule cle={gere ? "suivi-personnel" : "suivi-famille"}
        description={gere ? t("Le suivi montre ce qu'un élève maîtrise, au-delà des notes. Il ne modifie jamais les notes ni les bulletins.") : t("Vous voyez ici ce que l'enseignant a validé : compétences, objectifs et rapports publiés.")}
        etapes={gere ? [t("Créez vos compétences dans Référentiels."), t("Ouvrez la fiche d'un élève."), t("Évaluez ses compétences, ajoutez des évaluations et des objectifs."), t("Générez un rapport.")] : [t("Ouvrez une fiche."), t("Parcourez les onglets.")]} />
      <div className="card">
        <input className="input mb-4 max-w-sm" placeholder={t("Rechercher un élève")} aria-label={t("Rechercher un élève")}
          value={recherche} onChange={(e) => setRecherche(e.target.value)} />
        {isLoading && <p className="text-sm text-slate-500">{t("Chargement")}</p>}
        {isError && <p className="text-sm text-red-700">{t("Le suivi n'a pas pu être chargé.")}</p>}
        {!isLoading && !isError && eleves.length === 0 && (
          <p className="text-sm text-slate-500">{isAllAcademies ? t("Choisissez une académie en haut de la page pour voir ses élèves.") : t("Aucun élève ici. Un enseignant voit les élèves de ses classes : vérifiez les classes qui lui sont attribuées.")}</p>
        )}
        <motion.ul variants={cascade} initial="hidden" animate="show" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {eleves.map((e) => (
            <motion.li key={e.id} variants={apparition} whileHover={{ y: -2 }}>
              <Link to={`${base}/${e.id}`} className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm hover:shadow-md transition-shadow">
                <AnneauProgression valeur={e.progression ?? 0} taille={52} epaisseur={5}><span className="text-[11px] font-semibold text-slate-800">{e.progression === null ? "-" : `${Math.round(e.progression)}%`}</span></AnneauProgression>
                <span className="min-w-0">
                  <span className="block text-sm font-medium text-slate-900 truncate">{e.nom}</span>
                  <span className="block text-xs text-slate-500">{e.classe_nom || t("Sans classe")}</span>
                  {e.progression === null && <span className="block text-xs text-slate-400">{t("Suivi à commencer")}</span>}
                </span>
              </Link>
            </motion.li>
          ))}
        </motion.ul>
      </div>
    </div>
  );
}
