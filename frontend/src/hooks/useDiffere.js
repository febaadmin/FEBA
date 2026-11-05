import { useEffect, useState } from "react";

/** Valeur recopiée après `delai` ms sans changement (recherche : une requête par pause, pas par caractère). */
export function useDiffere(valeur, delai = 350) {
  const [differee, setDifferee] = useState(valeur);
  useEffect(() => {
    const minuteur = setTimeout(() => setDifferee(valeur), delai);
    return () => clearTimeout(minuteur);
  }, [valeur, delai]);
  return differee;
}
