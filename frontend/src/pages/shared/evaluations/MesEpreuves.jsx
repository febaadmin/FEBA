/** Espace de l'élève : chaque épreuve dit son état, la raison et l'action possible. Le parent voit les résultats publiés. */
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { CalendarClock, CheckCircle2, Clock, FileQuestion, Hourglass, Lock, PlayCircle, RotateCcw, Search, Trophy, User } from "lucide-react";
import { evaluationsAPI } from "../../../api";
import AideModule from "../../../components/ui/AideModule";
import { CarteAnimee, Squelette, cascade } from "../../../components/ui/anime";
import PageHeader from "../../../components/ui/PageHeader";
import { useAuth } from "../../../hooks/useAuth";
import { t } from "../../../i18n";
import { TYPES_EPREUVE, libelle } from "./commun";

const ETATS = {
  en_cours: { label: "En cours", Icone: RotateCcw, cls: "bg-blue-100 text-blue-800", groupe: "faire" },
  disponible: { label: "Disponible", Icone: PlayCircle, cls: "bg-green-100 text-green-800", groupe: "faire" },
  a_venir: { label: "À venir", Icone: CalendarClock, cls: "bg-slate-100 text-slate-700", groupe: "venir" },
  correction: { label: "En attente de correction", Icone: Hourglass, cls: "bg-amber-100 text-amber-800", groupe: "fini" },
  terminee: { label: "Corrigée", Icone: CheckCircle2, cls: "bg-slate-100 text-slate-700", groupe: "fini" },
  resultat: { label: "Résultat publié", Icone: Trophy, cls: "bg-violet-100 text-violet-800", groupe: "fini" },
  expiree: { label: "Expirée", Icone: Lock, cls: "bg-red-100 text-red-800", groupe: "fini" },
};
const ONGLETS = [["tout", "Toutes"], ["faire", "À faire"], ["venir", "À venir"], ["fini", "Terminées"]];
const date = (d) => new Date(d).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

function CarteEpreuve({ e, base }) {
  const etat = ETATS[e.etat];
  return (
    <CarteAnimee className="p-5 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-semibold text-slate-900 truncate">{e.titre}</h2>
          <p className="text-sm text-slate-500">{e.subject} - {libelle(TYPES_EPREUVE, e.type)}</p>
        </div>
        <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium whitespace-nowrap ${etat.cls}`}><etat.Icone className="w-3 h-3" aria-hidden="true" />{t(etat.label)}</span>
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-600">
        <div className="flex items-center gap-1"><Clock className="w-3 h-3" aria-hidden="true" /><dt className="sr-only">{t("Durée")}</dt><dd>{t("{n} min", { n: e.duree_minutes })}</dd></div>
        <div className="flex items-center gap-1"><FileQuestion className="w-3 h-3" aria-hidden="true" /><dt className="sr-only">{t("Questions")}</dt><dd>{t("{n} question(s)", { n: e.nombre_questions })}</dd></div>
        <div className="flex items-center gap-1"><RotateCcw className="w-3 h-3" aria-hidden="true" /><dt className="sr-only">{t("Tentatives")}</dt><dd>{t("{a} tentative(s) sur {b}", { a: e.tentatives, b: e.tentatives_max })}</dd></div>
        {e.enseignant && <div className="flex items-center gap-1 min-w-0"><User className="w-3 h-3 shrink-0" aria-hidden="true" /><dt className="sr-only">{t("Enseignant")}</dt><dd className="truncate">{e.enseignant}</dd></div>}
        <div className="col-span-2 flex flex-wrap gap-x-3"><dt className="sr-only">{t("Note maximale")}</dt><dd>{t("Sur {n}", { n: Number(e.note_max) })}</dd><dd>{t("Réussite à partir de {n} %", { n: Number(e.seuil_reussite) })}</dd></div>
      </dl>
      <div className="mt-auto rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-700">
        {e.etat === "a_venir" ? t("S'ouvre le {d}, ferme le {f}.", { d: date(e.ouverture), f: date(e.fermeture) })
          : e.etat === "disponible" || e.etat === "en_cours" ? `${t(e.raison)} ${t("Jusqu'au {d}", { d: date(e.fermeture) })}.` : t(e.raison)}
      </div>
      {(e.etat === "disponible" || e.etat === "en_cours") && <Link to={`${base}/${e.id}/passer`} className="btn-primary text-center">{e.etat === "en_cours" ? t("Reprendre") : t("Commencer")}</Link>}
      {e.etat === "resultat" && <Link to={`${base}/resultat/${e.tentative_resultat}`} className="btn-primary text-center">{t("Consulter le résultat")}</Link>}
    </CarteAnimee>
  );
}

export default function MesEpreuves() {
  const { user } = useAuth();
  const base = useLocation().pathname.replace(/\/$/, "");
  const eleve = user?.role === "student";
  const [onglet, setOnglet] = useState("tout");
  const [recherche, setRecherche] = useState("");
  const { data, isLoading, isError: erreurListe } = useQuery({ queryKey: ["eval-mes"], queryFn: () => evaluationsAPI.mesEpreuves(), enabled: eleve, refetchInterval: 60000 });
  const { data: res, isError } = useQuery({ queryKey: ["eval-resultats"], queryFn: () => evaluationsAPI.resultats(), enabled: !eleve });
  const epreuves = useMemo(() => data?.data || [], [data]);
  const visibles = epreuves.filter((e) => (onglet === "tout" || ETATS[e.etat].groupe === onglet)
    && `${e.titre} ${e.subject}`.toLowerCase().includes(recherche.toLowerCase()));
  const resultats = res?.data || [];
  const compte = (g) => epreuves.filter((e) => g === "tout" || ETATS[e.etat].groupe === g).length;

  if (!eleve) {
    return (
      <div className="space-y-4">
        <PageHeader title={t("Résultats des épreuves")} subtitle={t("Les notes que l'enseignant a publiées pour vos enfants.")} />
        <div className="card">
          {isError && <p className="text-sm text-slate-500">{t("Votre académie n'a pas encore ouvert ces résultats aux familles.")}</p>}
          {!isError && resultats.length === 0 && <p className="text-sm text-slate-500">{t("Aucun résultat publié pour le moment.")}</p>}
          <ul className="divide-y divide-slate-100">
            {resultats.map((r) => (
              <li key={r.id} className="py-2 flex flex-wrap justify-between gap-2 text-sm">
                <span>{r.epreuve} - {r.eleve}</span>
                <span className="font-medium">{r.note} / {r.note_max} - {r.reussie ? t("Réussie") : t("Non réussie")}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    );
  }
  return (
    <div className="space-y-4">
      <PageHeader title={t("Mes épreuves")} subtitle={t("Vos quiz, évaluations et examens en ligne.")} />
      <AideModule cle="mes-epreuves" description={t("Vos épreuves ouvertes s'affichent ici. Le temps démarre seulement quand vous cliquez sur Commencer l'épreuve.")} />
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap gap-1" role="tablist" aria-label={t("Filtrer les épreuves")}>
          {ONGLETS.map(([k, l]) => (
            <button key={k} type="button" role="tab" aria-selected={onglet === k} onClick={() => setOnglet(k)}
              className={`relative rounded-full px-3 py-1.5 text-sm transition-colors ${onglet === k ? "text-white" : "text-slate-600 hover:bg-slate-100"}`}>
              {onglet === k && <motion.span layoutId="onglet-epreuves" className="absolute inset-0 rounded-full bg-primary" transition={{ type: "spring", stiffness: 400, damping: 32 }} />}
              <span className="relative">{t(l)} ({compte(k)})</span>
            </button>
          ))}
        </div>
        <div className="relative flex-1 min-w-48">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" aria-hidden="true" />
          <input className="input pl-9" placeholder={t("Rechercher une épreuve")} aria-label={t("Rechercher une épreuve")} value={recherche} onChange={(e) => setRecherche(e.target.value)} />
        </div>
      </div>
      {isLoading && <Squelette />}
      {erreurListe && <p className="card text-sm text-red-700">{t("Vos épreuves n'ont pas pu être chargées. Vérifiez votre connexion et rechargez la page.")}</p>}
      {!isLoading && !erreurListe && visibles.length === 0 && (
        <div className="card text-center py-10 text-sm text-slate-600">
          <FileQuestion className="w-8 h-8 mx-auto text-slate-400 mb-2" aria-hidden="true" />
          {epreuves.length ? t("Aucune épreuve pour ce filtre.") : t("Aucune épreuve pour le moment. Vos enseignants les publieront ici.")}
        </div>
      )}
      <motion.div key={onglet} variants={cascade} initial="hidden" animate="show" className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {visibles.map((e) => <CarteEpreuve key={e.id} e={e} base={base} />)}
      </motion.div>
    </div>
  );
}
