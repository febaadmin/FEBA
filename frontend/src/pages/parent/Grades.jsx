/**
 * ParentGrades — v26 CORRIGÉ
 *
 * CORRECTIONS :
 *  1. Affichage des moyennes FR / EN / Bilingue par enfant et par période
 *  2. Appel correct à gradesAPI.averages avec le param `student`
 *  3. Cartes de synthèse par enfant avant le tableau de notes
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { gradesAPI, parentsAPI, schoolsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import { TrendingUp, BookOpen, Globe } from "lucide-react";

/* ── Carte moyenne ──────────────────────────────────────────────────────────── */
function AvgCard({ label, value, icon: Icon, color }) {
  const colors = {
    blue:   { bg: "bg-blue-50",   text: "text-blue-600",   badge: "bg-blue-100" },
    green:  { bg: "bg-green-50",  text: "text-green-600",  badge: "bg-green-100" },
    purple: { bg: "bg-purple-50", text: "text-purple-600", badge: "bg-purple-100" },
    amber:  { bg: "bg-amber-50",  text: "text-amber-600",  badge: "bg-amber-100" },
  };
  const c = colors[color] || colors.blue;
  const num = value != null ? Number(value) : null;
  const noteClr = num == null ? "" : num >= 14 ? "text-green-600" : num >= 10 ? "text-amber-600" : "text-red-500";
  return (
    <div className={`${c.bg} rounded-2xl p-4 flex items-center gap-3`}>
      <div className={`${c.badge} p-2 rounded-xl`}><Icon className={`w-5 h-5 ${c.text}`} /></div>
      <div>
        <p className="text-xs font-medium text-slate-500">{label}</p>
        <p className={`text-2xl font-extrabold ${num == null ? "text-slate-300" : noteClr}`}>
          {num != null ? `${num.toFixed(2)}/20` : "—"}
        </p>
      </div>
    </div>
  );
}

/* ── Bloc moyennes d'un enfant ────────────────────────────────────────────── */
function ChildAverages({ child, period, schoolYearId }) {
  const { data: avgData } = useQuery({
    queryKey: ["parent-avg", child.id, period || "all", schoolYearId],
    queryFn: () => gradesAPI.averages({ student: child.id, period: period || undefined, school_year: schoolYearId }),
    enabled: !!child.id && !!schoolYearId,
  });
  const { data: biData } = useQuery({
    queryKey: ["parent-bilingual", child.id, period || "all", schoolYearId],
    queryFn: () => gradesAPI.bilingual({ student: child.id, period: period || undefined, school_year: schoolYearId }),
    enabled: !!child.id && !!schoolYearId,
  });

  const avg = avgData?.data;
  const bi  = biData?.data;

  return (
    <div>
      <p className="text-xs font-bold text-slate-500 mb-2 uppercase tracking-wide">{child.first_name} {child.last_name}</p>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <AvgCard label="Moy. Générale"  value={avg?.overall_average}  icon={TrendingUp} color="blue"   />
        <AvgCard label="Moy. Française" value={bi?.french_average}    icon={BookOpen}   color="green"  />
        <AvgCard label="Moy. Anglaise"  value={bi?.english_average}   icon={Globe}      color="amber"  />
        <AvgCard label="Moy. Bilingue"  value={bi?.bilingual_average} icon={TrendingUp} color="purple" />
      </div>
    </div>
  );
}

/* ── Composant principal ─────────────────────────────────────────────────── */
export default function ParentGrades() {
  const [selectedChild,  setSelectedChild]  = useState("");
  const [selectedPeriod, setSelectedPeriod] = useState("");

  const { data: meData }    = useQuery({ queryKey: ["parent-me"],  queryFn: parentsAPI.me });
  const { data: yearsData } = useQuery({ queryKey: ["years"],      queryFn: schoolsAPI.years });

  const children  = (meData?.data?.children_links || []).map(l => l.student_detail).filter(Boolean);
  const years     = yearsData?.data?.results || yearsData?.data || [];
  const activeYear = years.find(y => y.is_current);

  // Enfants à afficher (filtrés ou tous)
  const displayedChildren = selectedChild
    ? children.filter(c => String(c.id) === selectedChild)
    : children;

  const gradesParams = {
    ...(activeYear    && { school_year: activeYear.id }),
    ...(selectedPeriod && { period: selectedPeriod }),
    ...(selectedChild  && { student: selectedChild }),
  };

  const { data, isLoading } = useQuery({
    queryKey: ["parent-grades", activeYear?.id, selectedPeriod, selectedChild],
    queryFn: () => gradesAPI.list(gradesParams),
    enabled: !!activeYear,
  });

  const grades = data?.data?.results || data?.data || [];

  const noteColor = (v) => {
    const n = parseFloat(v);
    if (n >= 14) return "text-green-600 font-bold";
    if (n >= 10) return "text-amber-600";
    return "text-red-500";
  };

  const PERIODS = [
    { value: "",       label: "Toutes périodes" },
    { value: "T1",     label: "Trimestre 1" },
    { value: "T2",     label: "Trimestre 2" },
    { value: "T3",     label: "Trimestre 3" },
    { value: "annual", label: "Annuel" },
  ];

  const cols = [
    { key: "student", label: "Élève",       accessor: "student_name" },
    { key: "subject", label: "Matière",     accessor: "subject_name" },
    { key: "period",  label: "Période",     accessor: "period_label" },
    { key: "value",   label: "Note",        render: r => <span className={noteColor(r.value)}>{r.value}/20</span> },
    { key: "coeff",   label: "Coeff",       accessor: "subject_coefficient" },
    { key: "appr",    label: "Appréciation",accessor: "appreciation" },
    { key: "comment", label: "Commentaire", render: r => r.comment || "—" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Notes de mes enfants"
        subtitle={`${grades.length} note(s)${activeYear ? ` — ${activeYear.name}` : ""}`}
      />

      {/* ── Filtres ────────────────────────────────────────────────────────── */}
      <div className="card flex gap-3 flex-wrap items-center">
        {children.length > 1 && (
          <div className="flex gap-2 flex-wrap">
            <button onClick={() => setSelectedChild("")}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${!selectedChild ? "bg-amber-500 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
              Tous
            </button>
            {children.map(c => (
              <button key={c.id} onClick={() => setSelectedChild(String(c.id))}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${selectedChild === String(c.id) ? "bg-amber-500 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
                {c.first_name}
              </button>
            ))}
          </div>
        )}
        <select value={selectedPeriod} onChange={e => setSelectedPeriod(e.target.value)}
          className="input text-sm">
          {PERIODS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
        </select>
        {activeYear && (
          <span className="ml-auto text-xs text-slate-400 bg-slate-50 px-3 py-1.5 rounded-lg">
            📅 {activeYear.name}
          </span>
        )}
      </div>

      {/* ── Cartes de moyennes par enfant ────────────────────────────────── */}
      {activeYear && displayedChildren.length > 0 && (
        <div className="space-y-4">
          {displayedChildren.map(child => (
            <div key={child.id} className="card space-y-3">
              <ChildAverages child={child} period={selectedPeriod} schoolYearId={activeYear.id} />
            </div>
          ))}
        </div>
      )}

      {/* ── Tableau de notes ─────────────────────────────────────────────── */}
      <div className="card">
        <DataTable columns={cols} data={grades} loading={isLoading} />
      </div>
    </div>
  );
}
