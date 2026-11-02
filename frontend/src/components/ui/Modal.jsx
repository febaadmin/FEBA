import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import { t } from "../../i18n";

export default function Modal({ open, onClose, title, children, size = "md" }) {
  useEffect(() => {
    if (!open) return undefined;
    const handler = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
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
            className={`relative outline-none bg-white rounded-2xl shadow-fenetre w-full ${sizes[size]} max-h-[92vh] overflow-y-auto z-10 mx-4 md:mx-0`}>
            <div className="flex items-center justify-between p-6 border-b border-slate-100">
              <h2 className="text-lg font-semibold text-slate-800">{title}</h2>
              <button type="button" onClick={onClose} aria-label={t("Fermer")} className="p-2 rounded-xl hover:bg-slate-100 transition-colors">
                <X className="w-5 h-5 text-slate-500" />
              </button>
            </div>
            <div className="p-6">{children}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}