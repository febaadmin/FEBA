/**
 * AdminBulletins — v20 CORRIGÉ
 * 
 * Corrections :
 *  - Filtre par année (boutons par année, défaut = année active)
 *  - Bouton "Toutes les années" pour voir l'archive complète
 *  - `data` déclaré dans le bon ordre (après currentYear)
 *  - Suppression du doublon de variable data (state vs query)
 */
import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { FileText, Download, RefreshCw, Users, MessageSquare, Eye } from "lucide-react";
import { useForm } from "react-hook-form";
import toast from "react-hot-toast";
import { bulletinsAPI, classesAPI, schoolsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import DataTable from "../../components/ui/DataTable";
import Modal from "../../components/ui/Modal";
import { extractApiError } from "../../utils/errors";
import { t } from "../../i18n";
import { useSchoolYearScope } from "../../hooks/useSchoolYearScope";
import BulletinCommentManager, { OperationReport } from "../../components/bulletins/BulletinCommentManager";
import BulletinPreviewDialog from "../../components/bulletins/BulletinPreviewDialog";

import { ageColumn } from "../../utils/age";
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
  const { register, handleSubmit, reset } = useForm();
  const [commentOpen, setCommentOpen] = useState(false);
  const [commentInitial, setCommentInitial] = useState({});
  const [commentKey, setCommentKey] = useState(0);
  const [genOpId, setGenOpId] = useState(null);
  const openComments = (initial = {}) => {
    setCommentInitial(initial); setCommentKey((k) => k + 1); setCommentOpen(true);
  };
  // Aperçu (moteur officiel, aucune écriture) : point d'entrée de toute
  // génération individuelle, et de la révision avant une génération groupée.
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewInitial, setPreviewInitial] = useState({});
  const [previewKey, setPreviewKey] = useState(0);
  const openPreview = (initial = {}) => {
    setPreviewInitial(initial); setPreviewKey((k) => k + 1); setPreviewOpen(true);
  };
  // Génération groupée : révision (portée, élèves, commentaire commun) avant confirmation.
  const [review, setReview] = useState(null);
  const [commonComment, setCommonComment] = useState("");

  // 1. D'abord les données de référence
  const { data: classData } = useQuery({ queryKey: ["classes"], queryFn: () => classesAPI.list() });
  const { data: yearsData } = useQuery({ queryKey: ["years"], queryFn: schoolsAPI.years });

  const classes    = classData?.data?.results  || classData?.data  || [];
  const years      = yearsData?.data?.results  || yearsData?.data  || [];
  // P2 : en mode « Toutes les Académies », aucune année ne peut
  // représenter les deux académies — voir useSchoolYearScope.
  const { currentYear: currentYear, yearLabel } = useSchoolYearScope(years);

  // 2. Bulletins filtrés par année (FIX v20 : par défaut = année active)
  const activeYearId = filterYear === "all" ? "" : (filterYear || currentYear?.id || "");
  const { data: bulletinData, isLoading, refetch } = useQuery({
    queryKey: ["bulletins", activeYearId],
    queryFn: () => bulletinsAPI.list(activeYearId ? { school_year: activeYearId } : {}),
    enabled: years.length > 0,
  });

  const bulletins    = bulletinData?.data?.results || bulletinData?.data || [];

  const genMut = useMutation({
    mutationFn: (d) => {
      // Commentaire commun : une seule opération applique le commentaire puis
      // génère (création des bulletins absents des élèves notés).
      if (commonComment.trim()) {
        return bulletinsAPI.createOperation({
          scope: genMode === "class" ? "class" : "academy", class_id: d.class_id,
          period: d.period, school_year_id: d.school_year_id, action: "set_comment",
          comment: commonComment, regenerate: true, create_missing: true,
        });
      }
      if (genMode === "class") return bulletinsAPI.generateClass(d);
      return bulletinsAPI.generateAll(d);
    },
    onSuccess: (res) => {
      const resData = res.data;
      if (res.status === 202 && resData?.id) {
        // Classe ou académie : opération réelle du worker, suivie jusqu'au bilan.
        setGenOpId(resData.id);
        toast.success(t("Génération lancée : suivez son avancement ci-dessous."));
      } else {
        toast.success(t("Bulletin généré avec succès ! PDF disponible."));
        qc.invalidateQueries({ queryKey: ["bulletins"] });
      }
      setGenOpen(false);
      setReview(null);
      setCommonComment("");
      reset();
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const reviewMut = useMutation({
    mutationFn: (d) => bulletinsAPI.commentPreview({
      scope: genMode === "class" ? "class" : "academy", class_id: d.class_id,
      period: d.period, school_year_id: d.school_year_id,
    }).then((r) => ({ ...r.data, request: d })),
    onSuccess: (data) => setReview(data),
    onError: (e) => toast.error(extractApiError(e)),
  });

  const { data: genOpData } = useQuery({
    queryKey: ["bulletin-operation", genOpId],
    queryFn: () => bulletinsAPI.operation(genOpId),
    enabled: Boolean(genOpId),
    refetchInterval: (q) => {
      const st = q.state.data?.data?.status;
      return st && st !== "queued" && st !== "running" ? false : 2000;
    },
  });
  const genOp = genOpData?.data;
  const genOpFinished = Boolean(genOp && genOp.status !== "queued" && genOp.status !== "running");
  useEffect(() => {
    if (genOpFinished) qc.invalidateQueries({ queryKey: ["bulletins"] });
  }, [genOpFinished, qc]);

  const onSubmit = (d) => {
    const payload = { ...d };
    if (!payload.school_year_id && currentYear) payload.school_year_id = currentYear.id;
    // 1re étape : révision (aucune génération) ; la génération ne part que
    // depuis le bouton de confirmation de la révision.
    reviewMut.mutate(payload);
  };
  const toGenerate = review ? review.existing_bulletins + review.missing_with_grades : 0;
  const closeGen = () => { setGenOpen(false); setReview(null); setCommonComment(""); reset(); };

  const cols = [
    { key: "student",      label: t("Élève"),        accessor: "student_name" },
    ageColumn("student_age"),
    { key: "class",        label: t("Classe"),        accessor: "student_class" },
    { key: "period",       label: t("Période"),       accessor: "period_label" },
    { key: "year",         label: t("Année"),         accessor: "school_year_name" },
    { key: "avg",          label: t("Moyenne"),       render: r => r.average ? `${parseFloat(r.average).toFixed(2)}/20` : "—" },
    { key: "appreciation", label: t("Appréciation"),  accessor: "appreciation", render: r => r.appreciation ? t(r.appreciation) : "—" },
    { key: "comment",      label: t("Commentaire du directeur"), render: r => (
      <span className="block max-w-[220px] truncate text-xs" title={r.general_comment || ""}>
        {r.general_comment || <span className="text-slate-400">—</span>}
      </span>
    ) },
    { key: "date",         label: t("Généré le"),     render: r => (
      <span>
        {r.generated_at?.slice(0, 10)}
        {r.pdf_outdated && <span className="block text-[10px] text-amber-700">{t("PDF à régénérer")}</span>}
      </span>
    ) },
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
            <button onClick={() => openComments({ yearId: activeYearId || currentYear?.id })}
              className="btn-secondary flex items-center gap-2">
              <MessageSquare className="w-4 h-4" />{t("Commentaires du directeur")}</button>
            <button onClick={() => refetch()} className="btn-secondary flex items-center gap-2">
              <RefreshCw className="w-4 h-4" />{t("Rafraîchir")}</button>
            <button onClick={() => openPreview({ yearId: currentYear?.id })}
              className="btn-primary flex items-center gap-2">
              <FileText className="w-4 h-4" />{t("Prévisualiser / générer un bulletin")}</button>
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

      {genOp && <OperationReport op={genOp} />}

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
            <div className="flex items-center gap-1">
              <button type="button" title={t("Aperçu du bulletin")}
                onClick={() => openPreview({ studentId: row.student, yearId: row.school_year, period: row.period })}
                className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs bg-slate-100 text-slate-700 hover:bg-slate-200 font-medium">
                <Eye className="w-3 h-3" />{t("Aperçu")}</button>
              <button type="button" title={t("Commentaire du directeur")}
                onClick={() => openComments({ scope: "student", studentId: row.student,
                  yearId: row.school_year, period: row.period })}
                className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs bg-slate-100 text-slate-700 hover:bg-slate-200 font-medium">
                <MessageSquare className="w-3 h-3" />{t("Commentaire")}</button>
              {(row.pdf_url || row.pdf_file) ? (
                <a href={row.pdf_url || row.pdf_file} target="_blank" rel="noreferrer"
                  className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs bg-primary-50 text-primary hover:bg-primary-100 font-medium">
                  <Download className="w-3 h-3" />{t("PDF")}</a>
              ) : <span className="text-xs text-slate-400">{t("PDF absent")}</span>}
            </div>
          )} />
      </div>

      <BulletinCommentManager key={commentKey} open={commentOpen} onClose={() => setCommentOpen(false)} initial={commentInitial} />
      <BulletinPreviewDialog key={`p${previewKey}`} open={previewOpen} onClose={() => setPreviewOpen(false)} initial={previewInitial} />

      <Modal open={genOpen} onClose={closeGen} size="lg"
        title={genMode === "class" ? t("Générer les bulletins d'une classe") : t("Générer tous les bulletins")}>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {genMode === "all" && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm text-amber-700">
              ⚠️ {t("Génération des bulletins PDF de tous les élèves actifs de l'académie sélectionnée.")}{" "}
              {t("Les PDF existants seront régénérés ; les commentaires du directeur sont conservés.")}
            </div>
          )}
          {genMode === "class" && (
            <div>
              <label className="label">{t("Classe*")}</label>
              <select {...register("class_id", { required: true })} className="input" disabled={Boolean(review)}>
                <option value="">-- Sélectionner --</option>
                {classes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">{t("Période*")}</label>
              <select {...register("period", { required: true })} className="input" disabled={Boolean(review)}>
                {PERIODS.map(p => <option key={p.value} value={p.value}>{t(p.label)}</option>)}
              </select>
            </div>
            <div>
              <label className="label">{t("Année scolaire*")}</label>
              <select {...register("school_year_id", { required: true })} className="input" disabled={Boolean(review)}>
                <option value="">-- Sélectionner --</option>
                {years.map(y => <option key={y.id} value={y.id}>{y.name}{y.is_current ? " ✓" : ""}</option>)}
              </select>
            </div>
          </div>

          {review && (
            <div className="space-y-3" data-testid="generation-review">
              <div className="bg-slate-50 rounded-xl p-3 text-sm">
                <p><strong>{review.class ? `${t("Classe")} ${review.class.name}` : review.academy?.name}</strong>
                  {" "}— {review.school_year?.name}, {t(PERIODS.find(p => p.value === review.period)?.label || "")}</p>
                <p>{t("{n} élève(s)", { n: review.students })} · {t("Bulletins existants")} : {review.existing_bulletins}
                  {" "}· {t("Bulletins absents")} : {review.missing_with_grades + review.missing_without_grades}
                  {" "}({t("dont {n} sans aucune note", { n: review.missing_without_grades })})</p>
              </div>
              <div className="max-h-56 overflow-y-auto border rounded-xl divide-y">
                {(review.students_list || []).map(st => (
                  <div key={st.id} className="flex items-center justify-between px-3 py-1.5 text-sm">
                    <span>{st.name}
                      <span className="text-xs text-slate-500"> · {st.has_pdf ? t("bulletin généré") : st.has_grades ? t("à générer") : t("aucune note : ignoré")}
                        {st.comment ? ` · « ${st.comment.slice(0, 40)}${st.comment.length > 40 ? "…" : ""} »` : ""}</span></span>
                    <button type="button" className="text-xs text-primary font-medium flex items-center gap-1"
                      onClick={() => openPreview({ studentId: st.id, yearId: review.request.school_year_id, period: review.request.period })}>
                      <Eye className="w-3 h-3" />{t("Aperçu")}</button>
                  </div>
                ))}
              </div>
              <div>
                <label className="label" htmlFor="common-comment">{t("Commentaire commun (facultatif, remplace les commentaires existants)")}</label>
                <textarea id="common-comment" className="input min-h-[70px]" value={commonComment}
                  onChange={(e) => setCommonComment(e.target.value)} />
              </div>
              <div className="border border-amber-300 bg-amber-50 rounded-xl p-3 text-sm" data-testid="generation-confirm">
                {t("{n} bulletin(s) seront générés ou régénérés.", { n: toGenerate })}
                {commonComment.trim() && ` ${t("Le commentaire commun sera appliqué à chacun.")}`}
              </div>
            </div>
          )}

          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={closeGen} className="btn-secondary">{t("Annuler")}</button>
            {!review ? (
              <button type="submit" disabled={reviewMut.isPending} className="btn-primary">
                {reviewMut.isPending ? t("Chargement…") : t("Réviser avant génération")}</button>
            ) : (
              <>
                <button type="button" className="btn-secondary" onClick={() => setReview(null)}>{t("Modifier la portée")}</button>
                <button type="button" disabled={genMut.isPending || toGenerate === 0} className="btn-primary"
                  onClick={() => genMut.mutate(review.request)}>
                  {genMut.isPending ? t("Génération…") : t("Confirmer et générer ({n})", { n: toGenerate })}</button>
              </>
            )}
          </div>
        </form>
      </Modal>
    </div>
  );
}
