/**
 * Logo de l'académie active dans les barres latérales.
 *
 * Sans logo activé (académie nouvellement créée), ou si l'image ne se
 * charge pas, on affiche le MONOGRAMME de l'académie — jamais une image
 * cassée, jamais le logo d'une autre académie.
 */
import { useState } from "react";
import { useBranding } from "../hooks/useBranding";

export default function AcademyLogo({ className = "w-full h-full object-contain" }) {
  const { logoSrc, logoAlt, monogram } = useBranding();
  const [failed, setFailed] = useState(null);
  if (logoSrc && failed !== logoSrc) {
    return <img src={logoSrc} alt={logoAlt} className={className} onError={() => setFailed(logoSrc)} />;
  }
  return (
    <span role="img" aria-label={logoAlt} data-testid="academy-monogram"
          className="w-full h-full flex items-center justify-center bg-primary text-white font-bold text-xs">
      {monogram}
    </span>
  );
}
