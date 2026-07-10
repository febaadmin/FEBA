/**
 * AdminEnrollments — v29.2 (REFONTE COMPLÈTE)
 *
 * Système d'admission et passage en classe supérieure entièrement reconstruit.
 *
 * Onglets :
 *  1. Passage de niveau — Inscrire toute une année → nouvelle année (1 clic)
 *  2. Passage par classe — Inscrire une classe → nouvelle année / nouvelle classe
 *  3. Inscription individuelle — Inscrire / transférer un élève précis
 *  4. Assistant fin d'année — Décisions groupées (promotion/redoublement/exclusion...)
 *  5. Historique — Parcours académique complet d'un élève
 *
 * Corrections v29.2 :
 *  - extractApiError remplace toutes les gestions d'erreur fragmentées
 *  - payload correct pour l'action enroll (student passé via save, pas le payload)
 *  - messages d'erreur explicites depuis le backend
 *  - résultats d'opérations groupées affichés de façon détaillée
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Users, GraduationCap, School, ArrowRight, CheckCircle, XCircle,
  AlertCircle, RefreshCw, History, ChevronDown, ChevronUp,
  UserCheck, UserX, Repeat, BookOpen, LogOut
} from "lucide-react";
import toast from "react-hot-toast";
import { studentsAPI, schoolsAPI, classesAPI } from "../../api";
import { extractApiError } from "../../utils/errors";
import PageHeader from "../../components/ui/PageHeader";
import SearchableSelect from "../../components/ui/SearchableSelect";

/* ── Promotion status labels ──────────────────────────────────────────────── */
const PROMOTION_STATUSES = [
  { value: "normal",     label: "Passage normal",             icon: UserCheck, color: "text-emerald-600" },
  { value: "honor",      label: "Passage avec mention",       icon: GraduationCap, color: "text-blue-600" },
  { value: "repeat",     label: "Redoublement",               icon: Repeat, color: "text-amber-600" },
  { value: "transfer",   label: "Transfert de filière",       icon: ArrowRight, color: "text-purple-600" },
  { value: "graduated",  label: "Diplômé / fin de cycle",     icon: GraduationCap, color: "text-teal-600" },
  { value: "excluded",   label: "Exclu",                      icon: UserX, color: "text-red-600" },
  { value: "withdrawn",  label: "Retiré / Départ",            icon: LogOut, color: "text-slate-600" },
];

/* ── Composant Section repliable ─────────────────────────────────────────── */
function Section({ title, subtitle, icon: Icon, children, accentColor = "blue" }) {
  const [open, setOpen] = useState(true);
  const borderCls = {
    blue:   "border-blue-200",
    green:  "border-emerald-200",
    amber:  "border-amber-200",
    purple: "border-purple-200",
    teal:   "border-teal-200",
  }[accentColor] || "border-slate-200";

  return (
    <div className={`rounded-2xl border-2 ${borderCls} bg-white overflow-hidden shadow-sm`}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-6 py-4 text-left hover:bg-slate-50 transition-colors"
      >
        <div>
          <div className="flex items-center gap-2">
            <Icon className="w-5 h-5 text-slate-600" />
            <span className="font-bold text-slate-800">{title}</span>
          </div>
          {subtitle && <p className="text-xs text-slate-500 mt-0.5 ml-7">{subtitle}</p>}
        </div>
        {open
          ? <ChevronUp className="w-4 h-4 text-slate-400" />
          : <ChevronDown className="w-4 h-4 text-slate-400" />}
      </button>
      {open && <div className="px-6 pb-6 border-t border-slate-100">{children}</div>}
    </div>
  );
}

/* ── ResultBanner ─────────────────────────────────────────────────────────── */
function ResultBanner({ result, onClear }) {
  if (!result) return null;
  // FIX v33 : "0 inscrits" ne doit pas s'afficher en vert triomphant.
  // On distingue succès réel, résultat neutre (tous déjà inscrits) et échec.
  const enrolled = result.enrolled ?? result.succeeded ?? result.generated ?? 0;
  const ok = !result.error && enrolled > 0;
  const neutral = !result.error && enrolled === 0;
  const nothingHint =
    neutral && result.enrolled === 0 &&
    (result.skipped ? "Tous ces élèves étaient déjà inscrits dans l'année cible." :
      "Aucun élève trouvé pour ce critère. Vérifiez la classe/année source sélectionnée.");
  return (
    <div className={`flex items-start gap-3 rounded-xl p-4 text-sm ${
      ok ? "bg-emerald-50 border border-emerald-200 text-emerald-800"
         : neutral ? "bg-amber-50 border border-amber-200 text-amber-800"
         : "bg-red-50 border border-red-200 text-red-800"
    }`}>
      {ok
        ? <CheckCircle className="w-5 h-5 mt-0.5 shrink-0 text-emerald-600" />
        : <AlertCircle className={`w-5 h-5 mt-0.5 shrink-0 ${neutral ? "text-amber-600" : "text-red-600"}`} />}
      <div className="flex-1 space-y-1">
        {result.error && <p className="font-medium">{result.error}</p>}
        {result.enrolled !== undefined && (
          <p><strong>{result.enrolled}</strong> élève(s) inscrit(s)</p>
        )}
        {nothingHint && <p className="text-sm">{nothingHint}</p>}
        {result.skipped !== undefined && result.skipped > 0 && (
          <p className="text-sm opacity-75">{result.skipped} déjà inscrit(s) — ignoré(s)</p>
        )}
        {result.succeeded !== undefined && (
          <p><strong>{result.succeeded}/{result.total}</strong> décision(s) appliquée(s)</p>
        )}
        {result.generated !== undefined && (
          <p><strong>{result.generated}</strong> bulletin(s) généré(s)</p>
        )}
        {Array.isArray(result.failed) && result.failed.length > 0 && (
          <details className="mt-1 text-xs">
            <summary className="cursor-pointer font-medium">
              {result.failed.length} échec(s) — cliquer pour détails
            </summary>
            <ul className="mt-1 space-y-0.5 pl-2">
              {result.failed.slice(0, 10).map((f, i) => (
                <li key={i} className="text-red-700">
                  {f.error || JSON.stringify(f)}
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
      <button type="button" onClick={onClear} className="text-slate-400 hover:text-slate-600 ml-2">✕</button>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════ */

export default function AdminEnrollments() {
  const qc = useQueryClient();

  // ── Données de référence ─────────────────────────────────────────────────
  const { data: yearsData }   = useQuery({ queryKey: ["school-years"],   queryFn: () => schoolsAPI.years() });
  const { data: classesData } = useQuery({ queryKey: ["classes-all"],    queryFn: () => classesAPI.list({ all_years: "1" }) });
  const { data: studentsData } = useQuery({ queryKey: ["students-all"],  queryFn: () => studentsAPI.list({ all_years: "1", page_size: 500 }) });

  const years    = yearsData?.data?.results || yearsData?.data || [];
  const classes  = classesData?.data?.results || classesData?.data || [];
  const students = studentsData?.data?.results || studentsData?.data || [];

  const activeYear = years.find(y => y.is_current);

  // ── Onglets ──────────────────────────────────────────────────────────────
  const [tab, setTab] = useState("bulk-year");

  // ── Passage de niveau (toute une année) ─────────────────────────────────
  const [byYearSrc, setByYearSrc]     = useState("");
  const [byYearDst, setByYearDst]     = useState("");
  const [byYearResult, setByYearResult] = useState(null);

  const bulkYearMut = useMutation({
    mutationFn: () => studentsAPI.enrollAllFromYear({
      source_year_id: byYearSrc,
      target_year_id: byYearDst,
    }),
    onSuccess: (r) => {
      setByYearResult(r.data);
      qc.invalidateQueries({ queryKey: ["students-all"] });
      const n = r.data?.enrolled ?? 0;
      n > 0 ? toast.success(`Passage de niveau : ${n} élève(s) inscrit(s).`)
            : toast(r.data?.skipped ? "Tous déjà inscrits dans l'année cible." : "Aucun élève à inscrire.", { icon: "ℹ️" });
    },
    onError: (e) => {
      setByYearResult({ error: extractApiError(e) });
      toast.error(extractApiError(e));
    },
  });

  // ── Passage par classe ───────────────────────────────────────────────────
  const [byClassSrc,    setByClassSrc]    = useState("");
  const [byClassYear,   setByClassYear]   = useState("");
  const [byClassDst,    setByClassDst]    = useState("");
  const [byClassResult, setByClassResult] = useState(null);

  const bulkClassMut = useMutation({
    mutationFn: () => studentsAPI.enrollClass({
      class_id:       byClassSrc,
      target_year_id: byClassYear,
      new_class_id:   byClassDst || undefined,
    }),
    onSuccess: (r) => {
      setByClassResult(r.data);
      qc.invalidateQueries({ queryKey: ["students-all"] });
      const n = r.data?.enrolled ?? 0;
      n > 0 ? toast.success(`Passage par classe : ${n} élève(s) inscrit(s).`)
            : toast(r.data?.skipped ? "Tous déjà inscrits dans l'année cible." : "Aucun élève trouvé pour cette classe.", { icon: "ℹ️" });
    },
    onError: (e) => {
      setByClassResult({ error: extractApiError(e) });
      toast.error(extractApiError(e));
    },
  });

  // ── Inscription individuelle ─────────────────────────────────────────────
  const [indivStudent,    setIndivStudent]    = useState("");
  const [indivYear,       setIndivYear]       = useState(activeYear?.id || "");
  const [indivClass,      setIndivClass]      = useState("");
  const [indivStatus,     setIndivStatus]     = useState("normal");
  const [indivNote,       setIndivNote]       = useState("");
  const [indivResult,     setIndivResult]     = useState(null);

  const indivMut = useMutation({
    mutationFn: () => studentsAPI.enroll(indivStudent, {
      school_year:      Number(indivYear),
      class_obj:        indivClass ? Number(indivClass) : null,
      promotion_status: indivStatus,
      note:             indivNote,
    }),
    onSuccess: (r) => {
      setIndivResult({ enrolled: 1 });
      qc.invalidateQueries({ queryKey: ["students-all"] });
      toast.success("Élève inscrit avec succès !");
      setIndivStudent(""); setIndivClass(""); setIndivNote("");
    },
    onError: (e) => {
      setIndivResult({ error: extractApiError(e) });
      toast.error(extractApiError(e));
    },
  });

  // ── Assistant fin d'année ────────────────────────────────────────────────
  const [eoyYear,      setEoyYear]      = useState(activeYear?.id || "");
  const [eoyDecisions, setEoyDecisions] = useState([]); // [{student_id, action, class_id?, reason?}]
  const [eoyStudentId, setEoyStudentId] = useState("");
  const [eoyAction,    setEoyAction]    = useState("promote");
  const [eoyClass,     setEoyClass]     = useState("");
  const [eoyReason,    setEoyReason]    = useState("");
  const [eoyResult,    setEoyResult]    = useState(null);

  const addEoyDecision = () => {
    if (!eoyStudentId) return toast.error("Sélectionnez un élève.");
    if (eoyDecisions.find(d => d.student_id === Number(eoyStudentId)))
      return toast.error("Décision déjà ajoutée pour cet élève.");
    const student = students.find(s => String(s.id) === String(eoyStudentId));
    setEoyDecisions(prev => [...prev, {
      student_id: Number(eoyStudentId),
      student_name: student ? `${student.first_name} ${student.last_name}` : `Élève #${eoyStudentId}`,
      action: eoyAction,
      class_id: eoyClass ? Number(eoyClass) : undefined,
      reason: eoyReason || undefined,
    }]);
    setEoyStudentId(""); setEoyClass(""); setEoyReason("");
  };

  const removeEoyDecision = (studentId) => {
    setEoyDecisions(prev => prev.filter(d => d.student_id !== studentId));
  };

  const eoyMut = useMutation({
    mutationFn: () => studentsAPI.endOfYearAssistant({
      target_year_id: Number(eoyYear),
      decisions: eoyDecisions.map(({ student_name: _, ...d }) => d),
    }),
    onSuccess: (r) => {
      setEoyResult(r.data);
      setEoyDecisions([]);
      qc.invalidateQueries({ queryKey: ["students-all"] });
      toast.success(`${r.data.succeeded}/${r.data.total} décision(s) appliquée(s) !`);
    },
    onError: (e) => {
      setEoyResult({ error: extractApiError(e) });
      toast.error(extractApiError(e));
    },
  });

  // ── Historique ───────────────────────────────────────────────────────────
  const [histStudent, setHistStudent] = useState("");
  const { data: histData, refetch: refetchHist, isFetching: histLoading } = useQuery({
    queryKey: ["student-history", histStudent],
    queryFn: () => studentsAPI.history(histStudent),
    enabled: !!histStudent,
  });
  const history = histData?.data || [];

  /* ── Helpers ─────────────────────────────────────────────────────────────── */
  const yearOptions = years.map(y => ({ value: y.id, label: `${y.name}${y.is_current ? " ✓ Active" : ""}` }));

  // BUG N°7 — plus AUCUN doublon dans les listes de classes :
  //  1. dédoublonnage strict par id (au cas où l'API renverrait deux fois
  //     la même classe) ;
  //  2. chaque liste déroulante est FILTRÉE par l'année scolaire concernée
  //     (année cible / année source) : une classe n'apparaît donc qu'UNE
  //     seule fois pour une année donnée, au lieu de mélanger les
  //     homonymes de toutes les années (CE1-A 2024, CE1-A 2025, ...).
  const uniqueClasses = [...new Map(classes.map(c => [c.id, c])).values()];
  const classToOption = (c, withYear) => ({
    value: c.id,
    label: `${c.name}${withYear && c.school_year_name ? ` — ${c.school_year_name}` : ""} (${c.class_level || c.level_name || ""})`,
  });
  // Liste pour UNE année précise : pas de doublon possible, libellé court.
  const classOptionsForYear = (yearId) => uniqueClasses
    .filter(c => String(c.school_year) === String(yearId))
    .map(c => classToOption(c, false));
  // Liste toutes années (sélection d'une classe SOURCE dans une année
  // passée) : libellé désambiguïsé par l'année.
  const classOptionsAllYears = uniqueClasses.map(c => classToOption(c, true));
  const studentOptions = students.map(s => ({
    value: s.id,
    label: `${s.first_name} ${s.last_name} — ${s.class_name || "Sans classe"} (${s.matricule || ""})`,
  }));

  const statusBadge = (status) => {
    const s = PROMOTION_STATUSES.find(x => x.value === status);
    return s ? (
      <span className={`text-xs font-medium ${s.color}`}>{s.label}</span>
    ) : <span className="text-xs text-slate-400">{status}</span>;
  };

  const ACTION_LABELS = {
    promote:  "Passage normal",
    honor:    "Passage avec mention",
    repeat:   "Redoublement",
    transfer: "Transfert de filière",
    graduate: "Diplômation",
    depart:   "Départ",
    exclude:  "Exclusion",
  };

  const TABS = [
    { id: "bulk-year",  label: "Passage de niveau",       icon: RefreshCw },
    { id: "bulk-class", label: "Passage par classe",       icon: School },
    { id: "individual", label: "Inscription individuelle", icon: Users },
    { id: "eoy",        label: "Assistant fin d'année",    icon: GraduationCap },
    { id: "history",    label: "Historique élève",         icon: History },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Admissions & Passages en classe"
        subtitle="Gérez les inscriptions, transferts et passages de niveau"
      />

      {/* Année active */}
      {activeYear && (
        <div className="flex items-center gap-2 text-sm bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-2.5">
          <CheckCircle className="w-4 h-4 text-emerald-600" />
          <span className="text-emerald-800 font-medium">Année active : {activeYear.name}</span>
          <span className="text-emerald-600 ml-1">({activeYear.start_date} → {activeYear.end_date})</span>
        </div>
      )}

      {/* Onglets */}
      <div className="flex gap-1 flex-wrap bg-slate-100 rounded-2xl p-1.5">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
              tab === id
                ? "bg-white text-primary shadow-sm"
                : "text-slate-600 hover:text-slate-800 hover:bg-white/60"
            }`}
          >
            <Icon className="w-4 h-4" /> {label}
          </button>
        ))}
      </div>

      {/* ── Tab 1 : Passage de niveau ──────────────────────────────────────── */}
      {tab === "bulk-year" && (
        <div className="card space-y-4">
          <h3 className="font-bold text-slate-800">Passage de niveau — Toute une année</h3>
          <p className="text-sm text-slate-500">
            <strong>Réinscription globale.</strong> Inscrit automatiquement TOUS les élèves de
            l'année source dans l'année cible, dans une classe du même nom lorsqu'elle existe.
            Chaque élève conserve ses données historiques. Idéal pour ouvrir une nouvelle année d'un coup.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Année source (départ)</label>
              <SearchableSelect options={yearOptions} value={byYearSrc} onChange={setByYearSrc} placeholder="— Sélectionner —" />
            </div>
            <div>
              <label className="label">Année cible (arrivée)</label>
              <SearchableSelect options={yearOptions} value={byYearDst} onChange={setByYearDst} placeholder="— Sélectionner —" />
            </div>
          </div>
          <ResultBanner result={byYearResult} onClear={() => setByYearResult(null)} />
          <button
            type="button"
            onClick={() => {
              if (!byYearSrc || !byYearDst) return toast.error("Sélectionnez les deux années.");
              if (byYearSrc === byYearDst) return toast.error("Les deux années doivent être différentes.");
              bulkYearMut.mutate();
            }}
            disabled={bulkYearMut.isPending}
            className="btn-primary w-full sm:w-auto flex items-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${bulkYearMut.isPending ? "animate-spin" : ""}`} />
            {bulkYearMut.isPending ? "Passage en cours..." : "Lancer le passage de niveau"}
          </button>
        </div>
      )}

      {/* ── Tab 2 : Passage par classe ─────────────────────────────────────── */}
      {tab === "bulk-class" && (
        <div className="card space-y-4">
          <h3 className="font-bold text-slate-800">Passage par classe</h3>
          <p className="text-sm text-slate-500">
            <strong>Promotion d'une classe entière.</strong> Inscrit tous les élèves d'UNE classe
            précise dans une nouvelle année, avec affectation optionnelle à une nouvelle classe.
            Les élèves sans autre décision suivent tous le même parcours.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="label">Classe source</label>
              <SearchableSelect options={classOptionsAllYears} value={byClassSrc} onChange={setByClassSrc} placeholder="— Sélectionner —" />
            </div>
            <div>
              <label className="label">Année cible</label>
              <SearchableSelect options={yearOptions} value={byClassYear} onChange={(v) => { setByClassYear(v); setByClassDst(""); }} placeholder="— Sélectionner —" />
            </div>
            <div>
              <label className="label">Nouvelle classe (optionnel)</label>
              <SearchableSelect
                options={byClassYear ? classOptionsForYear(byClassYear) : []}
                value={byClassDst} onChange={setByClassDst}
                placeholder={byClassYear ? "— Même classe —" : "— Choisir d'abord l'année cible —"} />
            </div>
          </div>
          <ResultBanner result={byClassResult} onClear={() => setByClassResult(null)} />
          <button
            type="button"
            onClick={() => {
              if (!byClassSrc || !byClassYear) return toast.error("Classe source et année cible requises.");
              bulkClassMut.mutate();
            }}
            disabled={bulkClassMut.isPending}
            className="btn-primary flex items-center gap-2"
          >
            <School className={`w-4 h-4 ${bulkClassMut.isPending ? "animate-spin" : ""}`} />
            {bulkClassMut.isPending ? "Passage en cours..." : "Passer cette classe"}
          </button>
        </div>
      )}

      {/* ── Tab 3 : Inscription individuelle ──────────────────────────────── */}
      {tab === "individual" && (
        <div className="card space-y-4">
          <h3 className="font-bold text-slate-800">Inscription individuelle</h3>
          <p className="text-sm text-slate-500">
            <strong>Un seul élève à la fois.</strong> Inscrivez un nouvel élève, réinscrivez un
            élève existant dans une nouvelle année, ou transférez-le vers une autre classe.
            Pour promouvoir une classe ou un niveau entier, utilisez plutôt
            « Passage par classe », « Passage de niveau » ou « Assistant fin d'année ».
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Élève *</label>
              <SearchableSelect options={studentOptions} value={indivStudent} onChange={setIndivStudent} placeholder="— Sélectionner un élève —" />
            </div>
            <div>
              <label className="label">Année scolaire cible *</label>
              <SearchableSelect options={yearOptions} value={indivYear} onChange={(v) => { setIndivYear(v); setIndivClass(""); }} placeholder="— Sélectionner —" />
            </div>
            <div>
              <label className="label">Classe cible (optionnel)</label>
              <SearchableSelect
                options={indivYear ? classOptionsForYear(indivYear) : []}
                value={indivClass} onChange={setIndivClass}
                placeholder={indivYear ? "— Sans classe —" : "— Choisir d'abord l'année cible —"} />
            </div>
            <div>
              <label className="label">Statut de passage</label>
              <select value={indivStatus} onChange={e => setIndivStatus(e.target.value)} className="input">
                {PROMOTION_STATUSES.map(s => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="label">Note / Observation (optionnel)</label>
            <textarea
              value={indivNote}
              onChange={e => setIndivNote(e.target.value)}
              rows={2}
              className="input resize-none"
              placeholder="Raison du transfert, mention spéciale..."
            />
          </div>
          <ResultBanner result={indivResult} onClear={() => setIndivResult(null)} />
          <button
            type="button"
            onClick={() => {
              if (!indivStudent) return toast.error("Sélectionnez un élève.");
              if (!indivYear)    return toast.error("Sélectionnez une année scolaire.");
              indivMut.mutate();
            }}
            disabled={indivMut.isPending}
            className="btn-primary flex items-center gap-2"
          >
            <Users className={`w-4 h-4 ${indivMut.isPending ? "animate-spin" : ""}`} />
            {indivMut.isPending ? "Inscription en cours..." : "Inscrire cet élève"}
          </button>
        </div>
      )}

      {/* ── Tab 4 : Assistant fin d'année ─────────────────────────────────── */}
      {tab === "eoy" && (
        <div className="space-y-4">
          <div className="card space-y-4">
            <h3 className="font-bold text-slate-800">Assistant de fin d'année</h3>
            <p className="text-sm text-slate-500">
              Gérez en une seule opération les décisions de passage, redoublement,
              exclusion ou départ pour plusieurs élèves simultanément.
            </p>

            <div>
              <label className="label">Année scolaire cible (nouvelle année) *</label>
              <div className="sm:w-1/2">
                <SearchableSelect options={yearOptions} value={eoyYear} onChange={(v) => { setEoyYear(v); setEoyClass(""); }} placeholder="— Sélectionner —" />
              </div>
            </div>

            {/* Formulaire d'ajout de décision */}
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
              <h4 className="text-sm font-semibold text-slate-700">Ajouter une décision</h4>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="label">Élève</label>
                  <SearchableSelect options={studentOptions} value={eoyStudentId} onChange={setEoyStudentId} placeholder="— Sélectionner un élève —" />
                </div>
                <div>
                  <label className="label">Action</label>
                  <select value={eoyAction} onChange={e => setEoyAction(e.target.value)} className="input">
                    {[
                      { value: "promote",  label: "Passage normal" },
                      { value: "honor",    label: "Passage avec mention" },
                      { value: "repeat",   label: "Redoublement" },
                      { value: "transfer", label: "Transfert de filière" },
                      { value: "graduate", label: "Diplômation" },
                      { value: "depart",   label: "Départ (retraite)" },
                      { value: "exclude",  label: "Exclusion" },
                    ].map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </div>
                {["promote", "honor", "repeat", "transfer"].includes(eoyAction) && (
                  <div>
                    <label className="label">Nouvelle classe (optionnel)</label>
                    <SearchableSelect
                      options={eoyYear ? classOptionsForYear(eoyYear) : []}
                      value={eoyClass} onChange={setEoyClass}
                      placeholder={eoyYear ? "— Non affectée —" : "— Choisir d'abord l'année cible —"} />
                  </div>
                )}
              </div>
              {["depart", "exclude", "graduate"].includes(eoyAction) && (
                <div>
                  <label className="label">Motif (optionnel)</label>
                  <input
                    value={eoyReason}
                    onChange={e => setEoyReason(e.target.value)}
                    className="input"
                    placeholder="Raison ou observations..."
                  />
                </div>
              )}
              <button
                type="button"
                onClick={addEoyDecision}
                className="btn-secondary text-sm"
              >
                + Ajouter cette décision
              </button>
            </div>

            {/* Liste des décisions */}
            {eoyDecisions.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-semibold text-slate-700">
                  {eoyDecisions.length} décision(s) en attente
                </h4>
                {eoyDecisions.map((d) => (
                  <div key={d.student_id}
                    className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm">
                    <div className="flex items-center gap-3">
                      <BookOpen className="w-4 h-4 text-slate-400" />
                      <span className="font-medium text-slate-800">{d.student_name}</span>
                      <span className="text-slate-500">→</span>
                      <span className="text-primary font-medium">{ACTION_LABELS[d.action] || d.action}</span>
                      {d.class_id && (
                        <span className="text-xs bg-slate-100 rounded px-1.5 py-0.5 text-slate-600">
                          Classe #{d.class_id}
                        </span>
                      )}
                      {d.reason && (
                        <span className="text-xs text-slate-400 italic">{d.reason}</span>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={() => removeEoyDecision(d.student_id)}
                      className="text-red-400 hover:text-red-600 ml-4"
                    >
                      <XCircle className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <ResultBanner result={eoyResult} onClear={() => setEoyResult(null)} />

            <button
              type="button"
              onClick={() => {
                if (!eoyYear)               return toast.error("Sélectionnez une année cible.");
                if (eoyDecisions.length === 0) return toast.error("Ajoutez au moins une décision.");
                eoyMut.mutate();
              }}
              disabled={eoyMut.isPending || eoyDecisions.length === 0}
              className="btn-primary flex items-center gap-2 disabled:opacity-50"
            >
              <GraduationCap className={`w-4 h-4 ${eoyMut.isPending ? "animate-spin" : ""}`} />
              {eoyMut.isPending
                ? "Application en cours..."
                : `Appliquer ${eoyDecisions.length} décision(s)`}
            </button>
          </div>
        </div>
      )}

      {/* ── Tab 5 : Historique ────────────────────────────────────────────── */}
      {tab === "history" && (
        <div className="card space-y-4">
          <h3 className="font-bold text-slate-800">Parcours académique d'un élève</h3>
          <div className="flex gap-3">
            <div className="flex-1">
              <SearchableSelect options={studentOptions} value={histStudent} onChange={setHistStudent} placeholder="— Sélectionner un élève —" />
            </div>
            <button
              type="button"
              onClick={() => refetchHist()}
              disabled={!histStudent || histLoading}
              className="btn-secondary flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${histLoading ? "animate-spin" : ""}`} />
              Consulter
            </button>
          </div>

          {history.length > 0 ? (
            <div className="space-y-3">
              {history.map((e, i) => (
                <div key={e.id}
                  className={`rounded-xl border px-4 py-3 text-sm ${
                    e.is_current_year
                      ? "border-emerald-200 bg-emerald-50"
                      : "border-slate-200 bg-white"
                  }`}>
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-1 text-xs text-slate-400 w-5 justify-center font-bold">
                      {i + 1}
                    </div>
                    <div className="flex-1 grid grid-cols-2 sm:grid-cols-4 gap-2">
                      <div>
                        <p className="text-xs text-slate-400">Année</p>
                        <p className="font-medium text-slate-800">{e.school_year_name || `Année #${e.school_year}`}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-400">Classe</p>
                        <p className="font-medium text-slate-800">{e.class_name || "—"}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-400">Décision</p>
                        {statusBadge(e.promotion_status)}
                      </div>
                      <div>
                        <p className="text-xs text-slate-400">Inscrit le</p>
                        <p className="text-slate-600">{e.enrolled_at?.slice(0, 10) || "—"}</p>
                      </div>
                    </div>
                    {e.is_current_year && (
                      <span className="text-xs bg-emerald-600 text-white rounded-full px-2 py-0.5 font-medium">
                        Année active
                      </span>
                    )}
                  </div>
                  {e.stats && (
                    <div className="mt-3 pt-3 border-t border-slate-200/70 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 text-xs">
                      <div><p className="text-slate-400">Moyenne</p><p className="font-semibold text-slate-800">{e.stats.grades_average != null ? `${e.stats.grades_average}/20` : "—"}</p></div>
                      <div><p className="text-slate-400">Notes</p><p className="font-semibold text-slate-800">{e.stats.grades_count}</p></div>
                      <div><p className="text-slate-400">Absences</p><p className="font-semibold text-slate-800">{e.stats.absences}</p></div>
                      <div><p className="text-slate-400">Retards</p><p className="font-semibold text-slate-800">{e.stats.lates}</p></div>
                      <div><p className="text-slate-400">Paiements</p><p className="font-semibold text-slate-800">{e.stats.payments_total ? `${e.stats.payments_total.toLocaleString("fr-FR")} FCFA` : "0 FCFA"}</p></div>
                      <div><p className="text-slate-400">Bulletins</p><p className="font-semibold text-slate-800">{e.stats.bulletins_count}</p></div>
                      <div><p className="text-slate-400">Devoirs</p><p className="font-semibold text-slate-800">{e.stats.homework_count}</p></div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : histStudent && !histLoading ? (
            <div className="text-center py-8 text-slate-400">
              <History className="w-10 h-10 mx-auto mb-2 opacity-40" />
              <p>Aucun historique trouvé pour cet élève.</p>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
