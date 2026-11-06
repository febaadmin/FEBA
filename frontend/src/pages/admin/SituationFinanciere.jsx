/**
 * Situation financière : tableau de bord de l'académie (KPI expliqués, graphiques),
 * vues par classe, par niveau et par élève, fiche financière détaillée et export.
 *
 * Tout est calculé par le serveur (compute_dues : tarifs, échéanciers standard ou
 * personnels, exonérations, remises, paiements confirmés nets des remboursements).
 * Les filtres s'appliquent à la fois aux KPI, aux tableaux et aux graphiques ; un
 * clic sur une barre ou une catégorie filtre la vue correspondante. Sans tarif, les
 * montants attendus sont « non calculables » (jamais présentés comme nuls).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BLEU, ETAT, MOUVEMENT, OR } from "../../theme/graphiques";
import { useReducedMotion } from "framer-motion";
import { ArrowDown, ArrowUp, Download, Search, X } from "lucide-react";
import toast from "react-hot-toast";
import { paymentsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import Modal from "../../components/ui/Modal";
import ReleveEleve, { AIDES } from "../../components/payments/ReleveEleve";
import { AideKpi } from "../../components/payments/AideKpi";
import { CarteGraphique } from "../../components/analytics/elements";
import { useAuth } from "../../hooks/useAuth";
import { useAcademyKey } from "../../hooks/useEntityContext";
import { useAcademy } from "../../context/AcademyContext";
import { t } from "../../i18n";
import { extractApiError } from "../../utils/errors";
import { formatCalendarDate } from "../../utils/datetime";
import { formatMinor } from "../../utils/money";
import { NATURES_FRAIS } from "../../utils/naturesFrais";

// Palette FEBA : encaissé (vert), à échoir (bleu nuit), en retard (rouge, statut).
// Système graphique FEBA : états (encaissé, en retard…) en couleurs d'état, séries en couleurs de palette.
const C = { encaisse: ETAT.succes, a_echoir: BLEU, retard: ETAT.alerte, net: BLEU, paye: ETAT.succes, restant: OR,
  solde: ETAT.succes, partiel: ETAT.attention, aucun: ETAT.alerte, exonere: ETAT.neutre };
const VUES = [["classe", "Par classe"], ["niveau", "Par niveau"], ["eleve", "Par élève"]];
const STATUTS = [["", "Tous les statuts"], ["solde", "Soldé"], ["partiel", "Paiement partiel"], ["aucun", "Aucun paiement"],
  ["exonere", "Exonéré"], ["en_retard", "En retard"], ["a_jour", "À jour"]];
const VIDE = { annee: "", cycle: "", niveau: "", classe: "", nature: "", statut: "", debut: "", fin: "", q: "" };

function telecharger(nom, blob) {
  const url = URL.createObjectURL(blob instanceof Blob ? blob : new Blob([blob]));
  const a = document.createElement("a");
  a.href = url; a.download = nom; a.click();
  URL.revokeObjectURL(url);
}

function Kpi({ titre, valeur, detail, aide, ton, testid }) {
  return (
    <div className={`rounded-xl border p-3 min-w-0 ${ton || "border-slate-100 bg-white"}`} data-testid={testid}>
      <p className="text-xs text-slate-500 flex items-center gap-1">{t(titre)}<AideKpi texte={t(aide)} /></p>
      <p className="mt-0.5 text-lg sm:text-xl font-bold text-slate-900 tabular-nums break-words">{valeur}</p>
      {detail && <p className="text-xs text-slate-500 mt-0.5">{detail}</p>}
    </div>
  );
}

const AIDES_KPI = {
  effectif: "Élèves actifs de l'académie.",
  concernes: "Élèves ayant au moins une échéance dans la sélection (tarif applicable).",
  ...AIDES,
  encaisse_total: "Tous les paiements confirmés de la sélection, nets des remboursements, y compris ceux qui ne correspondent à aucune échéance (hors échéancier).",
  soldes: "Élèves dont le reste à payer est nul.",
  partiels: "Élèves ayant payé une partie du net dû.",
  aucun: "Élèves n'ayant rien payé sur leurs échéances.",
  recouvrement_echu: "Encaissé sur les échéances passées divisé par le net de ces échéances, multiplié par 100.",
};

function Kpis({ a }) {
  const tt = a.totaux, k = a.kpi;
  const pct = (v) => (v === null || v === undefined ? t("Non calculable") : `${v} %`);
  const nc = !a.calculable;
  const m = (v) => (nc ? t("Non calculable") : v);
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2" data-testid="situation-kpi">
      <Kpi titre="Effectif" valeur={k.effectif} detail={`${k.eleves_concernes} ${t("concerné(s)")}`} aide={AIDES_KPI.concernes} />
      <Kpi titre="Frais théoriques" valeur={m(tt.theorique_affiche)} aide={AIDES_KPI.theorique} />
      <Kpi titre="Remises" valeur={m(tt.remises_affiche)} aide={AIDES_KPI.remises} />
      <Kpi titre="Exonérations" valeur={m(tt.exonerations_affiche)} aide={AIDES_KPI.exonerations} />
      <Kpi titre="Net attendu" valeur={m(tt.net_affiche)} aide={AIDES_KPI.net} ton="border-feba-navy/20 bg-feba-navy/5" testid="kpi-net" />
      {nc ? (
        <Kpi titre="Total encaissé" valeur={tt.encaisse_total_affiche} detail={t("Aucune échéance : rien n'est imputé")} aide={AIDES_KPI.encaisse_total} ton="border-emerald-200 bg-emerald-50/60" testid="kpi-encaisse" />
      ) : (
        <Kpi titre="Encaissé" valeur={tt.paye_affiche} detail={`${t("Total encaissé")} ${tt.encaisse_total_affiche}`} aide={AIDES_KPI.paye} ton="border-emerald-200 bg-emerald-50/60" testid="kpi-encaisse" />
      )}
      <Kpi titre="Reste à payer" valeur={m(tt.restant_affiche)} aide={AIDES_KPI.restant} />
      <Kpi titre="En retard" valeur={m(tt.retard_affiche)} detail={`${k.eleves_en_retard} ${t("élève(s)")}`} aide={AIDES_KPI.retard} ton="border-red-200 bg-red-50/60" />
      <Kpi titre="Taux de recouvrement" valeur={pct(tt.taux_recouvrement)} detail={`${t("Sur échéances passées")} : ${pct(tt.taux_recouvrement_echu)}`} aide={AIDES_KPI.recouvrement} testid="kpi-taux" />
      <Kpi titre="Élèves soldés" valeur={k.eleves_soldes} aide={AIDES_KPI.soldes} />
      <Kpi titre="Paiement partiel" valeur={k.eleves_partiels} aide={AIDES_KPI.partiels} />
      <Kpi titre="Aucun paiement" valeur={k.eleves_aucun_paiement} aide={AIDES_KPI.aucun} />
    </div>
  );
}

function Infobulle({ active, payload, label, devise, entier = false }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs shadow-md">
      {label && <p className="font-semibold text-slate-800 mb-0.5">{label}</p>}
      {payload.map((p) => (
        <p key={p.dataKey} className="flex items-center gap-1.5 text-slate-700">
          <span className="w-2 h-2 rounded-sm" style={{ background: p.color || p.payload?.fill }} aria-hidden="true" />
          {p.name} : <strong className="tabular-nums">{p.unit === "%" ? `${p.value} %` : p.unit === "n" || entier ? p.value : formatMinor(p.value, devise)}</strong>
        </p>
      ))}
    </div>
  );
}

function Graphiques({ a, vue, onFiltre }) {
  const reduit = useReducedMotion();
  const anim = !reduit;
  const g = a.graphiques, devise = a.devise;
  const axe = (v) => formatMinor(v, devise).replace(/\s?[A-Z]{3}$|FCFA$/, "");
  const groupes = a.groupes.map((x) => ({ nom: x.nom, id: x.id, net: x.net_minor, paye: x.paye_minor, restant: x.restant_minor,
    taux: x.taux_recouvrement ?? 0 }));
  const repart = [{ nom: t("Net attendu"), ...Object.fromEntries(g.repartition.map((r) => [r.cle, r.montant_minor])) }];
  const contexte = a.date_reference ? `${t("Au")} ${formatCalendarDate(a.date_reference)}` : "";
  const champ = vue === "niveau" ? "niveau" : "classe";
  return (
    <div className="grid lg:grid-cols-2 gap-3" data-testid="situation-graphiques">
      <CarteGraphique titre={t("Répartition du net attendu")} contexte={contexte} unite={devise} testid="graph-repartition"
        vide={!a.calculable || !a.totaux.net_minor} raisonVide={a.raison_non_calculable || t("Aucun montant attendu pour cette sélection.")}>
        <ResponsiveContainer width="100%" height={110}>
          <BarChart data={repart} layout="vertical" margin={{ left: 8, right: 16 }}>
            <XAxis type="number" hide domain={[0, "dataMax"]} /><YAxis type="category" dataKey="nom" hide />
            <Tooltip content={<Infobulle devise={devise} />} />
            <Legend wrapperStyle={{ fontSize: 12 }} formatter={encre} />
            {[["encaisse", "Encaissé"], ["a_echoir", "Restant à échoir"], ["retard", "En retard"]].map(([cle, nom], i, tab) => (
              <Bar key={cle} dataKey={cle} name={t(nom)} stackId="r" fill={C[cle]} isAnimationActive={anim} animationDuration={MOUVEMENT.duree} cursor="pointer"
                radius={i === tab.length - 1 ? [0, 4, 4, 0] : i === 0 ? [4, 0, 0, 4] : 0}
                onClick={() => onFiltre(cle === "retard" ? { statut: "en_retard" } : cle === "encaisse" ? { statut: "solde" } : { statut: "a_jour" }, "eleve")} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </CarteGraphique>

      <CarteGraphique titre={t("Statut de paiement des élèves")} contexte={contexte} unite={t("élèves")} testid="graph-statuts"
        vide={!a.kpi.eleves_concernes} raisonVide={t("Aucun élève concerné par cette sélection.")}>
        <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-3 items-center">
          <div className="h-44 relative">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={g.statuts.filter((x) => x.nombre > 0).map((x) => ({ ...x, libelle: t(x.libelle) }))} dataKey="nombre" nameKey="libelle"
                  innerRadius="62%" outerRadius="92%" paddingAngle={2} stroke="#fff" strokeWidth={2} cursor="pointer"
                  isAnimationActive={anim} animationDuration={MOUVEMENT.duree} onClick={(d) => onFiltre({ statut: d.cle }, "eleve")}>
                  {g.statuts.filter((x) => x.nombre > 0).map((x) => <Cell key={x.cle} fill={C[x.cle]} />)}
                </Pie>
                <Tooltip content={<Infobulle devise={devise} entier />} />
              </PieChart>
            </ResponsiveContainer>
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <span className="text-2xl font-bold text-slate-900 tabular-nums">{a.kpi.eleves_concernes}</span>
              <span className="text-[11px] text-slate-500">{t("élèves")}</span>
            </div>
          </div>
          <ul className="space-y-1.5 text-sm">
            {g.statuts.map((x) => (
              <li key={x.cle}>
                <button type="button" className="w-full flex items-center gap-2 rounded-lg px-1.5 py-1 hover:bg-slate-50 text-left"
                  onClick={() => onFiltre({ statut: x.cle }, "eleve")}>
                  <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: C[x.cle] }} aria-hidden="true" />
                  <span className="flex-1 truncate">{t(x.libelle)}</span>
                  <span className="tabular-nums text-slate-700">{x.nombre}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </CarteGraphique>

      {vue !== "eleve" && (
        <CarteGraphique titre={vue === "niveau" ? t("Comparaison par niveau") : t("Comparaison par classe")} contexte={contexte} unite={devise}
          testid="graph-groupes" vide={!groupes.length} raisonVide={a.raison_non_calculable || t("Aucune donnée pour cette sélection.")}
          className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={Math.max(220, groupes.length * 26 + 60)}>
            <BarChart data={groupes} layout="vertical" margin={{ left: 8, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
              <XAxis type="number" tickFormatter={axe} tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="nom" width={110} tick={{ fontSize: 11 }} />
              <Tooltip content={<Infobulle devise={devise} />} />
              <Legend wrapperStyle={{ fontSize: 12 }} formatter={encre} />
              {[["net", "Net attendu"], ["paye", "Encaissé"], ["restant", "Reste à payer"]].map(([cle, nom]) => (
                <Bar key={cle} dataKey={cle} name={t(nom)} fill={C[cle]} isAnimationActive={anim} animationDuration={MOUVEMENT.duree} cursor="pointer" maxBarSize={14} radius={[0, 4, 4, 0]}
                  onClick={(d) => d.id && onFiltre({ [champ]: String(d.id) }, "eleve")} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </CarteGraphique>
      )}

      {vue !== "eleve" && (
        <CarteGraphique titre={t("Taux de recouvrement")} contexte={contexte} unite="%" testid="graph-taux"
          vide={!groupes.length} raisonVide={t("Aucune donnée pour cette sélection.")}>
          <ResponsiveContainer width="100%" height={Math.max(180, groupes.length * 22 + 50)}>
            <BarChart data={groupes} layout="vertical" margin={{ left: 8, right: 24 }}>
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} unit=" %" />
              <YAxis type="category" dataKey="nom" width={110} tick={{ fontSize: 11 }} />
              <Tooltip content={<Infobulle devise={devise} />} />
              <Bar dataKey="taux" name={t("Taux de recouvrement")} unit="%" fill={C.paye} isAnimationActive={anim} animationDuration={MOUVEMENT.duree} maxBarSize={14} radius={[0, 4, 4, 0]}
                cursor="pointer" onClick={(d) => d.id && onFiltre({ [champ]: String(d.id) }, "eleve")} />
            </BarChart>
          </ResponsiveContainer>
        </CarteGraphique>
      )}

      <CarteGraphique titre={t("Encaissements par mois")} contexte={t("Date de paiement ; paiements confirmés, nets des remboursements")} unite={devise}
        testid="graph-encaissements" vide={!g.encaissements_mensuels.length} raisonVide={t("Aucun encaissement pour cette sélection.")}>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={g.encaissements_mensuels} margin={{ left: 0, right: 8 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
            <XAxis dataKey="mois" tick={{ fontSize: 11 }} /><YAxis tickFormatter={axe} tick={{ fontSize: 11 }} width={64} />
            <Tooltip content={<Infobulle devise={devise} />} />
            <Bar dataKey="montant_minor" name={t("Encaissé")} fill={C.encaisse} isAnimationActive={anim} animationDuration={MOUVEMENT.duree} radius={[4, 4, 0, 0]} maxBarSize={36} />
          </BarChart>
        </ResponsiveContainer>
      </CarteGraphique>

      <CarteGraphique titre={t("Remises et exonérations accordées")} contexte={contexte} unite={devise} testid="graph-ajustements"
        vide={!g.ajustements.length} raisonVide={t("Aucune remise ni exonération appliquée dans cette sélection.")}>
        <ul className="space-y-1.5 text-sm">
          {g.ajustements.map((x) => {
            const max = g.ajustements[0].montant_minor || 1;
            return (
              <li key={`${x.genre}-${x.categorie}`}>
                <div className="flex justify-between gap-2 text-xs"><span>{x.genre === "exoneration" ? t("Exonération") : t("Remise")} · {t(LIB_CAT[x.categorie] || x.categorie)}</span>
                  <span className="tabular-nums font-medium">{x.montant}</span></div>
                <div className="h-2 rounded bg-slate-100" aria-hidden="true">
                  <div className="h-2 rounded" style={{ width: `${(100 * x.montant_minor) / max}%`, background: x.genre === "exoneration" ? C.exonere : C.restant }} />
                </div>
              </li>
            );
          })}
        </ul>
      </CarteGraphique>
    </div>
  );
}

/** Sans tarif : seuls les encaissements réels sont montrés (aucun montant attendu inventé). */
function Encaissements({ a }) {
  const reduit = useReducedMotion();
  const g = a.graphiques.encaissements_mensuels;
  return (
    <CarteGraphique titre={t("Encaissements par mois")} contexte={t("Date de paiement ; paiements confirmés, nets des remboursements")} unite={a.devise}
      testid="graph-encaissements" vide={!g.length} raisonVide={t("Aucun encaissement pour cette sélection.")}>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={g} margin={{ left: 0, right: 8 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          <XAxis dataKey="mois" tick={{ fontSize: 11 }} /><YAxis tickFormatter={(v) => formatMinor(v, a.devise)} tick={{ fontSize: 11 }} width={80} />
          <Tooltip content={<Infobulle devise={a.devise} />} />
          <Bar dataKey="montant_minor" name={t("Encaissé")} fill={C.encaisse} isAnimationActive={!reduit} animationDuration={MOUVEMENT.duree} radius={[4, 4, 0, 0]} maxBarSize={36} />
        </BarChart>
      </ResponsiveContainer>
    </CarteGraphique>
  );
}

// Légende : texte à l'encre du texte (la couleur reste portée par la pastille).
const encre = (valeur) => <span className="text-slate-700">{valeur}</span>;

const LIB_CAT = { exceptionnelle: "Remise exceptionnelle", fratrie: "Plusieurs enfants d'une même famille", paiement_anticipe: "Paiement anticipé",
  paiement_integral: "Paiement intégral", sociale: "Remise sociale", situation_particuliere: "Situation particulière",
  decision_administrative: "Décision administrative", autre: "Autre", disposition: "Disposition de l'élève" };

function TableauGroupes({ a, vue, onGroupe }) {
  return (
    <div className="card overflow-x-auto">
      <table className="w-full text-sm" data-testid="situation-groupes">
        <thead><tr className="text-left text-xs text-slate-500">
          {[vue === "niveau" ? "Niveau" : "Classe", ...(vue === "classe" ? ["Niveau"] : []), "Élèves", "À jour", "En retard", "Théorique",
            "Remises et exonérations", "Net attendu", "Encaissé", "Reste à payer", "Dont en retard", "Recouvrement"].map((h) =>
            <th key={h} className="py-2 pr-3 font-medium whitespace-nowrap">{t(h)}</th>)}
        </tr></thead>
        <tbody>
          {a.groupes.map((g) => (
            <tr key={`${g.id}`} className="border-t border-slate-100 cursor-pointer hover:bg-slate-50 focus-within:bg-slate-50"
              onClick={() => onGroupe(g)}>
              <td className="py-2 pr-3 font-medium"><button type="button" className="hover:underline text-left" onClick={(e) => { e.stopPropagation(); onGroupe(g); }}>{g.nom}</button></td>
              {vue === "classe" && <td className="py-2 pr-3">{g.niveau || "-"}</td>}
              <td className="py-2 pr-3 tabular-nums">{g.eleves}</td>
              <td className="py-2 pr-3 tabular-nums">{g.eleves_a_jour}</td>
              <td className="py-2 pr-3 tabular-nums">{g.eleves_en_retard}</td>
              <td className="py-2 pr-3 tabular-nums whitespace-nowrap">{g.theorique_affiche}</td>
              <td className="py-2 pr-3 tabular-nums whitespace-nowrap">{formatMinor(g.remises_minor + g.exonerations_minor, a.devise)}</td>
              <td className="py-2 pr-3 tabular-nums whitespace-nowrap">{g.net_affiche}</td>
              <td className="py-2 pr-3 tabular-nums whitespace-nowrap">{g.paye_affiche}</td>
              <td className="py-2 pr-3 tabular-nums whitespace-nowrap">{g.restant_affiche}</td>
              <td className={`py-2 pr-3 tabular-nums whitespace-nowrap ${g.retard_minor > 0 ? "text-red-700 font-medium" : ""}`}>{g.retard_affiche}</td>
              <td className="py-2 pr-3 tabular-nums">{g.taux_recouvrement === null ? "-" : `${g.taux_recouvrement} %`}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-slate-500 mt-2">{t("Cliquer sur une ligne affiche les élèves qui la composent.")}</p>
    </div>
  );
}

const TON_STATUT = { solde: "bg-emerald-50 text-emerald-700", partiel: "bg-amber-50 text-amber-700", aucun: "bg-red-50 text-red-700", exonere: "bg-slate-100 text-slate-600" };

function TableauEleves({ a, tri, setTri, page, setPage, onEleve }) {
  const col = (cle, nom, droite) => (
    <th key={cle} className={`py-2 pr-3 font-medium whitespace-nowrap ${droite ? "text-right" : ""}`}
      aria-sort={tri.cle === cle ? (tri.ordre === "asc" ? "ascending" : "descending") : "none"}>
      {cle ? (
        <button type="button" className="inline-flex items-center gap-0.5 hover:text-slate-800"
          onClick={() => setTri({ cle, ordre: tri.cle === cle && tri.ordre === "desc" ? "asc" : "desc" })}>
          {t(nom)}{tri.cle === cle && (tri.ordre === "asc" ? <ArrowUp className="w-3 h-3" aria-hidden="true" /> : <ArrowDown className="w-3 h-3" aria-hidden="true" />)}
        </button>
      ) : t(nom)}
    </th>
  );
  return (
    <div className="card space-y-2">
      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="situation-eleves">
          <thead><tr className="text-left text-xs text-slate-500">
            {col("matricule", "Matricule")}{col("nom", "Élève")}{col("classe", "Classe")}{col(null, "Niveau")}
            {col(null, "Frais théoriques", true)}{col(null, "Remises", true)}{col(null, "Exonérations", true)}{col("net", "Net dû", true)}
            {col("paye", "Payé", true)}{col("restant", "Reste à payer", true)}{col(null, "Prochaine échéance")}{col("retard", "Retard", true)}{col("statut", "Statut")}
          </tr></thead>
          <tbody>
            {a.eleves.map((e) => (
              <tr key={e.id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="py-2 pr-3 text-slate-500">{e.matricule || "-"}</td>
                <td className="py-2 pr-3 font-medium"><button type="button" className="hover:underline text-left" onClick={() => onEleve(e)} data-testid={`eleve-${e.id}`}>{e.nom}</button></td>
                <td className="py-2 pr-3">{e.classe || "-"}</td>
                <td className="py-2 pr-3">{e.niveau || "-"}</td>
                <td className="py-2 pr-3 text-right tabular-nums whitespace-nowrap">{e.theorique_affiche}</td>
                <td className="py-2 pr-3 text-right tabular-nums whitespace-nowrap">{e.remises_minor ? e.remises_affiche : "-"}</td>
                <td className="py-2 pr-3 text-right tabular-nums whitespace-nowrap">{e.exonerations_minor ? e.exonerations_affiche : "-"}</td>
                <td className="py-2 pr-3 text-right tabular-nums whitespace-nowrap">{e.net_affiche}</td>
                <td className="py-2 pr-3 text-right tabular-nums whitespace-nowrap">{e.paye_affiche}</td>
                <td className="py-2 pr-3 text-right tabular-nums whitespace-nowrap">{e.restant_affiche}</td>
                <td className="py-2 pr-3 whitespace-nowrap">{e.prochaine_echeance ? `${formatCalendarDate(e.prochaine_echeance.date)} · ${e.prochaine_echeance.montant}` : "-"}</td>
                <td className={`py-2 pr-3 text-right tabular-nums whitespace-nowrap ${e.retard_minor > 0 ? "text-red-700 font-medium" : ""}`}>
                  {e.retard_minor > 0 ? `${e.retard_affiche} · ${e.jours_retard} ${t("j")}` : "-"}</td>
                <td className="py-2 pr-3"><span className={`badge ${TON_STATUT[e.statut] || ""}`}>{t(e.statut_libelle)}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
        {a.eleves.length === 0 && <p className="text-sm text-slate-500 py-6 text-center" data-testid="eleves-vide">{t("Aucun élève ne correspond à ces filtres.")}</p>}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-600">
        <span>{a.eleves_total} {t("élève(s)")} · {t("page {p} sur {n}", { p: a.page, n: a.pages })}</span>
        <span className="flex gap-1">
          <button type="button" className="btn-secondary !py-1 text-xs" disabled={page <= 1} onClick={() => setPage(page - 1)}>{t("Précédent")}</button>
          <button type="button" className="btn-secondary !py-1 text-xs" disabled={page >= a.pages} onClick={() => setPage(page + 1)}>{t("Suivant")}</button>
        </span>
      </div>
    </div>
  );
}

function BarreFiltres({ f, setF, options, consolide }) {
  const [texte, setTexte] = useState(f.q);
  useEffect(() => {
    if (texte === f.q) return undefined;
    const h = setTimeout(() => setF((x) => ({ ...x, q: texte })), 350);
    return () => clearTimeout(h);
  }, [texte, f.q, setF]);
  const maj = (k) => (e) => setF((x) => {
    const n = { ...x, [k]: e.target.value };
    if (k === "cycle") { n.niveau = ""; n.classe = ""; }
    if (k === "niveau") n.classe = "";
    return n;
  });
  const sel = (k, libelle, choix, tous) => (
    <label className="text-xs text-slate-500 min-w-0"><span className="block mb-0.5">{t(libelle)}</span>
      <select className="input !py-1.5 text-sm" value={f[k]} onChange={maj(k)} data-testid={`filtre-${k}`}>
        <option value="">{t(tous)}</option>{choix.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select></label>
  );
  const actifs = Object.entries(f).filter(([, v]) => v).length;
  return (
    <div className="card space-y-2" data-testid="situation-filtres">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 items-end">
        {!consolide && sel("annee", "Année scolaire", options.annees.map((a) => [a.id, a.nom]), "Toutes")}
        {!consolide && sel("cycle", "Cycle", options.cycles.map((c) => [c.id, t(c.nom)]), "Tous")}
        {!consolide && sel("niveau", "Niveau", options.niveaux.map((n) => [n.id, n.nom]), "Tous")}
        {!consolide && sel("classe", "Classe", options.classes.map((c) => [c.id, c.nom]), "Toutes")}
        {sel("nature", "Nature de frais", NATURES_FRAIS.map(([v, l]) => [v, t(l)]), "Toutes")}
        {sel("statut", "Statut de paiement", STATUTS.slice(1).map(([v, l]) => [v, t(l)]), "Tous les statuts")}
        <label className="text-xs text-slate-500"><span className="block mb-0.5">{t("Échéances du")}</span>
          <input type="date" className="input !py-1.5 text-sm" value={f.debut} onChange={maj("debut")} /></label>
        <label className="text-xs text-slate-500"><span className="block mb-0.5">{t("au")}</span>
          <input type="date" className="input !py-1.5 text-sm" value={f.fin} onChange={maj("fin")} /></label>
        <label className="text-xs text-slate-500 col-span-2 sm:col-span-1"><span className="block mb-0.5">{t("Rechercher un élève")}</span>
          <span className="relative block"><Search className="w-3.5 h-3.5 absolute left-2 top-2.5 text-slate-400" aria-hidden="true" />
            <input type="search" className="input !py-1.5 !pl-7 text-sm" value={texte} onChange={(e) => setTexte(e.target.value)}
              placeholder={t("Nom, matricule, classe")} data-testid="filtre-q" /></span></label>
      </div>
      {actifs > 0 && (
        <button type="button" className="text-xs text-feba-navy hover:underline inline-flex items-center gap-1" onClick={() => { setTexte(""); setF(VIDE); }}>
          <X className="w-3 h-3" aria-hidden="true" />{t("Effacer les filtres")} ({actifs})</button>
      )}
    </div>
  );
}

function Academie({ a, vue, setVue, setF, tri, setTri, page, setPage, onEleve, racine, consolide, exporter }) {
  const filtrer = (patch, versVue) => { setF((x) => ({ ...x, ...patch })); setPage(1); if (versVue) setVue(versVue); };
  return (
    <section className="space-y-3" data-testid={`situation-academie-${a.academie.id}`}>
      <div className="card space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-bold text-slate-800">{a.academie.nom} <span className="text-xs text-slate-500 font-normal">· {a.devise}</span></h2>
          {!consolide && (
            <button type="button" className="btn-secondary text-sm inline-flex items-center gap-1.5" onClick={exporter} data-testid="situation-export">
              <Download className="w-4 h-4" aria-hidden="true" />{t("Exporter (CSV)")}</button>
          )}
        </div>
        {!a.calculable ? (
          <div className="rounded-xl bg-amber-50 border border-amber-200 p-3 text-sm text-amber-900" data-testid="situation-sans-tarif" role="note">
            <p>{t(a.raison_non_calculable)}</p>
            <Link to={`${racine}/tarifs`} className="font-medium text-feba-navy hover:underline">{t("Configurer les tarifs et échéances")}</Link>
          </div>
        ) : null}
        <Kpis a={a} />
        {a.anomalies.length > 0 && (
          <details className="text-xs text-amber-800"><summary className="cursor-pointer font-medium">{a.anomalies.length} {t("anomalie(s) à corriger")}</summary>
            <ul className="list-disc pl-5 mt-1">{a.anomalies.map((m) => <li key={m}>{m}</li>)}</ul></details>
        )}
      </div>
      {a.calculable ? <Graphiques a={a} vue={vue} onFiltre={filtrer} /> : <Encaissements a={a} />}
      {a.calculable && (vue === "eleve"
        ? <TableauEleves a={a} tri={tri} setTri={setTri} page={page} setPage={setPage} onEleve={onEleve} />
        : <TableauGroupes a={a} vue={vue} onGroupe={(g) => filtrer({ [vue === "niveau" ? "niveau" : "classe"]: g.id ? String(g.id) : "" }, "eleve")} />)}
    </section>
  );
}

export default function SituationFinanciere() {
  const { user } = useAuth();
  const { isAllAcademies } = useAcademy();
  const academyKey = useAcademyKey();
  const [vue, setVue] = useState("classe");
  const [f, setF] = useState(VIDE);
  const [tri, setTri] = useState({ cle: "retard", ordre: "desc" });
  const [page, setPage] = useState(1);
  const [eleve, setEleve] = useState(null);
  // Nouveau filtre ou nouveau tri : retour à la première page.
  const changerF = useCallback((x) => { setF(x); setPage(1); }, []);
  const changerTri = useCallback((x) => { setTri(x); setPage(1); }, []);
  const params = useMemo(() => ({
    groupe: vue, page, tri: tri.cle, ordre: tri.ordre,
    ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)),
  }), [vue, page, tri, f]);
  const q = useQuery({ queryKey: ["situation", academyKey, params], queryFn: () => paymentsAPI.situation(params), placeholderData: keepPreviousData });
  const optQ = useQuery({ queryKey: ["paiements-filtres", academyKey, f.annee, f.cycle, f.niveau],
    queryFn: () => paymentsAPI.filtres(Object.fromEntries(Object.entries({ annee: f.annee, cycle: f.cycle, niveau: f.niveau }).filter(([, v]) => v))),
    enabled: !isAllAcademies });
  const o = optQ.data?.data || {};
  const options = { annees: o.annees || [], cycles: o.cycles || [], niveaux: o.niveaux || [], classes: o.classes || [] };
  const academies = q.data?.data?.academies || [];
  const racine = user?.role === "superadmin" ? "/superadmin" : "/admin";
  const exporter = async () => {
    try {
      const r = await paymentsAPI.situationExport(Object.fromEntries(Object.entries(f).filter(([, v]) => v)));
      telecharger("situation-financiere.csv", r.data);
    } catch (e) { toast.error(extractApiError(e)); }
  };
  return (
    <div className="space-y-4">
      <PageHeader title={t("Situation financière")} subtitle={t("Montants attendus, remises, exonérations, encaissements et restes à payer, par classe, niveau et élève")} />
      <div className="flex flex-wrap gap-2" role="tablist" aria-label={t("Vue")}>
        {VUES.map(([v, l]) => (
          <button key={v} type="button" role="tab" onClick={() => { setVue(v); setPage(1); }} aria-selected={vue === v} data-testid={`groupe-${v}`}
            className={vue === v ? "onglet-actif" : "onglet"}>{t(l)}</button>
        ))}
      </div>
      <BarreFiltres f={f} setF={changerF} options={options} consolide={isAllAcademies} />
      {q.isPending && <div className="card h-40 animate-pulse motion-reduce:animate-none" />}
      {q.isError && <p role="alert" className="card text-sm text-red-700">{extractApiError(q.error)}</p>}
      <div className={`space-y-6 transition-opacity motion-reduce:transition-none ${q.isFetching && !q.isPending ? "opacity-60" : ""}`} aria-busy={q.isFetching}>
        {academies.map((a) => (
          <Academie key={a.academie.id} a={a} vue={vue} setVue={setVue} setF={changerF} tri={tri} setTri={changerTri} page={page} setPage={setPage}
            onEleve={setEleve} racine={racine} consolide={isAllAcademies} exporter={exporter} />
        ))}
      </div>
      <Modal open={Boolean(eleve)} onClose={() => setEleve(null)} title={eleve ? `${t("Fiche financière")} - ${eleve.nom}` : ""} size="xl">
        {eleve && <ReleveEleve eleveId={eleve.id} academyKey={academyKey} />}
      </Modal>
    </div>
  );
}
