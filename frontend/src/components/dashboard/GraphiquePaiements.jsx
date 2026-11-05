/**
 * Paiements du tableau de bord super administrateur : indicateurs, évolution,
 * filtres combinables, comparaison avec la période précédente, détail d'une
 * barre et export.
 *
 * Tous les calculs sont faits par le serveur (/api/payments/tableau-de-bord/).
 * Une devise est affichée à la fois : XOF et USD ne s'additionnent jamais.
 * Sans échéancier configuré, « attendu » et « restant » sont « non calculables »,
 * jamais 0.
 */
import { useEffect, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Link } from "react-router-dom";
import { Download, Info, X } from "lucide-react";
import { paymentsAPI } from "../../api";
import { isCanceledError } from "../../api/academyScope";
import { useAcademy } from "../../context/AcademyContext";
import { currencyRules, formatMinor } from "../../utils/money";
import { dateLocale, t, useI18n } from "../../i18n";
import Modal from "../ui/Modal";

const PERIODES = [
  ["7j", "7 jours"], ["30j", "30 jours"], ["3m", "3 mois"], ["6m", "6 mois"],
  ["12m", "12 mois"], ["annee", "Année scolaire"], ["civile", "Année civile"], ["perso", "Personnalisée"],
];
const COULEUR_ENCAISSE = "#0E2A63";   // bleu marine FEBA
const COULEUR_ATTENDU = "#D89B16";    // or FEBA

export const FILTRES_VIDES = {
  annee: "", cycle: "", niveau: "", classe: "", eleve: "",
  nature: "", mode: "", statut: "", statut_echeance: "", solde: "", montant_min: "", montant_max: "",
};
// Un choix de structure rend caducs ceux qui en dépendent.
const DEPENDANTS = {
  annee: ["classe", "eleve"], cycle: ["niveau", "classe", "eleve"], niveau: ["classe", "eleve"], classe: ["eleve"],
};
const STRUCTURE = ["annee", "cycle", "niveau", "classe", "eleve"];
export const STATUTS = [["confirme", "Confirmés"], ["annule", "Annulés"], ["rembourse", "Remboursés (carte)"]];
export const STATUTS_ECHEANCE = [["overdue", "En retard"], ["partial", "Partiellement payée"], ["paid", "Réglée"],
  ["upcoming", "À venir"], ["exempted", "Exonérée"]];
export const SOLDES = [["du", "Élèves qui doivent encore"], ["a_jour", "Élèves à jour"]];

/** Avec un filtre de structure modifié, on efface ceux qui en dépendent. */
export function changerFiltre(filtres, cle, valeur) {
  const suivant = { ...filtres, [cle]: valeur };
  for (const d of DEPENDANTS[cle] || []) suivant[d] = "";
  return suivant;
}

/** Paramètres envoyés au serveur : seulement les filtres renseignés. */
export function parametres(periode, du, au, filtres, comparer) {
  const p = { periode, ...(periode === "perso" ? { du, au } : {}) };
  if (comparer) p.comparer = 1;
  for (const [k, v] of Object.entries(filtres)) if (v !== "" && v !== null && v !== undefined) p[k] = v;
  return p;
}

function telecharger(nom, donnees) {
  const url = URL.createObjectURL(donnees instanceof Blob ? donnees : new Blob([donnees]));
  const lien = document.createElement("a");
  lien.href = url;
  lien.download = nom;
  lien.click();
  URL.revokeObjectURL(url);
}

/**
 * Pourquoi l'attendu et le reste à payer sont (ou ne sont que partiellement) calculés.
 * Situation 3 : aucun tarif → explication et accès direct. Situation 2 : des élèves
 * actifs n'ont aucun tarif applicable, ou une académie de la devise n'en a aucun.
 */
export function CouvertureTarifs({ devise }) {
  const c = devise?.couverture;
  if (!devise) return null;
  const lien = (
    <Link to="/superadmin/tarifs" className="font-semibold underline underline-offset-2" data-testid="lien-tarifs">
      {t("Ouvrir « Tarifs et échéances »")}
    </Link>
  );
  if (!devise.echeancier_configure) {
    return (
      <div className="mb-4 flex gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900" data-testid="tarifs-absents" role="note">
        <Info className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
        <p>
          {t("Aucun échéancier n'est configuré pour cette période. Configurez les tarifs et les échéances dans « Tarifs et échéances » pour obtenir les montants prévisionnels et les restes à payer.")}{" "}
          {lien}
        </p>
      </div>
    );
  }
  const manques = [];
  if (c?.academies_sans_tarif?.length) manques.push(t("académies sans tarif : {n}", { n: c.academies_sans_tarif.join(", ") }));
  if (c?.eleves_sans_tarif > 0) manques.push(t("{n} élève(s) actif(s) sans tarif applicable sur {total}", { n: c.eleves_sans_tarif, total: c.eleves_actifs }));
  if (!manques.length) return null;
  return (
    <div className="mb-4 flex gap-2 rounded-xl border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-900" data-testid="tarifs-partiels" role="note">
      <Info className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
      <p>
        {t("Données partielles : l'attendu et le reste à payer ne comptent que les élèves ayant un tarif.")} {manques.join(" · ")}.{" "}
        {lien}
      </p>
    </div>
  );
}

function Variation({ valeur }) {
  if (valeur === null || valeur === undefined) return <span className="text-slate-400">{t("variation non calculable")}</span>;
  const signe = valeur > 0 ? "+" : "";
  return <span className={valeur > 0 ? "text-emerald-700" : valeur < 0 ? "text-red-700" : "text-slate-500"}>{signe}{valeur} % {t("vs période précédente")}</span>;
}

function Indicateur({ titre, valeur, detail, testid, variation, comparer }) {
  return (
    <div className="rounded-xl border border-slate-100 bg-slate-50/60 p-3" data-testid={testid}>
      <p className="text-xs text-slate-500">{titre}</p>
      <p className="mt-0.5 text-base font-bold text-slate-900 tabular-nums">{valeur}</p>
      {detail && <p className="text-xs text-slate-500 mt-0.5">{detail}</p>}
      {comparer && <p className="text-xs mt-0.5" data-testid={`${testid}-variation`}><Variation valeur={variation} /></p>}
    </div>
  );
}

function Choix({ libelle, valeur, onChange, options, testid, desactive, aide }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-slate-600 min-w-0">
      <span className="font-medium">{libelle}</span>
      <select className="input !py-1 text-sm" value={valeur} onChange={(e) => onChange(e.target.value)}
        data-testid={testid} disabled={desactive} title={aide || undefined}>
        <option value="">{t("Tous")}</option>
        {options.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
      </select>
    </label>
  );
}

function DetailPaiements({ ouvert, onClose, params, titre }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["tableau-paiements-detail", params],
    queryFn: () => paymentsAPI.tableauDeBordDetail(params),
    enabled: ouvert,
  });
  const r = data?.data;
  const [exportEnCours, setExport] = useState(false);
  const exporter = async () => {
    setExport(true);
    try {
      const rep = await paymentsAPI.tableauDeBordExport(params);
      telecharger(`paiements_${r?.du || ""}_${r?.au || ""}.csv`, rep.data);
    } finally {
      setExport(false);
    }
  };
  return (
    <Modal open={ouvert} onClose={onClose} title={titre} size="xl">
      {isError && !isCanceledError(error) ? (
        <p role="alert" className="text-sm text-red-700">{error?.response?.data?.detail || t("Le détail n'a pas pu être chargé.")}</p>
      ) : isPending || !r ? (
        <div className="h-40 rounded-xl bg-slate-100 animate-pulse" aria-label={t("Chargement…")} />
      ) : (
        <div data-testid="detail-paiements">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-3 text-sm">
            <p className="text-slate-600">
              {new Date(`${r.du}T12:00:00`).toLocaleDateString(dateLocale())} → {new Date(`${r.au}T12:00:00`).toLocaleDateString(dateLocale())}
              {" · "}<span data-testid="detail-total">{r.total}</span> {t("paiement(s)")}
              {r.tronque && <> · {t("500 premiers affichés ; l'export contient toute la sélection.")}</>}
            </p>
            <button type="button" className="btn-secondary !py-1 text-xs inline-flex items-center gap-1.5" onClick={exporter}
              disabled={exportEnCours || r.total === 0} data-testid="detail-export">
              <Download className="w-3.5 h-3.5" aria-hidden="true" />{t("Exporter (CSV)")}
            </button>
          </div>
          {r.paiements.length === 0 ? (
            <p className="text-sm text-slate-500 py-6 text-center">{t("Aucun paiement ne correspond à cette sélection.")}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-xs text-slate-500">
                  <th className="py-1.5 pr-2 font-medium">{t("Date")}</th>
                  <th className="py-1.5 pr-2 font-medium">{t("Élève")}</th>
                  <th className="py-1.5 pr-2 font-medium">{t("Classe")}</th>
                  <th className="py-1.5 pr-2 font-medium">{t("Nature")}</th>
                  <th className="py-1.5 pr-2 font-medium">{t("Mode")}</th>
                  <th className="py-1.5 pr-2 font-medium text-right">{t("Montant")}</th>
                  <th className="py-1.5 font-medium">{t("Statut")}</th>
                </tr></thead>
                <tbody>
                  {r.paiements.map((p) => (
                    <tr key={p.id} className="border-t border-slate-100">
                      <td className="py-1.5 pr-2 whitespace-nowrap">{new Date(`${p.date}T12:00:00`).toLocaleDateString(dateLocale())}</td>
                      <td className="py-1.5 pr-2">{p.eleve}</td>
                      <td className="py-1.5 pr-2">{p.classe || "-"}</td>
                      <td className="py-1.5 pr-2">{t(p.nature_libelle)}</td>
                      <td className="py-1.5 pr-2">{t(p.mode_libelle)}</td>
                      <td className="py-1.5 pr-2 text-right tabular-nums whitespace-nowrap">
                        {formatMinor(p.montant_minor, p.devise)}
                        {p.rembourse_minor > 0 && <span className="block text-xs text-slate-500">{t("remboursé")} {formatMinor(p.rembourse_minor, p.devise)}</span>}
                      </td>
                      <td className="py-1.5">{p.statut === "confirme" ? t("Confirmé") : t("Annulé")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

export default function GraphiquePaiements() {
  useI18n(); // rendu à chaque changement de langue
  const { academyKey, businessDataEnabled } = useAcademy();
  const [periode, setPeriode] = useState("12m");
  const [du, setDu] = useState("");
  const [au, setAu] = useState("");
  const [devise, setDevise] = useState(null);
  const [filtres, setFiltres] = useState(FILTRES_VIDES);
  const [comparer, setComparer] = useState(false);
  const [plus, setPlus] = useState(false);
  const [detail, setDetail] = useState(null);       // { case, titre } ; case null = toute la période
  const persoPret = periode !== "perso" || (du && au);

  // Changer d'académie rend caducs les filtres de structure (classes et élèves d'une autre académie).
  useEffect(() => {
    setFiltres((f) => ({ ...f, annee: "", cycle: "", niveau: "", classe: "", eleve: "" }));
  }, [academyKey]);

  const params = parametres(periode, du, au, filtres, comparer);
  const { data, isPending, isError, error } = useQuery({
    queryKey: ["tableau-paiements", academyKey, params],
    queryFn: () => paymentsAPI.tableauDeBord(params),
    enabled: businessDataEnabled && Boolean(persoPret),
  });
  const choixStructure = { annee: filtres.annee, cycle: filtres.cycle, niveau: filtres.niveau, classe: filtres.classe };
  const { data: optionsData } = useQuery({
    queryKey: ["tableau-paiements-filtres", academyKey, choixStructure],
    queryFn: () => paymentsAPI.tableauDeBordFiltres(Object.fromEntries(Object.entries(choixStructure).filter(([, v]) => v))),
    enabled: businessDataEnabled,
    placeholderData: keepPreviousData,
  });
  const o = optionsData?.data;
  const structureDispo = Boolean(o?.structure_disponible);
  const opts = (liste) => (liste || []).map((x) => [String(x.id), t(x.nom)]);
  const choix = {
    annee: opts(o?.annees), cycle: opts(o?.cycles), niveau: opts(o?.niveaux), classe: opts(o?.classes), eleve: opts(o?.eleves),
    nature: opts(o?.natures), mode: opts(o?.modes),
    statut: STATUTS.map(([v, n]) => [v, t(n)]), statut_echeance: STATUTS_ECHEANCE.map(([v, n]) => [v, t(n)]),
    solde: SOLDES.map(([v, n]) => [v, t(n)]),
  };
  const LIBELLES = {
    annee: t("Année scolaire"), cycle: t("Cycle"), niveau: t("Niveau"), classe: t("Classe"), eleve: t("Élève"),
    nature: t("Nature de frais"), mode: t("Mode de paiement"), statut: t("Statut du paiement"),
    statut_echeance: t("Statut d'échéance"), solde: t("Solde de l'élève"), montant_min: t("Montant minimal"), montant_max: t("Montant maximal"),
  };
  const changer = (cle) => (v) => setFiltres((f) => changerFiltre(f, cle, v));
  const actifs = Object.entries(filtres).filter(([, v]) => v !== "");

  const r = data?.data;
  const devises = r?.devises || [];
  const courante = devises.find((d) => d.devise === devise) || devises[0];
  const code = courante?.devise;
  const decimales = currencyRules(code)?.decimals ?? 0;
  const m = (v) => (v === null || v === undefined ? t("Non calculable") : formatMinor(v, code));
  const enMonnaie = (v) => (v === null || v === undefined ? null : v / 10 ** decimales);
  const fmtCase = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString(dateLocale(),
    r?.periode?.granularite === "jour" ? { day: "2-digit", month: "short" } : { month: "short", year: "2-digit" });
  const serie = (courante?.serie || []).map((c) => ({
    iso: c.date, date: fmtCase(c.date), encaisse: enMonnaie(c.encaisse_minor), attendu: enMonnaie(c.attendu_minor),
  }));
  const ind = courante?.indicateurs;
  const vide = courante && ind.nb_paiements === 0 && !ind.nb_annules && !courante.echeancier_configure && !ind.nb_en_attente && !ind.nb_echoues;
  const erreur = isError && !isCanceledError(error);
  const messageErreur = () => {
    const d = error?.response?.data || {};
    const precision = Object.entries(d).filter(([k]) => k !== "detail").map(([k, v]) => `${LIBELLES[k] || k} : ${v}`).join(" · ");
    return [d.detail, precision].filter(Boolean).join(" ") || t("Les paiements n'ont pas pu être chargés. Rechargez la page.");
  };
  const variations = courante?.variations || {};
  const ouvrirCase = (point) => {
    const iso = point?.payload?.iso;
    if (iso) setDetail({ case: iso, titre: `${t("Paiements")} · ${point.payload.date}` });
  };

  return (
    <section className="card" aria-labelledby="titre-paiements" data-testid="graphique-paiements">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <h2 id="titre-paiements" className="font-bold text-slate-800">{t("Paiements")}</h2>
          <p className="text-xs text-slate-500">
            {r ? `${new Date(r.periode.du).toLocaleDateString(dateLocale())} → ${new Date(r.periode.au).toLocaleDateString(dateLocale())}${code ? ` · ${t("Montants en")} ${code}` : ""}` : t("Encaissements réels, par devise")}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label={t("Période")}>
          {PERIODES.map(([v, libelle]) => (
            <button key={v} type="button" onClick={() => setPeriode(v)} aria-pressed={periode === v}
              data-testid={`periode-${v}`}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${periode === v ? "bg-feba-navy text-white" : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"}`}>
              {t(libelle)}
            </button>
          ))}
        </div>
      </div>

      {periode === "perso" && (
        <div className="flex flex-wrap gap-3 mb-4 text-sm">
          <label className="flex items-center gap-2">{t("Du")}<input type="date" value={du} onChange={(e) => setDu(e.target.value)} className="input !py-1" /></label>
          <label className="flex items-center gap-2">{t("Au")}<input type="date" value={au} onChange={(e) => setAu(e.target.value)} className="input !py-1" /></label>
        </div>
      )}

      <div className="mb-4 rounded-xl border border-slate-100 p-3" data-testid="paiements-filtres">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
          {STRUCTURE.map((cle) => (
            <Choix key={cle} libelle={LIBELLES[cle]} valeur={filtres[cle]} onChange={changer(cle)} options={choix[cle]}
              testid={`filtre-${cle}`} desactive={!structureDispo || (cle === "eleve" && !filtres.classe)}
              aide={!structureDispo ? t("Choisissez une académie pour filtrer par structure.") : cle === "eleve" && !filtres.classe ? t("Choisissez d'abord une classe.") : null} />
          ))}
        </div>
        {!structureDispo && o && (
          <p className="text-xs text-slate-500 mt-2">{t("Choisissez une académie pour filtrer par structure.")}</p>
        )}
        {plus && (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2 mt-2">
            {["nature", "mode", "statut", "statut_echeance", "solde"].map((cle) => (
              <Choix key={cle} libelle={LIBELLES[cle]} valeur={filtres[cle]} onChange={changer(cle)} options={choix[cle]} testid={`filtre-${cle}`} />
            ))}
            {["montant_min", "montant_max"].map((cle) => (
              <label key={cle} className="flex flex-col gap-1 text-xs text-slate-600">
                <span className="font-medium">{LIBELLES[cle]}{code ? ` (${code})` : ""}</span>
                <input type="number" min="0" step="any" inputMode="decimal" className="input !py-1 text-sm" value={filtres[cle]}
                  onChange={(e) => changer(cle)(e.target.value)} data-testid={`filtre-${cle}`} />
              </label>
            ))}
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2 mt-3">
          <button type="button" className="text-xs font-medium text-feba-navy hover:underline" onClick={() => setPlus((x) => !x)}
            aria-expanded={plus} data-testid="filtres-plus">
            {plus ? t("Moins de filtres") : t("Plus de filtres")}
          </button>
          <label className="flex items-center gap-1.5 text-xs text-slate-600">
            <input type="checkbox" checked={comparer} onChange={(e) => setComparer(e.target.checked)} data-testid="comparer" />
            {t("Comparer avec la période précédente")}
          </label>
          {actifs.length > 0 && (
            <button type="button" className="text-xs font-medium text-red-700 hover:underline ml-auto" onClick={() => setFiltres(FILTRES_VIDES)}
              data-testid="filtres-reinitialiser">
              {t("Réinitialiser les filtres")}
            </button>
          )}
        </div>
        {actifs.length > 0 && (
          <ul className="flex flex-wrap gap-1.5 mt-2" aria-label={t("Filtres actifs")} data-testid="filtres-actifs">
            {actifs.map(([cle, v]) => {
              const nom = (choix[cle] || []).find(([id]) => id === String(v))?.[1] || v;
              return (
                <li key={cle} className="inline-flex items-center gap-1 rounded-full bg-feba-navy/10 text-feba-navy text-xs px-2 py-0.5">
                  {LIBELLES[cle]} : {nom}
                  <button type="button" onClick={() => changer(cle)("")} aria-label={`${t("Retirer le filtre")} ${LIBELLES[cle]}`}>
                    <X className="w-3 h-3" aria-hidden="true" />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {devises.length > 1 && (
        <div className="flex gap-1.5 mb-4" role="group" aria-label={t("Devise")}>
          {devises.map((d) => (
            <button key={d.devise} type="button" onClick={() => setDevise(d.devise)} aria-pressed={d.devise === code}
              data-testid={`devise-${d.devise}`}
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold ${d.devise === code ? "bg-feba-gold text-white" : "bg-white border border-slate-200 text-slate-600"}`}>
              {d.devise} · {d.academies.map((a) => a.nom).join(", ")}
            </button>
          ))}
        </div>
      )}

      {!persoPret ? (
        <p className="text-sm text-slate-500 py-8 text-center">{t("Choisissez les deux dates de la période.")}</p>
      ) : erreur ? (
        <p role="alert" className="text-sm text-red-700 py-8 text-center">{messageErreur()}</p>
      ) : isPending || !r ? (
        <div className="h-64 rounded-xl bg-slate-100 animate-pulse" data-testid="paiements-chargement" aria-label={t("Chargement…")} />
      ) : !courante || vide ? (
        <p className="text-sm text-slate-500 py-8 text-center" data-testid="paiements-vide">
          {actifs.length ? t("Aucun paiement ne correspond à ces filtres.") : t("Aucun paiement sur cette période.")}
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <Indicateur testid="ind-encaisse" titre={t("Encaissé (net des remboursements)")} valeur={m(ind.encaisse_minor)}
              comparer={comparer} variation={variations.encaisse_minor}
              detail={`${ind.nb_paiements} ${t("paiement(s)")}${ind.rembourse_minor ? ` · ${t("remboursé")} ${m(ind.rembourse_minor)}` : ""}`} />
            <Indicateur testid="ind-attendu" titre={t("Attendu (échéances de la période)")} valeur={m(ind.attendu_minor)}
              comparer={comparer && courante.echeancier_configure} variation={variations.attendu_minor}
              detail={courante.echeancier_configure ? null : t("Aucun tarif avec échéances")} />
            <Indicateur testid="ind-restant" titre={t("Restant à payer (échéances passées)")} valeur={m(ind.restant_minor)}
              comparer={comparer && courante.echeancier_configure} variation={variations.restant_minor}
              detail={ind.taux_recouvrement !== null && ind.taux_recouvrement !== undefined ? `${t("Recouvrement")} ${ind.taux_recouvrement} %` : null} />
            <Indicateur testid="ind-attente" titre={t("En attente / échoués (carte)")} valeur={`${m(ind.en_attente_minor)} / ${m(ind.echoue_minor)}`}
              detail={`${ind.nb_en_attente} / ${ind.nb_echoues} · ${t("annulés")} ${ind.nb_annules} (${m(ind.annule_minor)})`} />
          </div>
          <CouvertureTarifs devise={courante} />
          {comparer && r.periode_precedente && (
            <p className="text-xs text-slate-500 mb-2" data-testid="periode-precedente">
              {t("Période précédente")} : {new Date(`${r.periode_precedente.du}T12:00:00`).toLocaleDateString(dateLocale())} → {new Date(`${r.periode_precedente.au}T12:00:00`).toLocaleDateString(dateLocale())}
              {" · "}{t("Encaissé")} {m(courante.precedent?.encaisse_minor)}
            </p>
          )}
          <div className="h-64" data-testid="paiements-graphique">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={serie} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#64748b" }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 11, fill: "#64748b" }} width={48}
                  tickFormatter={(v) => new Intl.NumberFormat(dateLocale(), { notation: "compact", maximumFractionDigits: 1 }).format(v)} />
                <Tooltip formatter={(v, nom) => [v === null ? t("Non calculable") : formatMinor(v * 10 ** decimales, code), nom]} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="encaisse" name={t("Encaissé")} fill={COULEUR_ENCAISSE} radius={[4, 4, 0, 0]} maxBarSize={36}
                  isAnimationActive={false} cursor="pointer" onClick={ouvrirCase} />
                {courante.echeancier_configure && (
                  <Line dataKey="attendu" name={t("Attendu")} stroke={COULEUR_ATTENDU} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-wrap items-center gap-3 mt-2">
            <p className="text-xs text-slate-500">{t("Cliquez sur une barre pour voir ses paiements.")}</p>
            <button type="button" className="btn-secondary !py-1 text-xs ml-auto" data-testid="voir-paiements"
              onClick={() => setDetail({ case: null, titre: t("Paiements de la période") })}>
              {t("Voir les paiements")}
            </button>
          </div>
          {serie.length > 0 && (
            <ul className="sr-only" data-testid="cases-graphique">
              {serie.map((c) => (
                <li key={c.iso}><button type="button" data-testid={`case-${c.iso}`}
                  onClick={() => ouvrirCase({ payload: c })}>{c.date} : {c.encaisse === null ? t("Non calculable") : formatMinor(c.encaisse * 10 ** decimales, code)}</button></li>
              ))}
            </ul>
          )}
          {r.par_academie.length > 1 && (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm" data-testid="paiements-par-academie">
                <thead><tr className="text-left text-xs text-slate-500">
                  <th className="py-1.5 font-medium">{t("Académie")}</th>
                  <th className="py-1.5 font-medium text-right">{t("Encaissé")}</th>
                  <th className="py-1.5 font-medium text-right">{t("Paiements")}</th>
                  <th className="py-1.5 font-medium text-right">{t("Restant à payer")}</th>
                </tr></thead>
                <tbody>
                  {r.par_academie.map((a) => (
                    <tr key={a.id} className="border-t border-slate-100">
                      <td className="py-1.5">{a.nom}</td>
                      <td className="py-1.5 text-right tabular-nums">{formatMinor(a.encaisse_minor, a.devise)}</td>
                      <td className="py-1.5 text-right tabular-nums">{a.nb_paiements}</td>
                      <td className="py-1.5 text-right tabular-nums">{a.restant_minor === null ? t("Non calculable") : formatMinor(a.restant_minor, a.devise)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <details className="mt-4 text-xs text-slate-600" data-testid="definitions-indicateurs">
            <summary className="cursor-pointer font-medium text-slate-700">{t("Définitions des indicateurs")}</summary>
            <ul className="mt-2 space-y-1 list-disc pl-5">
              <li>{t("Encaissé : paiements confirmés de la période, à leur date, moins les remboursements carte.")}</li>
              <li>{t("Attendu : montant des échéances dont la date tombe dans la période, réductions déduites, exonérations exclues.")}</li>
              <li>{t("Restant à payer : part non couverte des échéances de la période déjà passées.")}</li>
              <li>{t("Recouvrement : payé sur ces échéances passées, divisé par leur montant attendu.")}</li>
              <li>{t("En attente / échoués : paiements par carte sans encaissement, créés dans la période.")}</li>
              <li>{t("Non calculable : aucun tarif avec échéances n'est configuré ; la valeur est inconnue, pas nulle.")}</li>
              <li>{t("La classe, le niveau et le cycle sont ceux de l'élève aujourd'hui ; l'année est celle du paiement ou de l'échéance.")}</li>
            </ul>
          </details>
        </>
      )}
      <DetailPaiements ouvert={Boolean(detail)} onClose={() => setDetail(null)} titre={detail?.titre || ""}
        params={{ ...parametres(periode, du, au, filtres, false), ...(detail?.case ? { case: detail.case } : {}) }} />
    </section>
  );
}
