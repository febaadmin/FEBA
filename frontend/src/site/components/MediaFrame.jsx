/**
 * MediaFrame — cadre média du design system du site vitrine (V5).
 *
 * Compose : image à point focal (SiteImage) + dégradé de marque centralisé
 * (OVERLAYS de mediaMeta.js) + zone de contenu superposée facultative.
 * C'est LE composant à utiliser pour toute image porteuse d'un dégradé ou
 * d'un texte : aucun gradient arbitraire dans les pages.
 *
 * Usage :
 *   <MediaFrame src="/site/img/…-1600.webp" alt="…" overlay="left-navy"
 *     className="h-56 rounded-2xl shadow-md"
 *     contentClass="p-5 flex flex-col justify-center max-w-[60%]">
 *     …contenu posé sur la zone en dégradé…
 *   </MediaFrame>
 */
import SiteImage from "./SiteImage";
import { OVERLAYS } from "../mediaMeta";

export default function MediaFrame({
  src, alt = "", overlay = "none", eager = false, sizes = "100vw",
  className = "", imgClassName = "", contentClass = "",
  position, mobilePosition, children,
}) {
  return (
    <div className={`relative overflow-hidden ${className}`}>
      <SiteImage
        src={src} alt={alt} eager={eager} sizes={sizes}
        position={position} mobilePosition={mobilePosition}
        className={`absolute inset-0 w-full h-full object-cover ${imgClassName}`}
      />
      {overlay !== "none" && OVERLAYS[overlay] && (
        <div aria-hidden="true" className={`absolute inset-0 pointer-events-none ${OVERLAYS[overlay]}`} />
      )}
      {children && (
        <div className={`absolute inset-0 ${contentClass}`}>{children}</div>
      )}
    </div>
  );
}
