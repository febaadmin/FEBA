import { extractApiError } from "../../utils/errors";
/**
 * AvatarUpload — reusable avatar upload/delete widget
 * Props: user (object with first_name, last_name, avatar)
 *        onUpdate (fn called with updated user data)
 */
import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Camera, Trash2, User } from "lucide-react";
import { avatarAPI, authAPI } from "../../api";
import { resolveMediaUrl } from "../../utils/media";
import toast from "react-hot-toast";
import { t } from "../../i18n";

export default function AvatarUpload({ user, onUpdate, size = "lg" }) {
  const qc = useQueryClient();
  const fileRef = useRef();
  const [hover, setHover] = useState(false);

  const dims = size === "lg" ? "w-24 h-24" : "w-16 h-16";
  const iconSize = size === "lg" ? "w-10 h-10" : "w-7 h-7";
  const textSize = size === "lg" ? "text-2xl" : "text-base";

  const uploadMut = useMutation({
    mutationFn: (file) => avatarAPI.upload(file),
    onSuccess: (res) => {
      toast.success(t("Photo mise à jour !"));
      qc.invalidateQueries({ queryKey: ["me"] });
      onUpdate?.(res.data);
    },
    onError: () => toast.error(t("Erreur lors de l'upload")),
  });

  const deleteMut = useMutation({
    mutationFn: avatarAPI.delete,
    onSuccess: (res) => {
      toast.success(t("Photo supprimée"));
      qc.invalidateQueries({ queryKey: ["me"] });
      onUpdate?.(res.data);
    },
    onError: (e) => toast.error(extractApiError(e, "Erreur lors de la suppression de la photo.")),
  });

  const handleFile = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { toast.error(t("Fichier trop grand (max 5 MB)")); return; }
    uploadMut.mutate(file);
    e.target.value = "";
  };

  const initials = `${user?.first_name?.[0] || ""}${user?.last_name?.[0] || ""}`.toUpperCase() || "?";

  return (
    <div className="flex flex-col items-center gap-3">
      <div
        className={`relative ${dims} rounded-full overflow-hidden cursor-pointer group`}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        onClick={() => fileRef.current?.click()}
      >
        {user?.avatar ? (
          <img src={resolveMediaUrl(user.avatar)} alt="avatar" className="w-full h-full object-cover" onError={(e) => { e.currentTarget.style.display = "none"; }} />
        ) : (
          <div className={`w-full h-full flex items-center justify-center bg-gradient-to-br from-primary to-violet-600 text-white font-bold ${textSize}`}>
            {initials}
          </div>
        )}
        {/* Overlay on hover */}
        <div className={`absolute inset-0 bg-black/50 flex items-center justify-center transition-opacity ${hover ? "opacity-100" : "opacity-0"}`}>
          <Camera className="w-6 h-6 text-white" />
        </div>
        {(uploadMut.isPending || deleteMut.isPending) && (
          <div className="absolute inset-0 bg-white/70 flex items-center justify-center">
            <div className="w-5 h-5 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
          </div>
        )}
      </div>
      <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleFile} />
      <div className="flex gap-2">
        <button
          onClick={() => fileRef.current?.click()}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-primary text-white rounded-xl hover:bg-primary/90 transition-colors"
        >
          <Camera className="w-3.5 h-3.5" />
          {user?.avatar ? t("Changer") : t("Ajouter une photo")}
        </button>
        {user?.avatar && (
          <button
            onClick={() => deleteMut.mutate()}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-danger/10 text-danger rounded-xl hover:bg-danger/20 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />{t("Supprimer")}</button>
        )}
      </div>
    </div>
  );
}
