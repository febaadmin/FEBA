/**
 * Lightbox — visionneuse plein écran de la galerie (images et vidéo).
 * Fermeture par Échap / clic sur le fond, navigation clavier et boutons.
 * La vidéo n'est chargée qu'à l'ouverture de son slide (preload=none).
 */
import { useCallback, useEffect } from "react";
import { X, ChevronLeft, ChevronRight } from "lucide-react";

export default function Lightbox({ items, index, onClose, onNavigate }) {
  const item = items[index];

  const prev = useCallback(
    () => onNavigate((index - 1 + items.length) % items.length),
    [index, items.length, onNavigate],
  );
  const next = useCallback(
    () => onNavigate((index + 1) % items.length),
    [index, items.length, onNavigate],
  );

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") prev();
      if (e.key === "ArrowRight") next();
    };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose, prev, next]);

  if (!item) return null;

  return (
    <div className="fixed inset-0 z-50 bg-feba-navy/95 flex items-center justify-center p-4"
      role="dialog" aria-modal="true" aria-label={item.caption || "Visionneuse"}
      onClick={onClose}>
      <button onClick={onClose} aria-label="Fermer la visionneuse"
        className="absolute top-4 right-4 p-2.5 rounded-full bg-white/10 text-white hover:bg-feba-gold hover:text-feba-navy transition-colors z-10">
        <X className="w-6 h-6" />
      </button>

      {items.length > 1 && (
        <>
          <button onClick={(e) => { e.stopPropagation(); prev(); }} aria-label="Média précédent"
            className="absolute left-3 sm:left-6 p-2.5 rounded-full bg-white/10 text-white hover:bg-feba-gold hover:text-feba-navy transition-colors z-10">
            <ChevronLeft className="w-6 h-6" />
          </button>
          <button onClick={(e) => { e.stopPropagation(); next(); }} aria-label="Média suivant"
            className="absolute right-3 sm:right-6 p-2.5 rounded-full bg-white/10 text-white hover:bg-feba-gold hover:text-feba-navy transition-colors z-10">
            <ChevronRight className="w-6 h-6" />
          </button>
        </>
      )}

      <figure className="max-w-5xl max-h-[85vh] w-full" onClick={(e) => e.stopPropagation()}>
        {item.kind === "video" ? (
          <video key={item.video_url} controls preload="none" playsInline
            poster={item.image_src || undefined}
            className="w-full max-h-[75vh] rounded-xl bg-black">
            <source src={item.video_url} type="video/mp4" />
            Votre navigateur ne prend pas en charge la lecture vidéo.
          </video>
        ) : (
          <img src={item.image_src} alt={item.alt_text || item.caption || ""}
            className="w-full max-h-[75vh] object-contain rounded-xl" />
        )}
        {item.caption && (
          <figcaption className="text-center text-white/85 text-sm mt-3">{item.caption}</figcaption>
        )}
      </figure>
    </div>
  );
}
