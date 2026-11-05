/**
 * Éditeur de message : mise en forme simple (gras, italique, souligné, listes,
 * liens, paragraphes) ou texte brut.
 *
 * Aucune dépendance : zone `contentEditable` et commandes natives du navigateur.
 * Le HTML produit n'est PAS une autorité : le serveur le nettoie par liste
 * blanche (apps/notifications/html_securise.py) avant archivage et envoi, et
 * l'aperçu affiche la version nettoyée par le serveur. Le collage insère du
 * texte brut (pas de styles ni de scripts copiés depuis une page web).
 */
import { useEffect, useRef } from "react";
import { Bold, Eraser, Italic, Link2, List, ListOrdered, Underline } from "lucide-react";
import { t } from "../../i18n";

const OUTILS = [
  ["bold", Bold, "Gras"], ["italic", Italic, "Italique"], ["underline", Underline, "Souligné"],
  ["insertUnorderedList", List, "Liste à puces"], ["insertOrderedList", ListOrdered, "Liste numérotée"],
];

export function lienValide(url) {
  return /^(https?:\/\/|mailto:)[^\s"'<>]+$/i.test((url || "").trim());
}

export default function EditeurMessage({ format, onFormat, texte, onTexte, html, onHtml, id }) {
  const zone = useRef(null);
  // Le contenu n'est réinjecté que s'il change de l'extérieur (brouillon repris,
  // signature insérée, réinitialisation), jamais à chaque frappe : le curseur reste en place.
  useEffect(() => {
    if (format === "html" && zone.current && zone.current.innerHTML !== html) zone.current.innerHTML = html || "";
  }, [format, html]);

  const commande = (nom, valeur) => {
    zone.current?.focus();
    document.execCommand(nom, false, valeur);
    onHtml(zone.current?.innerHTML || "");
  };
  const lien = () => {
    const url = window.prompt(t("Adresse du lien (https://… ou mailto:…)"), "https://");
    if (url === null) return;
    if (!lienValide(url)) { window.alert(t("Lien refusé : seules les adresses https://, http:// et mailto: sont acceptées.")); return; }
    commande("createLink", url.trim());
  };
  const coller = (e) => {
    e.preventDefault();
    document.execCommand("insertText", false, e.clipboardData.getData("text/plain"));
    onHtml(zone.current?.innerHTML || "");
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label className="label !mb-0" htmlFor={id}>{t("Contenu")}</label>
        <div className="inline-flex rounded-lg border border-slate-200 p-0.5 text-xs" role="group" aria-label={t("Format du message")}>
          {[["html", "Mise en forme"], ["texte", "Texte brut"]].map(([v, n]) => (
            <button key={v} type="button" onClick={() => onFormat(v)} aria-pressed={format === v} data-testid={`format-${v}`}
              className={`px-2 py-0.5 rounded-md ${format === v ? "bg-feba-navy text-white" : "text-slate-600 hover:bg-slate-50"}`}>
              {t(n)}
            </button>
          ))}
        </div>
      </div>
      {format === "html" ? (
        <div className="rounded-xl border border-slate-200 focus-within:ring-2 focus-within:ring-primary/30 transition-shadow">
          <div className="flex flex-wrap gap-0.5 border-b border-slate-100 px-1.5 py-1" role="toolbar" aria-label={t("Mise en forme")}>
            {OUTILS.map(([nom, Icone, libelle]) => (
              <button key={nom} type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => commande(nom)}
                className="p-1.5 rounded-md text-slate-600 hover:bg-slate-100" title={t(libelle)} aria-label={t(libelle)}
                data-testid={`outil-${nom}`}>
                <Icone className="w-4 h-4" aria-hidden="true" />
              </button>
            ))}
            <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={lien}
              className="p-1.5 rounded-md text-slate-600 hover:bg-slate-100" title={t("Lien")} aria-label={t("Lien")} data-testid="outil-lien">
              <Link2 className="w-4 h-4" aria-hidden="true" />
            </button>
            <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => commande("removeFormat")}
              className="p-1.5 rounded-md text-slate-600 hover:bg-slate-100" title={t("Effacer la mise en forme")}
              aria-label={t("Effacer la mise en forme")}>
              <Eraser className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>
          <div id={id} ref={zone} role="textbox" aria-multiline="true" aria-label={t("Contenu")} contentEditable
            suppressContentEditableWarning onInput={(e) => onHtml(e.currentTarget.innerHTML)} onPaste={coller}
            className="min-h-[14rem] max-h-[28rem] overflow-y-auto px-3 py-2 text-sm text-slate-800 outline-none prose-sm [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_a]:text-primary [&_a]:underline"
            data-testid="editeur-html" />
        </div>
      ) : (
        <textarea id={id} className="input min-h-[14rem]" rows={10} value={texte} onChange={(e) => onTexte(e.target.value)}
          data-testid="editeur-texte" />
      )}
    </div>
  );
}
