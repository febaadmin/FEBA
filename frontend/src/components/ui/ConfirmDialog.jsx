import Modal from "./Modal";
import { AlertTriangle } from "lucide-react";
import { t } from "../../i18n";

export default function ConfirmDialog({ open, onClose, onConfirm, title = "Confirmer la suppression", message = "Cette action est irréversible.", loading }) {
  return (
    <Modal open={open} onClose={onClose} title={t(title)} size="sm">
      <div className="flex gap-4 items-start">
        <div className="p-3 rounded-xl bg-danger-50"><AlertTriangle className="w-5 h-5 text-danger" /></div>
        <p className="text-slate-600 text-sm leading-relaxed mt-1">{t(message)}</p>
      </div>
      <div className="flex gap-3 justify-end mt-6">
        <button onClick={onClose} className="btn-secondary">{t("Annuler")}</button>
        <button onClick={onConfirm} disabled={loading} className="btn-danger">
          {loading ? t("Suppression...") : t("Supprimer")}
        </button>
      </div>
    </Modal>
  );
}