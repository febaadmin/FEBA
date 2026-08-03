/**
 * SiteLangSwitcher — sélecteur FR/EN du site public.
 *
 * Composant UNIQUE, monté dans le layout : il apparaît donc sur TOUTES les
 * pages publiques (accueil, à propos, académique, admissions, vie scolaire,
 * FEBA FHA, actualités, galerie, contact, formulaires, pages légales, 404).
 *
 * L'ancien sélecteur local de la page FHA a été supprimé pour éviter le
 * doublon : la langue vient désormais d'une source unique (`useSiteLang`).
 *
 * Accessibilité : groupe de boutons étiqueté, `aria-pressed` sur l'option
 * active, navigation et activation au clavier natives (éléments `button`).
 */
import { useSiteLang } from "../useSiteLang";

export default function SiteLangSwitcher({ tone = "light", className = "" }) {
  const { lang, setLang } = useSiteLang();

  const styles = {
    light: {
      wrap: "bg-feba-navy/5",
      active: "bg-feba-navy text-white",
      idle: "text-feba-navy/70 hover:text-feba-navy",
    },
    dark: {
      wrap: "bg-white/15",
      active: "bg-white text-feba-navy",
      idle: "text-white/80 hover:text-white",
    },
  }[tone];

  return (
    <div
      role="group"
      aria-label={lang === "fr" ? "Choix de la langue" : "Language selection"}
      className={`inline-flex rounded-xl p-1 ${styles.wrap} ${className}`}
    >
      {[
        ["en", "English"],
        ["fr", "Français"],
      ].map(([code, label]) => (
        <button
          key={code}
          type="button"
          onClick={() => setLang(code)}
          aria-pressed={lang === code}
          aria-label={label}
          lang={code}
          className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase transition-colors ${
            lang === code ? styles.active : styles.idle
          }`}
        >
          {code}
        </button>
      ))}
    </div>
  );
}
