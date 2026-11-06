import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import { t } from "../../i18n";

// Fenêtres ouvertes, de la plus ancienne à la plus récente : Échap ne ferme que la
// fenêtre du dessus (avant : deux fenêtres superposées se fermaient ensemble et le
// texte saisi dans la seconde était perdu).
const pile = [];

export default function Modal({ open, onClose, title, children, size = "md" }) {
  const jeton = useRef(Symbol("fenetre"));
  useEffect(() => {
    if (!open) return undefined;
    const id = jeton.current;
    pile.push(id);
    const handler = (e) => {
      if (e.key === "Escape" && pile[pile.length - 1] === id) { e.stopPropagation(); onClose(); }
    };
    document.addEventListener("keydown", handler);
    return () => {
      document.removeEventListener("keydown", handler);
      const i = pile.lastIndexOf(id);
      if (i >= 0) pile.splice(i, 1);
    };
  }, [open, onClose]);

  // Le focus entre dans la fenêtre à l'ouverture et revient au bouton d'origine à la fermeture.
  const fenetre = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const origine = document.activeElement;
    fenetre.current?.focus();
    return () => origine?.focus?.();
  }, [open]);

  const sizes = { sm: "max-w-md", md: "max-w-xl", lg: "max-w-3xl", xl: "max-w-5xl" };

  // Rendue dans <body> : un ancêtre animé ou transformé capturerait sinon le `fixed` et le fond ne couvrirait plus l'écran.
  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-start sm:items-center justify-center p-3 sm:p-4 overflow-y-auto">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="absolute inset-0 bg-sidebar/45 backdrop-blur-[2px]" onClick={onClose} />
          <motion.div initial={{ opacity: 0, scale: 0.95, y: 16 }} animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 8 }} transition={{ type: "spring", stiffness: 420, damping: 32 }}
            ref={fenetre} tabIndex={-1} role="dialog" aria-modal="true" aria-label={typeof title === "string" ? title : undefined}
            className={`relative outline-none bg-white rounded-2xl shadow-fenetre w-full ${sizes[size]} max-h-[92vh] overflow-y-auto z-10`}>
            <div className="flex items-center justify-between gap-3 px-4 py-4 sm:p-6 border-b border-slate-100">
              <h2 className="text-base sm:text-lg font-semibold text-slate-800 min-w-0 break-words">{title}</h2>
              <button type="button" onClick={onClose} aria-label={t("Fermer")} className="p-2 rounded-xl hover:bg-slate-100 transition-colors">
                <X className="w-5 h-5 text-slate-500" />
              </button>
            </div>
            <div className="p-4 sm:p-6">{children}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}