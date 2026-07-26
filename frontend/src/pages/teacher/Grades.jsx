/**
 * TeacherGrades — v26 CORRIGÉ
 *
 * CORRECTIONS :
 *  1. school_year ajouté dans la query grades (notes de l'année active)
 *  2. Filtre par classe + matière pour cibler les élèves
 *  3. Message explicite si aucun élève trouvé (classes non assignées)
 *  4. Période "Toutes" disponible pour voir tout d'un coup
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Save, Pencil, Trash2, AlertCircle, Layers } from "lucide-react";
import { useForm, Controller } from "react-hook-form";
import toast from "react-hot-toast";
import { gradesAPI, studentsAPI, schoolsAPI, teachersAPI, classesAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import Modal from "../../components/ui/Modal";
import SearchableSelect from "../../components/ui/SearchableSelect";
import BulkGradeModal from "../../components/grades/BulkGradeModal";
import { isValidGrade, gradePayloadValue } from "../../utils/gradeInput";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import { extractApiError } from "../../utils/errors";
import { t, dateLocale } from "../../i18n";

const NOTE_TYPES = [
  { value: "devoir",        label: "Devoir" },
  { value: "interrogation", label: "Interrogation / Devoir de classe" },
  { value: "controle",      label: "Contrôle" },
  { value: "examen",        label: "Examen / Évaluation" },
  { value: "tp",            label: "Travaux Pratiques" },
  { value: "autre",         label: "Autre" },
];

export default function TeacherGrades() {
  const qc = useQueryClient();
  const [period,       setPeriod]       = useState("T1");
  const [filterClass,  setFilterClass]  = useState("");
  const [modalOpen,    setModalOpen]    = useState(false);
  const [bulkOpen,     setBulkOpen]     = useState(false);
  const [viewItem,     setViewItem]     = useState(null);
  const [showDeleted,  setShowDeleted]  = useState(false);
  const [editItem,     setEditItem]     = useState(null);
  const [deleteItem,   setDeleteItem]   = useState(null);

  const { register, handleSubmit, reset, control, formState: { errors } } = useForm({
    defaultValues: { period: "T1", note_type: "devoir" },
  });

  /* ── Données ───────────────────────────────────────────────────────────── */
  const { data: yearsData } = useQuery({ queryKey: ["years"],        queryFn: schoolsAPI.years });
  const { data: studData  } = useQuery({ queryKey: ["my-students"],  queryFn: () => studentsAPI.list() });
  const { data: subjData  } = useQuery({ queryKey: ["my-subjects"],  queryFn: () => teachersAPI.mySubjects() });
  const { data: classData } = useQuery({ queryKey: ["my-classes"],   queryFn: () => classesAPI.list() });

  const years       = yearsData?.data?.results || yearsData?.data || [];
  const currentYear = years.find(y => y.is_current);
  const students    = studData?.data?.results  || studData?.data  || [];
  const rawSubjects = subjData?.data;
  const subjects    = Array.isArray(rawSubjects) ? rawSubjects : (rawSubjects?.results || []);
  const allClasses  = classData?.data?.results || classData?.data || [];

  /* ── Notes avec filtres year + period ─────────────────────────────────── */
  const gradesQuery = {
    ...(period      && period !== "all" && { period }),
    ...(currentYear && { school_year: currentYear.id }),
    ...(filterClass && { student__current_class: filterClass }),
  };

  const { data, isLoading } = useQuery({
    queryKey: ["teacher-grades", gradesQuery, showDeleted],
    queryFn: () => showDeleted ? gradesAPI.listDeleted() : gradesAPI.list(gradesQuery),
    enabled: !!currentYear,
  });
  const { data: histData } = useQuery({
    queryKey: ["grade-history", viewItem?.id],
    queryFn:  () => gradesAPI.history(viewItem.id),
    enabled:  !!viewItem?.id,
  });

  const grades  = data?.data?.results || data?.data || [];
  const history = histData?.data || [];

  /* Filtrer les élèves par classe sélectionnée */
  const filteredStudents = filterClass
    ? students.filter(s => String(s.current_class) === String(filterClass) || String(s.class_id) === String(filterClass))
    : students;

  const studentOpts = filteredStudents.map(s => ({ value: s.id, label: `${s.full_name} — ${s.class_name || "?"}` }));
  const subjectOpts = subjects.map(s => ({ value: s.id, label: `${s.name} (coeff ${s.coefficient})` }));
  const classOpts   = allClasses.map(c => ({ value: c.id, label: c.name }));
  // Options pour la saisie groupée : TOUS les élèves (filtre de classe interne
  // au modal), avec l'identifiant de classe pour ce filtre.
  const bulkStudentOpts = students.map(s => ({
    value: s.id, label: `${s.full_name} — ${s.class_name || "?"}`,
    classId: s.current_class ?? s.class_id ?? "",
  }));

  /* ── Mutations ─────────────────────────────────────────────────────────── */
  const createMut = useMutation({
    mutationFn: gradesAPI.create,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["teacher-grades"] });
      toast.success(t("Note enregistrée !"));
      setModalOpen(false);
      reset({ period: "T1", note_type: "devoir" });
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => gradesAPI.update(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["teacher-grades"] });
      toast.success(t("Note modifiée !"));
      setEditItem(null); setModalOpen(false);
      reset({ period: "T1", note_type: "devoir" });
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const deleteMut = useMutation({
    mutationFn: gradesAPI.delete,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["teacher-grades"] }); toast.success(t("Note supprimée.")); setDeleteItem(null); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const restoreMut = useMutation({
    mutationFn: gradesAPI.restore,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["teacher-grades"] }); toast.success(t("Note restaurée !")); },
  });

  /* ── Helpers ───────────────────────────────────────────────────────────── */
  const nc = v => { const n = parseFloat(v); if (n >= 14) return "text-green-600 font-bold"; if (n >= 10) return "text-amber-600 font-medium"; return "text-red-500 font-medium"; };

  const openEdit = (g) => {
    setEditItem(g);
    reset({ value: g.value, period: g.period, note_type: g.note_type || "devoir", comment: g.comment, justification: "" });
    setModalOpen(true);
  };

  const openCreate = () => {
    setEditItem(null);
    reset({ period: period !== "all" ? period : "T1", note_type: "devoir" });
    setModalOpen(true);
  };

  const onSubmit = (d) => {
    // V7 : la note est normalisée (virgule → point) sans jamais être altérée ;
    // « 10 » reste « 10 ». La valeur envoyée = exactement la valeur saisie.
    const value = gradePayloadValue(d.value);
    if (editItem) {
      updateMut.mutate({ id: editItem.id, data: { value, period: d.period, note_type: d.note_type, comment: d.comment, justification: d.justification } });
    } else {
      // V8 : le poids d'une évaluation vaut toujours 1 — envoyé
      // explicitement, jamais repris d'un état de formulaire.
      const payload = { ...d, value, note_coefficient: 1 };
      if (!payload.school_year && currentYear) payload.school_year = currentYear.id;
      createMut.mutate(payload);
    }
  };

  const cols = [
    { key: "student",          label: t("Élève"),        accessor: "student_name" },
    { key: "class",            label: t("Classe"),        render: r => r.student_class || r.class_name || "—" },
    { key: "subject",          label: t("Matière"),      accessor: "subject_name" },
    { key: "period",           label: t("Période"),      accessor: "period" },
    { key: "note_type",        label: t("Type"),         render: r => r.note_type_label || r.note_type || "—" },
    { key: "value",            label: t("Note"),         render: r => <span className={nc(r.value)}>{r.value}/20</span> },
    { key: "appr",             label: t("Appréciation"), accessor: "appreciation", render: r => r.appreciation ? t(r.appreciation) : "—" },
  ];

  const histCols = [
    { key: "action", label: t("Action"),  render: r => <span className={r.action === "create" ? "text-green-600" : "text-amber-600"}>{r.action === "create" ? t("Création") : t("Modification")}</span> },
    { key: "old",    label: t("Anc."),    render: r => r.old_value != null ? `${r.old_value}/20` : "—" },
    { key: "new",    label: t("Nouv."),   render: r => `${r.new_value}/20` },
    { key: "by",     label: t("Par"),     accessor: "changed_by_name" },
    { key: "just",   label: t("Justif."), accessor: "justification" },
    { key: "at",     label: t("Date"),    render: r => new Date(r.changed_at).toLocaleString(dateLocale()) },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title={t("Mes Notes")} subtitle={`${grades.length} note(s) — ${period === "all" ? "Toutes périodes" : period} — ${currentYear?.name || "…"}`}
        action={
          <div className="flex gap-2">
            <button onClick={() => setShowDeleted(!showDeleted)}
              className={`btn-secondary text-sm ${showDeleted ? "ring-2 ring-amber-400" : ""}`}>
              {showDeleted ? t("Masquer supprimées") : t("Voir supprimées")}
            </button>
            <button onClick={() => setBulkOpen(true)} className="btn-secondary flex items-center gap-2">
              <Layers className="w-4 h-4" />{t("Saisie groupée")}</button>
            <button onClick={openCreate} className="btn-primary flex items-center gap-2">
              <Plus className="w-4 h-4" />{t("Saisir une note")}</button>
          </div>
        } />

      <BulkGradeModal
        open={bulkOpen}
        onClose={() => setBulkOpen(false)}
        onSaved={() => qc.invalidateQueries({ queryKey: ["teacher-grades"] })}
        studentOptions={bulkStudentOpts}
        subjectOptions={subjectOpts}
        classOptions={classOpts}
        schoolYearId={currentYear?.id}
        periodDefault={period !== "all" ? period : "T1"}
      />

      {/* Alerte si aucun élève trouvé */}
      {!isLoading && students.length === 0 && (
        <div className="card flex items-start gap-3 bg-amber-50 border border-amber-200 text-amber-700">
          <AlertCircle className="w-5 h-5 mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold">{t("Aucun élève trouvé")}</p>
            <p className="text-sm">{t("Assurez-vous que votre profil enseignant a des classes assignées. Contactez l'administrateur si nécessaire.")}</p>
          </div>
        </div>
      )}

      {/* Filtres */}
      <div className="card flex gap-3 flex-wrap items-center">
        <span className="text-sm font-medium text-slate-600">{t("Période :")}</span>
        {["all","T1","T2","T3","exam"].map(p => (
          <button key={p} onClick={() => setPeriod(p)}
            className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${period === p ? "bg-primary text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
            {p === "all" ? "Toutes" : p === "exam" ? "Examen" : p}
          </button>
        ))}
        <div className="ml-auto min-w-48">
          <select value={filterClass} onChange={e => setFilterClass(e.target.value)}
            className="input text-sm w-full">
            <option value="">{t("Toutes classes")}</option>
            {classOpts.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
        </div>
      </div>

      <div className="card">
        <DataTable columns={cols} data={grades} loading={isLoading}
          onRowClick={r => !r.is_deleted && setViewItem(r)}
          actions={row => (
            <div className="flex items-center gap-1 justify-end">
              {!row.is_deleted && (
                <>
                  <button onClick={(e) => { e.stopPropagation(); openEdit(row); }} className="p-1.5 rounded-lg hover:bg-primary-50 text-slate-400 hover:text-primary"><Pencil className="w-4 h-4" /></button>
                  <button onClick={(e) => { e.stopPropagation(); setDeleteItem(row); }} className="p-1.5 rounded-lg hover:bg-red-50 text-slate-400 hover:text-red-500"><Trash2 className="w-4 h-4" /></button>
                </>
              )}
              {row.is_deleted && (
                <button onClick={() => restoreMut.mutate(row.id)}
                  className="px-2 py-1 text-xs rounded-lg bg-green-100 text-green-600 hover:bg-green-200">{t("Restaurer")}</button>
              )}
            </div>
          )} />
      </div>

      {/* Historique */}
      {viewItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/40" onClick={() => setViewItem(null)} />
          <div className="relative bg-white rounded-2xl shadow-2xl max-w-2xl w-full p-6 max-h-[80vh] overflow-y-auto space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-slate-800">{t("Historique")} — {viewItem.student_name} / {viewItem.subject_name}</h2>
              <button onClick={() => setViewItem(null)} className="text-slate-400 hover:text-slate-600 text-2xl">×</button>
            </div>
            <DataTable columns={histCols} data={history} />
          </div>
        </div>
      )}

      {/* Modal saisie / modification */}
      <Modal open={modalOpen}
        onClose={() => { setModalOpen(false); setEditItem(null); reset({ period: "T1", note_type: "devoir" }); }}
        title={editItem ? t("Modifier la note") : t("Saisir une note")}>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {!editItem && (
            <>
              <div>
                <label className="label">{t("Classe (filtre élèves)")}</label>
                <select className="input" onChange={e => setFilterClass(e.target.value)} value={filterClass}>
                  <option value="">{t("Toutes mes classes")}</option>
                  {classOpts.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
              </div>
              <div>
                <label className="label">{t("Élève *")}</label>
                <Controller name="student" control={control} rules={{ required: true }}
                  render={({ field }) => <SearchableSelect options={studentOpts} value={field.value} onChange={field.onChange} placeholder={t("Rechercher un élève…")} />} />
                {errors.student && <p className="text-red-500 text-xs mt-1">{t("Requis")}</p>}
              </div>
              <div>
                <label className="label">{t("Matière *")} <span className="text-xs text-slate-400">(vos matières assignées)</span></label>
                <Controller name="subject" control={control} rules={{ required: true }}
                  render={({ field }) => <SearchableSelect options={subjectOpts} value={field.value} onChange={field.onChange} placeholder={t("Sélectionner la matière…")} />} />
                {errors.subject && <p className="text-red-500 text-xs mt-1">{t("Requis")}</p>}
              </div>
              <div>
                <label className="label">{t("Année scolaire")}</label>
                <select {...register("school_year")} className="input">
                  {years.map(y => <option key={y.id} value={y.id}>{y.name}{y.is_current ? " ✓" : ""}</option>)}
                </select>
              </div>
            </>
          )}

          {editItem && (
            <div className="bg-slate-50 rounded-xl px-4 py-3 text-sm text-slate-600">{t("Modification de")} <strong>{editItem.student_name}</strong> en <strong>{editItem.subject_name}</strong>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">{t("Note (0–20) *")}</label>
              {/* V7 : champ TEXTE (inputMode décimal) — insensible molette /
                  flèches / compteurs ; la note tapée n'est jamais altérée. */}
              <input {...register("value", { required: true, validate: v => isValidGrade(v) || t("Note entre 0 et 20.") })}
                type="text" inputMode="decimal" autoComplete="off" placeholder="0–20" className="input" />
            </div>
            <div>
              <label className="label">{t("Période *")}</label>
              <select {...register("period", { required: true })} className="input">
                <option value="T1">{t("T1")}</option>
                <option value="T2">{t("T2")}</option>
                <option value="T3">{t("T3")}</option>
                <option value="exam">{t("Examen")}</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">{t("Type de note *")}</label>
              <select {...register("note_type", { required: true })} className="input">
                {NOTE_TYPES.map(nt => <option key={nt.value} value={nt.value}>{t(nt.label)}</option>)}
              </select>
            </div>
            {/* V8 : le poids d'une évaluation vaut TOUJOURS 1 (un examen ne
                compte pas plus qu'une interrogation). Ni champ ni colonne : la
                notion a disparu de l'interface, la règle est imposée par le
                backend. Ne pas confondre avec le coefficient d'une MATIÈRE. */}
          </div>

          <div><label className="label">{t("Commentaire")}</label><textarea {...register("comment")} className="input" rows={2} /></div>
          <div><label className="label">{t("Justification")}</label><textarea {...register("justification")} className="input" rows={2} placeholder={t("Raison de la saisie ou modification…")} /></div>

          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={() => { setModalOpen(false); setEditItem(null); reset({ period: "T1", note_type: "devoir" }); }} className="btn-secondary">{t("Annuler")}</button>
            <button type="submit" disabled={createMut.isPending || updateMut.isPending} className="btn-primary flex items-center gap-2">
              <Save className="w-4 h-4" />
              {(createMut.isPending || updateMut.isPending) ? "Enregistrement…" : (editItem ? t("Modifier") : t("Enregistrer"))}
            </button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog open={!!deleteItem} onClose={() => setDeleteItem(null)}
        onConfirm={() => deleteMut.mutate(deleteItem?.id)} loading={deleteMut.isPending}
        message={`Supprimer la note de ${deleteItem?.student_name} en ${deleteItem?.subject_name} (${deleteItem?.value}/20) ?`} />
    </div>
  );
}
