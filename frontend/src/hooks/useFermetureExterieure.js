import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

/**
 * Ferme un menu déroulant : clic ou toucher hors du conteneur, Échap, focus parti ailleurs, changement de page.
 * Écoute en phase de capture : un `stopPropagation` ailleurs dans la page ne l'empêche pas de se fermer.
 */
export function useFermetureExterieure(conteneur, ouvert, fermer) {
  const { pathname } = useLocation();
  const rappel = useRef(fermer);
  useEffect(() => { rappel.current = fermer; });

  useEffect(() => {
    if (ouvert) rappel.current();
    // Seul un changement de page déclenche cette fermeture.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  useEffect(() => {
    if (!ouvert) return undefined;
    const dehors = (cible) => conteneur.current && cible instanceof Node && !conteneur.current.contains(cible);
    const pointeur = (e) => { if (dehors(e.target)) rappel.current(); };
    const touche = (e) => { if (e.key === "Escape") rappel.current(); };
    const focus = (e) => { if (dehors(e.target)) rappel.current(); };
    document.addEventListener("pointerdown", pointeur, true);
    document.addEventListener("keydown", touche, true);
    document.addEventListener("focusin", focus, true);
    return () => {
      document.removeEventListener("pointerdown", pointeur, true);
      document.removeEventListener("keydown", touche, true);
      document.removeEventListener("focusin", focus, true);
    };
  }, [ouvert, conteneur]);
}
