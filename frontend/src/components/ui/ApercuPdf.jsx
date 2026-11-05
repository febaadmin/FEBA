/**
 * Aperçu d'un PDF dans la page, sans cadre (iframe) : chaque page est dessinée
 * dans un <canvas> par pdf.js.
 *
 * Pourquoi : la politique de sécurité (CSP) de production interdit d'afficher une
 * URL blob: dans un cadre (frame-src), et l'API refuse d'être affichée dans un cadre
 * (X-Frame-Options DENY, frame-ancestors 'none'). L'aperçu du bulletin apparaissait
 * donc comme « Ce contenu est bloqué ». pdf.js respecte la CSP telle quelle :
 * - code et worker servis par notre propre origine (script-src 'self') ;
 * - aucun eval (isEvalSupported: false, recommandé depuis CVE-2024-4367) ;
 * - le PDF est passé en mémoire (aucune requête réseau supplémentaire).
 *
 * pdf.js (≈ 1 Mo) n'est chargé qu'à l'ouverture du premier aperçu.
 */
import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { t } from "../../i18n";

async function chargerPdfjs() {
  const [pdfjs, worker] = await Promise.all([
    import("pdfjs-dist"),
    import("pdfjs-dist/build/pdf.worker.min.mjs?url"),
  ]);
  pdfjs.GlobalWorkerOptions.workerSrc = worker.default;
  return pdfjs;
}

export default function ApercuPdf({ donnees, titre, className = "", testid }) {
  const conteneur = useRef(null);
  const [etat, setEtat] = useState("chargement");     // chargement | pret | erreur
  const [pages, setPages] = useState(0);

  useEffect(() => {
    if (!donnees) return undefined;
    let annule = false;
    let documentPdf = null;
    setEtat("chargement");
    (async () => {
      try {
        const pdfjs = await chargerPdfjs();
        const octets = new Uint8Array(donnees instanceof Blob ? await donnees.arrayBuffer() : donnees);
        documentPdf = await pdfjs.getDocument({ data: octets, isEvalSupported: false, useSystemFonts: true }).promise;
        if (annule) return;
        const zone = conteneur.current;
        const largeur = Math.max((zone?.clientWidth || 600) - 16, 200);
        const densite = Math.min(window.devicePixelRatio || 1, 2);
        const toiles = [];
        for (let n = 1; n <= documentPdf.numPages; n++) {
          const page = await documentPdf.getPage(n);
          const base = page.getViewport({ scale: 1 });
          const vue = page.getViewport({ scale: (largeur / base.width) * densite });
          const toile = document.createElement("canvas");
          toile.width = Math.floor(vue.width);
          toile.height = Math.floor(vue.height);
          toile.style.width = `${Math.floor(vue.width / densite)}px`;
          toile.className = "block mx-auto mb-2 bg-white shadow-sm";
          toile.setAttribute("role", "img");
          toile.setAttribute("aria-label", `${titre || t("Document PDF")} · ${t("page {n} sur {total}", { n, total: documentPdf.numPages })}`);
          await page.render({ canvasContext: toile.getContext("2d"), viewport: vue }).promise;
          if (annule) return;
          toiles.push(toile);
        }
        zone?.replaceChildren(...toiles);
        setPages(documentPdf.numPages);
        setEtat("pret");
      } catch (e) {
        // Cause visible dans la console (et donc dans les rapports d'incident) :
        // un échec silencieux a masqué le worker refusé en production.
        console.error("[ApercuPdf] rendu impossible :", e);
        if (!annule) setEtat("erreur");
      }
    })();
    return () => {
      annule = true;
      documentPdf?.destroy?.();
    };
  }, [donnees, titre]);

  return (
    <div className={`relative overflow-auto ${className}`} data-testid={testid} data-etat={etat} data-pages={pages}>
      {etat === "chargement" && (
        <div className="absolute inset-0 flex items-center justify-center" aria-label={t("Chargement…")}>
          <Loader2 className="w-6 h-6 animate-spin text-primary" aria-hidden="true" />
        </div>
      )}
      {etat === "erreur" && (
        <p role="alert" className="p-4 text-sm text-red-700 text-center">
          {t("L'aperçu n'a pas pu être affiché. Ouvrez ou téléchargez le PDF.")}
        </p>
      )}
      <div ref={conteneur} className="p-2" />
    </div>
  );
}
