import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { bulletinsAPI, schoolsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import { Download, FileText } from "lucide-react";

export default function ParentBulletins() {
  const [selectedYear, setSelectedYear] = useState("");

  // Active year for default filtering
  const { data: yearsData } = useQuery({ queryKey: ["years"], queryFn: schoolsAPI.years });
  const years = yearsData?.data?.results || yearsData?.data || [];
  const activeYear = years.find(y => y.is_current);

  const yearId = selectedYear || activeYear?.id;

  const { data, isLoading } = useQuery({
    queryKey: ["parent-bulletins", yearId],
    queryFn: () => bulletinsAPI.list(yearId ? { school_year: yearId } : {}),
  });
  const bulletins = data?.data?.results || data?.data || [];

  const cols = [
    { key: "student", label: "Élève", accessor: "student_name" },
    { key: "class",   label: "Classe", accessor: "student_class" },
    { key: "period",  label: "Période", accessor: "period_label" },
    { key: "year",    label: "Année", accessor: "school_year_name" },
    { key: "avg",     label: "Moyenne", render: r => r.average
        ? <span className="font-bold text-primary">{parseFloat(r.average).toFixed(2)}/20</span>
        : "—" },
    { key: "rank",    label: "Rang", render: r => r.rank_in_class ? `${r.rank_in_class}e` : "—" },
    { key: "appreciation", label: "Appréciation", accessor: "appreciation" },
    { key: "pdf", label: "PDF", accessor: "pdf_url", sortable: false,
      render: r => (r.pdf_url || r.pdf_file)
        ? <a href={r.pdf_url || r.pdf_file} target="_blank" rel="noreferrer"
             className="flex items-center gap-1 text-xs text-primary hover:underline font-medium">
            <Download className="w-3 h-3" />Télécharger
          </a>
        : <span className="text-xs text-slate-400">En cours</span>
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Bulletins scolaires" subtitle="Bulletins de mes enfants" />

      {/* Year filter */}
      <div className="card flex gap-3 items-center flex-wrap">
        <span className="text-sm font-medium text-slate-600">Année :</span>
        <button onClick={() => setSelectedYear("")}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${!selectedYear ? "bg-primary text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
          {activeYear ? activeYear.name : "Active"}
        </button>
        {years.filter(y => !y.is_current).map(y => (
          <button key={y.id} onClick={() => setSelectedYear(String(y.id))}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${selectedYear === String(y.id) ? "bg-primary text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
            {y.name}
          </button>
        ))}
      </div>

      {bulletins.length === 0 && !isLoading ? (
        <div className="card text-center py-12 text-slate-400">
          <FileText className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>Aucun bulletin disponible pour cette période</p>
        </div>
      ) : (
        <div className="card"><DataTable columns={cols} data={bulletins} loading={isLoading} /></div>
      )}
    </div>
  );
}
