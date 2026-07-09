/**
 * AdminUsers — v29.2
 *
 * Corrections :
 * - `username` supprimé du payload (auto-généré côté backend)
 * - `onError` exhaustif via extractApiError (plus de messages génériques)
 * - Validation frontend des mots de passe AVANT l'envoi API
 * - Affichage de TOUS les messages d'erreur champ par champ
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, ToggleLeft, ToggleRight, Eye, EyeOff, AlertCircle } from "lucide-react";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { authAPI } from "../../api";
import { extractApiErrors } from "../../utils/errors";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import StatusBadge from "../../components/ui/StatusBadge";
import { resolveMediaUrl } from "../../utils/media";

const ADMIN_ALLOWED_ROLES = [
  { value: "teacher", label: "Enseignant" },
  { value: "parent",  label: "Parent" },
  { value: "student", label: "Élève" },
];

const MIN_PASSWORD_LENGTH = 8;

export default function AdminUsers() {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen]   = useState(false);
  const [editItem,  setEditItem]    = useState(null);
  const [deleteItem,setDeleteItem]  = useState(null);
  const [roleFilter,setRoleFilter]  = useState("");
  const [viewItem,  setViewItem]    = useState(null);
  const [showPwd,   setShowPwd]     = useState(false);
  const [showPwd2,  setShowPwd2]    = useState(false);
  const [apiErrors, setApiErrors]   = useState([]);   // liste d'erreurs backend

  const {
    register,
    handleSubmit,
    watch,
    reset,
    formState: { errors },
  } = useForm({ mode: "onChange" });

  const password = watch("password");

  const { data, isLoading } = useQuery({
    queryKey: ["admin-users", roleFilter],
    queryFn: () => authAPI.listUsers(roleFilter ? { role: roleFilter } : {}),
  });
  const users = data?.data?.results || data?.data || [];

  /* ── Mutations ─────────────────────────────────────────────────────────── */

  const createMut = useMutation({
    mutationFn: (d) => {
      // username retiré : généré côté backend (v29.2)
      const { username: _ignored, ...payload } = d;
      return authAPI.createUser(payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      toast.success("Utilisateur créé avec succès !");
      closeModal();
    },
    onError: (e) => {
      const errs = extractApiErrors(e);
      setApiErrors(errs);
      toast.error(errs[0]);
    },
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => authAPI.updateUser(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      toast.success("Utilisateur modifié !");
      closeModal();
    },
    onError: (e) => {
      const errs = extractApiErrors(e);
      setApiErrors(errs);
      toast.error(errs[0]);
    },
  });

  const deleteMut = useMutation({
    mutationFn: authAPI.deleteUser,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      toast.success("Utilisateur supprimé.");
      setDeleteItem(null);
    },
    onError: (e) => toast.error(extractApiErrors(e)[0]),
  });

  const toggleMut = useMutation({
    mutationFn: authAPI.toggleActive,
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      toast.success(d.data.detail);
    },
    onError: (e) => toast.error(extractApiErrors(e)[0]),
  });

  /* ── Helpers UI ─────────────────────────────────────────────────────────── */

  const closeModal = () => {
    setModalOpen(false);
    setEditItem(null);
    setApiErrors([]);
    reset();
  };

  const openCreate = () => {
    setApiErrors([]);
    reset({ role: "teacher" });
    setModalOpen(true);
  };

  const openEdit = (u) => {
    setEditItem(u);
    setApiErrors([]);
    reset({
      first_name: u.first_name,
      last_name:  u.last_name,
      email:      u.email,
      phone:      u.phone,
      role:       u.role,
    });
    setModalOpen(true);
  };

  const onSubmit = (data) => {
    setApiErrors([]);
    if (editItem) updateMut.mutate({ id: editItem.id, data });
    else createMut.mutate(data);
  };

  const roleLabel = { teacher: "Enseignant", parent: "Parent", student: "Élève" };
  const roleBadge = (role) => {
    const cls = {
      teacher: "bg-emerald-50 text-emerald-700",
      parent:  "bg-amber-50 text-amber-700",
      student: "bg-sky-50 text-sky-700",
    };
    return (
      <span className={`badge ${cls[role] || "bg-slate-100 text-slate-600"}`}>
        {roleLabel[role] || role}
      </span>
    );
  };

  const cols = [
    { key: "name",   label: "Nom",     render: r => `${r.first_name} ${r.last_name}` },
    { key: "email",  label: "Email",   accessor: "email" },
    { key: "role",   label: "Rôle",    render: r => roleBadge(r.role) },
    { key: "status", label: "Statut",  render: r => <StatusBadge status={r.is_active ? "active" : "inactive"} /> },
    { key: "date",   label: "Créé le", render: r => r.created_at?.slice(0, 10) },
  ];

  const isPending = createMut.isPending || updateMut.isPending;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Gestion Utilisateurs"
        subtitle="Enseignants, Parents, Élèves"
        action={
          <button onClick={openCreate} className="btn-primary flex items-center gap-2">
            <Plus className="w-4 h-4" /> Nouvel utilisateur
          </button>
        }
      />

      {/* Filtres de rôle */}
      <div className="flex gap-2 flex-wrap">
        {[{ value: "", label: "Tous" }, ...ADMIN_ALLOWED_ROLES].map(opt => (
          <button
            key={opt.value}
            onClick={() => setRoleFilter(opt.value)}
            className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${
              roleFilter === opt.value
                ? "bg-primary text-white shadow-md"
                : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <div className="card">
        <DataTable
          columns={cols}
          data={users}
          loading={isLoading}
          onRowClick={row => setViewItem(row)}
          actions={(row) => (
            <div className="flex items-center gap-1 justify-end">
              <button
                onClick={() => toggleMut.mutate(row.id)}
                className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400"
                title={row.is_active ? "Désactiver" : "Activer"}
              >
                {row.is_active
                  ? <ToggleRight className="w-4 h-4 text-success" />
                  : <ToggleLeft className="w-4 h-4" />}
              </button>
              <button
                onClick={() => openEdit(row)}
                className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-400 hover:text-primary"
                title="Modifier"
              >
                <Pencil className="w-4 h-4" />
              </button>
              <button
                onClick={() => setDeleteItem(row)}
                className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger"
                title="Supprimer"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          )}
        />
      </div>

      {/* ── Modal création / modification ─────────────────────────────────── */}
      <Modal
        open={modalOpen}
        onClose={closeModal}
        title={editItem ? "Modifier l'utilisateur" : "Nouvel utilisateur"}
        size="md"
      >
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>

          {/* Erreurs backend groupées */}
          {apiErrors.length > 0 && (
            <div className="rounded-xl bg-red-50 border border-red-200 p-3 space-y-1">
              {apiErrors.map((err, i) => (
                <div key={i} className="flex items-start gap-2 text-sm text-red-700">
                  <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                  {err}
                </div>
              ))}
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Prénom *</label>
              <input
                {...register("first_name", { required: "Le prénom est obligatoire." })}
                className={`input ${errors.first_name ? "border-red-400" : ""}`}
                placeholder="Jean"
              />
              {errors.first_name && (
                <p className="mt-1 text-xs text-red-600">{errors.first_name.message}</p>
              )}
            </div>
            <div>
              <label className="label">Nom *</label>
              <input
                {...register("last_name", { required: "Le nom est obligatoire." })}
                className={`input ${errors.last_name ? "border-red-400" : ""}`}
                placeholder="Dupont"
              />
              {errors.last_name && (
                <p className="mt-1 text-xs text-red-600">{errors.last_name.message}</p>
              )}
            </div>
          </div>

          <div>
            <label className="label">Email *</label>
            <input
              {...register("email", {
                required: "L'email est obligatoire.",
                pattern: {
                  value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
                  message: "Format d'email invalide.",
                },
              })}
              type="email"
              className={`input ${errors.email ? "border-red-400" : ""}`}
              placeholder="jean.dupont@feba.bj"
              disabled={!!editItem}
            />
            {errors.email && (
              <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
            )}
          </div>

          <div>
            <label className="label">Téléphone</label>
            <input
              {...register("phone")}
              className="input"
              placeholder="+229 00 00 00 00"
            />
          </div>

          <div>
            <label className="label">Rôle *</label>
            <select
              {...register("role", { required: "Le rôle est obligatoire." })}
              className={`input ${errors.role ? "border-red-400" : ""}`}
            >
              {ADMIN_ALLOWED_ROLES.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            {errors.role && (
              <p className="mt-1 text-xs text-red-600">{errors.role.message}</p>
            )}
          </div>

          {/* Champs mot de passe — uniquement à la création */}
          {!editItem && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Mot de passe *</label>
                <div className="relative">
                  <input
                    {...register("password", {
                      required: "Le mot de passe est obligatoire.",
                      minLength: {
                        value: MIN_PASSWORD_LENGTH,
                        message: `Minimum ${MIN_PASSWORD_LENGTH} caractères.`,
                      },
                    })}
                    type={showPwd ? "text" : "password"}
                    className={`input pr-10 ${errors.password ? "border-red-400" : ""}`}
                    placeholder="••••••••"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPwd(v => !v)}
                    className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600"
                    tabIndex={-1}
                  >
                    {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {errors.password && (
                  <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>
                )}
              </div>

              <div>
                <label className="label">Confirmer *</label>
                <div className="relative">
                  <input
                    {...register("password2", {
                      required: "La confirmation est obligatoire.",
                      validate: (val) =>
                        val === password || "Les mots de passe ne correspondent pas.",
                    })}
                    type={showPwd2 ? "text" : "password"}
                    className={`input pr-10 ${errors.password2 ? "border-red-400" : ""}`}
                    placeholder="••••••••"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPwd2(v => !v)}
                    className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600"
                    tabIndex={-1}
                  >
                    {showPwd2 ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                {errors.password2 && (
                  <p className="mt-1 text-xs text-red-600">{errors.password2.message}</p>
                )}
              </div>
            </div>
          )}

          <div className="flex gap-3 justify-end pt-2 border-t border-slate-100">
            <button type="button" onClick={closeModal} className="btn-secondary">
              Annuler
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="btn-primary min-w-[120px]"
            >
              {isPending ? "Enregistrement..." : "Enregistrer"}
            </button>
          </div>
        </form>
      </Modal>

      {/* ── Confirmation suppression ────────────────────────────────────── */}
      {deleteItem && (
        <ConfirmDialog
          open
          title="Supprimer l'utilisateur"
          message={`Supprimer définitivement ${deleteItem.first_name} ${deleteItem.last_name} (${deleteItem.email}) ?`}
          onConfirm={() => deleteMut.mutate(deleteItem.id)}
          onCancel={() => setDeleteItem(null)}
          loading={deleteMut.isPending}
          danger
        />
      )}

      {/* ── Vue détail ───────────────────────────────────────────────────── */}
      {viewItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40" onClick={() => setViewItem(null)} />
          <div className="relative bg-white rounded-2xl shadow-2xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-slate-800 text-lg">Détail utilisateur</h2>
              <button onClick={() => setViewItem(null)} className="text-slate-400 hover:text-slate-600 text-2xl leading-none">×</button>
            </div>
            <div className="flex items-center gap-4">
              {viewItem.avatar
                ? <img src={resolveMediaUrl(viewItem.avatar)} className="w-16 h-16 rounded-xl object-cover" alt="" />
                : (
                  <div className="w-16 h-16 rounded-xl bg-primary-50 flex items-center justify-center text-primary text-xl font-bold">
                    {viewItem.first_name?.[0]}{viewItem.last_name?.[0]}
                  </div>
                )}
              <div>
                <p className="font-semibold text-slate-800">{viewItem.first_name} {viewItem.last_name}</p>
                <p className="text-sm text-slate-500">{viewItem.email}</p>
                {viewItem.phone && <p className="text-sm text-slate-400">{viewItem.phone}</p>}
              </div>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-500">Rôle</span>
                {roleBadge(viewItem.role)}
              </div>
              <div className="flex justify-between py-1 border-b border-slate-50">
                <span className="text-slate-500">Statut</span>
                <StatusBadge status={viewItem.is_active ? "active" : "inactive"} />
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-500">Créé le</span>
                <span className="text-slate-700">{viewItem.created_at?.slice(0, 10)}</span>
              </div>
            </div>
            <div className="flex gap-2 pt-2">
              <button onClick={() => { setViewItem(null); openEdit(viewItem); }} className="btn-secondary flex-1">
                Modifier
              </button>
              <button onClick={() => setViewItem(null)} className="btn-primary flex-1">
                Fermer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
