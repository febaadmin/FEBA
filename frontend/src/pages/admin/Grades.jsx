import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, BarChart2, BookOpen, Globe, User, Clock, History } from "lucide-react";
import { useForm, Controller } from "react-hook-form";
import toast from "react-hot-toast";
import { gradesAPI, studentsAPI, subjectsAPI, schoolsAPI, classesAPI } from "../../api";
// Native CSV export — no external dependency required
function exportCSV(rows, filename) {
  const headers = Object.keys(rows[0] || {});
  const csvLines = [
    headers.join(";"),
    ...rows.map(r => headers.map(h => `"${String(r[h] ?? "").replace(/"/g, '""')}"`).join(";")),
  ];
  const blob = new Blob(["\uFEFF" + csvLines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a); URL.revokeObjectURL(url);
}
import PageHeader from "../../components/ui/PageHeader";
// DataTable replaced by custom row-click table in list view
import Modal from "../../components/ui/Modal";
import SearchableSelect from "../../components/ui/SearchableSelect";
import { extractApiError } from "../../utils/errors";

const PERIODS = [
  { value: "T1", label: "Trimestre 1" },
  { value: "T2", label: "Trimestre 2" },
  { value: "T3", label: "Trimestre 3" },
  { value: "annual", label: "Annuel" },
];

const NOTE_TYPES = [
  { value: "devoir", label: "Devoir" },
  { value: "interrogation", label: "Interrogation" },
  { value: "controle", label: "Contrôle" },
  { value: "examen", label: "Examen" },
  { value: "tp", label: "Travaux Pratiques" },
  { value: "autre", label: "Autre" },
];

const LETTER_COLORS = {
  "A+": "bg-emerald-100 text-emerald-800", A: "bg-emerald-100 text-emerald-700",
  "A-": "bg-green-100 text-green-700", "B+": "bg-blue-100 text-blue-700",
  B: "bg-blue-100 text-blue-600", "B-": "bg-sky-100 text-sky-700",
  "C+": "bg-yellow-100 text-yellow-700", C: "bg-yellow-100 text-yellow-600",
  "C-": "bg-orange-100 text-orange-600", "D+": "bg-orange-100 text-orange-700",
  D: "bg-red-100 text-red-500", "D-": "bg-red-100 text-red-600",
  F: "bg-red-200 text-red-800",
};

function LetterBadge({ letter }) {
  if (!letter) return <span className="text-gray-400">—</span>;
  const cls = LETTER_COLORS[letter] || "bg-gray-100 text-gray-700";
  return <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-bold ${cls}`}>{letter}</span>;
}

export default function AdminGrades() {
  const qc = useQueryClient();
  const [view, setView] = useState("list"); // "list" | "summary" | "bilingual" | "deleted" | "allhistory"
  const [addOpen, setAddOpen] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [histItem, setHistItem] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [selectedRow, setSelectedRow] = useState(null); // Row-click selection
  const [bulkSelected, setBulkSelected] = useState(new Set()); // Bulk checkbox selection
  const [selectedStudent, setSelectedStudent] = useState(null);
  const [selectedPeriod, setSelectedPeriod] = useState("T1");
  const [filterClass, setFilterClass] = useState("");
  const [filterPeriod, setFilterPeriod] = useState("");
  const [filterYear, setFilterYear] = useState("");
  // Pagination
  const [gradePage, setGradePage] = useState(1);
  const GRADES_PER_PAGE = 20;

  const { register, handleSubmit, reset, control } = useForm();

  // CSV export (native, no dependency)
  const exportDeletedCSV = () => {
    const rows = deletedGrades.map(g => ({
      "Élève":          g.student_name || "",
      "Matricule":      g.student_matricule || "",
      "Classe":         g.student_class || "",
      "Matière":        g.subject_name || "",
      "Catégorie":      g.note_type_display || g.note_type || "",
      "Note":           parseFloat(g.value || 0).toFixed(2),
      "Coefficient":    g.note_coefficient || 1,
      "Lettre":         g.letter || "",
      "Période":        g.period || "",
      "Commentaire":    g.comment || "",
      "Justification":  g.deleted_justification || "",
      "Supprimé par":   g.deleted_by_name || "",
      "Date suppression": g.deleted_at ? new Date(g.deleted_at).toLocaleDateString("fr-FR") : "",
      "Année":          g.school_year_name || "",
    }));
    exportCSV(rows, `notes_supprimees_${new Date().toISOString().slice(0,10)}.csv`);
  };

  const exportExcel = () => {
    const rows = grades.map(r => ({
      "Élève":         r.student_name || "",
      "Matricule":     r.student_matricule || "",
      "Classe":        r.student_class || "",
      "Matière":       r.subject_name || "",
      "Période":       r.period || "",
      "Type":          r.note_type_display || r.note_type || "",
      "Note":          parseFloat(r.value || 0).toFixed(2),
      "Coefficient":   r.note_coefficient || 1,
      "Lettre":        r.letter || "",
      "Commentaire":   r.comment || "",
      "Année":         r.school_year_name || "",
      "Date saisie":   r.created_at ? new Date(r.created_at).toLocaleDateString("fr-FR") : "",
    }));
    const fileName = `notes_${filterYear || "toutes"}_${filterPeriod || "toutes"}_${new Date().toISOString().slice(0,10)}.csv`;
    exportCSV(rows, fileName);
  };

  const { data: yearsData } = useQuery({ queryKey: ["years"], queryFn: schoolsAPI.years });
  const { data: studData } = useQuery({ queryKey: ["students-all"], queryFn: () => studentsAPI.list() });
  const { data: subData } = useQuery({ queryKey: ["subjects"], queryFn: () => subjectsAPI.list() });
  // FIX v34 : les classes suivent l'année sélectionnée dans les filtres
  // (sans sélection → année active, par défaut backend). Plus de doublons inter-années.
  const { data: classData } = useQuery({
    queryKey: ["classes", filterYear],
    queryFn: () => classesAPI.list(filterYear ? { school_year: filterYear } : {}),
  });

  const years      = yearsData?.data?.results  || yearsData?.data  || [];
  const currentYear= years.find(y => y.is_current);
  const students   = studData?.data?.results   || studData?.data   || [];
  const subjects   = subData?.data?.results    || subData?.data    || [];
  const classes    = classData?.data?.results  || classData?.data  || [];

  // NOUVEAUX filtres combinés
  const [filterStudent,  setFilterStudent]  = useState("");
  const [filterSubject,  setFilterSubject]  = useState("");
  const [filterLanguage, setFilterLanguage] = useState(""); // "fr" | "en" | ""

  const gradesParams = {
    ...(filterClass    && { student__current_class: filterClass }),
    ...(filterPeriod   && { period: filterPeriod }),
    ...(filterYear     && { school_year: filterYear }),
    ...(!filterYear && currentYear && { school_year: currentYear.id }),
    // Filtres additionnels
    ...(filterStudent  && { student: filterStudent }),
    ...(filterSubject  && { subject: filterSubject }),
  };

  const { data: gradesData, isLoading, refetch } = useQuery({
    queryKey: ["grades", gradesParams],
    queryFn: () => gradesAPI.list(gradesParams),
  });

  const { data: summaryData, isLoading: summaryLoading, isError: summaryError } = useQuery({
    queryKey: ["grade-summary", selectedStudent, selectedPeriod, filterYear],
    queryFn: () => gradesAPI.studentSummary(selectedStudent, {
      period: selectedPeriod,
      school_year: filterYear || currentYear?.id,
    }),
    enabled: !!(view === "summary" && selectedStudent),
    retry: 1,
  });

  const { data: bilingualData, isLoading: bilingualLoading, isError: bilingualError } = useQuery({
    queryKey: ["grade-bilingual", selectedStudent, selectedPeriod, filterYear],
    queryFn: () => gradesAPI.bilingual({
      student: selectedStudent,
      period: selectedPeriod,
      school_year: filterYear || currentYear?.id,
    }),
    enabled: !!(view === "bilingual" && selectedStudent),
    retry: 1,
  });

  // FIX v20: Notes supprimées
  const { data: deletedData, isLoading: deletedLoading } = useQuery({
    queryKey: ["grades-deleted"],
    queryFn: () => gradesAPI.listDeleted(),
    enabled: view === "deleted",
  });

  const gradesRaw = gradesData?.data?.results || gradesData?.data || [];
  // Filtre côté client par langue de matière (FR/EN)
  const grades = filterLanguage
    ? gradesRaw.filter(g => (g.subject_language || g.language || "fr") === filterLanguage)
    : gradesRaw;
  const summary = summaryData?.data;
  const bilingual = bilingualData?.data;
  const deletedGrades = deletedData?.data?.results || deletedData?.data || [];

  // Historique global — v28
  const [histFilterStudent, setHistFilterStudent] = useState("");
  const [histFilterYear,    setHistFilterYear]    = useState("");
  const { data: allHistData, isLoading: allHistLoading } = useQuery({
    queryKey: ["grade-all-history", histFilterStudent, histFilterYear],
    queryFn: () => gradesAPI.allHistory({
      ...(histFilterStudent && { student: histFilterStudent }),
      ...(histFilterYear && { school_year: histFilterYear }),
      limit: 200,
    }),
    enabled: view === "allhistory",
  });
  const allHistRows = allHistData?.data?.results || [];

  const studentOpts = students.map(s => ({ value: s.id, label: `${s.full_name || s.first_name + ' ' + s.last_name} — ${s.class_name || "?"}` }));
  const subjectOpts = subjects.map(s => ({ value: s.id, label: `${s.name}${s.language ? ` (${s.language.toUpperCase()})` : ""}` }));

  const restoreMut = useMutation({
    mutationFn: (id) => gradesAPI.restore(id),
    onSuccess: () => { toast.success("Note restaurée !"); qc.invalidateQueries({ queryKey: ["grades"] }); qc.invalidateQueries({ queryKey: ["grades-deleted"] }); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const addMut = useMutation({
    mutationFn: (d) => gradesAPI.create(d),
    onSuccess: () => { toast.success("Note ajoutée !"); setAddOpen(false); reset(); qc.invalidateQueries({ queryKey: ["grades"] }); qc.invalidateQueries({ queryKey: ["grades-deleted"] }); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const editMut = useMutation({
    mutationFn: ({ id, data }) => gradesAPI.update(id, data),
    onSuccess: () => { toast.success("Note modifiée !"); setAddOpen(false); setEditItem(null); reset(); qc.invalidateQueries({ queryKey: ["grades"] }); qc.invalidateQueries({ queryKey: ["grades-deleted"] }); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const delMut = useMutation({
    mutationFn: ({ id, justification }) => gradesAPI.delete(id, justification),
    onSuccess: () => {
      toast.success("Note supprimée");
      // FIX v33 : nettoyage complet de l'état après suppression —
      // le panneau "Détail de la note" et l'historique référencaient
      // encore la note supprimée (erreurs 404 "ressource introuvable").
      setDeleteConfirm(null);
      setSelectedRow(null);
      setHistItem(null);
      qc.invalidateQueries({ queryKey: ["grades"] });
      qc.invalidateQueries({ queryKey: ["grades-deleted"] });
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const bulkDelMut = useMutation({
    mutationFn: (ids) => gradesAPI.bulkDelete(ids),
    onSuccess: (data) => { toast.success(`${data?.data?.deleted || ""} note(s) supprimée(s) — visibles dans l'onglet 'Supprimées'.`); setBulkSelected(new Set()); setSelectedRow(null); setHistItem(null); qc.invalidateQueries({ queryKey: ["grades"] }); qc.invalidateQueries({ queryKey: ["grades-deleted"] }); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const { data: histData } = useQuery({
    queryKey: ["grade-history", histItem?.id],
    queryFn: () => gradesAPI.history(histItem.id),
    enabled: !!histItem?.id,
  });
  const historyEntries = histData?.data || [];

  const onSubmit = (d) => {
    const payload = {
      ...d,
      school_year: d.school_year || currentYear?.id,
      value: parseFloat(d.value),
      note_coefficient: parseInt(d.note_coefficient) || 1,
    };
    if (editItem) {
      editMut.mutate({ id: editItem.id, data: payload });
    } else {
      addMut.mutate(payload);
    }
  };

  const cols = [
    { key: "student", label: "Élève",   render: r => r.student_name || r.student },
    { key: "class",   label: "Classe",  render: r => r.student_class || r.class_name || "—" },
    { key: "subject", label: "Matière", render: r => r.subject_name || r.subject },
    { key: "period",  label: "Période", accessor: "period" },
    { key: "type",    label: "Type",    render: r => r.note_type_display || r.note_type },
    { key: "value", label: "Note", render: r => (
      <div className="flex items-center gap-2">
        <span className="font-semibold">{parseFloat(r.value).toFixed(2)}/20</span>
        <LetterBadge letter={r.letter} />
      </div>
    )},
    { key: "coeff", label: "Coeff note", render: r => r.note_coefficient || 1 },
    { key: "year", label: "Année", render: r => r.school_year_name || r.school_year },
    { key: "actions", label: "", render: r => (
      <div className="flex items-center gap-1">
        <button title="Modifier" onClick={() => { setEditItem(r); reset({ student: r.student_id || r.student, subject: r.subject_id || r.subject, period: r.period, value: r.value, note_type: r.note_type, note_coefficient: r.note_coefficient || 1, comment: r.comment, school_year: r.school_year_id || r.school_year || currentYear?.id, justification: "" }); setAddOpen(true); }}
          className="p-1.5 rounded-lg hover:bg-blue-50 text-slate-400 hover:text-blue-600">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536M9 13l6.768-6.768a2 2 0 012.828 2.828L11.828 15.828a2 2 0 01-.707.414l-3.535.707.707-3.536A2 2 0 019 13z" /></svg>
        </button>
        <button title="Historique" onClick={() => setHistItem(r)}
          className="p-1.5 rounded-lg hover:bg-amber-50 text-slate-400 hover:text-amber-600">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
        </button>
        <button title="Supprimer" onClick={() => setDeleteConfirm(r)}
          className="p-1.5 rounded-lg hover:bg-red-50 text-slate-400 hover:text-red-600">
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    )},
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Notes" subtitle={`Gestion des notes — ${currentYear?.name || "Année active"}`}
        action={
          <div className="flex gap-2 flex-wrap">
            {view === "list" && grades.length > 0 && (
              <button onClick={exportExcel}
                className="btn-secondary flex items-center gap-2 text-sm">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
                Excel / CSV ({grades.length})
              </button>
            )}
            <button onClick={() => { reset({ school_year: currentYear?.id || "" }); setAddOpen(true); }}
              className="btn-primary flex items-center gap-2"><Plus className="w-4 h-4" />Ajouter une note</button>
          </div>
        }
      />

      {/* View tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-xl p-1 w-fit">
        {[
          { key: "list", label: "Liste", icon: BookOpen },
          { key: "summary", label: "Résumé par élève", icon: User },
          { key: "bilingual", label: "Bilingue", icon: Globe },
          { key: "deleted", label: "Supprimées", icon: Trash2 },
          { key: "allhistory", label: "Historique", icon: History },
        ].map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => setView(key)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition ${view === key ? "bg-white shadow text-blue-700" : "text-gray-600 hover:text-gray-800"}`}>
            <Icon className="w-4 h-4" />{label}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 bg-white rounded-xl border border-gray-200 p-4">
        {view !== "summary" && (
          <select value={filterYear} onChange={e => setFilterYear(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm">
            <option value="">Année scolaire</option>
            {years.map(y => <option key={y.id} value={y.id}>{y.name}{y.is_current ? " ★" : ""}</option>)}
          </select>
        )}
        {view === "list" && (
          <select value={filterPeriod} onChange={e => setFilterPeriod(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm">
            <option value="">Toutes périodes</option>
            {PERIODS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
        )}
        {view === "list" && (
          <select value={filterClass} onChange={e => setFilterClass(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm">
            <option value="">Toutes classes</option>
            {classes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        )}
        {/* NOUVEAU : filtre élève */}
        {view === "list" && (
          <div className="min-w-48">
            <select value={filterStudent} onChange={e => setFilterStudent(e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-full">
              <option value="">Tous les élèves</option>
              {students.map(s => <option key={s.id} value={s.id}>{s.full_name || `${s.first_name} ${s.last_name}`}</option>)}
            </select>
          </div>
        )}
        {/* NOUVEAU : filtre matière */}
        {view === "list" && (
          <div className="min-w-48">
            <select value={filterSubject} onChange={e => setFilterSubject(e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-full">
              <option value="">Toutes matières</option>
              {subjects.map(s => <option key={s.id} value={s.id}>{s.name}{s.language ? ` (${s.language?.toUpperCase()})` : ""}</option>)}
            </select>
          </div>
        )}
        {/* NOUVEAU : filtre catégorie FR / EN */}
        {view === "list" && (
          <select value={filterLanguage} onChange={e => setFilterLanguage(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm">
            <option value="">FR + EN</option>
            <option value="fr">🇫🇷 Français</option>
            <option value="en">🇬🇧 Anglais</option>
          </select>
        )}
        {(view === "summary" || view === "bilingual") && (
          <>
            <div className="min-w-56">
              <SearchableSelect
                options={studentOpts}
                value={selectedStudent}
                onChange={setSelectedStudent}
                placeholder="Choisir un élève..."
              />
            </div>
            <select value={selectedPeriod} onChange={e => setSelectedPeriod(e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm">
              {PERIODS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
            </select>
          </>
        )}
        {/* Bouton reset filtres */}
        {(filterStudent || filterSubject || filterLanguage || filterClass || filterPeriod) && (
          <button onClick={() => { setFilterStudent(""); setFilterSubject(""); setFilterLanguage(""); setFilterClass(""); setFilterPeriod(""); }}
            className="px-3 py-2 text-xs text-red-500 hover:text-red-700 hover:bg-red-50 rounded-lg border border-red-100">
            ✕ Reset filtres
          </button>
        )}
      </div>

      {/* LIST VIEW — Row-click selection pattern (like payment module) */}
      {view === "list" && (
        <div className="grid gap-4 grid-cols-1">
          {/* Table */}
          <div>
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="overflow-x-auto">
              <table className="w-full text-sm min-w-[700px]">
                {/* Bulk toolbar */}
                {bulkSelected.size > 0 && (
                  <div className="flex items-center gap-3 mb-3 px-2 py-2 bg-blue-50 rounded-xl border border-blue-200">
                    <span className="text-sm text-blue-700 font-medium">{bulkSelected.size} note(s) sélectionnée(s)</span>
                    <button onClick={() => bulkDelMut.mutate([...bulkSelected])} disabled={bulkDelMut.isPending}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600 text-white text-xs font-medium hover:bg-red-700 disabled:opacity-50">
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                      {bulkDelMut.isPending ? "Suppression…" : "Supprimer la sélection"}
                    </button>
                    <button onClick={() => setBulkSelected(new Set())} className="text-xs text-blue-500 hover:underline">Désélectionner</button>
                  </div>
                )}
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-3 py-3 w-10">
                      <input type="checkbox"
                        className="w-4 h-4 accent-blue-600 cursor-pointer"
                        checked={grades.length > 0 && grades.every(r => bulkSelected.has(r.id))}
                        onChange={e => { const n = new Set(bulkSelected); grades.forEach(r => e.target.checked ? n.add(r.id) : n.delete(r.id)); setBulkSelected(n); }}
                      />
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Élève</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Matière</th>
                    <th className="px-4 py-3 text-center text-xs font-semibold text-gray-500">Période</th>
                    <th className="px-4 py-3 text-center text-xs font-semibold text-gray-500">Type</th>
                    <th className="px-4 py-3 text-center text-xs font-semibold text-gray-500">Note</th>
                    <th className="px-4 py-3 text-center text-xs font-semibold text-gray-500">Coeff</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500">Année</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {isLoading && (
                    <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Chargement…</td></tr>
                  )}
                  {!isLoading && grades.length === 0 && (
                    <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Aucune note pour cette sélection.</td></tr>
                  )}
                  {grades.slice((gradePage-1)*GRADES_PER_PAGE, gradePage*GRADES_PER_PAGE).map(r => (
                    <tr
                      key={r.id}
                      onClick={() => setSelectedRow(selectedRow?.id === r.id ? null : r)}
                      className={`cursor-pointer transition-colors ${selectedRow?.id === r.id ? "bg-blue-50 border-l-4 border-l-blue-500" : bulkSelected.has(r.id) ? "bg-blue-50" : "hover:bg-gray-50"}`}
                    >
                      <td className="px-3 py-3 w-10" onClick={e => e.stopPropagation()}>
                        <input type="checkbox" className="w-4 h-4 accent-blue-600 cursor-pointer"
                          checked={bulkSelected.has(r.id)}
                          onChange={() => { const n = new Set(bulkSelected); n.has(r.id) ? n.delete(r.id) : n.add(r.id); setBulkSelected(n); }} />
                      </td>
                      <td className="px-4 py-3 font-medium text-gray-800">{r.student_name || r.student}</td>
                      <td className="px-4 py-3 text-gray-600">{r.subject_name || r.subject}</td>
                      <td className="px-4 py-3 text-center">
                        <span className="text-xs font-medium px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full">{r.period}</span>
                      </td>
                      <td className="px-4 py-3 text-center text-xs text-gray-500">{r.note_type_display || r.note_type}</td>
                      <td className="px-4 py-3 text-center">
                        <div className="flex items-center justify-center gap-1.5">
                          <span className="font-semibold">{parseFloat(r.value).toFixed(2)}/20</span>
                          <LetterBadge letter={r.letter} />
                        </div>
                      </td>
                      <td className="px-4 py-3 text-center text-gray-500">{r.note_coefficient || 1}</td>
                      <td className="px-4 py-3 text-xs text-gray-400">{r.school_year_name || r.school_year}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>{/* /overflow-x-auto */}
              {/* Pagination */}
              {grades.length > GRADES_PER_PAGE && (
                <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 bg-gray-50 text-sm text-gray-500">
                  <span>{grades.length} note(s) · Page {gradePage}/{Math.ceil(grades.length/GRADES_PER_PAGE)}</span>
                  <div className="flex items-center gap-1">
                    <button onClick={() => setGradePage(p => Math.max(1,p-1))} disabled={gradePage===1}
                      className="px-2.5 py-1 rounded-lg border border-gray-200 hover:bg-white disabled:opacity-40 transition">‹</button>
                    {Array.from({length: Math.ceil(grades.length/GRADES_PER_PAGE)}, (_,i) => i+1)
                      .filter(p => p === 1 || p === Math.ceil(grades.length/GRADES_PER_PAGE) || Math.abs(p-gradePage) <= 1)
                      .reduce((acc, p, i, arr) => {
                        if (i > 0 && p - arr[i-1] > 1) acc.push("...");
                        acc.push(p); return acc;
                      }, [])
                      .map((p, i) => p === "..." ? (
                        <span key={`e${i}`} className="px-1">…</span>
                      ) : (
                        <button key={p} onClick={() => setGradePage(p)}
                          className={`px-2.5 py-1 rounded-lg border transition ${p===gradePage ? "bg-blue-600 text-white border-blue-600" : "border-gray-200 hover:bg-white"}`}>{p}</button>
                      ))
                    }
                    <button onClick={() => setGradePage(p => Math.min(Math.ceil(grades.length/GRADES_PER_PAGE),p+1))} disabled={gradePage===Math.ceil(grades.length/GRADES_PER_PAGE)}
                      className="px-2.5 py-1 rounded-lg border border-gray-200 hover:bg-white disabled:opacity-40 transition">›</button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Detail panel — sidebar on desktop, modal overlay on mobile */}
          {selectedRow && (
            <>
              {/* Mobile overlay backdrop */}
              <div className="fixed inset-0 bg-black/40 z-40" onClick={() => setSelectedRow(null)} />

              {/* Panel — fixed bottom sheet on mobile, sticky sidebar on desktop */}
              {/* FIX v32 : bottom-sheet conservé en mobile ; en desktop le
                  panneau devient une modale CENTRÉE comme les autres formulaires
                  (avant : carte latérale collée à droite du tableau). */}
              <div className={`
                fixed bottom-0 left-0 right-0 z-50
                lg:inset-0 lg:flex lg:items-center lg:justify-center lg:p-6 lg:pointer-events-none
              `}>
                <div className="bg-white rounded-t-2xl lg:rounded-2xl border border-blue-200 shadow-2xl overflow-hidden w-full lg:max-w-md lg:pointer-events-auto">
                  <div className="bg-blue-600 px-4 py-3 flex items-center justify-between">
                    <span className="text-white font-semibold text-sm">Détail de la note</span>
                    <button onClick={() => setSelectedRow(null)} className="text-blue-200 hover:text-white transition">
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                  </div>
                  {/* Drag handle on mobile */}
                  <div className="flex justify-center pt-2 lg:hidden">
                    <div className="w-10 h-1 bg-gray-300 rounded-full" />
                  </div>
                  <div className="p-4 space-y-3 max-h-[70vh] lg:max-h-[75vh] overflow-y-auto">
                    {[
                      { label: "Élève",    value: selectedRow.student_name },
                      { label: "Matière",  value: selectedRow.subject_name },
                      { label: "Période",  value: selectedRow.period },
                      { label: "Type",     value: selectedRow.note_type_display || selectedRow.note_type },
                      { label: "Année",    value: selectedRow.school_year_name },
                    ].map(({ label, value }) => (
                      <div key={label} className="flex justify-between py-1.5 border-b border-gray-50 text-sm">
                        <span className="text-gray-500">{label}</span>
                        <span className="font-medium text-gray-800">{value || "—"}</span>
                      </div>
                    ))}
                    <div className="flex justify-between py-1.5 border-b border-gray-50 text-sm">
                      <span className="text-gray-500">Note</span>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-gray-900">{parseFloat(selectedRow.value).toFixed(2)}/20</span>
                        <LetterBadge letter={selectedRow.letter} />
                      </div>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-gray-50 text-sm">
                      <span className="text-gray-500">Coefficient</span>
                      <span className="font-medium">{selectedRow.note_coefficient || 1}</span>
                    </div>
                    {selectedRow.comment && (
                      <div className="text-xs text-gray-600 bg-gray-50 rounded-lg p-2">{selectedRow.comment}</div>
                    )}
                    {/* Actions */}
                    <div className="flex flex-col gap-2 pt-2">
                      <button
                        onClick={() => {
                          setEditItem(selectedRow);
                          reset({ student: selectedRow.student_id || selectedRow.student, subject: selectedRow.subject_id || selectedRow.subject, period: selectedRow.period, value: selectedRow.value, note_type: selectedRow.note_type, note_coefficient: selectedRow.note_coefficient || 1, comment: selectedRow.comment, school_year: selectedRow.school_year_id || selectedRow.school_year || currentYear?.id, justification: "" });
                          setAddOpen(true);
                        }}
                        className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536M9 13l6.768-6.768a2 2 0 012.828 2.828L11.828 15.828a2 2 0 01-.707.414l-3.535.707.707-3.536A2 2 0 019 13z" /></svg>
                        Modifier
                      </button>
                      <button
                        onClick={() => setHistItem(selectedRow)}
                        className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg bg-amber-50 text-amber-700 text-sm font-medium hover:bg-amber-100 transition border border-amber-200"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                        Voir l'historique
                      </button>
                      <button
                        onClick={() => setDeleteConfirm(selectedRow)}
                        className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg bg-red-50 text-red-600 text-sm font-medium hover:bg-red-100 transition border border-red-200"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                        Supprimer
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* SUMMARY VIEW */}
      {view === "summary" && (
        <div>
          {!selectedStudent ? (
            <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-400">
              <User className="w-12 h-12 mx-auto mb-3 text-gray-300" />
              <p>Sélectionnez un élève pour voir son résumé</p>
            </div>
          ) : summaryLoading ? (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400">
              <div className="animate-spin w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full mx-auto mb-2" />
              Chargement du résumé…
            </div>
          ) : summaryError ? (
            <div className="bg-white rounded-xl border border-red-200 p-8 text-center text-red-400">
              <p className="font-semibold mb-1">Erreur lors du chargement du résumé</p>
              <p className="text-sm text-red-300">
                {summaryError?.response?.data?.error || "Vérifiez que cet élève existe et a une classe assignée."}
              </p>
            </div>
          ) : !summary ? (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400">
              Sélectionnez un élève et une période pour voir le résumé de ses notes.
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="p-4 bg-blue-900 text-white flex items-center gap-4">
                <BarChart2 className="w-6 h-6 text-yellow-400" />
                <div>
                  <h3 className="font-bold">{summary.student_name}</h3>
                  <p className="text-blue-200 text-sm">{summary.class_name} — {selectedPeriod} — {summary.school_year}</p>
                </div>
                <div className="ml-auto text-right">
                  <div className="text-2xl font-bold text-yellow-400">{summary.average ? `${parseFloat(summary.average).toFixed(2)}/20` : "—"}</div>
                  <div className="text-blue-200 text-xs">Rang : {summary.rank || "—"}</div>
                </div>
              </div>
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Matière</th>
                    <th className="px-4 py-2 text-center text-xs font-semibold text-gray-500">Coeff</th>
                    <th className="px-4 py-2 text-center text-xs font-semibold text-gray-500">Langue</th>
                    <th className="px-4 py-2 text-center text-xs font-semibold text-gray-500">Moyenne</th>
                    <th className="px-4 py-2 text-center text-xs font-semibold text-gray-500">Lettre</th>
                    <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Notes</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {(summary.subjects || []).map((subj, i) => (
                    <tr key={subj.subject_id} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                      <td className="px-4 py-2 text-sm font-medium text-gray-800">{subj.subject_name}</td>
                      <td className="px-4 py-2 text-center text-sm text-gray-500">{subj.coefficient}</td>
                      <td className="px-4 py-2 text-center">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                          subj.language === 'en' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'
                        }`}>{subj.language === 'en' ? 'EN' : subj.language === 'fr' ? 'FR' : 'BI'}</span>
                      </td>
                      <td className="px-4 py-2 text-center text-sm font-semibold text-gray-800">
                        {subj.average != null ? `${parseFloat(subj.average).toFixed(2)}/20` : "—"}
                      </td>
                      <td className="px-4 py-2 text-center"><LetterBadge letter={subj.letter} /></td>
                      <td className="px-4 py-2 text-xs text-gray-500">
                        {(subj.notes || []).map(n => `${n.note_type?.[0]?.toUpperCase()}:${parseFloat(n.value).toFixed(1)}`).join("  ") || "Aucune note"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* BILINGUAL VIEW */}
      {view === "bilingual" && (
        <div className="space-y-4">
          {!selectedStudent ? (
            <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-400">
              <Globe className="w-12 h-12 mx-auto mb-3 text-gray-300" />
              <p>Sélectionnez un élève pour voir ses moyennes bilingues</p>
            </div>
          ) : bilingualLoading ? (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400">
              <div className="animate-spin w-6 h-6 border-2 border-purple-400 border-t-transparent rounded-full mx-auto mb-2" />
              Calcul des moyennes bilingues…
            </div>
          ) : bilingualError ? (
            <div className="bg-white rounded-xl border border-orange-200 p-8 text-center text-orange-500">
              <Globe className="w-10 h-10 mx-auto mb-3 text-orange-300" />
              <p className="font-semibold mb-1">Calcul bilingue indisponible</p>
              <p className="text-sm text-orange-400">
                {bilingualError?.response?.data?.error || "Vérifiez que cet élève a une classe avec des matières FR et EN assignées."}
              </p>
            </div>
          ) : !bilingual ? (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400">Aucune donnée bilingue disponible pour cet élève.</div>
          ) : (!bilingual.has_fr_subjects && !bilingual.has_en_subjects) ? (
            <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-500">
              <Globe className="w-10 h-10 mx-auto mb-3 text-slate-300" />
              <p className="font-semibold mb-1">Pas de calcul bilingue pour cette sélection</p>
              <p className="text-sm text-slate-400">
                Cet élève n'a pas de classe avec des matières FR et EN assignées
                pour l'année sélectionnée. Vérifiez son inscription et les matières
                de sa classe dans cette année.
              </p>
            </div>
          ) : (
            <>
              {/* Bilingual formula explanation */}
              <div className="bg-gradient-to-r from-blue-900 to-blue-800 rounded-xl p-4 text-white">
                <h3 className="font-bold text-yellow-400 mb-1">Système Bilingue FEBA</h3>
                <p className="text-blue-200 text-sm">
                  <strong className="text-white">Formule :</strong> Moyenne Bilingue = (Moyenne Française × 40%) + (Moyenne Anglaise × 60%)
                </p>
              </div>

              {/* Bilingual averages for current period */}
              {selectedPeriod !== 'annual' ? (
                <div className="grid grid-cols-3 gap-4">
                  {[
                    { label: "Moyenne Française", value: bilingual.fr_average, lang: "FR", color: "blue" },
                    { label: "Moyenne Anglaise", value: bilingual.en_average, lang: "EN", color: "green" },
                    { label: "Moyenne Bilingue", value: bilingual.bilingual_average, lang: "BI", color: "purple" },
                  ].map(item => {
                    const letter = item.value != null ? null : null;
                    return (
                      <div key={item.label} className={`bg-white rounded-xl border-2 ${
                        item.color === 'purple' ? 'border-purple-200' :
                        item.color === 'green' ? 'border-green-200' : 'border-blue-200'
                      } p-4 text-center`}>
                        <span className={`inline-block text-xs font-bold px-2 py-0.5 rounded-full mb-2 ${
                          item.color === 'purple' ? 'bg-purple-100 text-purple-700' :
                          item.color === 'green' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'
                        }`}>{item.lang}</span>
                        <div className={`text-3xl font-bold ${
                          item.color === 'purple' ? 'text-purple-700' :
                          item.color === 'green' ? 'text-green-700' : 'text-blue-700'
                        }`}>
                          {item.value != null ? parseFloat(item.value).toFixed(2) : "—"}
                        </div>
                        <div className="text-gray-500 text-sm mt-1">{item.label}</div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                /* Annual bilingual table */
                <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                  <div className="p-4 border-b border-gray-100">
                    <h3 className="font-semibold text-gray-800">Moyennes Bilingues Annuelles</h3>
                  </div>
                  <table className="w-full">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500">Trimestre</th>
                        <th className="px-4 py-2 text-center text-xs font-semibold text-blue-600">Moy. FR</th>
                        <th className="px-4 py-2 text-center text-xs font-semibold text-green-600">Moy. EN</th>
                        <th className="px-4 py-2 text-center text-xs font-semibold text-purple-600">Moy. Bilingue</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {['T1','T2','T3'].map(t => {
                        const td = bilingual[t] || {};
                        return (
                          <tr key={t}>
                            <td className="px-4 py-2 font-medium text-gray-700">{t}</td>
                            <td className="px-4 py-2 text-center text-blue-700">{td.fr_average != null ? parseFloat(td.fr_average).toFixed(2) : "—"}</td>
                            <td className="px-4 py-2 text-center text-green-700">{td.en_average != null ? parseFloat(td.en_average).toFixed(2) : "—"}</td>
                            <td className="px-4 py-2 text-center font-semibold text-purple-700">{td.bilingual_average != null ? parseFloat(td.bilingual_average).toFixed(2) : "—"}</td>
                          </tr>
                        );
                      })}
                      <tr className="bg-yellow-50 font-bold">
                        <td className="px-4 py-2 text-gray-800">ANNUELLE ★</td>
                        <td className="px-4 py-2 text-center text-blue-800">{bilingual.annual?.fr_average != null ? parseFloat(bilingual.annual.fr_average).toFixed(2) : "—"}</td>
                        <td className="px-4 py-2 text-center text-green-800">{bilingual.annual?.en_average != null ? parseFloat(bilingual.annual.en_average).toFixed(2) : "—"}</td>
                        <td className="px-4 py-2 text-center text-purple-800 text-lg">{bilingual.annual?.bilingual_average != null ? parseFloat(bilingual.annual.bilingual_average).toFixed(2) : "—"}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* FIX v20: VUE NOTES SUPPRIMÉES */}
      {view === "deleted" && (
        <div className="card">
          <div className="mb-4 flex items-center justify-between gap-2 flex-wrap">
            <div className="flex items-center gap-2">
              <Trash2 className="w-5 h-5 text-red-500" />
              <h3 className="font-semibold text-slate-800">Notes supprimées (soft-deleted)</h3>
            </div>
            <button onClick={exportDeletedCSV}
              className="btn-secondary flex items-center gap-2 text-sm">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
              Exporter
            </button>
          </div>
          <div className="overflow-x-auto">
          <table className="w-full text-sm min-w-[600px]">
            <thead className="bg-red-50 text-red-700">
              <tr>
                <th className="px-4 py-2 text-left">Élève</th>
                <th className="px-4 py-2 text-left">Matière</th>
                <th className="px-4 py-2 text-left">Période</th>
                <th className="px-4 py-2 text-right">Note</th>
                <th className="px-4 py-2 text-left">Supprimée par</th>
                <th className="px-4 py-2 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {deletedLoading && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Chargement…</td></tr>
              )}
              {!deletedLoading && deletedGrades.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-400">Aucune note supprimée.</td></tr>
              )}
              {deletedGrades.map(g => (
                <tr key={g.id} className="border-t border-red-100 hover:bg-red-50/50">
                  <td className="px-4 py-2 text-slate-700">{g.student_name}</td>
                  <td className="px-4 py-2 text-slate-600">{g.subject_name}</td>
                  <td className="px-4 py-2 text-slate-500">{g.period}</td>
                  <td className="px-4 py-2 text-right font-mono text-red-700 line-through">{g.value}/20</td>
                  <td className="px-4 py-2 text-slate-400 text-xs">{g.deleted_by_name || "—"}</td>
                  <td className="px-4 py-2">
                    <button onClick={() => restoreMut.mutate(g.id)}
                      className="px-2 py-1 rounded bg-green-100 text-green-700 text-xs hover:bg-green-200">
                      Restaurer
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </div>
      )}

      {/* FIX v20: VUE HISTORIQUE GLOBAL */}
      {view === "allhistory" && (
        <div className="card">
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <History className="w-5 h-5 text-blue-500" />
              <h3 className="font-semibold text-slate-800">Historique global des modifications</h3>
              <span className="text-xs text-slate-500 bg-blue-50 px-2 py-0.5 rounded-full">{allHistRows.length} entrée(s)</span>
            </div>
            <div className="flex gap-2 ml-auto flex-wrap">
              <select value={histFilterStudent} onChange={e => setHistFilterStudent(e.target.value)}
                className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm">
                <option value="">Tous les élèves</option>
                {students.map(s => <option key={s.id} value={s.id}>{s.full_name || `${s.first_name} ${s.last_name}`}</option>)}
              </select>
              <select value={histFilterYear} onChange={e => setHistFilterYear(e.target.value)}
                className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm">
                <option value="">Toutes les années</option>
                {years.map(y => <option key={y.id} value={y.id}>{y.name}</option>)}
              </select>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[700px]">
              <thead className="bg-blue-50 text-blue-700">
                <tr>
                  <th className="px-4 py-2 text-left">Date</th>
                  <th className="px-4 py-2 text-left">Élève</th>
                  <th className="px-4 py-2 text-left">Matière</th>
                  <th className="px-4 py-2 text-center">Période</th>
                  <th className="px-4 py-2 text-center">Action</th>
                  <th className="px-4 py-2 text-center">Ancienne valeur</th>
                  <th className="px-4 py-2 text-center">Nouvelle valeur</th>
                  <th className="px-4 py-2 text-left">Justification</th>
                  <th className="px-4 py-2 text-left">Par</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {allHistLoading && (
                  <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-400">Chargement…</td></tr>
                )}
                {!allHistLoading && allHistRows.length === 0 && (
                  <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-400">Aucun historique trouvé.</td></tr>
                )}
                {allHistRows.map(h => (
                  <tr key={h.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2 text-xs text-gray-500 whitespace-nowrap">
                      {h.changed_at ? new Date(h.changed_at).toLocaleString("fr-FR") : "—"}
                    </td>
                    <td className="px-4 py-2 font-medium text-gray-800">{h.student_name}</td>
                    <td className="px-4 py-2 text-gray-600">{h.subject_name}</td>
                    <td className="px-4 py-2 text-center">
                      <span className="text-xs font-medium px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full">{h.period}</span>
                    </td>
                    <td className="px-4 py-2 text-center">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${h.action === "create" ? "bg-green-100 text-green-700" : "bg-orange-100 text-orange-700"}`}>
                        {h.action_display}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-center text-gray-500">{h.old_value != null ? `${parseFloat(h.old_value).toFixed(2)}/20` : "—"}</td>
                    <td className="px-4 py-2 text-center font-semibold">{h.new_value != null ? `${parseFloat(h.new_value).toFixed(2)}/20` : "—"}</td>
                    <td className="px-4 py-2 text-xs text-gray-500 max-w-[180px] truncate" title={h.justification}>{h.justification || "—"}</td>
                    <td className="px-4 py-2 text-xs text-gray-500">{h.changed_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ADD NOTE MODAL */}
      <Modal open={addOpen} onClose={() => { setAddOpen(false); setEditItem(null); reset(); }} title={editItem ? "Modifier la note" : "Ajouter une note"} size="md">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {/* In edit mode: show read-only context, no reselection needed */}
          {editItem ? (
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 text-sm">
              <div className="font-semibold text-blue-800 mb-1">Note sélectionnée — modification</div>
              <div className="text-blue-700 space-y-0.5">
                <div><span className="text-blue-500">Élève :</span> {editItem.student_name}</div>
                <div><span className="text-blue-500">Matière :</span> {editItem.subject_name}</div>
                <div><span className="text-blue-500">Période :</span> {editItem.period}</div>
              </div>
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Élève *</label>
              <Controller name="student" control={control} rules={{ required: true }}
                render={({ field }) => (
                  <SearchableSelect options={studentOpts} value={field.value}
                    onChange={(v) => field.onChange(v)} placeholder="Choisir un élève..." />
                )} />
            </div>
          )}
          {!editItem && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Matière *</label>
                <select {...register("subject", { required: true })} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
                  <option value="">Choisir...</option>
                  {subjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Période *</label>
                <select {...register("period", { required: true })} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
                  {PERIODS.filter(p => p.value !== 'annual').map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
                </select>
              </div>
            </div>
          )}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Note (/20) *</label>
              <input {...register("value", { required: true, min: 0, max: 20 })}
                type="number" step="0.25" min="0" max="20"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Type *</label>
              <select {...register("note_type")} className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm">
                {NOTE_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Coeff. note</label>
              <input {...register("note_coefficient")} type="number" min="1" defaultValue="1"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Commentaire</label>
            <textarea {...register("comment")} rows={2}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
          </div>
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={() => setAddOpen(false)} className="btn-secondary flex-1">Annuler</button>
            <button type="submit" disabled={addMut.isPending || editMut.isPending} className="btn-primary flex-1">
              {addMut.isPending || editMut.isPending ? "Enregistrement…" : editItem ? "Modifier" : "Ajouter la note"}
            </button>
          </div>
          {/* Hidden: school_year pre-filled by reset() */}
          <input type="hidden" {...register("school_year")} />
        </form>
      </Modal>
      {/* DELETE CONFIRM MODAL */}
      <Modal open={!!deleteConfirm} onClose={() => setDeleteConfirm(null)} title="Supprimer la note" size="sm">
        <div className="space-y-4">
          <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">
            Supprimer <strong>{deleteConfirm && parseFloat(deleteConfirm.value || 0).toFixed(2)}/20</strong> de <strong>{deleteConfirm?.student_name}</strong> ?
            Cette action est irréversible.
          </div>
          <div>
            <label className="label">Justification de suppression*</label>
            <textarea id="del-just" className="input" rows={2} placeholder="Motif obligatoire : erreur de saisie, doublon…" />
          </div>
          <div className="flex gap-3 justify-end">
            <button type="button" onClick={() => setDeleteConfirm(null)} className="btn-secondary">Annuler</button>
            <button type="button" onClick={() => {
              const just = document.getElementById("del-just")?.value?.trim() || "";
              if (!just) {
                document.getElementById("del-just").classList.add("border-red-500");
                document.getElementById("del-just").focus();
                return;
              }
              delMut.mutate({ id: deleteConfirm.id, justification: just });
            }} disabled={delMut.isPending}
              className="px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-60">
              {delMut.isPending ? "Suppression…" : "Supprimer"}
            </button>
          </div>
        </div>
      </Modal>
      {/* HISTORY MODAL */}
      <Modal open={!!histItem} onClose={() => setHistItem(null)} title={`Historique — Note #${histItem?.id || ""}`} size="lg">
        <div className="space-y-3">
          {histData === undefined && histItem && (
            <div className="flex items-center justify-center py-8 text-slate-400">
              <div className="animate-spin w-5 h-5 border-2 border-blue-400 border-t-transparent rounded-full mr-2" />
              Chargement de l'historique…
            </div>
          )}
          {historyEntries.length === 0 && histData !== undefined && (
            <p className="text-center py-6 text-slate-400">Aucun historique disponible pour cette note.</p>
          )}
          {historyEntries.map((h, i) => (
            <div key={h.id || i} className="border border-slate-100 rounded-xl p-4 bg-slate-50">
              <div className="flex items-center justify-between mb-2">
                <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${h.action === 'create' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>
                  {h.action === 'create' ? '✚ Création' : '✎ Modification'}
                </span>
                <span className="text-xs text-slate-400 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {new Date(h.changed_at).toLocaleString('fr-FR')}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <span className="text-slate-500">Ancienne valeur :</span>
                  <span className="ml-1 font-semibold text-red-600">{h.old_value != null ? `${h.old_value}/20` : '—'}</span>
                </div>
                <div>
                  <span className="text-slate-500">Nouvelle valeur :</span>
                  <span className="ml-1 font-semibold text-green-700">{h.new_value != null ? `${h.new_value}/20` : '—'}</span>
                </div>
              </div>
              {h.justification && (
                <div className="mt-2 text-xs text-slate-600 bg-white rounded-lg p-2 border border-slate-100">
                  <span className="font-semibold">Justification :</span> {h.justification}
                </div>
              )}
              {h.changed_by_name && (
                <div className="mt-1 text-xs text-slate-400">Par : {h.changed_by_name}</div>
              )}
            </div>
          ))}
        </div>
      </Modal>
    </div>
  );
}
