import { useQuery } from "@tanstack/react-query";
import { attendanceAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import StatusBadge from "../../components/ui/StatusBadge";

export default function StudentAttendance() {
  const { data, isLoading } = useQuery({ queryKey: ["student-attendance"], queryFn: () => attendanceAPI.list() });
  const records = data?.data?.results || data?.data || [];
  const absent = records.filter(r => r.status === "absent").length;
  const late = records.filter(r => r.status === "late").length;

  const cols = [
    { key: "date", label: "Date", accessor: "date" },
    { key: "status", label: "Statut", accessor: "status", render: r => <StatusBadge status={r.status} /> },
    { key: "justification", label: "Justification", accessor: "justification", render: r => r.justification || "—" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Mes Absences" subtitle={`${absent} absence(s) • ${late} retard(s)`} />
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Total", value: records.length, color: "text-slate-700" },
          { label: "Absences", value: absent, color: "text-danger" },
          { label: "Retards", value: late, color: "text-amber-600" },
        ].map(stat => (
          <div key={stat.label} className="card text-center">
            <p className={`text-3xl font-bold ${stat.color}`}>{stat.value}</p>
            <p className="text-sm text-slate-500 mt-1">{stat.label}</p>
          </div>
        ))}
      </div>
      <div className="card"><DataTable columns={cols} data={records} loading={isLoading} /></div>
    </div>
  );
}