import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { attendanceAPI, parentsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import StatusBadge from "../../components/ui/StatusBadge";

export default function ParentAttendance() {
  const [selectedChild, setSelectedChild] = useState("");

  const { data: meData } = useQuery({ queryKey: ["parent-me"], queryFn: parentsAPI.me });
  const children = (meData?.data?.children_links || []).map(l => l.student_detail).filter(Boolean);

  // BUG FIX #2: pass all_years=1 pour ne pas filtrer par année scolaire
  // (certains enregistrements peuvent avoir school_year=null)
  const { data, isLoading } = useQuery({
    queryKey: ["parent-attendance", selectedChild],
    queryFn: () => {
      const params = { all_years: "1" };
      if (selectedChild) params.student = selectedChild;
      return attendanceAPI.list(params);
    },
  });
  const records = data?.data?.results || data?.data || [];

  const cols = [
    { key: "student", label: "Élève", accessor: "student_name" },
    { key: "date", label: "Date", accessor: "date" },
    { key: "status", label: "Statut", render: r => <StatusBadge status={r.status} /> },
    { key: "subject", label: "Matière", render: r => r.subject_name || "—" },
    { key: "justification", label: "Justification", render: r => r.justification || "—" },
  ];

  const absentCount = records.filter(r => r.status === "absent").length;
  const lateCount = records.filter(r => r.status === "late").length;

  return (
    <div className="space-y-6">
      <PageHeader title="Absences de mes enfants"
        subtitle={`${absentCount} absence(s) · ${lateCount} retard(s) · ${records.length} enregistrement(s) total`} />

      {children.length > 1 && (
        <div className="card flex gap-2 flex-wrap">
          <button onClick={() => setSelectedChild("")}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${!selectedChild ? "bg-amber-500 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
            Tous les enfants
          </button>
          {children.map(c => (
            <button key={c.id} onClick={() => setSelectedChild(String(c.id))}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${selectedChild === String(c.id) ? "bg-amber-500 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
              {c.first_name} {c.last_name}
            </button>
          ))}
        </div>
      )}

      {/* Stats rapides */}
      {records.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "Présences", count: records.filter(r => r.status === "present").length, color: "text-emerald-600" },
            { label: "Absences", count: absentCount, color: "text-red-600" },
            { label: "Retards", count: lateCount, color: "text-amber-600" },
          ].map(s => (
            <div key={s.label} className="card text-center py-3">
              <p className={`text-2xl font-bold ${s.color}`}>{s.count}</p>
              <p className="text-xs text-slate-500 mt-1">{s.label}</p>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <DataTable columns={cols} data={records} loading={isLoading} />
      </div>
    </div>
  );
}
