import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, Users, BookOpen, Globe, CheckCircle, AlertCircle, Copy } from "lucide-react";
import { useForm, Controller } from "react-hook-form";
import toast from "react-hot-toast";
import { classesAPI, schoolsAPI, subjectsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import Modal from "../../components/ui/Modal";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import SearchableSelect from "../../components/ui/SearchableSelect";
import { extractApiError } from "../../utils/errors";
import { t } from "../../i18n";
import { useSchoolYearScope } from "../../hooks/useSchoolYearScope";

export default function AdminClasses() {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [subjectModal, setSubjectModal] = useState(null); // class object
  const [editItem, setEditItem] = useState(null);
  const [deleteItem, setDeleteItem] = useState(null);
  const [selectedSubjects, setSelectedSubjects] = useState([]);
  const { register, handleSubmit, reset, control } = useForm();

  // FIX v34/v39 : la page gère les classes PAR ANNÉE (espace de travail isolé).
  // yearFilter "" = suivre l'année active ; on RÉSOUT toujours vers un id
  // concret (effectiveYearId) pour que la puce surlignée et le tableau
  // affichent EXACTEMENT la même année (bug vidéo : puce 2026-2027 active,
  // contenu 2023-2024).
  const [yearFilter, setYearFilter] = useState("");
  const { data: levelsData } = useQuery({ queryKey: ["levels"], queryFn: schoolsAPI.levels });
  const { data: yearsData } = useQuery({ queryKey: ["years"], queryFn: schoolsAPI.years });
  const _years = yearsData?.data?.results || yearsData?.data || [];
  // P2 : en mode « Toutes les Académies », aucune année ne peut
  // représenter les deux académies — voir useSchoolYearScope.
  const { currentYear: activeYear, yearLabel } = useSchoolYearScope(_years);
  const effectiveYearId = yearFilter || activeYear?.id || "";
  const { data, isLoading } = useQuery({
    queryKey: ["classes", effectiveYearId],
    queryFn: () => classesAPI.list(effectiveYearId ? { school_year: effectiveYearId } : { all_years: "1" }),
    enabled: _years.length > 0 || yearFilter === "",
  });
  const { data: subjectsData } = useQuery({ queryKey: ["subjects"], queryFn: () => subjectsAPI.list() });

  const classes = data?.data?.results || data?.data || [];
  const levels = levelsData?.data?.results || levelsData?.data || [];
  const years = _years;                       // alias (déjà dérivé plus haut)
  const activeYearId = activeYear?.id;         // année active résolue une seule fois
  const allSubjects = subjectsData?.data?.results || subjectsData?.data || [];
  const frSubjects = allSubjects.filter(s => s.language === "fr");
  const enSubjects = allSubjects.filter(s => s.language === "en");

  const createMut = useMutation({
    mutationFn: classesAPI.create,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["classes"] }); toast.success(t("Classe créée !")); closeModal(); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const updateMut = useMutation({
    mutationFn: ({ id, data }) => classesAPI.update(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["classes"] }); toast.success(t("Classe modifiée !")); closeModal(); },
    onError: (e) => {
      const status = e?.response?.status;
      if (status === 404) toast.error(t("Cette classe n'existe plus (liste actualisée)."));
      else toast.error(extractApiError(e));
      qc.invalidateQueries({ queryKey: ["classes"] });
      closeModal();
    },
  });
  const deleteMut = useMutation({
    mutationFn: classesAPI.delete,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["classes"] }); toast.success(t("Classe supprimée.")); setDeleteItem(null); },
    onError: (e) => {
      // FIX v40 : si la classe n'existe plus (404) ou dépend de l'historique
      // (409), on informe clairement et on rafraîchit la liste au lieu de
      // réessayer en boucle.
      const status = e?.response?.status;
      if (status === 404) toast.error(t("Cette classe n'existe plus (liste actualisée)."));
      else toast.error(extractApiError(e));
      qc.invalidateQueries({ queryKey: ["classes"] });
      setDeleteItem(null);
    },
  });
  const subjectsMut = useMutation({
    mutationFn: ({ id, subject_ids }) => classesAPI.setSubjects(id, subject_ids),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["classes"] });
      toast.success(t("Matières mises à jour !"));
      setSubjectModal(null);
    }
  });

  const closeModal = () => { setModalOpen(false); setEditItem(null); reset(); };

  // FIX v38 : copie des classes d'une année vers une autre (ouverture d'année)
  const [copyOpen, setCopyOpen] = useState(false);
  const [copySource, setCopySource] = useState("");
  const [copyTarget, setCopyTarget] = useState("");
  const copyMut = useMutation({
    mutationFn: () => classesAPI.copyFromYear({ source_year_id: copySource, target_year_id: copyTarget }),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["classes"] });
      toast.success(r.data?.detail || "Classes copiées.");
      setCopyOpen(false);
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const openCopy = () => {
    setCopySource("");
    setCopyTarget(yearFilter || activeYearId || "");
    setCopyOpen(true);
  };

  const openCreate = () => {
    // FIX v38 : l'année scolaire est pré-sélectionnée (année filtrée sur la
    // page, sinon année active) — la modale ne s'ouvre plus avec un champ vide.
    reset({ max_students: 30, school_year: yearFilter || activeYearId || "" });
    setEditItem(null);
    setModalOpen(true);
  };

  const openEdit = (c) => {
    setEditItem(c);
    reset({
      name: c.name,
      level: c.level,
      school_year: c.school_year,
      max_students: c.max_students,
    });
    setModalOpen(true);
  };

  const openSubjects = (c) => {
    const currentIds = (c.subjects_detail || []).map(s => s.id);
    setSelectedSubjects(currentIds);
    setSubjectModal(c);
  };

  const toggleSubject = (id) => {
    setSelectedSubjects(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const onSubmit = (d) => {
    if (editItem) updateMut.mutate({ id: editItem.id, data: d });
    else createMut.mutate(d);
  };

  const onSaveSubjects = () => {
    if (!subjectModal) return;
    const frSelected = selectedSubjects.filter(id => frSubjects.some(s => s.id === id));
    const enSelected = selectedSubjects.filter(id => enSubjects.some(s => s.id === id));
    if (frSelected.length === 0) {
      toast.error(t("Sélectionnez au moins une matière française."));
      return;
    }
    if (enSelected.length === 0) {
      toast.error(t("Sélectionnez au moins une matière anglaise."));
      return;
    }
    subjectsMut.mutate({ id: subjectModal.id, subject_ids: selectedSubjects });
  };

  const cols = [
    { key: "name", label: t("Classe"), accessor: "name" },
    { key: "level", label: t("Niveau"), accessor: "level_name" },
    { key: "year", label: t("Année"), accessor: "school_year_name" },
    {
      key: "students", label: t("Élèves"), render: r => (
        <span className="flex items-center gap-1 text-sm">
          <Users className="w-3 h-3" />{r.student_count || 0}/{r.max_students}
        </span>
      )
    },
    {
      key: "bilingual", label: t("Bilingue"), render: r => (
        r.has_bilingual
          ? <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full"><CheckCircle className="w-3 h-3" />{t("FR+EN")}</span>
          : <span className="inline-flex items-center gap-1 text-xs font-medium text-orange-700 bg-orange-50 px-2 py-0.5 rounded-full"><AlertCircle className="w-3 h-3" />{t("Incomplet")}</span>
      )
    },
    {
      key: "subjects_count", label: t("Matières"), render: r => (
        <span className="text-xs text-slate-500">
          🇫🇷 {r.fr_subject_count || 0} · 🇬🇧 {r.en_subject_count || 0}
        </span>
      )
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Classes")}
        subtitle={t("{n} classe(s)", { n: classes.length })}
        action={
          <div className="flex items-center gap-2">
            <button onClick={openCopy} className="btn-secondary flex items-center gap-2">
              <Copy className="w-4 h-4" />{t("Copier depuis une année")}</button>
            <button onClick={openCreate} className="btn-primary flex items-center gap-2">
              <Plus className="w-4 h-4" />{t("Nouvelle classe")}</button>
          </div>
        }
      />

      {/* FIX v34/v38 : chaque année gère SES classes — année active par défaut */}
      <div className="flex items-center gap-2 flex-wrap bg-white rounded-xl border border-slate-200 p-3">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mr-1">{t("Année :")}</span>
        <button onClick={() => setYearFilter("")}
          className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${!yearFilter ? "bg-primary text-white shadow" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
          Année active{activeYear ? ` (${activeYear.name})` : ""}
        </button>
        {years.map(y => {
          // Surligné si explicitement choisi, OU si c'est l'année active suivie par défaut
          const isSelected = String(yearFilter) === String(y.id) ||
            (yearFilter === "" && String(effectiveYearId) === String(y.id));
          return (
            <button key={y.id} onClick={() => setYearFilter(y.id)}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${isSelected ? "bg-primary text-white shadow" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
              {yearLabel(y)}{y.is_current ? " ✓" : ""}
            </button>
          );
        })}
      </div>

      <div className="card">
        <DataTable
          emptyMessage={`Aucune classe pour ${yearFilter ? (years.find(y => String(y.id) === String(yearFilter))?.name || "cette année") : "l'année active"}.\nCréez une classe, ou copiez en un clic celles d'une année précédente (« Copier depuis une année »).`}
          columns={cols}
          data={classes}
          loading={isLoading}
          actions={row => (
            <div className="flex items-center gap-1 justify-end">
              <button
                onClick={() => openSubjects(row)}
                title={t("Gérer les matières")}
                className="p-1.5 rounded-lg hover:bg-emerald-50 text-slate-400 hover:text-emerald-600"
              >
                <BookOpen className="w-4 h-4" />
              </button>
              <button onClick={() => openEdit(row)} className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-400 hover:text-primary">
                <Pencil className="w-4 h-4" />
              </button>
              <button onClick={() => setDeleteItem(row)} className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-400 hover:text-danger">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          )}
        />
      </div>

      {/* Modal create/edit class */}
      <Modal open={copyOpen} onClose={() => setCopyOpen(false)} title={t("Copier les classes d'une année")} size="md">
        <div className="space-y-4">
          <p className="text-sm text-slate-500">{t("Duplique les classes (nom, niveau, capacité, matières FR/EN) d'une année vers une autre. Les classes homonymes déjà présentes sont ignorées ; aucun élève n'est copié (utilisez ensuite les Inscriptions/Passages).")}</p>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">{t("Année source *")}</label>
              <SearchableSelect
                options={years.filter(y => String(y.id) !== String(copyTarget)).map(y => ({ value: y.id, label: y.name }))}
                value={copySource} onChange={setCopySource} placeholder="— Sélectionner —" />
            </div>
            <div>
              <label className="label">{t("Année cible *")}</label>
              <SearchableSelect
                options={years.map(y => ({ value: y.id, label: `${y.name}${y.is_current ? " ✓ Active" : ""}` }))}
                value={copyTarget} onChange={setCopyTarget} placeholder="— Sélectionner —" />
            </div>
          </div>
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={() => setCopyOpen(false)} className="btn-secondary">{t("Annuler")}</button>
            <button type="button" disabled={!copySource || !copyTarget || copyMut.isPending}
              onClick={() => copyMut.mutate()} className="btn-primary">
              {copyMut.isPending ? t("Copie…") : t("Copier les classes")}
            </button>
          </div>
        </div>
      </Modal>

      <Modal open={modalOpen} onClose={closeModal} title={editItem ? t("Modifier la classe") : t("Nouvelle classe")}>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="label">{t("Nom de la classe*")}</label>
            <input {...register("name", { required: true })} placeholder={t("ex: CM2-A")} className="input" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">{t("Niveau*")}</label>
              <Controller name="level" control={control} rules={{ required: true }}
                render={({ field }) => (
                  <SearchableSelect
                    options={levels.map(l => ({ value: l.id, label: l.name }))}
                    value={field.value} onChange={field.onChange}
                    placeholder={t("Rechercher un niveau…")} />
                )} />
            </div>
            <div>
              <label className="label">{t("Année scolaire*")}</label>
              <Controller name="school_year" control={control} rules={{ required: true }}
                render={({ field }) => (
                  <SearchableSelect
                    options={years.map(y => ({ value: y.id, label: `${y.name}${y.is_current ? " ✓" : ""}` }))}
                    value={field.value} onChange={field.onChange}
                    placeholder={t("Rechercher une année…")} />
                )} />
            </div>
          </div>
          <div>
            <label className="label">{t("Capacité max")}</label>
            <input {...register("max_students")} type="number" className="input" />
          </div>
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={closeModal} className="btn-secondary">{t("Annuler")}</button>
            <button type="submit" disabled={createMut.isPending || updateMut.isPending} className="btn-primary">{t("Enregistrer")}</button>
          </div>
        </form>
      </Modal>

      {/* Modal gestion matières */}
      <Modal open={!!subjectModal} onClose={() => setSubjectModal(null)} title={`Matières — ${subjectModal?.name || ""}`} size="lg">
        <div className="space-y-5">
          <p className="text-sm text-slate-500">{t("Sélectionnez les matières assignées à cette classe.")}<strong className="text-slate-700"> {t("Au moins une matière française et une matière anglaise sont obligatoires")}</strong> pour le calcul bilingue.
          </p>

          {/* Vérif bilingue */}
          {subjectModal && (() => {
            const frSel = selectedSubjects.filter(id => frSubjects.some(s => s.id === id));
            const enSel = selectedSubjects.filter(id => enSubjects.some(s => s.id === id));
            if (frSel.length === 0 || enSel.length === 0) {
              return (
                <div className="flex items-center gap-2 bg-orange-50 border border-orange-200 text-orange-700 rounded-xl p-3 text-sm">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  {frSel.length === 0 ? "Aucune matière française sélectionnée." : ""}
                  {enSel.length === 0 ? " Aucune matière anglaise sélectionnée." : ""}
                </div>
              );
            }
            return (
              <div className="flex items-center gap-2 bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-xl p-3 text-sm">
                <CheckCircle className="w-4 h-4 shrink-0" />
                Classe bilingue ✓ — {frSel.length} matière(s) FR · {enSel.length} matière(s) EN
              </div>
            );
          })()}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Matières françaises */}
            <div>
              <h4 className="flex items-center gap-2 font-semibold text-sm text-blue-700 mb-2">
                🇫🇷 Matières Françaises
              </h4>
              <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
                {frSubjects.map(s => (
                  <label key={s.id} className={`flex items-center gap-2.5 p-2.5 rounded-lg cursor-pointer border transition ${
                    selectedSubjects.includes(s.id)
                      ? "bg-blue-50 border-blue-300 text-blue-800"
                      : "border-slate-200 hover:bg-slate-50 text-slate-600"
                  }`}>
                    <input
                      type="checkbox"
                      checked={selectedSubjects.includes(s.id)}
                      onChange={() => toggleSubject(s.id)}
                      className="rounded"
                    />
                    <span className="text-sm font-medium">{s.name}</span>
                    <span className="ml-auto text-xs text-slate-400">coeff {s.coefficient}</span>
                  </label>
                ))}
                {frSubjects.length === 0 && (
                  <p className="text-xs text-slate-400 p-2">{t("Aucune matière française disponible. Créez-en dans l'onglet Matières.")}</p>
                )}
              </div>
            </div>

            {/* Matières anglaises */}
            <div>
              <h4 className="flex items-center gap-2 font-semibold text-sm text-green-700 mb-2">
                🇬🇧 Matières Anglaises
              </h4>
              <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
                {enSubjects.map(s => (
                  <label key={s.id} className={`flex items-center gap-2.5 p-2.5 rounded-lg cursor-pointer border transition ${
                    selectedSubjects.includes(s.id)
                      ? "bg-green-50 border-green-300 text-green-800"
                      : "border-slate-200 hover:bg-slate-50 text-slate-600"
                  }`}>
                    <input
                      type="checkbox"
                      checked={selectedSubjects.includes(s.id)}
                      onChange={() => toggleSubject(s.id)}
                      className="rounded"
                    />
                    <span className="text-sm font-medium">{s.name}</span>
                    <span className="ml-auto text-xs text-slate-400">coeff {s.coefficient}</span>
                  </label>
                ))}
                {enSubjects.length === 0 && (
                  <p className="text-xs text-slate-400 p-2">{t("Aucune matière anglaise disponible. Créez-en dans l'onglet Matières.")}</p>
                )}
              </div>
            </div>
          </div>

          <div className="flex gap-3 justify-end pt-2 border-t border-slate-100">
            <button type="button" onClick={() => setSubjectModal(null)} className="btn-secondary">{t("Annuler")}</button>
            <button
              onClick={onSaveSubjects}
              disabled={subjectsMut.isPending}
              className="btn-primary flex items-center gap-2"
            >
              {subjectsMut.isPending ? (
                <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
              ) : (
                <BookOpen className="w-4 h-4" />
              )}
              Enregistrer les matières
            </button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleteItem}
        onClose={() => setDeleteItem(null)}
        onConfirm={() => deleteMut.mutate(deleteItem?.id)}
        loading={deleteMut.isPending}
        message={`Supprimer la classe ${deleteItem?.name} ?`}
      />
    </div>
  );
}
