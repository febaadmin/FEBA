/**
 * Image du site vitrine : srcset responsive (800/1600), lazy loading par
 * défaut, dimensions stables (CLS) et — V5 — POINT FOCAL automatique.
 *
 * Le cadrage de chaque visuel packagé est défini une seule fois dans
 * mediaMeta.js (object-position desktop + variante mobile) et appliqué ici
 * via des variables CSS (classe .site-img, voir index.css). Les composants
 * peuvent surcharger ponctuellement avec `position` / `mobilePosition`
 * (ex. valeurs administrées provenant de l'API).
 */
import { metaFor } from "../mediaMeta";

export default function SiteImage({
  src, alt = "", className = "", eager = false, sizes = "100vw",
  position, mobilePosition, ...rest
}) {
  if (!src) return null;
  const small = src.replace("-1600.webp", "-800.webp");
  const hasVariants = small !== src;
  const meta = metaFor(src);
  const pos = position || meta.position;
  const posMobile = mobilePosition || meta.mobile || pos;
  return (
    <img
      src={src}
      srcSet={hasVariants ? `${small} 800w, ${src} 1600w` : undefined}
      sizes={hasVariants ? sizes : undefined}
      alt={alt}
      loading={eager ? "eager" : "lazy"}
      decoding={eager ? "sync" : "async"}
      className={`site-img ${className}`}
      style={{ "--site-img-pos": pos, "--site-img-pos-mobile": posMobile }}
      {...rest}
    />
  );
}
