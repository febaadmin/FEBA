/**
 * Page « Paiements » : recherche, filtres combinables, tri, pagination et
 * récapitulatif, tous calculés par le serveur (GET /api/payments/).
 *
 * Les filtres sont ceux du graphique du tableau de bord (mêmes paramètres, même
 * code serveur) : un paiement est sélectionné et compté de la même façon sur
 * les deux écrans. Les montants ne sont jamais additionnés entre devises.
 */
import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, FileSpreadsheet, Receipt, Search, Trash2, X } from "lucide-react";
import toast from "react-hot-toast";
import { paymentsAPI } from "../../api";
import { isCanceledError } from "../../api/academyScope";
import { useAcademy } from "../../context/AcademyContext";
import { useDiffere } from "../../hooks/useDiffere";
import { t, useI18n } from "../../i18n";
import { formatMinor } from "../../utils/money";
import { paymentDateTimeText } from "../../utils/datetime";
import { ageText } from "../../utils/age";
import { extractApiError } from "../../utils/errors";
import ChoixMultiple from "../ui/ChoixMultiple";
import { PERIODES_CALENDAIRES, PERIODES_DUREES, STATUTS } from "../dashboard/GraphiquePaiements";

export const FILTRES_PAGE = {
  periode: "", du: "", au: "", annee: "", cycle: "", niveau: "", classe: "", eleve: "",
  nature: [], mode: [], statut: "", montant_min: "", montant_max: "", montant: "",
};
const DEPENDANTS = { annee: ["classe", "eleve"], cycle: ["niveau", "classe", "eleve"], niveau: ["classe", "eleve"], classe: ["eleve"] };
const TAILLES = [25, 50, 100];

/** Paramètres de la requête : seulement les valeurs renseignées. */
export function parametresPage(filtres, q, tri, page, taille) {
  const p = { page, page_size: taille, tri };
  // Une année choisie remplace l'année en cours ; sans année, toutes les années si une période est choisie.
  if (!filtres.annee && filtres.periode) p.all_years = 1;
  for (const [k, v] of Object.entries(filtres)) {
    if (Array.isArray(v)) { if (v.length) p[k] = v.join(","); }
    else if (v !== "" && v !== null && v !== undefined) p[k] = v;
  }
  if (filtres.periode !== "perso") { delete p.du; delete p.au; }
  if (q.trim()) p.q = q.trim();
  return p;
}

function telecharger(nom, blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nom;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function Selection({ libelle, valeur, onChange, options, testid, desactive, aide, tous = t("Tous") }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-slate-600 min-w-0">
      <span className="font-medium">{libelle}</span>
      <select className="input !py-1 text-sm" value={valeur} onChange={(e) => onChange(e.target.value)}
        data-testid={testid} disabled={desactive} title={aide || undefined}>
        <option value="">{tous}</option>
        {options.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
      </select>
    </label>
  );
}

function EnteteTri({ libelle, cle, tri, setTri, droite }) {
  const actif = tri.replace("-", "") === cle;
  const desc = tri.startsWith("-");
  const Icone = !actif ? ArrowUpDown : desc ? ArrowDown : ArrowUp;
  return (
    <th className={`px-3 py-2 font-semibold text-slate-600 ${droite ? "text-right" : "text-left"}`}
      aria-sort={actif ? (desc ? "descending" : "ascending") : "none"}>
      <button type="button" className="inline-flex items-center gap-1 hover:text-slate-900" data-testid={`tri-${cle}`}
        onClick={() => setTri(actif && !desc ? `-${cle}` : cle)}>
        {libelle}<Icone className={`w-3 h-3 ${actif ? "text-feba-navy" : "text-slate-300"}`} aria-hidden="true" />
      </button>
    </th>
  );
}

export default function RecherchePaiements({ onOuvrir, onRecu, onSupprimer, onSupprimerSelection, rafraichir }) {
  useI18n();
  const { academyKey } = useAcademy();
  const [saisie, setSaisie] = useState("");
  const q = useDiffere(saisie, 350);
  // Les filtres appartiennent à une académie : changer d'académie repart de zéro
  // (classes et élèves d'une autre académie n'ont plus de sens).
  const [filtresEtat, setFiltresEtat] = useState({ academie: academyKey, valeurs: FILTRES_PAGE });
  const filtres = filtresEtat.academie === academyKey ? filtresEtat.valeurs : FILTRES_PAGE;
  const setFiltres = (fn) => setFiltresEtat({ academie: academyKey, valeurs: typeof fn === "function" ? fn(filtres) : fn });
  const [plus, setPlus] = useState(false);
  const [tri, setTri] = useState("-date");
  const [taille, setTaille] = useState(25);
  const [exportEnCours, setExport] = useState(false);
  // Page et sélection valent pour UNE recherche : toute modification ramène à la page 1, sans cases cochées.
  const cle = JSON.stringify([academyKey, q, filtres, tri, taille]);
  const [pageEtat, setPageEtat] = useState({ cle, page: 1, choisis: [] });
  const page = pageEtat.cle === cle ? pageEtat.page : 1;
  const choisis = pageEtat.cle === cle ? pageEtat.choisis : [];
  const setPage = (fn) => setPageEtat({ cle, page: typeof fn === "function" ? fn(page) : fn, choisis: [] });
  const setChoisis = (fn) => setPageEtat({ cle, page, choisis: typeof fn === "function" ? fn(choisis) : fn });

  const persoIncomplet = filtres.periode === "perso" && (!filtres.du || !filtres.au);
  const params = parametresPage(filtres, q, tri, page, taille);
  const { data, isFetching, isPending, isError, error } = useQuery({
    queryKey: ["payments-recherche", academyKey, params, rafraichir],
    queryFn: () => paymentsAPI.recherche(params),
    placeholderData: keepPreviousData,
    enabled: !persoIncomplet,
  });
  const structure = { annee: filtres.annee, cycle: filtres.cycle, niveau: filtres.niveau, classe: filtres.classe };
  const { data: optionsData } = useQuery({
    queryKey: ["payments-filtres", academyKey, structure],
    queryFn: () => paymentsAPI.filtres(Object.fromEntries(Object.entries(structure).filter(([, v]) => v))),
    placeholderData: keepPreviousData,
  });
  const o = optionsData?.data;
  const structureDispo = Boolean(o?.structure_disponible);
  const opts = (liste, compte) => (liste || []).map((x) => [String(x.id), compte && x.nb !== undefined ? `${t(x.nom)} (${x.nb})` : t(x.nom)]);
  const choix = {
    annee: opts(o?.annees), cycle: opts(o?.cycles), niveau: opts(o?.niveaux), classe: opts(o?.classes), eleve: opts(o?.eleves),
    nature: opts(o?.natures, true), mode: opts(o?.modes, true), statut: STATUTS.map(([v, n]) => [v, t(n)]),
    periode: [...PERIODES_CALENDAIRES, ...PERIODES_DUREES].map(([v, n]) => [v, t(n)]),
  };
  const LIBELLES = {
    periode: t("Période"), du: t("Du"), au: t("Au"), annee: t("Année scolaire"), cycle: t("Cycle"), niveau: t("Niveau"),
    classe: t("Classe"), eleve: t("Élève"), nature: t("Type de paiement"), mode: t("Mode de paiement"), statut: t("Statut"),
    montant_min: t("Montant minimal"), montant_max: t("Montant maximal"), montant: t("Montant exact"),
  };
  const changer = (cle) => (v) => setFiltres((f) => {
    const suivant = { ...f, [cle]: v };
    for (const d of DEPENDANTS[cle] || []) suivant[d] = "";
    return suivant;
  });
  const actifs = Object.entries(filtres).filter(([k, v]) => (Array.isArray(v) ? v.length : v !== "") && !(k === "du" || k === "au"));
  const nomDe = (cle, v) => (choix[cle] || []).find(([id]) => id === String(v))?.[1]?.replace(/ \(\d+\)$/, "") || v;
  const reinitialiser = () => { setFiltres(FILTRES_PAGE); setSaisie(""); };

  const r = data?.data;
  const lignes = r?.results || [];
  const total = r?.count ?? 0;
  const pages = Math.max(1, Math.ceil(total / taille));
  const totaux = r?.totaux || [];
  const messageErreur = () => {
    const d = error?.response?.data || {};
    const precision = Object.entries(d).filter(([k]) => k !== "detail").map(([k, v]) => `${LIBELLES[k] || k} : ${v}`).join(" · ");
    return [d.detail, precision].filter(Boolean).join(" ") || t("Les paiements n'ont pas pu être chargés.");
  };
  const tousChoisis = lignes.length > 0 && lignes.every((l) => choisis.includes(l.id));
  const basculerTous = () => setChoisis(tousChoisis ? [] : lignes.map((l) => l.id));

  const exporter = async () => {
    setExport(true);
    try {
      const { page: _p, page_size: _t, ...sansPage } = params;
      const rep = await paymentsAPI.exportXlsx(sansPage);
      telecharger(`paiements_${new Date().toISOString().slice(0, 10)}.xlsx`, rep.data);
    } catch (e) {
      toast.error(extractApiError(e));
    } finally {
      setExport(false);
    }
  };

  const libelleTotaux = totaux.map((d) => (
    <span key={d.devise} className="whitespace-nowrap" data-testid={`totaux-${d.devise}`}>
      <strong>{formatMinor(d.net_minor, d.devise)}</strong> {t("encaissé net")} ({d.nb_confirmes} {t("confirmé(s)")}
      {d.rembourse_minor ? `, ${t("remboursé")} ${formatMinor(d.rembourse_minor, d.devise)}` : ""})
      {d.nb_annules ? ` · ${d.nb_annules} ${t("annulé(s)")} : ${formatMinor(d.annule_minor, d.devise)}` : ""}
    </span>
  ));

  return (
    <div className="card space-y-3" data-testid="recherche-paiements">
      <div className="flex flex-wrap gap-2 items-end">
        <label className="relative flex-1 min-w-[16rem]">
          <span className="sr-only">{t("Rechercher un paiement")}</span>
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true" />
          <input type="search" value={saisie} onChange={(e) => setSaisie(e.target.value)} className="input pl-9 pr-8"
            placeholder={t("Élève, matricule, référence, montant, date (jj/mm/aaaa), classe, type, mode…")}
            data-testid="paiements-recherche" />
          {saisie && (
            <button type="button" className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              onClick={() => setSaisie("")} aria-label={t("Effacer la recherche")}><X className="w-4 h-4" /></button>
          )}
        </label>
        <div className="w-44"><Selection libelle={LIBELLES.periode} valeur={filtres.periode} onChange={changer("periode")}
          options={choix.periode} testid="pf-periode" tous={t("Toutes les dates")} /></div>
        <div className="w-44"><Selection libelle={LIBELLES.annee} valeur={filtres.annee} onChange={changer("annee")}
          options={choix.annee} testid="pf-annee" tous={t("Année en cours")} desactive={!structureDispo} /></div>
        <button type="button" onClick={exporter} disabled={exportEnCours || total === 0}
          className="btn-secondary flex items-center gap-2 text-sm" data-testid="paiements-export">
          <FileSpreadsheet className="w-4 h-4" aria-hidden="true" />{exportEnCours ? t("Export…") : t("Export Excel")}
        </button>
      </div>

      {filtres.periode === "perso" && (
        <div className="flex flex-wrap gap-3 text-sm">
          <label className="flex items-center gap-2">{t("Du")}<input type="date" className="input !py-1" value={filtres.du}
            onChange={(e) => changer("du")(e.target.value)} data-testid="pf-du" /></label>
          <label className="flex items-center gap-2">{t("Au")}<input type="date" className="input !py-1" value={filtres.au}
            onChange={(e) => changer("au")(e.target.value)} data-testid="pf-au" /></label>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
        <ChoixMultiple libelle={LIBELLES.nature} options={choix.nature} valeurs={filtres.nature} onChange={changer("nature")} testid="pf-nature" />
        <ChoixMultiple libelle={LIBELLES.mode} options={choix.mode} valeurs={filtres.mode} onChange={changer("mode")} testid="pf-mode" />
        <Selection libelle={LIBELLES.statut} valeur={filtres.statut} onChange={changer("statut")} options={choix.statut} testid="pf-statut" />
        {["cycle", "niveau", "classe"].map((cle) => (
          <Selection key={cle} libelle={LIBELLES[cle]} valeur={filtres[cle]} onChange={changer(cle)} options={choix[cle]}
            testid={`pf-${cle}`} desactive={!structureDispo}
            aide={!structureDispo ? t("Choisissez une académie pour filtrer par structure.") : null} />
        ))}
      </div>
      {plus && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          <Selection libelle={LIBELLES.eleve} valeur={filtres.eleve} onChange={changer("eleve")} options={choix.eleve}
            testid="pf-eleve" desactive={!filtres.classe} aide={!filtres.classe ? t("Choisissez d'abord une classe.") : null} />
          {["montant_min", "montant_max", "montant"].map((cle) => (
            <label key={cle} className="flex flex-col gap-1 text-xs text-slate-600">
              <span className="font-medium">{LIBELLES[cle]}</span>
              <input type="number" min="0" step="any" inputMode="decimal" className="input !py-1 text-sm" value={filtres[cle]}
                onChange={(e) => changer(cle)(e.target.value)} data-testid={`pf-${cle}`} />
            </label>
          ))}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className="text-xs font-medium text-feba-navy hover:underline" onClick={() => setPlus((x) => !x)}
          aria-expanded={plus} data-testid="pf-plus">{plus ? t("Moins de filtres") : t("Plus de filtres")}</button>
        {actifs.map(([cle, v]) => (
          <span key={cle} className="inline-flex items-center gap-1 rounded-full bg-feba-navy/10 text-feba-navy text-xs px-2 py-0.5" data-testid={`pf-puce-${cle}`}>
            {LIBELLES[cle]} : {Array.isArray(v) ? v.map((x) => nomDe(cle, x)).join(", ")
              : cle === "periode" && v === "perso" ? `${filtres.du || "…"} → ${filtres.au || "…"}` : nomDe(cle, v)}
            <button type="button" onClick={() => changer(cle)(Array.isArray(v) ? [] : "")} aria-label={`${t("Retirer le filtre")} ${LIBELLES[cle]}`}>
              <X className="w-3 h-3" aria-hidden="true" />
            </button>
          </span>
        ))}
        {(actifs.length > 0 || saisie) && (
          <button type="button" className="text-xs font-medium text-red-700 hover:underline ml-auto" onClick={reinitialiser}
            data-testid="pf-reinitialiser">{t("Réinitialiser les filtres")}</button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-700 rounded-xl bg-slate-50 px-3 py-2" data-testid="paiements-recap" aria-live="polite">
        <span data-testid="paiements-total"><strong>{total}</strong> {t("paiement(s)")}</span>
        {libelleTotaux}
        {isFetching && <span className="text-xs text-slate-400">{t("Actualisation…")}</span>}
        {choisis.length > 0 && (
          <button type="button" className="ml-auto text-xs font-medium text-danger hover:underline inline-flex items-center gap-1"
            onClick={() => onSupprimerSelection(choisis, () => setChoisis([]))} data-testid="paiements-supprimer-selection">
            <Trash2 className="w-3.5 h-3.5" aria-hidden="true" />{t("Supprimer la sélection ({n})", { n: choisis.length })}
          </button>
        )}
      </div>

      {persoIncomplet ? (
        <p className="text-sm text-slate-500 py-8 text-center">{t("Choisissez les deux dates de la période.")}</p>
      ) : isError && !isCanceledError(error) ? (
        <p role="alert" className="text-sm text-red-700 py-8 text-center" data-testid="paiements-erreur">{messageErreur()}</p>
      ) : isPending ? (
        <div className="h-48 rounded-xl bg-slate-100 animate-pulse" aria-label={t("Chargement…")} />
      ) : lignes.length === 0 ? (
        <p className="text-sm text-slate-500 py-8 text-center" data-testid="paiements-vide">
          {actifs.length || q ? t("Aucun paiement ne correspond à cette recherche ou à ces filtres.") : t("Aucun paiement enregistré pour cette année.")}
        </p>
      ) : (
        <div className={`overflow-x-auto transition-opacity ${isFetching ? "opacity-60" : ""}`}>
          <table className="w-full text-sm" data-testid="paiements-tableau">
            <thead className="bg-slate-50 border-b border-slate-100">
              <tr>
                <th className="px-3 py-2 w-8">
                  <input type="checkbox" checked={tousChoisis} onChange={basculerTous} aria-label={t("Tout sélectionner")} />
                </th>
                <th className="px-3 py-2 text-left font-semibold text-slate-600">{t("Référence")}</th>
                <EnteteTri libelle={t("Élève")} cle="eleve" tri={tri} setTri={setTri} />
                <th className="px-3 py-2 text-left font-semibold text-slate-600">{t("Classe")}</th>
                <EnteteTri libelle={t("Type")} cle="type" tri={tri} setTri={setTri} />
                <EnteteTri libelle={t("Montant")} cle="montant" tri={tri} setTri={setTri} droite />
                <EnteteTri libelle={t("Mode")} cle="mode" tri={tri} setTri={setTri} />
                <EnteteTri libelle={t("Date et heure")} cle="date" tri={tri} setTri={setTri} />
                <EnteteTri libelle={t("Statut")} cle="statut" tri={tri} setTri={setTri} />
                <th className="px-3 py-2"><span className="sr-only">{t("Actions")}</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {lignes.map((p) => (
                <tr key={p.id} className="hover:bg-slate-50 cursor-pointer" onClick={() => onOuvrir(p)} data-testid={`paiement-${p.id}`}>
                  <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                    <input type="checkbox" checked={choisis.includes(p.id)} aria-label={t("Sélectionner {r}", { r: p.reference_number })}
                      onChange={() => setChoisis((c) => (c.includes(p.id) ? c.filter((x) => x !== p.id) : [...c, p.id]))} />
                  </td>
                  <td className="px-3 py-2 font-mono text-xs whitespace-nowrap">{p.reference_number}</td>
                  <td className="px-3 py-2">
                    <span className="block">{p.student_name}</span>
                    <span className="block text-xs text-slate-400">{[p.student_matricule, ageText(p.student_age, p.student_age_status)].filter(Boolean).join(" · ")}</span>
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">{p.student_class || "-"}</td>
                  <td className="px-3 py-2">{t(p.payment_type_label || p.payment_type || "-")}</td>
                  <td className="px-3 py-2 text-right font-bold text-success whitespace-nowrap tabular-nums">{formatMinor(p.amount_minor, p.currency)}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{t(p.payment_method_label || p.payment_method || "-")}</td>
                  <td className="px-3 py-2 whitespace-nowrap" title={p.has_time ? "" : t("Heure non enregistrée pour ce paiement")}>
                    {paymentDateTimeText(p)}{!p.has_time && <span className="ml-1 text-xs text-slate-400">· {t("heure n.e.")}</span>}
                  </td>
                  <td className="px-3 py-2">
                    {p.is_confirmed
                      ? <span className="text-xs text-success font-medium bg-success/10 px-2 py-0.5 rounded-full">{t("Confirmé")}</span>
                      : <span className="text-xs text-danger font-medium bg-danger/10 px-2 py-0.5 rounded-full">{t("Annulé")}</span>}
                  </td>
                  <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center gap-1 justify-end">
                      <button type="button" onClick={() => onRecu(p)} title={t("Générer reçu")} aria-label={t("Générer reçu")}
                        className="p-1.5 rounded-lg hover:bg-green-50 text-slate-400 hover:text-success"><Receipt className="w-4 h-4" /></button>
                      <button type="button" onClick={() => onSupprimer(p)} title={t("Supprimer")} aria-label={t("Supprimer")}
                        className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger"><Trash2 className="w-4 h-4" /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {total > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-600">
          <label className="flex items-center gap-2">{t("Par page")}
            <select className="input !py-1 w-auto" value={taille} onChange={(e) => setTaille(Number(e.target.value))} data-testid="pf-taille">
              {TAILLES.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <span data-testid="paiements-pagination">
            {t("{a}–{b} sur {n}", { a: (page - 1) * taille + 1, b: Math.min(page * taille, total), n: total })}
          </span>
          <div className="flex gap-1">
            <button type="button" className="btn-secondary !px-2 !py-1" disabled={page <= 1} onClick={() => setPage((x) => x - 1)}
              aria-label={t("Page précédente")} data-testid="page-precedente"><ChevronLeft className="w-4 h-4" /></button>
            <span className="px-2 py-1">{page} / {pages}</span>
            <button type="button" className="btn-secondary !px-2 !py-1" disabled={page >= pages} onClick={() => setPage((x) => x + 1)}
              aria-label={t("Page suivante")} data-testid="page-suivante"><ChevronRight className="w-4 h-4" /></button>
          </div>
        </div>
      )}
    </div>
  );
}
