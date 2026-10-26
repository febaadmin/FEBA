/**
 * useBranding — identité visuelle de l'académie AFFICHÉE.
 *
 * Source de vérité : l'API publique /schools/public-branding/<code>/, qui
 * renvoie le logo EFFECTIF de l'académie (logo téléversé et activé, sinon
 * son logo de repli — jamais celui d'une autre) et ses favicons, avec des
 * URL versionnées (?v=…) : une activation change l'URL, le navigateur ne
 * peut pas resservir l'ancienne image.
 *
 * Corrige :
 *  - la requête n'était lancée qu'avec un jeton : le site public et la page
 *    de connexion affichaient toujours le logo statique du frontend ;
 *  - la clé de cache ne distinguait pas les académies ;
 *  - le favicon n'était remplacé que par le logo « actif » brut.
 *
 * `academyCode` : académie explicite (site public : FEBA FHA sur /feba-fha).
 * Sinon : académie active du contexte, sinon FEBA (site du groupe, mode
 * « toutes les académies » du super administrateur).
 */
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { schoolsAPI } from "../api";
import { useAcademy } from "../context/AcademyContext";
import febaLogo from "../assets/feba_logo.png";

export const DEFAULT_ACADEMY_CODE = "FEBA";
export const brandingQueryKey = (code) => ["branding-public", code];

/** URL déterministe du logo effectif d'une académie (avant même la réponse). */
export const academyLogoUrl = (code) => `/api/schools/public-branding/${encodeURIComponent(code)}/logo/`;

const FAVICON_SLOTS = [
  { size: "32", key: "favicon_32_url", rel: "icon", sizes: "32x32" },
  { size: "16", key: "favicon_16_url", rel: "icon", sizes: "16x16" },
  { size: "180", key: "apple_touch_icon_url", rel: "apple-touch-icon", sizes: "180x180" },
];

/** Remplace les favicons de la page par ceux de l'académie (idempotent). */
export function applyFavicons(data) {
  if (!data || typeof document === "undefined") return;
  for (const slot of FAVICON_SLOTS) {
    const href = data[slot.key];
    if (!href) continue;
    let link = document.head.querySelector(`link[data-feba-favicon="${slot.size}"]`);
    if (!link) {
      link = document.createElement("link");
      link.setAttribute("data-feba-favicon", slot.size);
      link.rel = slot.rel;
      link.type = "image/png";
      link.sizes = slot.sizes;
      document.head.appendChild(link);
    }
    if (link.getAttribute("href") !== href) link.setAttribute("href", href);
  }
  // Aucune icône concurrente (ancienne référence /favicon.svg, icône posée
  // par une bibliothèque) ne doit garder la priorité.
  document.head.querySelectorAll("link[rel~='icon']:not([data-feba-favicon])")
    .forEach((el) => el.remove());
}

/** Initiales d'une académie (« Lycée de Parakou » → « LP »), au plus 3. */
export function monogramOf(name) {
  const words = String(name || "").replace(/[_-]+/g, " ").split(/\s+/)
    .filter((w) => w && !/^(de|du|des|la|le|les|d'|l')$/i.test(w));
  return words.slice(0, 3).map((w) => w[0].toUpperCase()).join("") || "?";
}

export function useBranding(academyCode) {
  const { activeAcademy } = useAcademy();
  const code = academyCode || activeAcademy?.code || DEFAULT_ACADEMY_CODE;

  const { data, error } = useQuery({
    queryKey: brandingQueryKey(code),
    queryFn: () => schoolsAPI.publicBranding(code).then((r) => r.data),
    staleTime: 60_000,
    retry: 1,
    throwOnError: false,
  });

  useEffect(() => { applyFavicons(data); }, [data]);

  // Repli : URL déterministe de CETTE académie ; le logo FEBA embarqué ne
  // sert qu'à FEBA (jamais à une autre académie) si l'API est injoignable.
  //
  // Réponse reçue SANS logo (académie créée sans logo activé) : aucune
  // image — l'URL de repli renverrait 404 et l'interface afficherait une
  // image cassée. Les écrans affichent alors le monogramme de l'académie.
  const logoSrc = data
    ? data.logo_url || null
    : (error && code === DEFAULT_ACADEMY_CODE ? febaLogo : academyLogoUrl(code));
  const displayName = data?.display_name || activeAcademy?.name || code;

  return {
    logoSrc,
    logoAlt: displayName,
    monogram: monogramOf(data?.short_name || activeAcademy?.short_name || displayName),
    academyCode: code,
    isDynamic: Boolean(data?.logo_is_uploaded),
    brandingData: data,
    hasError: Boolean(error),
  };
}
