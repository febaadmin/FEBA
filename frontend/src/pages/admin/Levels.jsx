import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, Layers } from "lucide-react";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { schoolsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import { extractApiError } from "../../utils/errors";
import { t } from "../../i18n";
import AcademyBadge from "../../components/AcademyBadge";
import { useAcademy } from "../../context/AcademyContext";

/* Le cycle décide du barème du bulletin (backend : apps.grades.grading) :
   maternelle et primaire sur 10, collège et lycée sur 20. Le serveur
   refuse un cycle incompatible avec le type de l'académie ; ces listes ne
   servent qu'à ne pas proposer ce qui serait refusé. */
export const CYCLES = [
  ["maternelle", "Maternelle", 10],
  ["primaire", "Primaire", 10],
  ["college", "Collège", 20],
  ["lycee", "Lycée", 20],
];
const ALLOWED_BY_TYPE = {
  online: ["maternelle", "primaire", "college", "lycee"],
  physical_primary: ["maternelle", "primaire"],
  physical_secondary: ["college", "lycee"],
};
const DEFAULT_BY_TYPE = { physical_secondary: "college" };

export default function AdminLevels() {
  const { isAllAcademies, activeAcademy, academyKey } = useAcademy();
  const academyType = activeAcademy?.academy_type || null;
  const allowedCycles = CYCLES.filter(([code]) =>
    (ALLOWED_BY_TYPE[academyType] || CYCLES.map(([c]) => c)).includes(code));
  const defaultCycle = DEFAULT_BY_TYPE[academyType] || "primaire";
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [deleteItem, setDeleteItem] = useState(null);
  const { register, handleSubmit, reset, formState: { errors } } = useForm();

  const { data: levelsData, isLoading } = useQuery({
    queryKey: ["levels", academyKey], queryFn: schoolsAPI.levels,
  });
  const levels = levelsData?.data?.results || levelsData?.data || [];

  const createMut = useMutation({
    mutationFn: schoolsAPI.createLevel,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["levels"] }); toast.success(t("Niveau créé !")); closeModal(); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, data }) => schoolsAPI.updateLevel(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["levels"] }); toast.success(t("Modifié !")); closeModal(); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const deleteMut = useMutation({
    mutationFn: schoolsAPI.deleteLevel,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["levels"] }); toast.success(t("Supprimé.")); setDeleteItem(null); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const closeModal = () => { setModalOpen(false); setEditItem(null); reset(); };
  // L'académie n'est PAS choisie dans le formulaire : c'est l'académie
  // active, imposée par le serveur. L'ancien formulaire présélectionnait
  // « la première école de la liste ».
  const openCreate = () => { reset({ order: levels.length + 1, cycle: defaultCycle }); setModalOpen(true); };
  const openEdit = (l) => { setEditItem(l); reset({ name: l.name, order: l.order, cycle: l.cycle }); setModalOpen(true); };
  const cycleLabel = (code) => {
    const row = CYCLES.find(([c]) => c === code);
    return row ? `${t(row[1])} · /${row[2]}` : code || "-";
  };
  const onSubmit = (d) => {
    if (editItem) updateMut.mutate({ id: editItem.id, data: d });
    else createMut.mutate(d);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Niveaux scolaires")}
        subtitle={t("{n} niveau(x) : CI, CP, CM1, CM2, 6ème…", { n: levels.length })}
        action={
          <button onClick={openCreate} disabled={isAllAcademies}
                  title={isAllAcademies ? t("Sélectionnez une académie pour créer un niveau.") : undefined}
                  className="btn-primary flex items-center gap-2 disabled:opacity-50">
            <Plus className="w-4 h-4" />{t("Nouveau niveau")}</button>
        }
      />

      <div className="card">
        {isLoading ? (
          <div className="py-12 text-center text-slate-400">{t("Chargement…")}</div>
        ) : levels.length === 0 ? (
          <div className="py-16 text-center text-slate-400">
            <Layers className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p className="font-medium">{t("Aucun niveau configuré")}</p>
            <p className="text-sm mt-1">{t("Créez les niveaux CI, CP, CM1, CM2, etc. avant de créer des classes.")}</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100">
                  {/* P2 : en vue consolidée, deux niveaux homonymes de deux
                      académies étaient indiscernables. */}
                  {isAllAcademies && (
                    <th className="text-left py-3 px-4 font-semibold text-slate-500 text-xs uppercase tracking-wider">{t("Académie")}</th>
                  )}
                  <th className="text-left py-3 px-4 font-semibold text-slate-500 text-xs uppercase tracking-wider">{t("Ordre")}</th>
                  <th className="text-left py-3 px-4 font-semibold text-slate-500 text-xs uppercase tracking-wider">{t("Nom du niveau")}</th>
                  <th className="text-left py-3 px-4 font-semibold text-slate-500 text-xs uppercase tracking-wider">{t("Cycle · barème")}</th>
                  <th className="text-left py-3 px-4 font-semibold text-slate-500 text-xs uppercase tracking-wider">{t("École")}</th>
                  <th className="py-3 px-4 w-20" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {[...levels].sort((a,b) => a.order - b.order).map(level => (
                  <tr key={level.id} className="hover:bg-slate-50/50 transition-colors">
                    {isAllAcademies && (
                      <td className="py-3 px-4">
                        <AcademyBadge code={level.academy_code} name={level.academy_name} shortName={level.academy_short_name} />
                      </td>
                    )}
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-primary-50 text-primary font-bold text-xs">
                        {level.order}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-semibold text-slate-800 text-base">{level.name}</span>
                    </td>
                    <td className="py-3 px-4 text-slate-600" data-testid={`level-cycle-${level.id}`}>
                      {cycleLabel(level.cycle)}
                    </td>
                    <td className="py-3 px-4 text-slate-500">{level.school_name || "-"}</td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-1 justify-end">
                        <button onClick={() => openEdit(level)} className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-400 hover:text-primary">
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button onClick={() => setDeleteItem(level)} className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal open={modalOpen} onClose={closeModal} title={editItem ? t("Modifier le niveau") : t("Nouveau niveau")}>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="label">{t("Nom du niveau*")}</label>
            <input {...register("name", { required: true })} placeholder={t("ex: CI, CP, CM1, CM2, 6ème…")} className="input" />
            {errors.name && <p className="text-danger text-xs mt-1">{t("Requis")}</p>}
          </div>
          <div>
            <label className="label">{t("Ordre d'affichage")}</label>
            <input {...register("order", { valueAsNumber: true })} type="number" min="0" className="input" />
          </div>
          <div>
            <label className="label">{t("Cycle scolaire*")}</label>
            <select {...register("cycle", { required: true })} className="input" data-testid="level-cycle">
              {allowedCycles.map(([code, label, scale]) => (
                <option key={code} value={code}>{t(label)} : {t("bulletin sur")} {scale}</option>
              ))}
            </select>
            <p className="text-xs text-slate-500 mt-1">
              {t("Le cycle fixe le barème du bulletin : maternelle et primaire sur 10, collège et lycée sur 20.")}
            </p>
          </div>
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={closeModal} className="btn-secondary">{t("Annuler")}</button>
            <button type="submit" disabled={createMut.isPending || updateMut.isPending} className="btn-primary">
              {(createMut.isPending || updateMut.isPending) ? t("Enregistrement…") : t("Enregistrer")}
            </button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={!!deleteItem}
        onClose={() => setDeleteItem(null)}
        onConfirm={() => deleteMut.mutate(deleteItem?.id)}
        loading={deleteMut.isPending}
        message={`Supprimer le niveau "${deleteItem?.name}" ? Les classes associées seront impactées.`}
      />
    </div>
  );
}
