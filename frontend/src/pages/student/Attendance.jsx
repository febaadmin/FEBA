import { useQuery } from "@tanstack/react-query";
import { attendanceAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import StatusBadge from "../../components/ui/StatusBadge";
import { t } from "../../i18n";

export default function StudentAttendance() {
  const { data, isLoading } = useQuery({ queryKey: ["student-attendance"], queryFn: () => attendanceAPI.list() });
  const records = data?.data?.results || data?.data || [];
  const absent = records.filter(r => r.status === "absent").length;
  const late = records.filter(r => r.status === "late").length;

  const cols = [
    { key: "date", label: t("Date"), accessor: "date" },
    { key: "status", label: t("Statut"), accessor: "status", render: r => <StatusBadge status={r.status} /> },
    { key: "justification", label: t("Justification"), accessor: "justification", render: r => r.justification || "—" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title={t("Mes Absences")} subtitle={t("{a} absence(s) • {b} retard(s)", { a: absent, b: late })} />
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: t("Total"), value: records.length, color: "text-slate-700" },
          { label: t("Absences"), value: absent, color: "text-danger" },
          { label: t("Retards"), value: late, color: "text-amber-600" },
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