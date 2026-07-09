import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { homeworkAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import Modal from "../../components/ui/Modal";
import { CalendarClock, FileText, Download, BookOpen } from "lucide-react";

export default function ParentHomework() {
  const [selected, setSelected] = useState(null);
  const { data, isLoading } = useQuery({ queryKey: ["parent-homework"], queryFn: () => homeworkAPI.list() });
  const homework = data?.data?.results || data?.data || [];

  const cols = [
    { key: "title", label: "Titre", accessor: "title" },
    { key: "class", label: "Classe", accessor: "class_name" },
    { key: "subject", label: "Matière", accessor: "subject_name" },
    { key: "due", label: "Date limite", render: r => (
      <span className={`flex items-center gap-1 text-sm ${new Date(r.due_date) < new Date() ? "text-danger font-medium" : "text-slate-700"}`}>
        <CalendarClock className="w-3 h-3" />{r.due_date}
      </span>
    )},
    { key: "att", label: "Pièces jointes", sortable: false, render: r => (
      (r.attachments?.length > 0)
        ? <span className="text-xs text-primary font-medium">{r.attachments.length} fichier(s)</span>
        : <span className="text-xs text-slate-400">—</span>
    )},
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Devoirs" subtitle="Devoirs des classes de mes enfants" />
      <div className="card">
        <DataTable columns={cols} data={homework} loading={isLoading} onRowClick={row => setSelected(row)} />
      </div>

      <Modal open={!!selected} onClose={() => setSelected(null)} title={selected?.title || "Devoir"} size="md">
        {selected && (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2 text-xs text-slate-500">
              <span className="bg-slate-100 px-2 py-1 rounded-lg">{selected.class_name}</span>
              <span className="bg-slate-100 px-2 py-1 rounded-lg">{selected.subject_name}</span>
              <span className={`px-2 py-1 rounded-lg font-medium ${new Date(selected.due_date) < new Date() ? "bg-danger-50 text-danger" : "bg-success-50 text-success"}`}>
                <CalendarClock className="w-3 h-3 inline mr-1" />Rendu le {selected.due_date}
              </span>
            </div>
            <div className="bg-slate-50 rounded-xl p-4">
              <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">{selected.description}</p>
            </div>
            {selected.attachments?.length > 0 && (
              <div>
                <p className="text-sm font-semibold text-slate-700 mb-2 flex items-center gap-2">
                  <FileText className="w-4 h-4" />Pièces jointes
                </p>
                <div className="space-y-2">
                  {selected.attachments.map(att => (
                    <a key={att.id} href={att.file} target="_blank" rel="noreferrer"
                      className="flex items-center gap-2 p-3 bg-primary-50 rounded-xl text-sm text-primary hover:bg-primary-100 transition-colors">
                      <Download className="w-4 h-4 shrink-0" />
                      <span className="truncate">{att.name || "Fichier"}</span>
                    </a>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
