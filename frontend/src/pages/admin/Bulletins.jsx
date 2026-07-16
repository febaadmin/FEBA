/**
 * AdminBulletins — v20 CORRIGÉ
 * 
 * Corrections :
 *  - Filtre par année (boutons par année, défaut = année active)
 *  - Bouton "Toutes les années" pour voir l'archive complète
 *  - `data` déclaré dans le bon ordre (après currentYear)
 *  - Suppression du doublon de variable data (state vs query)
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { FileText, Download, RefreshCw, Users } from "lucide-react";
import { useForm, Controller } from "react-hook-form";
import toast from "react-hot-toast";
import { bulletinsAPI, studentsAPI, classesAPI, schoolsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import Modal from "../../components/ui/Modal";
import SearchableSelect from "../../components/ui/SearchableSelect";
import { extractApiError } from "../../utils/errors";
import { t } from "../../i18n";

const PERIODS = [
  { value: "T1", label: "Trimestre 1" },
  { value: "T2", label: "Trimestre 2" },
  { value: "T3", label: "Trimestre 3" },
  { value: "annual", label: "Annuel" },
];

export default function AdminBulletins() {
  const qc = useQueryClient();
  const [genOpen, setGenOpen] = useState(false);
  const [genMode, setGenMode] = useState("student"); // "student" | "class" | "all"
  const [filterYear, setFilterYear] = useState(""); // "" = année active, "all" = toutes
  const { register, handleSubmit, reset, control } = useForm();

  // 1. D'abord les données de référence
  const { data: studData } = useQuery({ queryKey: ["students-all"], queryFn: () => studentsAPI.list() });
  const { data: classData } = useQuery({ queryKey: ["classes"], queryFn: () => classesAPI.list() });
  const { data: yearsData } = useQuery({ queryKey: ["years"], queryFn: schoolsAPI.years });

  const students   = studData?.data?.results   || studData?.data   || [];
  const classes    = classData?.data?.results  || classData?.data  || [];
  const years      = yearsData?.data?.results  || yearsData?.data  || [];
  const currentYear = years.find(y => y.is_current);

  // 2. Bulletins filtrés par année (FIX v20 : par défaut = année active)
  const activeYearId = filterYear === "all" ? "" : (filterYear || currentYear?.id || "");
  const { data: bulletinData, isLoading, refetch } = useQuery({
    queryKey: ["bulletins", activeYearId],
    queryFn: () => bulletinsAPI.list(activeYearId ? { school_year: activeYearId } : {}),
    enabled: years.length > 0,
  });

  const bulletins    = bulletinData?.data?.results || bulletinData?.data || [];
  const studentOpts  = students.map(s => ({ value: s.id, label: `${s.full_name} — ${s.class_name || "?"}` }));

  const genMut = useMutation({
    mutationFn: (d) => {
      if (genMode === "class") return bulletinsAPI.generateClass(d);
      if (genMode === "all")   return bulletinsAPI.generateAll(d);
      return bulletinsAPI.generate(d);
    },
    onSuccess: (res) => {
      const resData = res.data;
      if (resData?.pdf_url || resData?.pdf_file || resData?.student) {
        toast.success(t("Bulletin généré avec succès ! PDF disponible."));
      } else {
        toast.success(resData?.detail || "Bulletin(s) en cours de génération…");
      }
      setGenOpen(false);
      reset();
      setTimeout(() => { refetch(); qc.invalidateQueries({ queryKey: ["bulletins"] }); }, 3000);
    },
    onError: (e) => {
      const msg = e.response?.data?.error || e.response?.data?.detail || "Erreur lors de la génération";
      toast.error(msg);
    },
  });

  const onSubmit = (d) => {
    const payload = { ...d };
    if (!payload.school_year_id && currentYear) payload.school_year_id = currentYear.id;
    genMut.mutate(payload);
  };

  const cols = [
    { key: "student",      label: t("Élève"),        accessor: "student_name" },
    { key: "class",        label: t("Classe"),        accessor: "student_class" },
    { key: "period",       label: t("Période"),       accessor: "period_label" },
    { key: "year",         label: t("Année"),         accessor: "school_year_name" },
    { key: "avg",          label: t("Moyenne"),       render: r => r.average ? `${parseFloat(r.average).toFixed(2)}/20` : "—" },
    { key: "appreciation", label: t("Appréciation"),  accessor: "appreciation" },
    { key: "date",         label: t("Généré le"),     render: r => r.generated_at?.slice(0, 10) },
  ];

  const bulkDeleteMut = useMutation({
    mutationFn: (ids) => bulletinsAPI.bulkDelete(ids),
    onSuccess: (data) => { qc.invalidateQueries({ queryKey: ["bulletins"] }); toast.success(t("{n} élément(s) supprimé(s).", { n: data?.data?.deleted || "" })); },
    onError: (e) => toast.error(extractApiError(e)),
  });

  return (
    <div className="space-y-6">
      <PageHeader title={t("Bulletins")} subtitle={t("Génération et archive des bulletins PDF")}
        action={
          <div className="flex gap-2 flex-wrap">
            <button onClick={() => refetch()} className="btn-secondary flex items-center gap-2">
              <RefreshCw className="w-4 h-4" />{t("Rafraîchir")}</button>
            <button onClick={() => { reset({ school_year_id: currentYear?.id || "" }); setGenMode("student"); setGenOpen(true); }}
              className="btn-primary flex items-center gap-2">
              <FileText className="w-4 h-4" />{t("Générer un bulletin")}</button>
            <button onClick={() => { reset({ school_year_id: currentYear?.id || "" }); setGenMode("class"); setGenOpen(true); }}
              className="btn-secondary flex items-center gap-2">
              <Users className="w-4 h-4" />{t("Par classe")}</button>
            <button onClick={() => { reset({ school_year_id: currentYear?.id || "" }); setGenMode("all"); setGenOpen(true); }}
              className="btn-secondary flex items-center gap-2 text-xs">{t("Tous les élèves")}</button>
          </div>
        } />

      {/* FIX v20 : Filtre par année scolaire */}
      <div className="card flex gap-2 items-center flex-wrap">
        <span className="text-sm font-medium text-slate-600">{t("Filtrer par année :")}</span>
        <button onClick={() => setFilterYear("")}
          className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${filterYear === "" ? "bg-primary text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
          Année active {currentYear ? `(${currentYear.name})` : ""}
        </button>
        {years.filter(y => !y.is_current).map(y => (
          <button key={y.id} onClick={() => setFilterYear(String(y.id))}
            className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${filterYear === String(y.id) ? "bg-primary text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>
            {y.name}
          </button>
        ))}
        <button onClick={() => setFilterYear("all")}
          className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${filterYear === "all" ? "bg-slate-700 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>{t("Toutes les années")}</button>
      </div>

      <div className="card">
        {/* FIX BUG N°9 (audit) : les props selectable / onBulkDelete /
            bulkDeletePending étaient posées par erreur sur l'icône <Download>
            (warnings React « unknown prop » + sélection groupée inopérante).
            Elles appartiennent à DataTable. */}
        <DataTable
          columns={cols}
          data={bulletins}
          loading={isLoading}
          selectable
          onBulkDelete={ids => bulkDeleteMut.mutate(ids)}
          bulkDeletePending={bulkDeleteMut.isPending}
          actions={row => (
            (row.pdf_url || row.pdf_file) ? (
              <a href={row.pdf_url || row.pdf_file} target="_blank" rel="noreferrer"
                className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs bg-primary-50 text-primary hover:bg-primary-100 font-medium">
                <Download className="w-3 h-3" />{t("PDF")}</a>
            ) : <span className="text-xs text-slate-400">{t("En cours…")}</span>
          )} />
      </div>

      <Modal open={genOpen} onClose={() => { setGenOpen(false); reset(); }}
        title={genMode === "class" ? "Générer bulletins d'une classe" : genMode === "all" ? t("Générer tous les bulletins") : t("Générer un bulletin")}>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {genMode === "all" && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm text-amber-700">
              ⚠️ Génération des bulletins PDF de <strong>{t("tous les élèves actifs")}</strong>.
              Les bulletins existants seront remplacés.
            </div>
          )}
          {genMode === "student" && (
            <div>
              <label className="label">{t("Élève*")}</label>
              <Controller name="student_id" control={control} rules={{ required: true }}
                render={({ field }) => (
                  <SearchableSelect options={studentOpts} value={field.value} onChange={field.onChange}
                    placeholder={t("Rechercher un élève…")} />
                )} />
            </div>
          )}
          {genMode === "class" && (
            <div>
              <label className="label">{t("Classe*")}</label>
              <select {...register("class_id", { required: true })} className="input">
                <option value="">-- Sélectionner --</option>
                {classes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
          )}
          <div>
            <label className="label">{t("Période*")}</label>
            <select {...register("period", { required: true })} className="input">
              {PERIODS.map(p => <option key={p.value} value={p.value}>{t(p.label)}</option>)}
            </select>
          </div>
          <div>
            <label className="label">{t("Année scolaire*")}</label>
            <select {...register("school_year_id", { required: true })} className="input">
              <option value="">-- Sélectionner --</option>
              {years.map(y => <option key={y.id} value={y.id}>{y.name}{y.is_current ? " ✓" : ""}</option>)}
            </select>
          </div>
          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={() => { setGenOpen(false); reset(); }} className="btn-secondary">{t("Annuler")}</button>
            <button type="submit" disabled={genMut.isPending} className="btn-primary">
              {genMut.isPending ? t("Génération…") : t("Générer")}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
