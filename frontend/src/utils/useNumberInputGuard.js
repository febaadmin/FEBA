import { useEffect } from "react";

/**
 * Garde globale (V7) : empêche TOUT <input type="number"> focalisé de voir sa
 * valeur modifiée par la molette de la souris. C'est le geste accidentel le
 * plus courant (faire défiler la page alors qu'un champ numérique a le focus)
 * — il décrémentait/incrémentait la valeur d'un « step » à l'insu de
 * l'utilisateur. La saisie ne doit jamais changer sans action délibérée.
 *
 * Défense en profondeur : les champs de NOTE sont désormais des champs texte
 * (insensibles par nature) ; cette garde protège les autres champs numériques
 * restants (coefficients, montants, âges…).
 */
export function useNumberInputGuard() {
  useEffect(() => {
    const onWheel = (e) => {
      const el = document.activeElement;
      if (
        el &&
        el.tagName === "INPUT" &&
        el.type === "number" &&
        el === e.target
      ) {
        // Empêche l'action par défaut (± step) sans voler le focus.
        e.preventDefault();
      }
    };
    // passive:false requis pour pouvoir appeler preventDefault sur wheel.
    document.addEventListener("wheel", onWheel, { passive: false });
    return () => document.removeEventListener("wheel", onWheel);
  }, []);
}
