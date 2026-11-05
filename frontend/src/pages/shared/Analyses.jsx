/**
 * Centre d'analyse (personnel) : centre de pilotage visuel.
 *
 * Tout est calculé par le serveur (/api/analytics/…), dans le périmètre du profil :
 * un enseignant ne voit que ses classes, sans aucune donnée financière.
 * Les filtres (combinables, sélection multiple pour les classes, matières,
 * enseignants et types d'évaluation) s'appliquent à tous les onglets. Le mode de
 * présentation (FR, EN, bilingue) ne change que les libellés.
 *
 * Chaque graphique indique sa période, sa population et son unité ; sans donnée,
 * il dit pourquoi au lieu d'afficher un graphique vide.
 */
import { useEffect, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertTriangle, X } from "lucide-react";
import { analyticsAPI } from "../../api";
import { isCanceledError } from "../../api/academyScope";
import PageHeader from "../../components/ui/PageHeader";
import { ChoixPresentation, libelleDouble, PresentationProvider, usePresentation, useT } from "../../components/analytics/presentation";
import { CarteGraphique, ChoixMultiple, GRIS, NAVY, OR, Tableau, Tuile, VERT, Vide } from "../../components/analytics/elements";
import { useAuth } from "../../hooks/useAuth";
import { useAcademyKey } from "../../hooks/useEntityContext";

export const VIDES = { annee: "", periode: "", cycle: "", niveau: "", classe: [], matiere: [], enseignant: [], type_evaluation: [], eleve: "", genre: "" };
const DEPENDANTS = { annee: ["classe", "eleve"], cycle: ["niveau", "classe", "eleve"], niveau: ["classe", "eleve", "matiere"], classe: ["eleve"] };
export const changer = (f, cle, v) => {
  const s = { ...f, [cle]: v };
  for (const d of DEPENDANTS[cle] || []) s[d] = Array.isArray(VIDES[d]) ? [] : "";
  return s;
};
/** Paramètres envoyés : valeurs renseignées seulement ; listes jointes par des virgules. */
export const parametres = (f) => Object.fromEntries(Object.entries(f)
  .filter(([, v]) => (Array.isArray(v) ? v.length : v !== ""))
  .map(([k, v]) => [k, Array.isArray(v) ? v.join(",") : v]));
const ONGLETS = [["ensemble", "Vue d'ensemble"], ["resultats", "Résultats"], ["matieres", "Matières"], ["classes", "Classes"],
  ["enseignants", "Enseignants"], ["effectifs", "Effectifs"], ["presences", "Présences"]];
const PERIODES = { T1: "Trimestre 1", T2: "Trimestre 2", T3: "Trimestre 3", exam: "Examen" };
const CYCLES = { maternelle: "Maternelle", primaire: "Primaire", college: "Collège", lycee: "Lycée", sans: "Sans classe" };
const TYPES = [["devoir", "Devoir"], ["interrogation", "Interrogation / Devoir de classe"], ["controle", "Contrôle"],
  ["examen", "Examen / Évaluation"], ["tp", "Travaux Pratiques"], ["autre", "Autre"]];
const AXE = { fontSize: 11, fill: "#64748b" };

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

function useAnalyse(nom, params) {
  const academyKey = useAcademyKey();
  return useQuery({ queryKey: ["analyse", nom, academyKey, params], queryFn: () => analyticsAPI[nom](params), placeholderData: keepPreviousData });
}

const val = (v, t, suffixe = "") => (v === null || v === undefined ? t("Non disponible") : `${v}${suffixe}`);

function Etat({ q, children }) {
  if (q.isError) return <Erreur error={q.error} />;
  if (q.isPending) return <Chargement />;
  return children(q.data.data);
}

/** Barres horizontales d'une valeur par élément (classes, matières, enseignants). */
function Barres({ donnees, max, unite, couleur = NAVY, testid, surligne = () => false }) {
  const t = useT();
  const hauteur = Math.max(160, donnees.length * 30 + 40);
  return (
    <div style={{ height: hauteur }} data-testid={testid}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={donnees} layout="vertical" margin={{ left: 8, right: 24 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
          <XAxis type="number" domain={[0, max]} tick={AXE} />
          <YAxis type="category" dataKey="nom" tick={AXE} width={120} />
          <Tooltip formatter={(v, _n, p) => [`${v ?? t("Non disponible")}${v === null || v === undefined ? "" : unite}`, p.payload.info || p.payload.nom]} />
          <Bar dataKey="valeur" name={t("Valeur")} radius={[0, 4, 4, 0]} isAnimationActive={false}>
            {donnees.map((d) => <Cell key={d.nom} fill={surligne(d) ? OR : couleur} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function Repartition({ tranches, bareme, testid }) {
  const t = useT();
  return (
    <div className="h-52" data-testid={testid}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={tranches.map((x) => ({ tranche: `${x.de}–${x.a}`, eleves: x.eleves }))} margin={{ bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
          <XAxis dataKey="tranche" tick={AXE} label={{ value: t("Moyenne sur {b}", { b: bareme }), position: "insideBottom", offset: -4, fontSize: 11 }} height={40} />
          <YAxis allowDecimals={false} tick={AXE} width={32} />
          <Tooltip formatter={(v) => [v, t("élèves")]} labelFormatter={(l) => t("Moyennes entre {l}", { l })} />
          <Bar dataKey="eleves" name={t("Élèves")} fill={NAVY} radius={[4, 4, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function Evolution({ points, bareme, testid }) {
  const t = useT();
  if (!points || points.length < 2) return <Vide raison={t("Une seule période notée : l'évolution apparaîtra avec la période suivante.")} />;
  return (
    <div className="h-52" data-testid={testid}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points.map((p) => ({ periode: t(PERIODES[p.periode]), moyenne: p.moyenne }))}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
          <XAxis dataKey="periode" tick={AXE} />
          <YAxis domain={[0, bareme]} tick={AXE} width={32} />
          <Tooltip formatter={(v) => [`${v} / ${bareme}`, t("Moyenne")]} />
          <Line dataKey="moyenne" name={t("Moyenne")} stroke={OR} strokeWidth={2} dot={{ r: 4 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function Limites({ limites }) {
  const t = useT();
  if (!limites?.length) return null;
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900" data-testid="analyse-limites" role="note">
      <p className="font-semibold flex items-center gap-1.5"><AlertTriangle className="w-4 h-4" aria-hidden="true" />{t("Limites des données")}</p>
      <ul className="mt-1 list-disc pl-5 space-y-0.5">{limites.map((l) => <li key={l.texte}>{t(l.texte, l.params)}</li>)}</ul>
    </div>
  );
}

// ── Onglets ─────────────────────────────────────────────────────────────

function VueEnsemble({ params, contexte }) {
  const t = useT();
  const q = useAnalyse("vueEnsemble", params);
  return (
    <Etat q={q}>{(r) => {
      const k = r.kpi;
      const b = r.bareme;
      const tableauClasses = (
        <Tableau lignes={r.classes} colonnes={[["nom", t("Classe")], ["eleves_notes", t("Élèves notés"), true],
          ["moyenne", t("Moyenne"), true, (l) => val(l.moyenne, t, ` / ${b}`)], ["taux_reussite", t("Réussite"), true, (l) => val(l.taux_reussite, t, " %")]]} />
      );
      return (
        <div className="space-y-4" data-testid="analyse-ensemble">
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
            <Tuile testid="kpi-inscrits" titre={t("Élèves inscrits")} valeur={k.inscrits} detail={r.annee.nom}
              aide={t("Inscriptions annuelles actives de l'année choisie.")} />
            <Tuile testid="kpi-notes" titre={t("Élèves notés")} valeur={k.eleves_notes} detail={`${k.notes} ${t("notes")}`} />
            <Tuile testid="kpi-moyenne" accent titre={t("Moyenne générale")} valeur={val(k.moyenne, t, ` / ${b}`)}
              detail={`${t("Médiane")} ${val(k.mediane, t)}`} aide={t("Moyennes des matières pondérées par leur coefficient, comme sur le bulletin.")} />
            <Tuile testid="kpi-reussite" accent titre={t("Taux de réussite")} valeur={val(k.taux_reussite, t, " %")}
              detail={`${t("Seuil")} ${r.seuil_pourcent} %`} aide={t("Part des élèves dont la moyenne atteint le seuil.")} />
            <Tuile testid="kpi-objectif" titre={t("Objectif atteint / à accompagner")} valeur={`${k.objectif_atteint} / ${k.a_accompagner}`}
              detail={t("élèves au-dessus / sous le seuil")} />
            <Tuile testid="kpi-presence" titre={t("Taux de présence")} valeur={k.appels ? val(k.taux_presence, t, " %") : t("Non mesurable")}
              detail={k.appels ? `${k.appels} ${t("appels")}` : t("aucun appel enregistré")} />
          </div>
          <Limites limites={r.limites} />
          <div className="grid lg:grid-cols-2 gap-4">
            <CarteGraphique testid="ens-repartition" titre={t("Répartition des moyennes générales")} contexte={contexte}
              population={t("{n} élèves notés", { n: k.eleves_notes })} unite={t("nombre d'élèves")} vide={!k.eleves_notes}
              raisonVide={t("Aucune note pour cette sélection.")}>
              <Repartition tranches={r.repartition} bareme={b} />
            </CarteGraphique>
            <CarteGraphique testid="ens-classes" titre={t("Moyenne générale par classe")} contexte={contexte}
              population={t("{n} classes", { n: r.classes.length })} unite={t("moyenne sur {b}", { b })} vide={!r.classes.length}
              raisonVide={t("Aucune note pour cette sélection.")} detail={tableauClasses}>
              <Barres donnees={r.classes.map((c) => ({ nom: c.nom, valeur: c.moyenne, info: `${c.nom} · ${t("Réussite")} ${val(c.taux_reussite, t, " %")} · ${c.eleves_notes} ${t("élèves")}` }))}
                max={b} unite={` / ${b}`} />
            </CarteGraphique>
            <CarteGraphique testid="ens-progression" titre={t("Évolution de la moyenne par période")} contexte={r.annee.nom}
              unite={t("moyenne sur {b}", { b })}>
              <Evolution points={r.progression} bareme={b} />
            </CarteGraphique>
            <CarteGraphique testid="ens-cycles" titre={t("Effectifs par cycle")} contexte={r.annee.nom}
              population={t("{n} inscrits", { n: k.inscrits })} unite={t("nombre d'élèves")} vide={!r.par_cycle.length}
              raisonVide={t("Aucune inscription pour cette année.")}>
              <Barres donnees={r.par_cycle.map((c) => ({ nom: t(CYCLES[c.cycle] || c.cycle), valeur: c.inscrits }))}
                max={Math.max(...r.par_cycle.map((c) => c.inscrits), 1)} unite="" couleur={VERT} />
            </CarteGraphique>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            {[["matieres_plus_hautes", "Matières aux moyennes les plus élevées"], ["matieres_difficultes", "Matières aux résultats les plus faibles"]].map(([cle, titre]) => (
              <CarteGraphique key={cle} testid={`ens-${cle}`} titre={t(titre)} contexte={contexte} unite={t("moyenne sur {b}", { b })}
                vide={!r[cle].length} raisonVide={t("Pas assez de matières comparables (nombre de notes suffisant) pour ce classement.")}>
                <ul className="space-y-1.5">
                  {r[cle].map((m) => (
                    <li key={m.id} className="flex items-center justify-between gap-2 text-sm">
                      <span className="truncate">{m.nom}</span>
                      <span className="tabular-nums text-slate-600 whitespace-nowrap">{val(m.moyenne, t, ` / ${b}`)} · {val(m.taux_reussite, t, " %")} · {m.notes} {t("notes")}</span>
                    </li>
                  ))}
                </ul>
              </CarteGraphique>
            ))}
          </div>
        </div>
      );
    }}</Etat>
  );
}

function Resultats({ params, contexte }) {
  const t = useT();
  const { mode } = usePresentation();
  const [seuil, setSeuil] = useState(50);
  const q = useAnalyse("resultats", { ...params, seuil });
  return (
    <Etat q={q}>{(r) => {
      const b = r.bareme;
      const s = r.synthese;
      if (!s.eleves_notes) return <Vide testid="resultats-vide" raison={t("Aucune note pour cette sélection.")} />;
      const sur = (v) => val(v, t, ` / ${b}`);
      const population = t("{n} élèves notés, {m} notes", { n: s.eleves_notes, m: s.notes });
      return (
        <div className="space-y-4" data-testid="analyse-resultats">
          {r.bareme_mixte && <p className="text-xs text-amber-800 bg-amber-50 rounded-lg px-3 py-2">{t("La sélection mélange des niveaux notés sur 10 et sur 20 : les moyennes sont affichées sur 20.")}</p>}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Tuile testid="res-moyenne" accent titre={t("Moyenne générale")} valeur={sur(s.moyenne)} detail={`${t("Médiane")} ${sur(s.mediane)}`} />
            <Tuile testid="res-reussite" accent titre={t("Taux de réussite")} valeur={val(s.taux_reussite, t, " %")} detail={`${t("Seuil")} ${r.seuil_pourcent} %`} />
            <Tuile testid="res-eleves" titre={t("Élèves notés")} valeur={s.eleves_notes} detail={`${s.notes} ${t("notes")}`} />
            <Tuile testid="res-dispersion" titre={t("Écart-type")} valeur={val(s.ecart_type, t)} detail={`${t("Min.")} ${val(s.minimum, t)} · ${t("Max.")} ${val(s.maximum, t)}`}
              aide={t("Écart-type : dispersion des moyennes des élèves ; plus il est élevé, plus les résultats sont hétérogènes.")} />
          </div>
          <label className="flex items-center gap-2 text-xs text-slate-600">
            {t("Seuil de réussite")}
            <select className="input !py-1 !w-auto text-sm" value={seuil} onChange={(e) => setSeuil(Number(e.target.value))} data-testid="seuil">
              {[40, 50, 60, 70].map((v) => <option key={v} value={v}>{v} %</option>)}
            </select>
          </label>
          <div className="grid lg:grid-cols-2 gap-4">
            <CarteGraphique testid="res-repartition" titre={t("Répartition des moyennes")} contexte={contexte} population={population} unite={t("nombre d'élèves")}>
              <Repartition tranches={r.repartition} bareme={b} />
            </CarteGraphique>
            <CarteGraphique testid="res-progression" titre={t("Progression par période")} contexte={contexte} unite={t("moyenne sur {b}", { b })}>
              <Evolution points={r.progression} bareme={b} />
            </CarteGraphique>
            <CarteGraphique testid="res-maitrise" titre={t("Niveaux de maîtrise")} contexte={contexte} population={population} unite={t("nombre d'élèves")}>
              <Barres donnees={r.maitrise.map((m) => ({ nom: libelleDouble(mode, m.libelle_fr, m.libelle_en), valeur: m.eleves,
                info: `${libelleDouble(mode, m.libelle_fr, m.libelle_en)} · ${t("dès")} ${m.min_pourcent} %` }))}
                max={Math.max(...r.maitrise.map((m) => m.eleves), 1)} unite="" couleur={VERT} />
            </CarteGraphique>
            <CarteGraphique testid="res-classes" titre={t("Moyenne par classe")} contexte={contexte} unite={t("moyenne sur {b}", { b })}
              detail={<Tableau testid="res-classes-table" lignes={r.par_classe} colonnes={[
                ["nom", t("Classe")], ["eleves_notes", t("Élèves notés"), true], ["notes", t("Notes"), true],
                ["moyenne", t("Moyenne"), true, (l) => sur(l.moyenne)], ["taux_reussite", t("Réussite"), true, (l) => val(l.taux_reussite, t, " %")]]} />}>
              <Barres donnees={r.par_classe.map((c) => ({ nom: c.nom, valeur: c.moyenne, info: `${c.nom} · ${t("Réussite")} ${val(c.taux_reussite, t, " %")}` }))}
                max={b} unite={` / ${b}`} />
            </CarteGraphique>
          </div>
          <div data-testid="res-listes">
            {r.listes ? (
              <div className="grid md:grid-cols-2 gap-4">
                {[["plus_hautes", "Moyennes les plus élevées"], ["a_accompagner", "Élèves à accompagner (sous le seuil)"]].map(([cle, titre]) => (
                  <CarteGraphique key={cle} titre={t(titre)} contexte={contexte}
                    population={t("Seuls les élèves ayant au moins {n} notes sont comparés.", { n: r.min_evaluations })}>
                    <Tableau lignes={r.listes[cle]} vide={t("Aucun élève dans cette liste.")} colonnes={[
                      ["nom", t("Élève")], ["notes", t("Notes"), true], ["moyenne", t("Moyenne"), true, (l) => sur(l.moyenne)]]} />
                  </CarteGraphique>
                ))}
                {r.listes.exclus_trop_peu_de_notes > 0 && (
                  <p className="text-xs text-slate-500 md:col-span-2">{t("{n} élève(s) écarté(s) faute de notes suffisantes.", { n: r.listes.exclus_trop_peu_de_notes })}</p>
                )}
              </div>
            ) : <p className="text-xs text-slate-500">{t("Choisissez une seule classe ou un niveau pour voir les listes d'élèves : ils ne sont comparés qu'entre conditions comparables.")}</p>}
          </div>
        </div>
      );
    }}</Etat>
  );
}

function Matieres({ params, contexte }) {
  const t = useT();
  const q = useAnalyse("matieresDetail", params);
  const [choisie, setChoisie] = useState(null);
  return (
    <Etat q={q}>{(r) => {
      const b = r.bareme;
      if (!r.matieres.length) return <Vide raison={t("Aucune note pour cette sélection.")} />;
      const tri = [...r.matieres].sort((x, y) => (y.moyenne ?? -1) - (x.moyenne ?? -1));
      const m = r.matieres.find((x) => x.id === choisie) || tri[0];
      const hautes = new Set(r.classement.plus_hautes);
      const faibles = new Set(r.classement.difficultes);
      return (
        <div className="grid lg:grid-cols-2 gap-4" data-testid="analyse-matieres">
          <CarteGraphique testid="mat-moyennes" titre={t("Moyenne par matière")} contexte={contexte} unite={t("moyenne sur {b}", { b })}
            population={t("{n} matières", { n: r.matieres.length })}
            detail={<Tableau testid="mat-table" lignes={tri} colonnes={[
              ["nom", t("Matière")], ["coefficient", t("Coef."), true], ["eleves_notes", t("Élèves notés"), true], ["notes", t("Notes"), true],
              ["moyenne", t("Moyenne"), true, (l) => val(l.moyenne, t, ` / ${b}`)], ["ecart_type", t("Écart-type"), true],
              ["taux_reussite", t("Réussite"), true, (l) => val(l.taux_reussite, t, " %")]]} />}>
            <Barres donnees={tri.map((x) => ({ nom: x.nom, id: x.id, valeur: x.moyenne, info: `${x.nom} · ${x.notes} ${t("notes")} · ${t("Réussite")} ${val(x.taux_reussite, t, " %")}` }))}
              max={b} unite={` / ${b}`} surligne={(d) => faibles.has(d.id)} />
            <p className="text-xs text-slate-500 mt-1">
              {t("En or : matières aux résultats les plus faibles parmi celles qui ont assez de notes (au moins {n}).", { n: r.classement.min_evaluations })}
              {r.classement.non_comparees > 0 && ` ${t("{n} matière(s) non comparée(s) faute de notes.", { n: r.classement.non_comparees })}`}
            </p>
          </CarteGraphique>
          <div className="space-y-3">
            <label className="flex flex-col gap-1 text-xs text-slate-600">
              <span className="font-medium">{t("Matière détaillée")}</span>
              <select className="input !py-1 text-sm" value={m.id} onChange={(e) => setChoisie(Number(e.target.value))} data-testid="mat-choix">
                {tri.map((x) => <option key={x.id} value={x.id}>{x.nom}{hautes.has(x.id) ? " ▲" : faibles.has(x.id) ? " ▼" : ""}</option>)}
              </select>
            </label>
            <div className="grid grid-cols-3 gap-2">
              <Tuile titre={t("Moyenne")} valeur={val(m.moyenne, t, ` / ${b}`)} />
              <Tuile titre={t("Réussite")} valeur={val(m.taux_reussite, t, " %")} />
              <Tuile titre={t("Notes")} valeur={m.notes} detail={`${m.eleves_notes} ${t("élèves")}`} />
            </div>
            <CarteGraphique testid="mat-repartition" titre={t("Répartition des moyennes · {m}", { m: m.nom })} contexte={contexte} unite={t("nombre d'élèves")}>
              <Repartition tranches={m.repartition} bareme={b} />
            </CarteGraphique>
            <CarteGraphique testid="mat-evolution" titre={t("Évolution · {m}", { m: m.nom })} unite={t("moyenne sur {b}", { b })}>
              <Evolution points={m.evolution} bareme={b} />
            </CarteGraphique>
          </div>
        </div>
      );
    }}</Etat>
  );
}

function Classes({ params, contexte }) {
  const t = useT();
  const q = useAnalyse("classes", params);
  return (
    <Etat q={q}>{(r) => {
      const b = r.bareme;
      if (!r.classes.length) return <Vide raison={t("Aucune classe pour cette sélection.")} />;
      const notees = r.classes.filter((c) => c.eleves_notes);
      return (
        <div className="grid lg:grid-cols-2 gap-4" data-testid="analyse-classes">
          <CarteGraphique testid="cls-moyennes" titre={t("Moyenne générale par classe")} contexte={contexte} unite={t("moyenne sur {b}", { b })}
            vide={!notees.length} raisonVide={t("Aucune note pour cette sélection.")}>
            <Barres donnees={notees.map((c) => ({ nom: c.nom, valeur: c.moyenne, info: `${c.nom} · ${c.eleves_notes} ${t("élèves notés")}` }))} max={b} unite={` / ${b}`} />
          </CarteGraphique>
          <CarteGraphique testid="cls-reussite" titre={t("Taux de réussite par classe")} contexte={contexte} unite="%"
            vide={!notees.length} raisonVide={t("Aucune note pour cette sélection.")}>
            <Barres donnees={notees.map((c) => ({ nom: c.nom, valeur: c.taux_reussite, info: `${c.nom} · ${t("Seuil")} ${r.seuil_pourcent} %` }))} max={100} unite=" %" couleur={VERT} />
          </CarteGraphique>
          <CarteGraphique testid="cls-effectifs" titre={t("Effectifs : inscrits et élèves notés")} contexte={contexte} unite={t("nombre d'élèves")}
            detail={<Tableau testid="cls-table" lignes={r.classes} colonnes={[
              ["nom", t("Classe")], ["niveau", t("Niveau")], ["inscrits", t("Inscrits"), true], ["eleves_notes", t("Élèves notés"), true],
              ["moyenne", t("Moyenne"), true, (l) => val(l.moyenne, t, ` / ${b}`)], ["taux_reussite", t("Réussite"), true, (l) => val(l.taux_reussite, t, " %")]]} />}>
            <div style={{ height: Math.max(180, r.classes.length * 34 + 50) }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={r.classes.map((c) => ({ nom: c.nom, inscrits: c.inscrits, notes: c.eleves_notes }))} layout="vertical" margin={{ left: 8, right: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                  <XAxis type="number" allowDecimals={false} tick={AXE} />
                  <YAxis type="category" dataKey="nom" tick={AXE} width={110} />
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="inscrits" name={t("Inscrits")} fill={GRIS} radius={[0, 4, 4, 0]} isAnimationActive={false} />
                  <Bar dataKey="notes" name={t("Élèves notés")} fill={NAVY} radius={[0, 4, 4, 0]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CarteGraphique>
          <CarteGraphique testid="cls-evolution" titre={t("Évolution par classe")} unite={t("moyenne sur {b}", { b })}>
            {notees.every((c) => c.evolution.length < 2) ? <Vide raison={t("Une seule période notée : l'évolution apparaîtra avec la période suivante.")} /> : (
              <Tableau lignes={notees} colonnes={[["nom", t("Classe")], ...["T1", "T2", "T3", "exam"].map((p) => [p, t(PERIODES[p]), true,
                (l) => val(l.evolution.find((e) => e.periode === p)?.moyenne, t)])]} />
            )}
          </CarteGraphique>
        </div>
      );
    }}</Etat>
  );
}

function Enseignants({ params, contexte, filtres, setFiltres, options, estPersonnel }) {
  const t = useT();
  const q = useAnalyse("enseignantsProfils", params);
  return (
    <Etat q={q}>{(r) => {
      const b = r.bareme;
      const profils = r.profils;
      const choix = filtres.enseignant;
      return (
        <div className="space-y-4" data-testid="analyse-enseignants">
          <p className="text-xs text-slate-700 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2" data-testid="avertissement-enseignants">{t(r.avertissement)}</p>
          {estPersonnel && (
            <div className="flex flex-wrap items-center gap-1.5" data-testid="ens-selection">
              <span className="text-xs text-slate-600">{t("Choisissez un ou plusieurs enseignants pour les comparer :")}</span>
              {(options || []).map(([id, nom]) => (
                <button key={id} type="button" aria-pressed={choix.includes(id)} data-testid={`ens-choix-${id}`}
                  onClick={() => setFiltres((f) => ({ ...f, enseignant: f.enseignant.includes(id) ? f.enseignant.filter((x) => x !== id) : [...f.enseignant, id] }))}
                  className={`px-2.5 py-1 rounded-full text-xs ${choix.includes(id) ? "bg-feba-navy text-white" : "bg-white border border-slate-200 text-slate-600"}`}>
                  {nom}
                </button>
              ))}
            </div>
          )}
          {r.sans_note?.length > 0 && (
            <p className="text-xs text-amber-800 bg-amber-50 rounded-lg px-3 py-2" data-testid="ens-sans-note">
              {t("Aucune note attribuée dans cette sélection par : {noms}.", { noms: r.sans_note.map((x) => x.nom).join(", ") })}
            </p>
          )}
          {!profils.length ? <Vide raison={t("Aucune note attribuée par ces enseignants pour cette sélection.")} /> : (
            <>
              {profils.length > 1 && (
                <CarteGraphique testid="ens-comparaison" titre={t("Comparaison descriptive des enseignants")} contexte={contexte}
                  unite={t("moyenne sur {b}", { b })}
                  population={t("Classes, matières et nombre de notes diffèrent : à lire avec le détail de chaque profil.")}>
                  <Barres donnees={profils.map((p) => ({ nom: p.nom, valeur: p.moyenne, info: `${p.nom} · ${p.matieres.join(", ")} · ${p.classes.join(", ")} · ${p.notes} ${t("notes")}` }))}
                    max={b} unite={` / ${b}`} />
                </CarteGraphique>
              )}
              <div className="grid xl:grid-cols-2 gap-4">
                {profils.map((p) => (
                  <section key={p.id} className="rounded-xl border border-slate-200 p-3 space-y-3 min-w-0" data-testid={`ens-profil-${p.id}`}>
                    <div>
                      <h3 className="font-semibold text-slate-800">{p.nom}</h3>
                      <p className="text-xs text-slate-500">{t("Classes")} : {p.classes.join(", ")} · {t("Matières")} : {p.matieres.join(", ")}</p>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      <Tuile titre={t("Élèves évalués")} valeur={p.eleves_evalues} />
                      <Tuile titre={t("Notes attribuées")} valeur={p.notes} />
                      <Tuile titre={t("Moyenne des notes")} valeur={val(p.moyenne, t, ` / ${b}`)} />
                      <Tuile titre={t("Réussite (élève × matière)")} valeur={val(p.taux_reussite, t, " %")}
                        aide={t("Part des moyennes élève × matière qui atteignent le seuil.")} />
                    </div>
                    {p.affectations_sans_note > 0 && (
                      <p className="text-xs text-amber-800">{t("{n} affectation(s) (classe et matière) sans aucune note pour cette sélection.", { n: p.affectations_sans_note })}</p>
                    )}
                    <CarteGraphique titre={t("Répartition des moyennes par élève et par matière")} contexte={contexte}
                      population={t("{n} moyennes (un élève dans une matière)", { n: p.moyennes_eleve_matiere })} unite={t("nombre de moyennes")}>
                      <Repartition tranches={p.repartition} bareme={b} />
                    </CarteGraphique>
                    <CarteGraphique titre={t("Évolution par période")} unite={t("moyenne sur {b}", { b })}>
                      <Evolution points={p.evolution} bareme={b} />
                    </CarteGraphique>
                    <CarteGraphique titre={t("Par classe et matière")} contexte={contexte} unite={t("moyenne sur {b}", { b })}>
                      <Tableau lignes={p.detail} colonnes={[["classe", t("Classe")], ["matiere", t("Matière")], ["eleves_notes", t("Élèves notés"), true],
                        ["notes", t("Notes"), true], ["moyenne", t("Moyenne"), true, (l) => val(l.moyenne, t, ` / ${b}`)],
                        ["taux_reussite", t("Réussite"), true, (l) => val(l.taux_reussite, t, " %")]]} />
                    </CarteGraphique>
                  </section>
                ))}
              </div>
            </>
          )}
        </div>
      );
    }}</Etat>
  );
}

function Effectifs({ params, contexte }) {
  const t = useT();
  const q = useAnalyse("effectifs", params);
  return (
    <Etat q={q}>{(r) => (
      <div className="space-y-4" data-testid="analyse-effectifs">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Tuile testid="eff-inscrits" accent titre={t("Élèves inscrits")} valeur={r.inscrits} detail={r.annee.nom} />
          <Tuile titre={t("Filles")} valeur={r.par_genre.F} />
          <Tuile titre={t("Garçons")} valeur={r.par_genre.M} />
          <Tuile titre={t("Genre non renseigné")} valeur={r.par_genre.non_renseigne} />
        </div>
        {r.actifs_sans_inscription > 0 && (
          <p className="text-xs text-amber-800 bg-amber-50 rounded-lg px-3 py-2" data-testid="eff-sans-inscription">
            {t("{n} élève(s) actif(s) sans inscription pour cette année : ils ne sont pas comptés.", { n: r.actifs_sans_inscription })}
          </p>
        )}
        <div className="grid lg:grid-cols-2 gap-4">
          <CarteGraphique testid="eff-niveaux" titre={t("Inscrits par niveau")} contexte={contexte} unite={t("nombre d'élèves")} vide={!r.par_niveau.length}
            raisonVide={t("Aucune inscription pour cette année.")}>
            <Barres donnees={r.par_niveau.map((n) => ({ nom: n.nom, valeur: n.inscrits }))} max={Math.max(...r.par_niveau.map((n) => n.inscrits), 1)} unite="" couleur={VERT} />
          </CarteGraphique>
          <CarteGraphique testid="eff-classes" titre={t("Remplissage des classes")} contexte={contexte} unite={t("% de la capacité")}
            vide={!r.par_classe.length} raisonVide={t("Aucune inscription pour cette année.")}
            detail={<Tableau testid="eff-table" lignes={r.par_classe} colonnes={[
              ["nom", t("Classe")], ["niveau", t("Niveau")], ["inscrits", t("Inscrits"), true], ["filles", t("Filles"), true],
              ["garcons", t("Garçons"), true], ["capacite", t("Capacité"), true], ["taux_remplissage", t("Remplissage"), true, (l) => val(l.taux_remplissage, t, " %")]]} />}>
            <Barres donnees={r.par_classe.map((c) => ({ nom: c.nom, valeur: c.taux_remplissage ?? 0, info: `${c.nom} · ${c.inscrits} / ${c.capacite ?? "?"}` }))}
              max={Math.max(100, ...r.par_classe.map((c) => c.taux_remplissage || 0))} unite=" %" surligne={(d) => d.valeur > 100} />
          </CarteGraphique>
          <CarteGraphique testid="eff-mois" titre={t("Inscriptions enregistrées par mois")} contexte={r.annee.nom} unite={t("nombre d'inscriptions")}
            vide={!r.inscriptions_par_mois.length} raisonVide={t("Aucune inscription pour cette année.")}>
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={r.inscriptions_par_mois}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="mois" tick={AXE} />
                  <YAxis allowDecimals={false} tick={AXE} width={32} />
                  <Tooltip formatter={(v) => [v, t("inscriptions")]} />
                  <Bar dataKey="inscriptions" name={t("Inscriptions")} fill={NAVY} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CarteGraphique>
        </div>
      </div>
    )}</Etat>
  );
}

function Presences({ params, contexte }) {
  const t = useT();
  const q = useAnalyse("presences", params);
  return (
    <Etat q={q}>{(r) => {
      const s = r.synthese;
      if (!s.appels) return <Vide testid="presences-vide" raison={t("Aucun appel enregistré pour cette sélection : la présence ne peut pas être mesurée. Les appels se saisissent dans « Absences ».")} />;
      return (
        <div className="space-y-4" data-testid="analyse-presences">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Tuile testid="pres-taux" accent titre={t("Taux de présence")} valeur={val(s.taux_presence, t, " %")} detail={`${s.appels} ${t("appels")}`} />
            <Tuile titre={t("Absences")} valeur={s.absent} detail={val(s.taux_absence, t, " %")} />
            <Tuile titre={t("Retards")} valeur={s.late} />
            <Tuile titre={t("Absences excusées")} valeur={s.excused} />
          </div>
          <div className="grid lg:grid-cols-2 gap-4">
            <CarteGraphique titre={t("Taux de présence par mois")} contexte={contexte} unite="%" vide={!r.par_mois.length}>
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={r.par_mois.map((m) => ({ mois: m.mois, taux: m.taux_presence }))}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                    <XAxis dataKey="mois" tick={AXE} />
                    <YAxis domain={[0, 100]} tick={AXE} width={32} />
                    <Tooltip formatter={(v) => [`${v} %`, t("Taux de présence")]} />
                    <Line dataKey="taux" name={t("Taux de présence")} stroke={NAVY} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CarteGraphique>
            <CarteGraphique titre={t("Taux de présence par classe")} contexte={contexte} unite="%"
              detail={<Tableau testid="pres-classes" lignes={r.par_classe} colonnes={[
                ["nom", t("Classe")], ["appels", t("Appels"), true], ["absent", t("Absences"), true], ["late", t("Retards"), true],
                ["taux_presence", t("Présence"), true, (l) => val(l.taux_presence, t, " %")]]} />}>
              <Barres donnees={r.par_classe.map((c) => ({ nom: c.nom, valeur: c.taux_presence, info: `${c.nom} · ${c.appels} ${t("appels")}` }))} max={100} unite=" %" couleur={VERT} />
            </CarteGraphique>
          </div>
          {r.eleves_a_suivre?.length > 0 && (
            <CarteGraphique titre={t("Élèves à suivre (absences non justifiées)")} contexte={contexte}>
              <Tableau lignes={r.eleves_a_suivre} colonnes={[["nom", t("Élève")], ["absences_non_justifiees", t("Absences"), true]]} />
            </CarteGraphique>
          )}
        </div>
      );
    }}</Etat>
  );
}

// ── Page ────────────────────────────────────────────────────────────────

function Contenu() {
  const t = useT();
  const { user } = useAuth();
  const academyKey = useAcademyKey();
  const [filtres, setFiltres] = useState(VIDES);
  const [onglet, setOnglet] = useState("ensemble");
  const estPersonnel = user?.role === "superadmin" || user?.role === "admin";
  useEffect(() => setFiltres(VIDES), [academyKey]);
  const params = parametres(filtres);
  const optionsParams = parametres({ ...VIDES, annee: filtres.annee, cycle: filtres.cycle, niveau: filtres.niveau, classe: filtres.classe });
  const options = useQuery({ queryKey: ["analyse-filtres", academyKey, optionsParams], queryFn: () => analyticsAPI.filtres(optionsParams),
    placeholderData: keepPreviousData });
  const o = options.data?.data;
  const LIBELLES = { annee: t("Année scolaire"), periode: t("Période"), cycle: t("Cycle"), niveau: t("Niveau"), classe: t("Classes"),
    matiere: t("Matières"), enseignant: t("Enseignants"), type_evaluation: t("Types d'évaluation"), eleve: t("Élève"), genre: t("Genre") };
  const choix = {
    annee: (o?.annees || []).map((x) => [String(x.id), x.nom]), periode: (o?.periodes || []).map((x) => [x.id, t(x.nom)]),
    cycle: (o?.cycles || []).map((x) => [x.id, t(x.nom)]), niveau: (o?.niveaux || []).map((x) => [String(x.id), x.nom]),
    classe: (o?.classes || []).map((x) => [String(x.id), x.nom]), matiere: (o?.matieres || []).map((x) => [String(x.id), x.nom]),
    enseignant: (o?.enseignants || []).map((x) => [String(x.id), x.nom]), eleve: (o?.eleves || []).map((x) => [String(x.id), x.nom]),
    type_evaluation: TYPES.map(([v, n]) => [v, t(n)]), genre: [["F", t("Filles")], ["M", t("Garçons")]],
  };
  const simples = ["annee", "periode", "cycle", "niveau"];
  const multiples = ["classe", "matiere", ...(estPersonnel ? ["enseignant"] : []), "type_evaluation"];
  const actifs = Object.entries(filtres).filter(([, v]) => (Array.isArray(v) ? v.length : v !== ""));
  const anneeNom = choix.annee.find(([id]) => id === filtres.annee)?.[1] || o?.annees?.find((a) => a.en_cours)?.nom || "";
  const contexte = [anneeNom, filtres.periode ? t(PERIODES[filtres.periode]) : t("toutes périodes")].filter(Boolean).join(" · ");
  const libelleValeur = (cle, v) => (Array.isArray(v) ? v.map((x) => choix[cle].find(([id]) => id === x)?.[1] || x).join(", ")
    : choix[cle].find(([id]) => id === v)?.[1] || v);

  if (options.isError) {
    return (
      <div className="space-y-4">
        <PageHeader title={t("Centre d'analyse")} />
        <div className="card"><Erreur error={options.error} /></div>
      </div>
    );
  }
  const select = (cle) => (
    <label key={cle} className="flex flex-col gap-1 text-xs text-slate-600 min-w-0">
      <span className="font-medium">{LIBELLES[cle]}</span>
      <select className="input !py-1 text-sm" value={filtres[cle]} data-testid={`af-${cle}`}
        disabled={cle === "eleve" && !filtres.classe.length}
        onChange={(e) => setFiltres((f) => changer(f, cle, e.target.value))}>
        <option value="">{cle === "annee" ? t("Année en cours") : t("Tous")}</option>
        {choix[cle].map(([v, n]) => <option key={v} value={v}>{n}</option>)}
      </select>
    </label>
  );
  return (
    <div className="space-y-4">
      <PageHeader title={t("Centre d'analyse")} subtitle={o ? `${o.academie.nom} · ${contexte}` : t("Effectifs, résultats et présences")} action={<ChoixPresentation />} />
      <div className="card space-y-3" data-testid="analyse-filtres">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">{simples.map(select)}</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {multiples.map((cle) => (
            <ChoixMultiple key={cle} libelle={LIBELLES[cle]} options={choix[cle]} valeurs={filtres[cle]} testid={`af-${cle}`}
              onChange={(v) => setFiltres((f) => changer(f, cle, v))} />
          ))}
        </div>
        <details className="text-xs">
          <summary className="cursor-pointer font-medium text-feba-navy">{t("Filtres avancés : élève, genre")}</summary>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-2">{["eleve", "genre"].map(select)}</div>
        </details>
        {actifs.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <ul className="flex flex-wrap gap-1.5" aria-label={t("Filtres actifs")} data-testid="af-actifs">
              {actifs.map(([cle, v]) => (
                <li key={cle} className="inline-flex items-center gap-1 rounded-full bg-feba-navy/10 text-feba-navy text-xs px-2 py-0.5">
                  {LIBELLES[cle]} : {libelleValeur(cle, v)}
                  <button type="button" onClick={() => setFiltres((f) => changer(f, cle, Array.isArray(VIDES[cle]) ? [] : ""))}
                    aria-label={`${t("Retirer le filtre")} ${LIBELLES[cle]}`}>
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
          {ONGLETS.map(([v, nom]) => (
            <button key={v} type="button" role="tab" aria-selected={onglet === v} onClick={() => setOnglet(v)} data-testid={`onglet-${v}`}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium ${onglet === v ? "bg-feba-navy text-white" : "bg-white border border-slate-200 text-slate-600"}`}>
              {t(nom)}
            </button>
          ))}
        </div>
        {onglet === "ensemble" && <VueEnsemble params={params} contexte={contexte} />}
        {onglet === "resultats" && <Resultats params={params} contexte={contexte} />}
        {onglet === "matieres" && <Matieres params={params} contexte={contexte} />}
        {onglet === "classes" && <Classes params={params} contexte={contexte} />}
        {onglet === "enseignants" && <Enseignants params={params} contexte={contexte} filtres={filtres} setFiltres={setFiltres}
          options={choix.enseignant} estPersonnel={estPersonnel} />}
        {onglet === "effectifs" && <Effectifs params={params} contexte={contexte} />}
        {onglet === "presences" && <Presences params={params} contexte={contexte} />}
      </div>
    </div>
  );
}

export default function Analyses() {
  return <PresentationProvider><Contenu /></PresentationProvider>;
}
