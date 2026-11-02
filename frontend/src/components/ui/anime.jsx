/**
 * Briques animées communes. MotionConfig (App) coupe les mouvements si le système
 * demande moins d'animations ; les valeurs affichées restent toujours exactes.
 */
import { useEffect, useRef, useState } from "react";
import { animate, motion, useReducedMotion } from "framer-motion";

export function CompteurAnime({ valeur, suffixe = "", decimales = 0 }) {
  const reduit = useReducedMotion();
  const [affiche, setAffiche] = useState(reduit ? valeur : 0);
  const precedent = useRef(0);
  useEffect(() => {
    if (reduit) { setAffiche(valeur); return undefined; }
    const controle = animate(precedent.current, valeur, { duration: 0.8, ease: "easeOut", onUpdate: setAffiche });
    precedent.current = valeur;
    return () => controle.stop();
  }, [valeur, reduit]);
  return <span>{Number(affiche).toFixed(decimales)}{suffixe}</span>;
}

export function AnneauProgression({ valeur, taille = 96, epaisseur = 9, couleur = "#2563eb", children }) {
  const r = (taille - epaisseur) / 2;
  const c = 2 * Math.PI * r;
  const part = Math.min(Math.max(valeur, 0), 100) / 100;
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: taille, height: taille }}>
      <svg width={taille} height={taille} aria-hidden="true" className="-rotate-90">
        <circle cx={taille / 2} cy={taille / 2} r={r} fill="none" stroke="#e2e8f0" strokeWidth={epaisseur} />
        <motion.circle cx={taille / 2} cy={taille / 2} r={r} fill="none" stroke={couleur} strokeWidth={epaisseur} strokeLinecap="round"
          strokeDasharray={c} initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - part) }} transition={{ duration: 0.9, ease: "easeOut" }} />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center text-center">{children}</div>
    </div>
  );
}

export function Squelette({ lignes = 3 }) {
  return (
    <div className="space-y-3 animate-attente motion-reduce:animate-none" aria-hidden="true">
      {Array.from({ length: lignes }, (_, i) => <div key={i} className="h-16 rounded-xl bg-slate-100" />)}
    </div>
  );
}

export const apparition = { hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0 } };
export const cascade = { show: { transition: { staggerChildren: 0.05 } } };

export function CarteAnimee({ className = "", children, ...props }) {
  return (
    <motion.div variants={apparition} whileHover={{ y: -2 }} transition={{ type: "spring", stiffness: 300, damping: 26 }}
      className={`rounded-2xl border border-slate-200 bg-white shadow-sm hover:shadow-md transition-shadow ${className}`} {...props}>
      {children}
    </motion.div>
  );
}
