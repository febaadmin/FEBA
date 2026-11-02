import { useEffect } from "react";

const CONTROLES = "input:not([type=hidden]),select,textarea";
let suivant = 0;

/** Relie un libellé au champ unique de son bloc, pour le lecteur d'écran et le clic sur le libellé. */
export function lierLibelles(racine) {
  racine.querySelectorAll("label:not([for])").forEach((libelle) => {
    if (libelle.querySelector(CONTROLES) || !libelle.parentElement) return;
    const champs = libelle.parentElement.querySelectorAll(CONTROLES);
    if (champs.length !== 1) return;
    const champ = champs[0];
    if (!champ.id) { suivant += 1; champ.id = `champ-${suivant}`; }
    libelle.htmlFor = champ.id;
  });
}

/** Les formulaires de l'application écrivent `<label>` puis le champ : la liaison se fait ici, une seule fois. */
export function useLabelLinker() {
  useEffect(() => {
    let attente = null;
    const lancer = () => {
      if (attente) return;
      attente = requestAnimationFrame(() => { attente = null; lierLibelles(document.body); });
    };
    const observateur = new MutationObserver(lancer);
    observateur.observe(document.body, { childList: true, subtree: true });
    lancer();
    return () => { observateur.disconnect(); if (attente) cancelAnimationFrame(attente); };
  }, []);
}
