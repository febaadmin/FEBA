/**
 * Centre d'analyse (personnel) : effectifs, résultats, matières, enseignants, présences.
 *
 * Tout est calculé par le serveur (/api/analytics/…), dans le périmètre du
 * profil : un enseignant ne voit que ses classes, sans aucune donnée financière.
 * Les filtres sont communs à tous les onglets ; le mode de présentation
 * (FR, EN, bilingue) ne change que les libellés.
 */
import { useEffect, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { X } from "lucide-react";
import { analyticsAPI } from "../../api";
import { isCanceledError } from "../../api/academyScope";
import PageHeader from "../../components/ui/PageHeader";
import { ChoixPresentation, libelleDouble, PresentationProvider, usePresentation, useT } from "../../components/analytics/presentation";
import { useAuth } from "../../hooks/useAuth";
import { useAcademyKey } from "../../hooks/useEntityContext";

const NAVY = "#0E2A63";
const OR = "#D89B16";
export const VIDES = { annee: "", periode: "", cycle: "", niveau: "", classe: "", matiere: "", enseignant: "", eleve: "", genre: "" };
const DEPENDANTS = { annee: ["classe", "eleve"], cycle: ["niveau", "classe", "eleve"], niveau: ["classe", "eleve", "matiere"], classe: ["eleve"] };
export const changer = (f, cle, v) => {
  const s = { ...f, [cle]: v };
  for (const d of DEPENDANTS[cle] || []) s[d] = "";
  return s;
};
export const parametres = (f) => Object.fromEntries(Object.entries(f).filter(([, v]) => v !== ""));
const ONGLETS = [["resultats", "Résultats"], ["matieres", "Matières"], ["enseignants", "Enseignants"], ["effectifs", "Effectifs"], ["presences", "Présences"]];
const PERIODES = { T1: "Trimestre 1", T2: "Trimestre 2", T3: "Trimestre 3", exam: "Examen" };

function Erreur({ error }) {
  const t = useT();
  if (!error || isCanceledError(error)) return null;
  const d = error?.response?.data || {};
  const msg = d.detail || Object.values(d).flat().join(" ") || t("L'analyse n'a pas pu être chargée.");
  return <p role="alert" className="text-sm text-red-700 py-6 text-center" data-testid="analyse-erreur">{msg}</p>;
}

function Chargement() {
  const t = useT();
  return <div className="h-40 rounded-xl bg-slate-100 animate-pulse" aria-label={t("Chargement…")} />;
}

function Tuile({ titre, valeur, detail, testid }) {
  return (
    <div className="rounded-xl border border-slate-100 bg-slate-50/60 p-3" data-testid={testid}>
      <p className="text-xs text-slate-500">{titre}</p>
      <p className="mt-0.5 text-lg font-bold text-slate-900 tabular-nums">{valeur}</p>
      {detail && <p className="text-xs text-slate-500 mt-0.5">{detail}</p>}
    </div>
  );
}

function Definitions({ items }) {
  const t = useT();
  return (
    <details className="text-xs text-slate-600" data-testid="analyse-definitions">
      <summary className="cursor-pointer font-medium text-slate-700">{t("Définitions")}</summary>
      <ul className="mt-2 space-y-1 list-disc pl-5">{items.map((x) => <li key={x}>{x}</li>)}</ul>
    </details>
  );
}

function useAnalyse(nom, params, actif = true) {
  const academyKey = useAcademyKey();
  return useQuery({ queryKey: ["analyse", nom, academyKey, params], queryFn: () => analyticsAPI[nom](params), enabled: actif });
}

const val = (v, t, suffixe = "") => (v === null || v === undefined ? t("Non disponible") : `${v}${suffixe}`);

function Tableau({ colonnes, lignes, testid, vide }) {
  const t = useT();
  if (!lignes.length) return <p className="text-sm text-slate-500 py-4 text-center">{vide || t("Aucune donnée pour cette sélection.")}</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" data-testid={testid}>
        <thead><tr className="text-left text-xs text-slate-500">
          {colonnes.map(([cle, nom, droite]) => <th key={cle} className={`py-1.5 pr-3 font-medium ${droite ? "text-right" : ""}`}>{nom}</th>)}
        </tr></thead>
        <tbody>
          {lignes.map((l, i) => (
            <tr key={l.id ?? i} className="border-t border-slate-100">
              {colonnes.map(([cle, , droite, rendu]) => (
                <td key={cle} className={`py-1.5 pr-3 ${droite ? "text-right tabular-nums whitespace-nowrap" : ""}`}>{rendu ? rendu(l) : l[cle] ?? "-"}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Resultats({ params }) {
  const t = useT();
  const { mode } = usePresentation();
  const [seuil, setSeuil] = useState(50);
  const q = useAnalyse("resultats", { ...params, seuil });
  if (q.isError) return <Erreur error={q.error} />;
  if (q.isPending) return <Chargement />;
  const r = q.data.data;
  const b = r.bareme;
  const s = r.synthese;
  if (!s.eleves_notes) return <p className="text-sm text-slate-500 py-8 text-center" data-testid="resultats-vide">{t("Aucune note pour cette sélection.")}</p>;
  const sur = (v) => val(v, t, ` / ${b}`);
  return (
    <div className="space-y-5" data-testid="analyse-resultats">
      {r.bareme_mixte && <p className="text-xs text-amber-800 bg-amber-50 rounded-lg px-3 py-2">{t("La sélection mélange des niveaux notés sur 10 et sur 20 : les moyennes sont affichées sur 20.")}</p>}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Tuile testid="res-moyenne" titre={t("Moyenne générale")} valeur={sur(s.moyenne)} detail={`${t("Médiane")} ${sur(s.mediane)}`} />
        <Tuile testid="res-reussite" titre={t("Taux de réussite")} valeur={val(s.taux_reussite, t, " %")} detail={`${t("Seuil")} ${r.seuil_pourcent} %`} />
        <Tuile testid="res-eleves" titre={t("Élèves notés")} valeur={s.eleves_notes} detail={`${s.notes} ${t("notes")}`} />
        <Tuile testid="res-dispersion" titre={t("Écart-type")} valeur={val(s.ecart_type, t)} detail={`${t("Min.")} ${val(s.minimum, t)} · ${t("Max.")} ${val(s.maximum, t)}`} />
      </div>
      <label className="flex items-center gap-2 text-xs text-slate-600">
        {t("Seuil de réussite")}
        <select className="input !py-1 !w-auto text-sm" value={seuil} onChange={(e) => setSeuil(Number(e.target.value))} data-testid="seuil">
          {[40, 50, 60, 70].map((v) => <option key={v} value={v}>{v} %</option>)}
        </select>
      </label>
      <div className="grid md:grid-cols-2 gap-4">
        <figure>
          <figcaption className="text-sm font-semibold text-slate-700 mb-2">{t("Répartition des moyennes")}</figcaption>
          <div className="h-52" data-testid="res-repartition">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={r.repartition.map((x) => ({ tranche: `${x.de}–${x.a}`, eleves: x.eleves }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="tranche" tick={{ fontSize: 11, fill: "#64748b" }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#64748b" }} width={32} />
                <Tooltip formatter={(v) => [v, t("élèves")]} />
                <Bar dataKey="eleves" fill={NAVY} radius={[4, 4, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </figure>
        <figure>
          <figcaption className="text-sm font-semibold text-slate-700 mb-2">{t("Progression par période")}</figcaption>
          {r.progression.length < 2 ? (
            <p className="text-sm text-slate-500 py-8 text-center">{t("Une seule période notée : pas encore de progression.")}</p>
          ) : (
            <div className="h-52" data-testid="res-progression">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={r.progression.map((p) => ({ periode: t(PERIODES[p.periode]), moyenne: p.moyenne }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="periode" tick={{ fontSize: 11, fill: "#64748b" }} />
                  <YAxis domain={[0, b]} tick={{ fontSize: 11, fill: "#64748b" }} width={32} />
                  <Tooltip formatter={(v) => [`${v} / ${b}`, t("Moyenne")]} />
                  <Line dataKey="moyenne" stroke={OR} strokeWidth={2} dot={{ r: 4 }} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </figure>
      </div>
      <div>
        <h3 className="text-sm font-semibold text-slate-700 mb-2">{t("Niveaux de maîtrise")}</h3>
        <ul className="flex flex-wrap gap-2" data-testid="res-maitrise">
          {r.maitrise.map((m) => (
            <li key={m.min_pourcent} className="rounded-lg border border-slate-200 px-2.5 py-1 text-xs">
              {libelleDouble(mode, m.libelle_fr, m.libelle_en)} ({t("dès")} {m.min_pourcent} %) : <strong>{m.eleves}</strong>
            </li>
          ))}
        </ul>
      </div>
      <Tableau testid="res-classes" lignes={r.par_classe} colonnes={[
        ["nom", t("Classe")], ["eleves_notes", t("Élèves notés"), true], ["notes", t("Notes"), true],
        ["moyenne", t("Moyenne"), true, (l) => sur(l.moyenne)], ["taux_reussite", t("Réussite"), true, (l) => val(l.taux_reussite, t, " %")],
      ]} />
      <div data-testid="res-listes">
        {r.listes ? (
          <div className="grid md:grid-cols-2 gap-4">
            {[["plus_hautes", "Moyennes les plus élevées"], ["a_accompagner", "Élèves à accompagner (sous le seuil)"]].map(([cle, titre]) => (
              <div key={cle}>
                <h3 className="text-sm font-semibold text-slate-700 mb-1">{t(titre)}</h3>
                <Tableau lignes={r.listes[cle]} vide={t("Aucun élève dans cette liste.")} colonnes={[
                  ["nom", t("Élève")], ["notes", t("Notes"), true], ["moyenne", t("Moyenne"), true, (l) => sur(l.moyenne)],
                ]} />
              </div>
            ))}
            <p className="text-xs text-slate-500 md:col-span-2">
              {t("Seuls les élèves ayant au moins {n} notes sont comparés.", { n: r.min_evaluations })}
              {r.listes.exclus_trop_peu_de_notes > 0 && ` ${t("{n} élève(s) écarté(s) faute de notes suffisantes.", { n: r.listes.exclus_trop_peu_de_notes })}`}
            </p>
          </div>
        ) : <p className="text-xs text-slate-500">{t("Choisissez une classe ou un niveau pour voir les listes d'élèves : ils ne sont comparés qu'entre conditions comparables.")}</p>}
      </div>
      <Definitions items={[
        t("Moyenne d'une matière : moyenne de toutes les notes de l'élève (chaque évaluation compte pareil)."),
        t("Moyenne générale : moyennes des matières pondérées par leur coefficient, comme sur le bulletin."),
        t("Taux de réussite : part des élèves dont la moyenne atteint le seuil choisi."),
        t("Niveaux de maîtrise : barème d'appréciations de l'académie (Paramètres)."),
        t("Progression : même sélection, moyenne de chaque période."),
      ]} />
    </div>
  );
}

function Matieres({ params }) {
  const t = useT();
  const q = useAnalyse("matieres", params);
  if (q.isError) return <Erreur error={q.error} />;
  if (q.isPending) return <Chargement />;
  const r = q.data.data;
  const sur = (v) => val(v, t, ` / ${r.bareme}`);
  return (
    <div className="space-y-3" data-testid="analyse-matieres">
      <Tableau testid="mat-table" lignes={r.matieres} colonnes={[
        ["nom", t("Matière")], ["coefficient", t("Coef."), true], ["eleves_notes", t("Élèves notés"), true], ["notes", t("Notes"), true],
        ["moyenne", t("Moyenne"), true, (l) => sur(l.moyenne)], ["ecart_type", t("Écart-type"), true],
        ["taux_reussite", t("Réussite"), true, (l) => val(l.taux_reussite, t, " %")],
      ]} />
      <Definitions items={[t("Écart-type : dispersion des moyennes des élèves ; plus il est élevé, plus les résultats sont hétérogènes."),
        t("Comparez des matières avec un nombre de notes proche : une matière peu évaluée donne une moyenne moins fiable.")]} />
    </div>
  );
}

function Enseignants({ params }) {
  const t = useT();
  const q = useAnalyse("enseignants", params);
  if (q.isError) return <Erreur error={q.error} />;
  if (q.isPending) return <Chargement />;
  const r = q.data.data;
  return (
    <div className="space-y-3" data-testid="analyse-enseignants">
      <p className="text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2" data-testid="avertissement-enseignants">
        {t(r.avertissement)}
      </p>
      <Tableau testid="ens-table" lignes={r.lignes} colonnes={[
        ["enseignant", t("Enseignant")], ["classe", t("Classe")], ["matiere", t("Matière")],
        ["eleves_notes", t("Élèves notés"), true], ["notes_par_eleve", t("Notes par élève"), true],
        ["moyenne", t("Moyenne"), true, (l) => val(l.moyenne, t, ` / ${r.bareme}`)],
        ["taux_reussite", t("Réussite"), true, (l) => val(l.taux_reussite, t, " %")],
      ]} />
    </div>
  );
}

function Effectifs({ params }) {
  const t = useT();
  const q = useAnalyse("effectifs", params);
  if (q.isError) return <Erreur error={q.error} />;
  if (q.isPending) return <Chargement />;
  const r = q.data.data;
  return (
    <div className="space-y-4" data-testid="analyse-effectifs">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Tuile testid="eff-inscrits" titre={t("Élèves inscrits")} valeur={r.inscrits} detail={r.annee.nom} />
        <Tuile titre={t("Filles")} valeur={r.par_genre.F} />
        <Tuile titre={t("Garçons")} valeur={r.par_genre.M} />
        <Tuile titre={t("Genre non renseigné")} valeur={r.par_genre.non_renseigne} />
      </div>
      {r.actifs_sans_inscription > 0 && (
        <p className="text-xs text-amber-800 bg-amber-50 rounded-lg px-3 py-2" data-testid="eff-sans-inscription">
          {t("{n} élève(s) actif(s) sans inscription pour cette année : ils ne sont pas comptés.", { n: r.actifs_sans_inscription })}
        </p>
      )}
      <Tableau testid="eff-classes" lignes={r.par_classe} colonnes={[
        ["nom", t("Classe")], ["niveau", t("Niveau")], ["inscrits", t("Inscrits"), true], ["filles", t("Filles"), true],
        ["garcons", t("Garçons"), true], ["capacite", t("Capacité"), true],
        ["taux_remplissage", t("Remplissage"), true, (l) => val(l.taux_remplissage, t, " %")],
      ]} />
      <Definitions items={[t("Inscrits : inscriptions annuelles actives de l'année choisie (élèves actifs)."),
        t("Remplissage : inscrits divisés par la capacité de la classe.")]} />
    </div>
  );
}

function Presences({ params }) {
  const t = useT();
  const q = useAnalyse("presences", params);
  if (q.isError) return <Erreur error={q.error} />;
  if (q.isPending) return <Chargement />;
  const r = q.data.data;
  const s = r.synthese;
  if (!s.appels) return <p className="text-sm text-slate-500 py-8 text-center">{t("Aucun appel enregistré pour cette sélection.")}</p>;
  return (
    <div className="space-y-4" data-testid="analyse-presences">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Tuile testid="pres-taux" titre={t("Taux de présence")} valeur={val(s.taux_presence, t, " %")} detail={`${s.appels} ${t("appels")}`} />
        <Tuile titre={t("Absences")} valeur={s.absent} detail={val(s.taux_absence, t, " %")} />
        <Tuile titre={t("Retards")} valeur={s.late} />
        <Tuile titre={t("Absences excusées")} valeur={s.excused} />
      </div>
      {r.par_mois.length > 0 && (
        <div className="h-52">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={r.par_mois.map((m) => ({ mois: m.mois, taux: m.taux_presence }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
              <XAxis dataKey="mois" tick={{ fontSize: 11, fill: "#64748b" }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#64748b" }} width={32} />
              <Tooltip formatter={(v) => [`${v} %`, t("Taux de présence")]} />
              <Bar dataKey="taux" fill={NAVY} radius={[4, 4, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      <Tableau testid="pres-classes" lignes={r.par_classe} colonnes={[
        ["nom", t("Classe")], ["appels", t("Appels"), true], ["absent", t("Absences"), true], ["late", t("Retards"), true],
        ["taux_presence", t("Présence"), true, (l) => val(l.taux_presence, t, " %")],
      ]} />
      {r.eleves_a_suivre?.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-slate-700 mb-1">{t("Élèves à suivre (absences non justifiées)")}</h3>
          <Tableau lignes={r.eleves_a_suivre} colonnes={[["nom", t("Élève")], ["absences_non_justifiees", t("Absences"), true]]} />
        </div>
      )}
      <Definitions items={[t("Taux de présence : présents et retards divisés par le nombre d'appels enregistrés."),
        t("Les jours sans appel ne sont pas comptés : un taux élevé avec peu d'appels reste peu significatif.")]} />
    </div>
  );
}

function Contenu() {
  const t = useT();
  const { user } = useAuth();
  const academyKey = useAcademyKey();
  const [filtres, setFiltres] = useState(VIDES);
  const [onglet, setOnglet] = useState("resultats");
  const estPersonnel = user?.role === "superadmin" || user?.role === "admin";
  useEffect(() => setFiltres(VIDES), [academyKey]);
  const params = parametres(filtres);
  const options = useQuery({ queryKey: ["analyse-filtres", academyKey, params], queryFn: () => analyticsAPI.filtres(params),
    placeholderData: keepPreviousData });
  const o = options.data?.data;
  const LIBELLES = { annee: t("Année scolaire"), periode: t("Période"), cycle: t("Cycle"), niveau: t("Niveau"), classe: t("Classe"),
    matiere: t("Matière"), enseignant: t("Enseignant"), eleve: t("Élève"), genre: t("Genre") };
  const choix = {
    annee: (o?.annees || []).map((x) => [String(x.id), x.nom]), periode: (o?.periodes || []).map((x) => [x.id, t(x.nom)]),
    cycle: (o?.cycles || []).map((x) => [x.id, t(x.nom)]), niveau: (o?.niveaux || []).map((x) => [String(x.id), x.nom]),
    classe: (o?.classes || []).map((x) => [String(x.id), x.nom]), matiere: (o?.matieres || []).map((x) => [String(x.id), x.nom]),
    enseignant: (o?.enseignants || []).map((x) => [String(x.id), x.nom]), eleve: (o?.eleves || []).map((x) => [String(x.id), x.nom]),
    genre: [["F", t("Filles")], ["M", t("Garçons")]],
  };
  const cles = Object.keys(VIDES).filter((k) => k !== "enseignant" || estPersonnel);
  const onglets = ONGLETS;
  const actifs = Object.entries(filtres).filter(([, v]) => v !== "");

  if (options.isError) {
    return (
      <div className="space-y-4">
        <PageHeader title={t("Centre d'analyse")} />
        <div className="card"><Erreur error={options.error} /></div>
      </div>
    );
  }
  return (
    <div className="space-y-4">
      <PageHeader title={t("Centre d'analyse")} subtitle={o ? `${o.academie.nom}` : t("Effectifs, résultats et présences")} action={<ChoixPresentation />} />
      <div className="card" data-testid="analyse-filtres">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
          {cles.map((cle) => (
            <label key={cle} className="flex flex-col gap-1 text-xs text-slate-600 min-w-0">
              <span className="font-medium">{LIBELLES[cle]}</span>
              <select className="input !py-1 text-sm" value={filtres[cle]} data-testid={`af-${cle}`}
                disabled={cle === "eleve" && !filtres.classe}
                onChange={(e) => setFiltres((f) => changer(f, cle, e.target.value))}>
                <option value="">{cle === "annee" ? t("Année en cours") : t("Tous")}</option>
                {choix[cle].map(([v, n]) => <option key={v} value={v}>{n}</option>)}
              </select>
            </label>
          ))}
        </div>
        {actifs.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 mt-3">
            <ul className="flex flex-wrap gap-1.5" aria-label={t("Filtres actifs")} data-testid="af-actifs">
              {actifs.map(([cle, v]) => (
                <li key={cle} className="inline-flex items-center gap-1 rounded-full bg-feba-navy/10 text-feba-navy text-xs px-2 py-0.5">
                  {LIBELLES[cle]} : {choix[cle].find(([id]) => id === v)?.[1] || v}
                  <button type="button" onClick={() => setFiltres((f) => changer(f, cle, ""))} aria-label={`${t("Retirer le filtre")} ${LIBELLES[cle]}`}>
                    <X className="w-3 h-3" aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
            <button type="button" className="text-xs font-medium text-red-700 hover:underline ml-auto" data-testid="af-reinitialiser"
              onClick={() => setFiltres(VIDES)}>{t("Réinitialiser les filtres")}</button>
          </div>
        )}
      </div>
      <div className="card">
        <div className="flex flex-wrap gap-1.5 mb-4" role="tablist">
          {onglets.map(([v, nom]) => (
            <button key={v} type="button" role="tab" aria-selected={onglet === v} onClick={() => setOnglet(v)} data-testid={`onglet-${v}`}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium ${onglet === v ? "bg-feba-navy text-white" : "bg-white border border-slate-200 text-slate-600"}`}>
              {t(nom)}
            </button>
          ))}
        </div>
        {onglet === "resultats" && <Resultats params={params} />}
        {onglet === "matieres" && <Matieres params={params} />}
        {onglet === "enseignants" && <Enseignants params={params} />}
        {onglet === "effectifs" && <Effectifs params={params} />}
        {onglet === "presences" && <Presences params={params} />}
      </div>
    </div>
  );
}

export default function Analyses() {
  return <PresentationProvider><Contenu /></PresentationProvider>;
}
