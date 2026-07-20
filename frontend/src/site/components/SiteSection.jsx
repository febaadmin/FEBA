/** Briques de mise en page communes du site vitrine. */
import SiteImage from "./SiteImage";

export function Section({ children, className = "", tone = "cream", id }) {
  const tones = {
    cream: "bg-feba-cream",
    white: "bg-white",
    navy: "bg-feba-navy text-white",
    green: "bg-feba-green text-white",
  };
  return (
    <section id={id} className={`py-14 sm:py-20 ${tones[tone]} ${className}`}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6">{children}</div>
    </section>
  );
}

export function SectionHeading({ overline, title, intro, light = false, center = true }) {
  return (
    <div className={`max-w-3xl ${center ? "mx-auto text-center" : ""} mb-10 sm:mb-14`}>
      {overline && (
        <p className="text-feba-gold font-bold uppercase tracking-[0.2em] text-xs mb-3">{overline}</p>
      )}
      <h2 className={`text-2xl sm:text-4xl font-bold ${light ? "text-white" : "text-feba-navy"}`}>
        {title}
      </h2>
      {intro && (
        <p className={`mt-4 text-sm sm:text-base leading-relaxed ${light ? "text-white/85" : "text-feba-gray"}`}>
          {intro}
        </p>
      )}
    </div>
  );
}

export function PageBanner({ title, intro, image }) {
  return (
    <div className="relative bg-feba-navy">
      {image && (
        <SiteImage src={image} alt="" aria-hidden="true" eager
          className="absolute inset-0 w-full h-full object-cover opacity-25" />
      )}
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 py-16 sm:py-24">
        <h1 className="text-white text-3xl sm:text-5xl font-bold">{title}</h1>
        {intro && <p className="text-white/85 mt-4 max-w-2xl text-sm sm:text-lg">{intro}</p>}
        <div className="w-16 h-1 bg-feba-gold rounded mt-6" />
      </div>
    </div>
  );
}
