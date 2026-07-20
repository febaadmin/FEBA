/**
 * HeroCarousel — carrousel premium du site vitrine.
 *
 * - slides administrables (API /website/hero-slides/) ;
 * - défilement automatique (6 s) désactivé si prefers-reduced-motion,
 *   suspendu au survol/focus ;
 * - navigation flèches + points, accessible au clavier (aria) ;
 * - gestes tactiles (swipe gauche/droite) ;
 * - dégradé bleu marine pour garantir le contraste du texte.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronLeft, ChevronRight } from "lucide-react";
import SiteImage from "./SiteImage";
import { OVERLAYS } from "../mediaMeta";
import { DEFAULT_SLIDES } from "../siteDefaults";

const AUTOPLAY_MS = 6000;

export default function HeroCarousel({ slides = [] }) {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const touchStartX = useRef(null);
  const reducedMotion = useRef(
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches
  );

  // V6 : le carrousel n'est JAMAIS remplacé par une image statique. Si aucun
  // slide n'est administré (API vide, base non seedée, redéploiement), on
  // affiche les 5 slides de repli bâtis sur les médias packagés — un vrai
  // carrousel premium, avec points focaux, flèches et indicateurs.
  const activeSlides = slides.length ? slides : DEFAULT_SLIDES;
  const count = activeSlides.length;
  const go = useCallback(
    (delta) => setIndex((i) => (i + delta + count) % count),
    [count],
  );

  // Garde l'index dans les bornes si la source de slides change.
  useEffect(() => { setIndex((i) => (i >= count ? 0 : i)); }, [count]);

  useEffect(() => {
    if (count < 2 || paused || reducedMotion.current) return undefined;
    const timer = setInterval(() => go(1), AUTOPLAY_MS);
    return () => clearInterval(timer);
  }, [count, paused, go]);

  return (
    <section
      className="relative h-[440px] sm:h-[540px] lg:h-[600px] overflow-hidden bg-feba-navy"
      role="region"
      aria-roledescription="carrousel"
      aria-label="À la une"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
      onTouchStart={(e) => { touchStartX.current = e.touches[0].clientX; }}
      onTouchEnd={(e) => {
        if (touchStartX.current == null) return;
        const dx = e.changedTouches[0].clientX - touchStartX.current;
        if (Math.abs(dx) > 48) go(dx < 0 ? 1 : -1);
        touchStartX.current = null;
      }}
    >
      {activeSlides.map((slide, i) => (
        <div key={slide.id ?? i} aria-hidden={i !== index}
          className={`absolute inset-0 transition-opacity duration-700 ${i === index ? "opacity-100" : "opacity-0 pointer-events-none"}`}>
          {/* V5 : point focal administré (focal_x/focal_y) — le sujet de
              chaque slide reste cadré quel que soit le format d'écran. */}
          <SiteImage src={slide.image_src} alt="" eager={i === 0}
            position={slide.focal} sizes="100vw"
            className="absolute inset-0 w-full h-full object-cover" />
          {/* V6.1 — habillage marine DA FEBA (plus de voile gris délavé) :
              fondu bas + ancrage marine à gauche (texte) + pointe dorée. */}
          <div aria-hidden="true" className={`absolute inset-0 ${OVERLAYS.hero}`} />
          <div aria-hidden="true" className={`absolute inset-0 ${OVERLAYS["hero-left"]}`} />
          <div aria-hidden="true" className={`absolute inset-0 ${OVERLAYS["hero-gold"]}`} />
          <div aria-hidden="true" className={`absolute inset-0 ${OVERLAYS["top-navy"]}`} />
          <div className="relative h-full max-w-7xl mx-auto px-4 sm:px-6 flex flex-col justify-end pb-16 sm:pb-20">
            <h1 className="text-white text-[1.7rem] leading-snug sm:text-5xl lg:text-[3.4rem] font-bold max-w-[92%] sm:max-w-2xl sm:leading-tight drop-shadow">
              {slide.title}
            </h1>
            {slide.subtitle && (
              <p className="text-white/90 text-sm sm:text-xl mt-3 max-w-[88%] sm:max-w-xl drop-shadow">
                {slide.subtitle}
              </p>
            )}
            {slide.cta_label && slide.cta_url && (
              <div className="mt-6">
                <Link to={slide.cta_url}
                  className="inline-block px-6 py-3 rounded-xl bg-feba-gold text-feba-navy font-bold text-sm sm:text-base hover:bg-feba-gold2 focus-visible:ring-4 ring-feba-gold/40 transition-colors">
                  {slide.cta_label}
                </Link>
              </div>
            )}
          </div>
        </div>
      ))}

      {count > 1 && (
        <>
          {/* V5 : flèches masquées sur mobile (swipe tactile + points suffisent,
              et le titre ne passe plus jamais sous une flèche). */}
          <button onClick={() => go(-1)} aria-label="Slide précédent"
            className="hidden sm:block absolute left-3 top-1/2 -translate-y-1/2 p-2.5 rounded-full bg-feba-navy/50 text-white hover:bg-feba-gold hover:text-feba-navy transition-colors focus-visible:ring-4 ring-feba-gold/50">
            <ChevronLeft className="w-5 h-5" />
          </button>
          <button onClick={() => go(1)} aria-label="Slide suivant"
            className="hidden sm:block absolute right-3 top-1/2 -translate-y-1/2 p-2.5 rounded-full bg-feba-navy/50 text-white hover:bg-feba-gold hover:text-feba-navy transition-colors focus-visible:ring-4 ring-feba-gold/50">
            <ChevronRight className="w-5 h-5" />
          </button>
          <div className="absolute bottom-5 left-1/2 -translate-x-1/2 flex gap-2" role="tablist" aria-label="Choisir un slide">
            {activeSlides.map((s, i) => (
              <button key={s.id ?? i} role="tab" aria-selected={i === index}
                aria-label={`Slide ${i + 1} : ${s.title}`}
                onClick={() => setIndex(i)}
                className={`h-2.5 rounded-full transition-all ${i === index ? "w-7 bg-feba-gold" : "w-2.5 bg-white/50 hover:bg-white/80"}`} />
            ))}
          </div>
        </>
      )}
    </section>
  );
}
