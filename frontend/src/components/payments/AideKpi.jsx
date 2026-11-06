/**
 * Explication d'un indicateur : bouton « i » accessible (souris, clavier, toucher,
 * lecteur d'écran). Le texte s'ouvre au survol, au focus ou au toucher, et se
 * ferme avec Échap ou en cliquant ailleurs.
 */
import { useId, useRef, useState } from "react";
import { Info } from "lucide-react";
import { useFermetureExterieure } from "../../hooks/useFermetureExterieure";
import { t } from "../../i18n";

export function AideKpi({ texte }) {
  const [ouvert, setOuvert] = useState(false);
  const id = useId();
  const zone = useRef(null);
  useFermetureExterieure(zone, ouvert, () => setOuvert(false));
  if (!texte) return null;
  return (
    <span className="relative inline-flex" ref={zone} onMouseEnter={() => setOuvert(true)} onMouseLeave={() => setOuvert(false)}>
      <button type="button" className="text-slate-400 hover:text-feba-navy focus-visible:text-feba-navy rounded" aria-label={t("Explication")}
        aria-describedby={ouvert ? id : undefined} aria-expanded={ouvert} onClick={() => setOuvert((v) => !v)} onFocus={() => setOuvert(true)}
        onBlur={() => setOuvert(false)}>
        <Info className="w-3 h-3" aria-hidden="true" />
      </button>
      {ouvert && (
        <span id={id} role="tooltip"
          className="absolute left-0 top-5 z-30 w-60 max-w-[70vw] rounded-lg bg-slate-900 px-2.5 py-2 text-[11px] font-normal leading-snug text-white shadow-lg">
          {texte}
        </span>
      )}
    </span>
  );
}
