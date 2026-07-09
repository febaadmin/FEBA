import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { bulletinsAPI, schoolsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import { Download, FileText, Award } from "lucide-react";
import { motion } from "framer-motion";

const PERIOD_LABELS = { T1: "Trimestre 1", T2: "Trimestre 2", T3: "Trimestre 3", annual: "Annuel" };

const LETTER_COLORS = {
  "A+": "text-emerald-600", A: "text-emerald-600", "A-": "text-green-600",
  "B+": "text-blue-600", B: "text-blue-500", "B-": "text-sky-600",
  "C+": "text-yellow-600", C: "text-amber-500", "C-": "text-orange-500",
  "D+": "text-red-400", D: "text-red-500", "D-": "text-red-600", F: "text-red-700",
};

export default function StudentBulletins() {
  const [selectedYear, setSelectedYear] = useState("");

  const { data: yearsData } = useQuery({ queryKey: ["years"], queryFn: schoolsAPI.years });
  const years = yearsData?.data?.results || yearsData?.data || [];
  const activeYear = years.find(y => y.is_current);
  const yearId = selectedYear || activeYear?.id;

  const { data, isLoading } = useQuery({
    queryKey: ["student-bulletins", yearId],
    queryFn: () => bulletinsAPI.list(yearId ? { school_year: yearId } : {}),
  });
  const bulletins = data?.data?.results || data?.data || [];

  if (isLoading) return <div className="skeleton h-48 rounded-2xl" />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mes Bulletins"
        subtitle={`${bulletins.length} bulletin(s)${activeYear ? ` — ${activeYear.name}` : ""}`}
      />

      {/* Year selector */}
      {years.length > 1 && (
        <div className="card flex gap-2 flex-wrap items-center">
          <span className="text-sm font-medium text-slate-600">Année :</span>
          <button onClick={() => setSelectedYear("")}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${!selectedYear ? "bg-primary text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
            {activeYear?.name || "Active"}
          </button>
          {years.filter(y => !y.is_current).map(y => (
            <button key={y.id} onClick={() => setSelectedYear(String(y.id))}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${selectedYear === String(y.id) ? "bg-primary text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
              {y.name}
            </button>
          ))}
        </div>
      )}

      {bulletins.length === 0 ? (
        <div className="card text-center py-12 text-slate-400">
          <FileText className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>Aucun bulletin disponible</p>
          <p className="text-xs mt-1">Les bulletins sont générés par l'administration après chaque trimestre.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {bulletins.map((b, i) => {
            const avg = b.average ? parseFloat(b.average) : null;
            const avgColor = avg === null ? "text-slate-400" : avg >= 14 ? "text-green-600" : avg >= 10 ? "text-amber-600" : "text-red-600";
            const letterColor = LETTER_COLORS[b.letter] || "text-slate-600";
            return (
              <motion.div key={b.id}
                initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.08 }}
                className="card border-l-4 border-primary hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Award className="w-4 h-4 text-primary flex-shrink-0" />
                      <p className="font-bold text-slate-800">
                        {PERIOD_LABELS[b.period] || b.period_label || b.period}
                      </p>
                    </div>
                    <p className="text-sm text-slate-500 mb-2">{b.school_year_name}</p>
                    <div className="flex items-center gap-4 flex-wrap">
                      {avg !== null && (
                        <span className={`text-lg font-bold ${avgColor}`}>
                          {avg.toFixed(2)}/20
                        </span>
                      )}
                      {b.rank_in_class && (
                        <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">
                          {b.rank_in_class}e rang
                        </span>
                      )}
                      {b.letter && (
                        <span className={`text-sm font-bold ${letterColor}`}>
                          {b.letter}
                        </span>
                      )}
                      {b.appreciation && (
                        <span className="text-xs text-emerald-600 font-medium">{b.appreciation}</span>
                      )}
                    </div>
                  </div>
                  {(b.pdf_url || b.pdf_file) ? (
                    <a href={b.pdf_url || b.pdf_file} target="_blank" rel="noreferrer"
                      className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-primary text-white text-xs font-semibold hover:bg-primary/90 transition-colors flex-shrink-0">
                      <Download className="w-3.5 h-3.5" />PDF
                    </a>
                  ) : (
                    <span className="text-xs text-slate-400 px-2">En cours...</span>
                  )}
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
