/**
 * Actions du centre d'analyse (à la place de l'ancien sélecteur de langue en double) :
 *  - Imprimer / PDF : impression du rapport affiché (menus et filtres masqués, en-tête
 *    avec académie, période et filtres) ; « Enregistrer au format PDF » du navigateur ;
 *  - Exporter (CSV) : tous les tableaux du rapport affiché, avec leur titre ;
 *  - Copier le lien : l'onglet et les filtres sont dans l'adresse ; le lien n'ouvre
 *    rien de plus que ce que le destinataire a le droit de voir (contrôle serveur) ;
 *  - Vues enregistrées : combinaisons onglet + filtres mémorisées sur ce navigateur.
 */
import { useRef, useState } from "react";
import toast from "react-hot-toast";
import { Bookmark, ChevronDown, Download, Link2, Printer, Trash2 } from "lucide-react";
import { useFermetureExterieure } from "../../hooks/useFermetureExterieure";
import { tableauxEnCsv, telechargerTexte } from "../../utils/exportTableaux";
import { useT } from "./presentation";

const CLE = (profil) => `feba.analyses.vues.${profil}`;
const lireVues = (profil) => { try { return JSON.parse(localStorage.getItem(CLE(profil)) || "[]"); } catch { return []; } };
const ecrireVues = (profil, v) => { try { localStorage.setItem(CLE(profil), JSON.stringify(v)); return true; } catch { return false; } };

export function lienAnalyse(base, onglet, filtres) {
  const p = new URLSearchParams();
  if (onglet) p.set("onglet", onglet);
  const actifs = Object.fromEntries(Object.entries(filtres || {}).filter(([, v]) => (Array.isArray(v) ? v.length : v !== "" && v != null)));
  if (Object.keys(actifs).length) p.set("filtres", JSON.stringify(actifs));
  const q = p.toString();
  return q ? `${base}?${q}` : base;
}

/** Lecture prudente de l'adresse : seules les clés connues, au bon format, sont reprises. */
export function lireLien(search, vides, onglets) {
  const p = new URLSearchParams(search);
  const onglet = onglets.includes(p.get("onglet")) ? p.get("onglet") : null;
  let filtres = null;
  try {
    const brut = JSON.parse(p.get("filtres") || "null");
    if (brut && typeof brut === "object") {
      filtres = { ...vides };
      for (const [k, v] of Object.entries(brut)) {
        if (!(k in vides)) continue;
        if (Array.isArray(vides[k]) && Array.isArray(v)) filtres[k] = v.map(String).slice(0, 50);
        else if (!Array.isArray(vides[k]) && typeof v === "string") filtres[k] = v.slice(0, 40);
      }
    }
  } catch { /* adresse modifiée à la main : ignorée */ }
  return { onglet, filtres };
}

export default function ActionsAnalyse({ rapport, onglet, filtres, appliquer, profil, entete, nomFichier = "analyse" }) {
  const t = useT();
  const [vues, setVues] = useState(() => lireVues(profil));
  const [ouvert, setOuvert] = useState(false);
  const zone = useRef(null);
  useFermetureExterieure(zone, ouvert, () => setOuvert(false));

  const exporter = () => {
    const { csv, tableaux } = tableauxEnCsv(rapport.current, entete);
    if (!tableaux) { toast(t("Aucun tableau dans cet onglet : rien à exporter.")); return; }
    telechargerTexte(`${nomFichier}-${onglet || "rapport"}.csv`, csv);
    toast.success(t("{n} tableau(x) exporté(s).", { n: tableaux }));
  };
  const copier = async () => {
    const url = lienAnalyse(`${window.location.origin}${window.location.pathname}`, onglet, filtres);
    try { await navigator.clipboard.writeText(url); toast.success(t("Lien copié : il reprend cet onglet et ces filtres.")); }
    catch { window.prompt(t("Copiez ce lien :"), url); }
  };
  const enregistrer = () => {
    const nom = window.prompt(t("Nom de la vue (ex. « CM2 – trimestre 1 ») :"));
    if (!nom || !nom.trim()) return;
    const n = [{ nom: nom.trim().slice(0, 60), onglet, filtres }, ...vues.filter((v) => v.nom !== nom.trim())].slice(0, 20);
    setVues(n);
    if (ecrireVues(profil, n)) toast.success(t("Vue enregistrée sur ce navigateur."));
    else toast.error(t("Le navigateur n'autorise pas l'enregistrement local."));
  };
  const supprimer = (nom) => { const n = vues.filter((v) => v.nom !== nom); setVues(n); ecrireVues(profil, n); };

  return (
    <div className="flex flex-wrap items-center gap-1.5 print:hidden" data-testid="actions-analyse">
      <button type="button" className="btn-secondary !min-h-[36px] !py-1.5 text-xs" onClick={() => window.print()} data-testid="analyse-imprimer">
        <Printer className="w-4 h-4" aria-hidden="true" />{t("Imprimer / PDF")}</button>
      <button type="button" className="btn-secondary !min-h-[36px] !py-1.5 text-xs" onClick={exporter} data-testid="analyse-exporter">
        <Download className="w-4 h-4" aria-hidden="true" />{t("Exporter (CSV)")}</button>
      {appliquer && <button type="button" className="btn-secondary !min-h-[36px] !py-1.5 text-xs" onClick={copier} data-testid="analyse-lien">
        <Link2 className="w-4 h-4" aria-hidden="true" />{t("Copier le lien")}</button>}
      {appliquer && <div className="relative" ref={zone}>
        <button type="button" className="btn-secondary !min-h-[36px] !py-1.5 text-xs" aria-expanded={ouvert} aria-haspopup="menu"
          onClick={() => setOuvert((v) => !v)} data-testid="analyse-vues">
          <Bookmark className="w-4 h-4" aria-hidden="true" />{t("Vues enregistrées")}{vues.length ? ` (${vues.length})` : ""}
          <ChevronDown className="w-3.5 h-3.5" aria-hidden="true" /></button>
        {ouvert && (
          <div role="menu" className="absolute right-0 top-11 z-30 w-72 max-w-[calc(100vw-2rem)] rounded-xl border border-slate-200 bg-white p-2 shadow-fenetre">
            <button type="button" role="menuitem" className="w-full text-left text-sm font-medium text-primary px-2 py-1.5 rounded-lg hover:bg-primary-50"
              onClick={() => { setOuvert(false); enregistrer(); }} data-testid="analyse-vue-enregistrer">+ {t("Enregistrer la vue actuelle")}</button>
            {vues.length === 0 ? <p className="text-xs text-slate-500 px-2 py-2">{t("Aucune vue enregistrée.")}</p> : (
              <ul className="mt-1 border-t border-slate-100 pt-1 max-h-64 overflow-y-auto">
                {vues.map((v) => (
                  <li key={v.nom} className="flex items-center gap-1">
                    <button type="button" role="menuitem" className="flex-1 text-left text-sm px-2 py-1.5 rounded-lg hover:bg-slate-50 truncate"
                      onClick={() => { setOuvert(false); appliquer(v); }}>{v.nom}</button>
                    <button type="button" className="p-1.5 text-slate-400 hover:text-red-700" aria-label={`${t("Supprimer la vue")} ${v.nom}`}
                      onClick={() => supprimer(v.nom)}><Trash2 className="w-3.5 h-3.5" aria-hidden="true" /></button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>}
    </div>
  );
}
