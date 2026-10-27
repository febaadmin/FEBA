import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Upload, CheckCircle, Image, Trash2, RefreshCw, Eye } from "lucide-react";
import toast from "react-hot-toast";
import { schoolsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import Modal from "../../components/ui/Modal";
import { useAcademy } from "../../context/AcademyContext";
import AcademyLogo from "../../components/AcademyLogo";
import { extractApiError } from "../../utils/errors";
import { resolveMediaUrl } from "../../utils/media";
import { t } from "../../i18n";

export default function AdminBranding() {
  const qc = useQueryClient();
  const [previewUrl, setPreviewUrl] = useState(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [label, setLabel] = useState("");
  const fileRef = useRef();

  // L'académie est celle du CONTEXTE (sélecteur d'académie), jamais « la
  // première de la liste » ni l'identifiant 1 : c'est ce repli qui pouvait
  // poser le logo d'une académie chez une autre.
  const { activeAcademy, isAllAcademies } = useAcademy();
  const academyId = activeAcademy?.id || null;

  const { data: brandsData, isLoading, refetch } = useQuery({
    queryKey: ["branding", academyId],
    queryFn: () => schoolsAPI.listBranding(),
    enabled: Boolean(academyId),
  });

  const { data: activeData } = useQuery({
    queryKey: ["branding-active", academyId],
    queryFn: () => schoolsAPI.activeBranding(),
    enabled: Boolean(academyId),
  });

  const brands = brandsData?.data?.results || brandsData?.data || [];
  const active = activeData?.data;

  const uploadMut = useMutation({
    mutationFn: (formData) => schoolsAPI.uploadBranding(formData),
    onSuccess: () => {
      toast.success(t("Logo uploadé et activé avec succès ! Propagé dans toute l'application."));
      qc.invalidateQueries({ queryKey: ["branding"] });
      qc.invalidateQueries({ queryKey: ["branding-active"] });
      // Logo et favicons de TOUTES les pages ouvertes (useBranding).
      qc.invalidateQueries({ queryKey: ["branding-public"] });
      setUploadOpen(false);
      setSelectedFile(null);
      setLabel("");
      setPreviewUrl(null);
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const activateMut = useMutation({
    mutationFn: (id) => schoolsAPI.activateBranding(id),
    onSuccess: () => {
      toast.success(t("Logo activé avec succès !"));
      qc.invalidateQueries({ queryKey: ["branding"] });
      qc.invalidateQueries({ queryKey: ["branding-active"] });
      // Logo et favicons de TOUTES les pages ouvertes (useBranding).
      qc.invalidateQueries({ queryKey: ["branding-public"] });
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const deleteMut = useMutation({
    mutationFn: (id) => schoolsAPI.deleteBranding(id),
    onSuccess: () => {
      toast.success(t("Version supprimée."));
      qc.invalidateQueries({ queryKey: ["branding"] });
      qc.invalidateQueries({ queryKey: ["branding-active"] });
      // Logo et favicons de TOUTES les pages ouvertes (useBranding).
      qc.invalidateQueries({ queryKey: ["branding-public"] });
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    // Contrôle indicatif ; le serveur décode l'image et fait foi.
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) {
      toast.error(t("Format refusé : PNG, JPEG ou WebP uniquement."));
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      toast.error(t("Fichier trop volumineux (5 Mo au maximum)."));
      return;
    }
    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
  };

  const handleUpload = () => {
    if (!selectedFile) { toast.error(t("Veuillez sélectionner un fichier")); return; }
    const fd = new FormData();
    fd.append("logo", selectedFile);
    fd.append("label", label || `Logo ${new Date().toLocaleDateString()}`);
    fd.append("activate", "true");
    fd.append("school", String(academyId));
    uploadMut.mutate(fd);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Gestion du Branding & Logo")}
        subtitle={isAllAcademies || !activeAcademy?.name
          ? t("Gestion centralisée du logo officiel de chaque académie — propagé automatiquement dans toute l'application")
          : t("Gestion centralisée du logo officiel de {nom} — propagé automatiquement dans toute l'application", { nom: activeAcademy.name })}
        action={
          <button onClick={() => setUploadOpen(true)} disabled={!academyId}
            className="btn-primary flex items-center gap-2">
            <Upload className="w-4 h-4" />{t("Uploader un nouveau logo")}</button>
        }
      />

      {isAllAcademies && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800" role="alert">
          {t("Sélectionnez d'abord l'académie dont vous gérez le logo (sélecteur d'académie en haut de page).")}
        </div>
      )}
      {activeAcademy && (
        <p className="text-sm text-slate-600">{t("Académie")} : <strong>{activeAcademy.name}</strong></p>
      )}

      {/* Active Logo Banner */}
      <div className="bg-gradient-to-r from-blue-900 to-blue-800 rounded-xl p-6 text-white flex items-center gap-6">
        <div className="w-24 h-24 rounded-xl overflow-hidden bg-white border-4 border-yellow-400 shadow-xl flex-shrink-0">
          {active?.logo_url ? (
            <img src={resolveMediaUrl(active.logo_url)} alt={t("Logo actif")} className="w-full h-full object-contain" />
          ) : (
            // Logo de repli de l'académie, ou son monogramme si elle n'en a
            // aucun (académie nouvellement créée) : jamais une image cassée.
            <AcademyLogo />
          )}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle className="w-5 h-5 text-green-400" />
            <span className="font-bold text-lg">{t("Logo actuellement actif")}</span>
          </div>
          <p className="text-blue-200 text-sm">{active?.label || t("Logo officiel par défaut")}</p>
          <p className="text-blue-300 text-xs mt-1">{t("Affiché sur : Page de connexion • Tableaux de bord • Bulletins PDF • Tous les documents")}</p>
        </div>
        <div className="text-right text-xs text-blue-300">
          <p>{t("Propagation automatique")}</p>
          <p className="text-green-400 font-medium mt-1">✓ Active partout</p>
        </div>
      </div>

      {/* Propagation Info */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: t("Page de connexion"), icon: "🔐", status: "✓ Actif" },
          { label: t("Tableaux de bord"), icon: "📊", status: "✓ Actif" },
          { label: t("Bulletins PDF"), icon: "📄", status: "✓ Actif" },
          { label: t("Documents exports"), icon: "📤", status: "✓ Actif" },
        ].map((item) => (
          <div key={item.label} className="bg-white rounded-xl border border-gray-200 p-4 text-center">
            <div className="text-2xl mb-2">{item.icon}</div>
            <div className="text-sm font-medium text-gray-700">{item.label}</div>
            <div className="text-xs text-green-600 font-medium mt-1">{item.status}</div>
          </div>
        ))}
      </div>

      {/* Version History */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Image className="w-5 h-5 text-blue-600" />
            <h3 className="font-semibold text-gray-800">{t("Historique des versions")}</h3>
            <span className="bg-blue-100 text-blue-700 text-xs font-medium px-2 py-0.5 rounded-full">
              {brands.length} version(s)
            </span>
          </div>
          <button onClick={() => refetch()} className="btn-secondary flex items-center gap-1 text-sm">
            <RefreshCw className="w-3.5 h-3.5" />{t("Rafraîchir")}</button>
        </div>

        {isLoading ? (
          <div className="p-8 text-center text-gray-400">{t("Chargement…")}</div>
        ) : brands.length === 0 ? (
          <div className="p-8 text-center">
            <Image className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 text-sm">{t("Aucune version uploadée.")}</p>
            <p className="text-gray-400 text-xs mt-1">{t("Le logo par défaut de l'académie est utilisé.")}</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {brands.map((brand) => (
              <div key={brand.id} className="p-4 flex items-center gap-4">
                <div className="w-16 h-16 rounded-lg overflow-hidden bg-gray-100 border flex-shrink-0">
                  {brand.logo_url ? (
                    <img src={resolveMediaUrl(brand.logo_url)} alt={brand.label} className="w-full h-full object-contain" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-gray-400">
                      <Image className="w-6 h-6" />
                    </div>
                  )}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-800">{brand.label || "Logo sans titre"}</span>
                    {brand.is_active && (
                      <span className="inline-flex items-center gap-1 bg-green-100 text-green-700 text-xs font-medium px-2 py-0.5 rounded-full">
                        <CheckCircle className="w-3 h-3" />{t("Actif")}</span>
                    )}
                  </div>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Uploadé le {new Date(brand.uploaded_at).toLocaleDateString('fr-FR', {
                      day: '2-digit', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit'
                    })}
                    {brand.uploaded_by_name && ` par ${brand.uploaded_by_name}`}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  {brand.logo_url && (
                    <a href={brand.logo_url} target="_blank" rel="noopener noreferrer"
                      className="p-2 text-blue-500 hover:text-blue-700 hover:bg-blue-50 rounded-lg transition">
                      <Eye className="w-4 h-4" />
                    </a>
                  )}
                  {!brand.is_active && (
                    <button
                      onClick={() => activateMut.mutate(brand.id)}
                      disabled={activateMut.isPending}
                      className="text-xs btn-secondary px-3 py-1.5 flex items-center gap-1">
                      <CheckCircle className="w-3 h-3" />{t("Activer")}</button>
                  )}
                  {!brand.is_active && (
                    <button
                      onClick={() => {
                        if (window.confirm("Supprimer cette version ?")) deleteMut.mutate(brand.id);
                      }}
                      className="p-2 text-red-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Upload Modal */}
      <Modal open={uploadOpen} onClose={() => setUploadOpen(false)} title={t("Uploader un nouveau logo")} size="md">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t("Libellé de la version")}</label>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder={t("Ex: Logo officiel 2024-2025")}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">{t("Fichier logo")}</label>
            <div
              onClick={() => fileRef.current?.click()}
              className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition">
              {previewUrl ? (
                <div className="flex flex-col items-center gap-3">
                  <img src={previewUrl} alt={t("Aperçu")} className="max-h-32 max-w-full object-contain rounded-lg shadow" />
                  <p className="text-sm text-gray-600">{selectedFile?.name}</p>
                  <p className="text-xs text-gray-400">{t("Cliquer pour changer")}</p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2">
                  <Upload className="w-8 h-8 text-gray-400" />
                  <p className="text-gray-600 text-sm font-medium">{t("Cliquer pour sélectionner")}</p>
                  <p className="text-gray-400 text-xs">{t("PNG, JPG, SVG — Max 5MB")}</p>
                </div>
              )}
            </div>
            <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={handleFileChange} />
          </div>

          <div className="bg-blue-50 rounded-lg p-3 text-xs text-blue-700">
            <strong>{t("Propagation automatique :")}</strong> {t("Le nouveau logo sera immédiatement visible sur la page de connexion, les tableaux de bord, et tous les bulletins PDF générés après cet upload.")}</div>

          <div className="flex gap-3 pt-2">
            <button onClick={() => setUploadOpen(false)} className="btn-secondary flex-1">{t("Annuler")}</button>
            <button onClick={handleUpload} disabled={!selectedFile || !academyId || uploadMut.isPending}
              className="btn-primary flex-1 flex items-center justify-center gap-2">
              {uploadMut.isPending ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
              {uploadMut.isPending ? t("Upload en cours…") : t("Uploader & Activer")}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
