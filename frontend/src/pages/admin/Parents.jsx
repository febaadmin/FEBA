/**
 * AdminParents — v26 CORRIGÉ
 *
 * CORRECTIONS :
 *  1. CRITIQUE: `bulkDeleteMut` déplacé dans AdminParents (était dans MultiStudentSelect
 *     sans `qc` en scope → ReferenceError → page blanche)
 *  2. Dynamic import remplacé par import statique pour schoolsAPI
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2 } from "lucide-react";
import { useForm, Controller } from "react-hook-form";
import toast from "react-hot-toast";
import { parentsAPI, authAPI, studentsAPI, schoolsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import SearchableSelect from "../../components/ui/SearchableSelect";
import { extractApiError } from "../../utils/errors";
import { t } from "../../i18n";

/* ── MultiStudentSelect sans mutation (ne référence plus qc) ─────────────── */
function MultiStudentSelect({ options, value = [], onChange, placeholder }) {
  const selectedSet = new Set((value || []).map(Number));
  const remaining   = options.filter(o => !selectedSet.has(Number(o.value)));
  const selected    = options.filter(o =>  selectedSet.has(Number(o.value)));
  const add    = (v) => { if (v != null) onChange([...(value || []), Number(v)]); };
  const remove = (v) => onChange((value || []).filter(x => Number(x) !== Number(v)));
  return (
    <div className="space-y-2">
      <SearchableSelect options={remaining} value={null} onChange={add} placeholder={placeholder} />
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selected.map(o => (
            <span key={o.value} className="inline-flex items-center gap-1 bg-primary-50 text-primary text-xs font-medium px-2.5 py-1 rounded-full">
              {o.label}
              <button type="button" onClick={() => remove(o.value)} className="text-primary/60 hover:text-primary font-bold">×</button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AdminParents() {
  const qc = useQueryClient();
  const [modalOpen,       setModalOpen]       = useState(false);
  const [editItem,        setEditItem]        = useState(null);
  const [deleteItem,      setDeleteItem]      = useState(null);
  const [selectedParent,  setSelectedParent]  = useState(null);
  const [filterYear,      setFilterYear]      = useState("");
  const { register, handleSubmit, reset, control } = useForm();

  /* FIX: import statique schoolsAPI (plus de dynamic import) */
  const { data: yearsData } = useQuery({ queryKey: ["years"], queryFn: () => schoolsAPI.years() });
  const years       = yearsData?.data?.results || yearsData?.data || [];
  const currentYear = years.find(y => y.is_current);
  const activeYearId = filterYear || currentYear?.id || "";

  const { data, isLoading } = useQuery({
    queryKey: ["parents", activeYearId],
    queryFn:  () => parentsAPI.list(activeYearId ? { school_year: activeYearId } : {}),
  });
  const { data: usersData } = useQuery({
    queryKey: ["parent-users"],
    queryFn:  () => authAPI.listUsers({ role: "parent" }),
  });
  const { data: studData } = useQuery({
    queryKey: ["students-active-year", currentYear?.id],
    queryFn:  () => studentsAPI.list(currentYear ? { school_year: currentYear.id } : {}),
  });

  const parents     = data?.data?.results     || data?.data     || [];
  const parentUsers = usersData?.data?.results || usersData?.data || [];
  const allStudents = studData?.data?.results  || studData?.data  || [];

  const userOptions    = parentUsers.filter(u => u.id).map(u => ({
    value: u.id,
    label: `${u.first_name} ${u.last_name} (${u.email})`,
  }));
  const studentOptions = allStudents.map(s => ({
    value: s.id,
    label: `${s.full_name} — ${s.class_name || "?"}`,
  }));

  /* ── Mutations ─────────────────────────────────────────────────────────── */
  const createMut = useMutation({
    mutationFn: async (d) => {
      const { student_ids, user_id, ...rest } = d;
      if (student_ids?.length > 0) {
        for (const sid of student_ids) {
          const check = await parentsAPI.checkChildAssignment(sid);
          if (check.data.assigned) {
            throw Object.assign(
              new Error(check.data.message || `Élève #${sid} est déjà associé à un autre parent.`),
              { isPreValidation: true }
            );
          }
        }
      }
      const res      = await parentsAPI.create({ user: user_id, ...rest });
      const parentId = res.data?.id;
      if (parentId && student_ids?.length > 0) {
        for (const sid of student_ids) {
          try {
            await parentsAPI.linkStudent(parentId, sid);
          } catch (e) {
            toast.error(extractApiError(e));
          }
        }
      }
      return res;
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["parents"] }); toast.success(t("Parent créé !")); closeModal(); },
    onError:   (e) => toast.error(e.message || e.response?.data?.detail || "Erreur création.", { duration: 6000 }),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => parentsAPI.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["parents"] }); toast.success(t("Modifié !")); closeModal(); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const deleteMut = useMutation({
    mutationFn: parentsAPI.delete,
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ["parents"] }); toast.success(r.data?.detail || "Parent désactivé — historique conservé."); setDeleteItem(null); setSelectedParent(null); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  /* FIX: bulkDeleteMut CORRECT dans AdminParents (non dans MultiStudentSelect) */
  const bulkDeleteMut = useMutation({
    mutationFn: (ids) => parentsAPI.bulkDelete(ids),
    onSuccess: (data) => { qc.invalidateQueries({ queryKey: ["parents"] }); toast.success(data?.data?.detail || `${data?.data?.deleted || ""} parent(s) désactivé(s).`); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  /* ── Helpers ───────────────────────────────────────────────────────────── */
  const closeModal = () => { setModalOpen(false); setEditItem(null); reset(); };
  const openCreate = () => { reset({ student_ids: [] }); setModalOpen(true); };
  const openEdit   = (p) => {
    setEditItem(p);
    reset({ profession: p.profession, address: p.address, student_ids: (p.children_links || []).map(l => l.student) });
    setModalOpen(true);
  };
  const onSubmit = (d) => {
    if (editItem) updateMut.mutate({ id: editItem.id, data: { profession: d.profession, address: d.address } });
    else          createMut.mutate(d);
  };

  const cols = [
    { key: "name",       label: t("Nom"),       render: r => `${r.user_first_name || ""} ${r.user_last_name || ""}`.trim() || r.full_name || "—" },
    { key: "email",      label: t("Email"),     render: r => r.user_email || "—" },
    { key: "profession", label: t("Profession"), accessor: "profession" },
    { key: "children",   label: t("Enfants"),   render: r => `${r.children_count ?? 0} enfant(s)` },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title={t("Parents")} subtitle={t("{n} parent(s)", { n: parents.length })}
        action={<button onClick={openCreate} className="btn-primary flex items-center gap-2"><Plus className="w-4 h-4" />{t("Ajouter")}</button>} />

      {/* Filtre année */}
      {years.length > 0 && (
        <div className="card flex gap-3 items-center flex-wrap">
          <span className="text-sm font-medium text-slate-600">{t("Année :")}</span>
          <button onClick={() => setFilterYear("")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${!filterYear ? "bg-primary text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>{t("Toutes")}</button>
          {years.map(y => (
            <button key={y.id} onClick={() => setFilterYear(String(y.id))}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${filterYear === String(y.id) ? "bg-primary text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
              {y.name}{y.is_current ? " ★" : ""}
            </button>
          ))}
        </div>
      )}

      <div className="card">
        {/* FIX v36 : état vide contextuel — un parent apparaît dans une année
            dès qu'un de ses enfants y est inscrit. */}
        <DataTable
          emptyMessage={filterYear && filterYear !== "all"
            ? `Aucun parent pour ${years.find(y => String(y.id) === String(filterYear))?.name || "cette année"}.\nUn parent apparaît ici dès qu'un de ses enfants est inscrit dans cette année.\nBase vide ? Générez les données de démonstration : make seed`
            : "Aucun parent enregistré.\nBase vide ? Générez les données de démonstration : make seed"}
          columns={cols}
          data={parents}
          loading={isLoading}
          onRowClick={row => setSelectedParent(row)}
          selectable
          onBulkDelete={(ids) => bulkDeleteMut.mutate(ids)}
          bulkDeletePending={bulkDeleteMut.isPending}
          bulkDeleteLabel="Désactiver la sélection"
          bulkConfirmMessage={(n) => `Désactiver ${n} parent(s) ?\n\nAction réversible : leurs liens familiaux et tout l'historique multi-années sont conservés. Aucune donnée n'est détruite.`}
          actions={row => (
            <div className="flex items-center gap-1 justify-end">
              <button onClick={() => openEdit(row)} className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-400 hover:text-primary"><Pencil className="w-4 h-4" /></button>
              <button onClick={() => setDeleteItem(row)} className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger"><Trash2 className="w-4 h-4" /></button>
            </div>
          )}
        />
      </div>

      {/* Modal création/modification */}
      <Modal open={modalOpen} onClose={closeModal} title={editItem ? t("Modifier le parent") : t("Nouveau parent")} size="md">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {!editItem && (
            <div>
              <label className="label">{t("Compte utilisateur (rôle parent) *")}</label>
              <Controller name="user_id" control={control} rules={{ required: !editItem }}
                render={({ field }) => (
                  <SearchableSelect options={userOptions} value={field.value} onChange={field.onChange} placeholder={t("Rechercher un utilisateur parent…")} />
                )} />
            </div>
          )}
          <div><label className="label">{t("Profession")}</label><input {...register("profession")} className="input" /></div>
          <div><label className="label">{t("Adresse")}</label><textarea {...register("address")} className="input" rows={2} /></div>
          {!editItem && (
            <div>
              <label className="label">{t("Élèves associés")}</label>
              <Controller name="student_ids" control={control}
                render={({ field }) => (
                  <MultiStudentSelect options={studentOptions} value={field.value} onChange={field.onChange} placeholder={t("Ajouter un élève…")} />
                )} />
            </div>
          )}
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={closeModal} className="btn-secondary">{t("Annuler")}</button>
            <button type="submit" disabled={createMut.isPending || updateMut.isPending} className="btn-primary">{t("Enregistrer")}</button>
          </div>
        </form>
      </Modal>

      {/* Panel détail parent */}
      {selectedParent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40" onClick={() => setSelectedParent(null)} />
          <div className="relative bg-white rounded-2xl shadow-2xl max-w-lg w-full p-6 space-y-4 max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-slate-800 text-lg">{t("Détail du parent")}</h2>
              <button onClick={() => setSelectedParent(null)} className="text-slate-400 hover:text-slate-600 text-2xl leading-none">×</button>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between py-2 border-b border-slate-50"><span className="text-slate-500">{t("Nom complet")}</span><span className="font-bold text-slate-800">{`${selectedParent.user_first_name || ""} ${selectedParent.user_last_name || ""}`.trim() || "—"}</span></div>
              <div className="flex justify-between py-2 border-b border-slate-50"><span className="text-slate-500">{t("Email")}</span><span>{selectedParent.user_email || "—"}</span></div>
              <div className="flex justify-between py-2 border-b border-slate-50"><span className="text-slate-500">{t("Téléphone")}</span><span>{selectedParent.user_phone || "—"}</span></div>
              <div className="flex justify-between py-2 border-b border-slate-50"><span className="text-slate-500">{t("Profession")}</span><span>{selectedParent.profession || "—"}</span></div>
              <div className="flex justify-between py-2 border-b border-slate-50"><span className="text-slate-500">{t("Adresse")}</span><span>{selectedParent.address || "—"}</span></div>
              <div className="py-2">
                <p className="text-slate-500 font-medium mb-2">{t("Enfants associés")} ({selectedParent.children_count ?? 0})</p>
                {selectedParent.children_links?.length > 0 ? (
                  <div className="space-y-1">
                    {selectedParent.children_links.map(link => (
                      <div key={link.student} className="bg-primary-50 rounded-xl px-3 py-2 flex items-center gap-2">
                        <div className="w-6 h-6 rounded-full bg-primary text-white text-xs flex items-center justify-center font-bold">{link.student_name?.[0] || "?"}</div>
                        <div>
                          <p className="text-xs font-medium text-slate-800">{link.student_name || `Élève #${link.student}`}</p>
                          <p className="text-xs text-slate-400">{link.relation_label || link.relation || "—"}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : <p className="text-slate-400 text-xs">{t("Aucun enfant associé")}</p>}
              </div>
            </div>
            <div className="flex gap-2 pt-2">
              <button onClick={() => { setSelectedParent(null); openEdit(selectedParent); }} className="btn-secondary text-sm flex-1">{t("Modifier")}</button>
              <button onClick={() => setSelectedParent(null)} className="btn-primary text-sm flex-1">{t("Fermer")}</button>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog open={!!deleteItem} onClose={() => setDeleteItem(null)}
        onConfirm={() => deleteMut.mutate(deleteItem?.id)} loading={deleteMut.isPending}
        message={t("Désactiver ce parent ? Ses liens familiaux et son historique multi-années sont conservés (réactivation possible). La suppression définitive n’est possible qu’après retrait de tous ses liens élèves.")} />
    </div>
  );
}
