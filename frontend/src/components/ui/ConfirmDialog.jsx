import Modal from "./Modal";
import { AlertTriangle } from "lucide-react";

export default function ConfirmDialog({ open, onClose, onConfirm, title = "Confirmer la suppression", message = "Cette action est irréversible.", loading }) {
  return (
    <Modal open={open} onClose={onClose} title={title} size="sm">
      <div className="flex gap-4 items-start">
        <div className="p-3 rounded-xl bg-danger-50"><AlertTriangle className="w-5 h-5 text-danger" /></div>
        <p className="text-slate-600 text-sm leading-relaxed mt-1">{message}</p>
      </div>
      <div className="flex gap-3 justify-end mt-6">
        <button onClick={onClose} className="btn-secondary">Annuler</button>
        <button onClick={onConfirm} disabled={loading} className="btn-danger">
          {loading ? "Suppression..." : "Supprimer"}
        </button>
      </div>
    </Modal>
  );
}