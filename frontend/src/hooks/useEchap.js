import { useEffect, useRef } from "react";

/** Échap ferme un panneau ouvert (menu latéral sur téléphone…), comme les fenêtres et menus. */
export function useEchap(actif, fermer) {
  const rappel = useRef(fermer);
  useEffect(() => { rappel.current = fermer; });
  useEffect(() => {
    if (!actif) return undefined;
    const touche = (e) => { if (e.key === "Escape") rappel.current(); };
    document.addEventListener("keydown", touche);
    return () => document.removeEventListener("keydown", touche);
  }, [actif]);
}
