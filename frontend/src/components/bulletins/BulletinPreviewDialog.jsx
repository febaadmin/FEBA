/**
 * Aperçu d'un bulletin AVANT sa génération officielle (et de tout bulletin
 * existant), avec le commentaire du directeur éditable.
 *
 * - L'aperçu est le PDF rendu par le moteur officiel (/bulletins/preview/)
 *   à partir des données actuelles, avec le commentaire SAISI ici : il ne
 *   crée ni ne modifie rien (filigrane « APERÇU »).
 * - « Enregistrer le commentaire » écrit le commentaire en base (confirmé
 *   par le serveur) SANS générer le bulletin officiel.
 * - « Générer le bulletin définitif » ne part qu'après une confirmation
 *   explicite ; un commentaire saisi mais non enregistré est d'abord
 *   enregistré (le serveur le confirme), puis le bulletin est généré.
 * - « Annuler » ferme sans rien enregistrer.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, FileCheck2, Loader2, RefreshCw, Save, Trash2 } from "lucide-react";
import { bulletinsAPI, schoolsAPI, studentsAPI } from "../../api";
import Modal from "../ui/Modal";
import SearchableSelect from "../ui/SearchableSelect";
import { useAcademy } from "../../context/AcademyContext";
import { useSchoolYearScope } from "../../hooks/useSchoolYearScope";
import { extractApiError } from "../../utils/errors";
import { studentOptionLabel } from "../../utils/age";
import { t } from "../../i18n";
import { COMMENT_MAX } from "./BulletinCommentManager";

const PERIODS = [
  { value: "T1", label: "Trimestre 1" },
  { value: "T2", label: "Trimestre 2" },
  { value: "T3", label: "Trimestre 3" },
  { value: "annual", label: "Annuel" },
];
const listOf = (res) => res?.data?.results || res?.data || [];

/** Message d'erreur d'une réponse blob (le corps JSON est dans un Blob). */
async function blobError(e) {
  const data = e?.response?.data;
  if (data instanceof Blob) {
    try { const j = JSON.parse(await data.text()); return j.error || j.detail || extractApiError(e); }
    catch { /* corps illisible */ }
  }
  return extractApiError(e);
}

export default function BulletinPreviewDialog({ open, onClose, initial = {} }) {
  const qc = useQueryClient();
  const { isAllAcademies } = useAcademy();
  const [studentId, setStudentId] = useState(initial.studentId || "");
  const [yearId, setYearId] = useState(initial.yearId || "");
  const [period, setPeriod] = useState(initial.period || "T1");
  const [draft, setDraft] = useState(null);          // null = commentaire enregistré
  const [pdfUrl, setPdfUrl] = useState(null);
  const [previewedText, setPreviewedText] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [confirming, setConfirming] = useState(false);
  const urlRef = useRef(null);

  const { data: studData } = useQuery({ queryKey: ["students-all"], queryFn: () => studentsAPI.list(), enabled: open });
  const { data: yearsData } = useQuery({ queryKey: ["years"], queryFn: schoolsAPI.years, enabled: open });
  const students = listOf(studData);
  const years = listOf(yearsData);
  const { currentYear } = useSchoolYearScope(years);
  const effectiveYear = yearId || currentYear?.id || "";
  const studentOpts = useMemo(() => students.map((s) => ({ value: s.id, label: studentOptionLabel(s) })), [students]);
  const target = { scope: "student", student_id: studentId, school_year_id: effectiveYear, period };
  const targetKey = JSON.stringify(target);
  const ready = Boolean(open && studentId && effectiveYear && period && !isAllAcademies);

  // État enregistré (bulletin existant ou non, commentaire, notes).
  const stateQuery = useQuery({
    queryKey: ["bulletin-comment-preview", targetKey],
    queryFn: () => bulletinsAPI.commentPreview(target).then((r) => r.data),
    enabled: ready,
    retry: false,
  });
  const bulletin = stateQuery.data?.bulletin || null;
  const saved = bulletin?.general_comment || "";
  const comment = draft === null ? saved : draft;
  const dirty = draft !== null && draft !== saved;
  const tooLong = comment.trim().length > COMMENT_MAX;

  const showPdf = (blob, text) => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = URL.createObjectURL(blob);
    setPdfUrl(urlRef.current);
    setPreviewedText(text);
  };
  useEffect(() => () => { if (urlRef.current) URL.revokeObjectURL(urlRef.current); }, []);

  const previewMut = useMutation({
    mutationFn: (text) => bulletinsAPI.preview({ ...target, comment: text }).then((r) => ({ blob: r.data, text })),
    onSuccess: ({ blob, text }) => { setError(""); showPdf(blob, text); },
    onError: async (e) => setError(await blobError(e)),
  });

  // Premier aperçu dès que l'élève, l'année et la période sont connus.
  const autoKey = useRef(null);
  useEffect(() => {
    if (!ready || !stateQuery.data || autoKey.current === targetKey) return;
    autoKey.current = targetKey;
    previewMut.mutate(stateQuery.data.bulletin?.general_comment || "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, stateQuery.data, targetKey]);

  const refreshAll = () => {
    qc.invalidateQueries({ queryKey: ["bulletins"] });
    qc.invalidateQueries({ queryKey: ["bulletin-comment-preview"] });
  };

  const saveMut = useMutation({
    mutationFn: (text) => bulletinsAPI.commentTarget({
      student_id: studentId, school_year_id: effectiveYear, period,
      comment: text, regenerate: false, expected_comment: saved,
    }).then((r) => r.data),
    onSuccess: (data) => {
      qc.setQueryData(["bulletin-comment-preview", targetKey], (p) => ({ ...(p || {}), bulletin: data.bulletin }));
      refreshAll();
      setDraft(null);
      setError("");
      setNotice(data.bulletin.general_comment
        ? t("Commentaire enregistré par le serveur.")
        : t("Commentaire supprimé (enregistré par le serveur)."));
      previewMut.mutate(data.bulletin.general_comment || "");
    },
    onError: (e) => {
      setNotice("");
      setError(e.response?.status === 409
        ? t("Le commentaire a été modifié par quelqu'un d'autre entre-temps. Rechargez-le avant de l'enregistrer.")
        : extractApiError(e));
    },
  });

  const generateMut = useMutation({
    mutationFn: async () => {
      if (dirty) {
        const res = await bulletinsAPI.commentTarget({
          student_id: studentId, school_year_id: effectiveYear, period,
          comment, regenerate: false, expected_comment: saved,
        });
        qc.setQueryData(["bulletin-comment-preview", targetKey], (p) => ({ ...(p || {}), bulletin: res.data.bulletin }));
        setDraft(null);
      }
      const r = await bulletinsAPI.generate({ student_id: studentId, school_year_id: effectiveYear, period });
      return r.data;
    },
    onSuccess: (data) => {
      qc.setQueryData(["bulletin-comment-preview", targetKey], (p) => ({ ...(p || {}), bulletin: data }));
      refreshAll();
      setConfirming(false);
      setError("");
      setNotice(t("Bulletin définitif généré."));
    },
    onError: (e) => { setConfirming(false); setNotice(""); setError(extractApiError(e)); },
  });

  const busy = previewMut.isPending || saveMut.isPending || generateMut.isPending;
  const previewStale = pdfUrl && previewedText !== null && previewedText !== comment.trim();

  return (
    <Modal open={open} onClose={onClose} title={t("Aperçu du bulletin")} size="xl">
      <div className="space-y-4" data-testid="bulletin-preview-dialog">
        {isAllAcademies && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm text-amber-800">
            {t("Sélectionnez d'abord une académie : les commentaires ne s'appliquent jamais à toutes les académies à la fois.")}
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="sm:col-span-1">
            <label className="label">{t("Élève")}</label>
            <SearchableSelect options={studentOpts} value={studentId}
              onChange={(v) => { setStudentId(v); setDraft(null); setNotice(""); }}
              placeholder={t("Rechercher un élève…")} />
          </div>
          <div>
            <label className="label">{t("Année scolaire")}</label>
            <select className="input" value={effectiveYear} aria-label={t("Année scolaire")}
              onChange={(e) => { setYearId(e.target.value); setDraft(null); }}>
              {years.map((y) => <option key={y.id} value={y.id}>{y.name}{y.is_current ? " ✓" : ""}</option>)}
            </select>
          </div>
          <div>
            <label className="label">{t("Période")}</label>
            <select className="input" value={period} aria-label={t("Période")}
              onChange={(e) => { setPeriod(e.target.value); setDraft(null); }}>
              {PERIODS.map((p) => <option key={p.value} value={p.value}>{t(p.label)}</option>)}
            </select>
          </div>
        </div>

        {ready && stateQuery.data && (
          <p className="text-xs text-slate-600" data-testid="preview-state">
            {bulletin?.pdf_url
              ? <>{t("Bulletin généré le")} {new Date(bulletin.generated_at).toLocaleString()} ·{" "}
                <a href={bulletin.pdf_url} target="_blank" rel="noreferrer" className="text-primary font-medium"
                  data-testid="official-pdf-link">{t("Ouvrir le PDF officiel")}</a>
                {bulletin.pdf_outdated && <span className="text-amber-700"> · {t("PDF à régénérer")}</span>}</>
              : t("Bulletin pas encore généré : rien n'est créé tant que vous ne cliquez pas sur « Générer le bulletin définitif ».")}
          </p>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          <div className="lg:col-span-2 space-y-2">
            <label className="label" htmlFor="bp-comment">{t("Commentaire du Directeur / Principal's Comment")}</label>
            <textarea id="bp-comment" className="input min-h-[180px]" value={comment}
              readOnly={busy || !ready} maxLength={COMMENT_MAX + 200}
              onChange={(e) => { setDraft(e.target.value); setNotice(""); }}
              placeholder={t("Saisissez le commentaire imprimé sur le bulletin…")} />
            <p className={`text-xs ${tooLong ? "text-danger font-medium" : "text-slate-500"}`}>
              {comment.trim().length} / {COMMENT_MAX}
              {dirty && <span className="text-amber-700"> · {t("Modifié, non enregistré")}</span>}
            </p>
            <div className="flex flex-wrap gap-2">
              <button type="button" className="btn-secondary flex items-center gap-2"
                disabled={!ready || busy || tooLong} onClick={() => previewMut.mutate(comment)}>
                <RefreshCw className="w-4 h-4" />{t("Actualiser l'aperçu")}</button>
              <button type="button" className="btn-secondary flex items-center gap-2"
                disabled={!ready || busy || tooLong || !dirty} onClick={() => saveMut.mutate(comment)}>
                <Save className="w-4 h-4" />{saveMut.isPending ? t("Enregistrement…") : t("Enregistrer le commentaire")}</button>
              <button type="button" className="btn-secondary flex items-center gap-2"
                disabled={!ready || busy || !saved} onClick={() => saveMut.mutate("")}>
                <Trash2 className="w-4 h-4" />{t("Supprimer le commentaire")}</button>
            </div>
            {error && <div className="bg-danger-50 border border-danger-200 rounded-xl p-3 text-sm text-danger" role="alert">{error}</div>}
            {!error && notice && <div className="bg-success-50 border border-success-200 rounded-xl p-3 text-sm text-success-800"
              role="status" data-testid="preview-notice">{notice}</div>}
          </div>
          <div className="lg:col-span-3">
            <div className="relative border rounded-xl bg-slate-100 h-[60vh] flex items-center justify-center overflow-hidden">
              {previewMut.isPending && (
                <div className="absolute inset-0 flex items-center justify-center bg-white/70 z-10">
                  <Loader2 className="w-6 h-6 animate-spin text-primary" />
                </div>
              )}
              {pdfUrl ? (
                <iframe title={t("Aperçu du bulletin")} src={pdfUrl} className="w-full h-full" data-testid="preview-frame" />
              ) : (
                <span className="text-sm text-slate-500 flex items-center gap-2"><Eye className="w-4 h-4" />
                  {t("Choisissez l'élève, l'année et la période pour afficher l'aperçu.")}</span>
              )}
            </div>
            {previewStale && (
              <p className="text-xs text-amber-700 mt-1">{t("Le commentaire a changé : actualisez l'aperçu pour le voir sur le bulletin.")}</p>
            )}
          </div>
        </div>

        {confirming && (
          <div className="border border-amber-300 bg-amber-50 rounded-xl p-3 text-sm space-y-2" data-testid="generate-confirm">
            <p>{bulletin?.pdf_url
              ? t("Le bulletin officiel sera régénéré avec les données et le commentaire actuels. L'ancien PDF n'est remplacé qu'en cas de réussite.")
              : t("Le bulletin officiel sera créé avec les données et le commentaire actuels.")}
              {dirty && ` ${t("Le commentaire saisi sera d'abord enregistré.")}`}</p>
            <div className="flex gap-2 justify-end">
              <button type="button" className="btn-secondary" onClick={() => setConfirming(false)}>{t("Annuler")}</button>
              <button type="button" className="btn-primary" disabled={busy} onClick={() => generateMut.mutate()}>
                {generateMut.isPending ? t("Génération…") : t("Confirmer la génération")}</button>
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-2 justify-end pt-2 border-t">
          <button type="button" className="btn-secondary" onClick={onClose} disabled={generateMut.isPending}>{t("Annuler")}</button>
          <button type="button" className="btn-primary flex items-center gap-2"
            disabled={!ready || busy || tooLong || confirming} onClick={() => setConfirming(true)}>
            <FileCheck2 className="w-4 h-4" />{t("Générer le bulletin définitif")}</button>
        </div>
      </div>
    </Modal>
  );
}
