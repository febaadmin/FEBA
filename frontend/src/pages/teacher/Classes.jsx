import { useQuery } from "@tanstack/react-query";
import { classesAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import { Users, ChevronRight, BookOpen } from "lucide-react";
import { motion } from "framer-motion";
import { useState } from "react";
import DataTable from "../../components/ui/DataTable";
import Modal from "../../components/ui/Modal";

export default function TeacherClasses() {
  const [selectedClass, setSelectedClass] = useState(null);
  const { data, isLoading } = useQuery({ queryKey: ["teacher-classes-list"], queryFn: () => classesAPI.list() });
  const { data: studData } = useQuery({
    queryKey: ["class-students", selectedClass?.id],
    queryFn: () => classesAPI.students(selectedClass.id),
    enabled: !!selectedClass,
  });

  const classes = data?.data?.results || data?.data || [];
  const students = studData?.data || [];

  const cols = [
    { key: "name", label: "Nom", accessor: "full_name" },
    { key: "matricule", label: "Matricule", accessor: "matricule" },
    { key: "gender", label: "Genre", accessor: "gender", render: r => r.gender === "M" ? "M" : "F" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Mes Classes" subtitle={`${classes.length} classe(s) assignée(s)`} />

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(3)].map((_,i) => <div key={i} className="skeleton h-28 rounded-2xl" />)}
        </div>
      ) : classes.length === 0 ? (
        <div className="card text-center py-12 text-slate-400">
          <BookOpen className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>Aucune classe assignée. Contactez l'administration.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {classes.map((cls, i) => (
            <motion.div key={cls.id} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08 }}
              onClick={() => setSelectedClass(cls)}
              className="card border-l-4 border-emerald-500 hover:shadow-md transition-all cursor-pointer group">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-bold text-slate-800 text-lg">{cls.name}</p>
                  <p className="text-sm text-slate-500">{cls.level_name} • {cls.school_year_name}</p>
                  <div className="flex items-center gap-1 mt-2 text-xs text-slate-400">
                    <Users className="w-3 h-3" />{cls.student_count ?? 0} élèves inscrits
                  </div>
                </div>
                <ChevronRight className="w-5 h-5 text-slate-300 group-hover:text-emerald-500 transition-colors" />
              </div>
            </motion.div>
          ))}
        </div>
      )}

      <Modal open={!!selectedClass} onClose={() => setSelectedClass(null)}
        title={`Élèves — ${selectedClass?.name}`} size="lg">
        {studData ? (
          students.length > 0 ? (
            <DataTable columns={cols} data={students} />
          ) : (
            <p className="text-center text-slate-400 py-8">Aucun élève dans cette classe</p>
          )
        ) : (
          <div className="skeleton h-40 rounded-xl" />
        )}
      </Modal>
    </div>
  );
}