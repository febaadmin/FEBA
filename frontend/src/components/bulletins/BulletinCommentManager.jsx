/**
 * Commentaire du Directeur / Principal's Comment — gestion depuis Notes et
 * Bulletins.
 *
 * - Un élève : le bulletin de la période est chargé (commentaire, date de
 *   génération, PDF) ; enregistrer, modifier ou supprimer le commentaire
 *   régénère le PDF, dont le lien (nouveau fichier) est rafraîchi.
 * - Une classe / toute l'académie : la portée est vérifiée par le serveur
 *   (nombre d'élèves, bulletins existants, absents) puis confirmée avant
 *   le lancement ; l'opération s'exécute dans le worker Celery et son
 *   bilan s'affiche tel quel — une réussite partielle est annoncée comme
 *   telle.
 *
 * Le commentaire général du bulletin n'a rien à voir avec le commentaire
 * d'une note : ils restent indépendants.
 */
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, ExternalLink, Loader2, MessageSquare } from "lucide-react";
import { bulletinsAPI, classesAPI, schoolsAPI, studentsAPI } from "../../api";
import Modal from "../ui/Modal";
import SearchableSelect from "../ui/SearchableSelect";
import { useAcademy } from "../../context/AcademyContext";
import { useSchoolYearScope } from "../../hooks/useSchoolYearScope";
import { extractApiError } from "../../utils/errors";
import { studentOptionLabel } from "../../utils/age";
import { t } from "../../i18n";

export const COMMENT_MAX = 1200;

const PERIODS = [
  { value: "T1", label: "Trimestre 1" },
  { value: "T2", label: "Trimestre 2" },
  { value: "T3", label: "Trimestre 3" },
  { value: "annual", label: "Annuel" },
];

const SCOPES = [
  { value: "student", label: "Un élève" },
  { value: "class", label: "Une classe" },
  { value: "academy", label: "Tous les élèves de l'académie" },
];

const listOf = (res) => res?.data?.results || res?.data || [];

export function OperationReport({ op }) {
  const r = op.result || {};
  const running = op.status === "queued" || op.status === "running";
  const tone = op.status === "done" ? "bg-success-50 border-success-200 text-success-800"
    : running ? "bg-slate-50 border-slate-200 text-slate-700"
    : "bg-amber-50 border-amber-200 text-amber-800";
  return (
    <div className={`border rounded-xl p-3 text-sm space-y-2 ${tone}`} data-testid="operation-report">
      <div className="flex items-center gap-2 font-semibold">
        {running ? <Loader2 className="w-4 h-4 animate-spin" />
          : op.status === "done" ? <CheckCircle2 className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
        {running ? t("Opération en cours…") : op.status === "done" ? t("Opération terminée")
          : op.status === "partial" ? t("Opération terminée avec des échecs") : t("Opération échouée")}
      </div>
      {op.error && <p>{op.error}</p>}
      {r.targeted !== undefined && (
        <ul className="grid grid-cols-2 gap-x-4 gap-y-0.5">
          <li>{t("Élèves dans la portée")} : <strong>{r.targeted}</strong></li>
          <li>{t("Bulletins traités")} : <strong>{r.processed}</strong></li>
          <li>{t("Commentaires ajoutés ou modifiés")} : <strong>{r.comments_set}</strong></li>
          <li>{t("Commentaires supprimés")} : <strong>{r.comments_cleared}</strong></li>
          <li>{t("PDF générés ou régénérés")} : <strong>{r.pdf_generated}</strong></li>
          <li>{t("Bulletins créés")} : <strong>{r.bulletins_created}</strong></li>
          <li>{t("Échecs")} : <strong>{r.failed}</strong></li>
          <li>{t("Ignorés")} : <strong>{r.skipped}</strong></li>
        </ul>
      )}
      {r.failures?.length > 0 && (
        <div>
          <p className="font-semibold">{t("Échecs")}</p>
          <ul className="list-disc ml-5">
            {r.failures.map((f) => <li key={`f${f.student_id}`}>{f.student} : {f.reason}</li>)}
          </ul>
        </div>
      )}
      {r.skipped_items?.length > 0 && (
        <details>
          <summary className="cursor-pointer">{t("Élèves ignorés et raison")} ({r.skipped_items.length})</summary>
          <ul className="list-disc ml-5">
            {r.skipped_items.map((s) => <li key={`s${s.student_id}`}>{s.student} : {s.reason}</li>)}
          </ul>
        </details>
      )}
    </div>
  );
}

export default function BulletinCommentManager({ open, onClose, initial = {} }) {
  // Les parents remontent le composant (prop `key`) à chaque ouverture :
  // l'état part donc toujours de `initial`, sans réinitialisation en effet.
  const qc = useQueryClient();
  const { isAllAcademies, activeAcademy } = useAcademy();
  const [scope, setScope] = useState(initial.scope || "student");
  const [studentId, setStudentId] = useState(initial.studentId || "");
  const [classId, setClassId] = useState(initial.classId || "");
  const [yearId, setYearId] = useState(initial.yearId || "");
  const [period, setPeriod] = useState(initial.period || "T1");
  const [action, setAction] = useState("set_comment");
  const [regenerate, setRegenerate] = useState(true);
  const [createMissing, setCreateMissing] = useState(false);

  const { data: studData } = useQuery({ queryKey: ["students-all"], queryFn: () => studentsAPI.list(), enabled: open });
  const { data: classData } = useQuery({ queryKey: ["classes"], queryFn: () => classesAPI.list(), enabled: open });
  const { data: yearsData } = useQuery({ queryKey: ["years"], queryFn: schoolsAPI.years, enabled: open });
  const students = listOf(studData);
  const classes = listOf(classData);
  const years = listOf(yearsData);
  const { currentYear } = useSchoolYearScope(years);
  const effectiveYear = yearId || currentYear?.id || "";
  const studentOpts = useMemo(() => students.map((s) => ({ value: s.id, label: studentOptionLabel(s) })), [students]);

  const target = {
    scope, period, school_year_id: effectiveYear,
    ...(scope === "student" ? { student_id: studentId } : {}),
    ...(scope === "class" ? { class_id: classId } : {}),
  };
  const targetKey = JSON.stringify(target);
  const targetReady = Boolean(effectiveYear && period && (scope === "academy"
    || (scope === "student" && studentId) || (scope === "class" && classId)));

  // Les états passagers sont rattachés à la cible : changer d'élève, de
  // classe ou de période les fait disparaître d'eux-mêmes.
  const [draftState, setDraftState] = useState({ key: null, text: "" });
  const [confirmKey, setConfirmKey] = useState(null);
  const [opState, setOpState] = useState({ key: null, id: null });
  const [errorState, setErrorState] = useState({ key: null, text: "" });
  const setError = (text) => setErrorState({ key: targetKey, text });

  // Aperçu serveur de la portée (et, pour un élève, son bulletin).
  const previewQuery = useQuery({
    queryKey: ["bulletin-comment-preview", targetKey],
    queryFn: () => bulletinsAPI.commentPreview(target).then((r) => r.data),
    enabled: Boolean(open && targetReady && !isAllAcademies),
    retry: false,
    gcTime: 0,
  });
  const preview = previewQuery.data || null;
  const error = errorState.key === targetKey ? errorState.text
    : previewQuery.error ? extractApiError(previewQuery.error) : "";

  const refreshBulletins = () => {
    qc.invalidateQueries({ queryKey: ["bulletins"] });
  };

  // Brouillon : celui de l'utilisateur pour CE bulletin, sinon le commentaire enregistré.
  const bulletin = preview?.bulletin || null;
  const draftKey = `${targetKey}|${bulletin?.comment_updated_at || ""}|${bulletin?.generated_at || ""}`;
  const comment = draftState.key === draftKey ? draftState.text
    : (scope === "student" ? (bulletin?.general_comment || "") : "");
  const setComment = (text) => setDraftState({ key: draftKey, text });

  // Un élève : un seul chemin, bulletin déjà généré ou non. Synchrone ;
  // l'interface n'affiche que ce que le serveur a confirmé.
  const [savedState, setSavedState] = useState({ key: null, text: "" });
  const saved = savedState.key === targetKey ? savedState.text : "";
  const saveMut = useMutation({
    mutationFn: (text) => bulletinsAPI.commentTarget({
      student_id: studentId, school_year_id: effectiveYear, period,
      comment: text, regenerate, expected_comment: bulletin?.general_comment ?? "",
    }),
    onSuccess: (res) => {
      const result = res.data.result;
      qc.setQueryData(["bulletin-comment-preview", targetKey],
        (p) => ({ ...(p || {}), bulletin: res.data.bulletin }));
      refreshBulletins();
      setError(result.failed ? result.failures.map((f) => f.reason).join(" ; ") : "");
      setSavedState({ key: targetKey, text: result.failed ? "" : (result.items?.[0]?.outcome || "") });
    },
    onError: (e) => {
      setSavedState({ key: targetKey, text: "" });
      if (e.response?.status === 409) {
        setError(t("Le commentaire a été modifié par quelqu'un d'autre entre-temps. Rechargez-le avant de l'enregistrer."));
        previewQuery.refetch();
      } else setError(extractApiError(e));
    },
  });

  // Opérations groupées : Celery + suivi.
  const opMut = useMutation({
    mutationFn: () => bulletinsAPI.createOperation({
      ...target,
      action,
      comment: action === "set_comment" ? comment : "",
      regenerate, create_missing: createMissing,
    }),
    onSuccess: (res) => { setOpState({ key: targetKey, id: res.data.id }); setConfirmKey(null); setError(""); },
    onError: (e) => { setConfirmKey(null); setError(extractApiError(e)); },
  });
  const opId = opState.key === targetKey ? opState.id : null;
  const { data: opData } = useQuery({
    queryKey: ["bulletin-operation", opId],
    queryFn: () => bulletinsAPI.operation(opId),
    enabled: Boolean(opId),
    refetchInterval: (q) => {
      const st = q.state.data?.data?.status;
      return st && st !== "queued" && st !== "running" ? false : 1500;
    },
  });
  const op = opId ? opData?.data : null;
  const opFinished = Boolean(op && op.status !== "queued" && op.status !== "running");
  useEffect(() => {
    if (!opFinished) return;
    qc.invalidateQueries({ queryKey: ["bulletins"] });
    qc.invalidateQueries({ queryKey: ["bulletin-comment-preview"] });
  }, [opFinished, qc]);

  const confirming = confirmKey === `${targetKey}|${action}`;
  const setConfirming = (on) => setConfirmKey(on ? `${targetKey}|${action}` : null);
  const tooLong = comment.trim().length > COMMENT_MAX;
  const busy = saveMut.isPending || opMut.isPending || (op && (op.status === "queued" || op.status === "running"));
  const scopeLabel = scope === "student" ? (preview?.student?.name || "")
    : scope === "class" ? `${t("Classe")} ${preview?.class?.name || ""}`
    : `${t("Tous les élèves de l'académie")} ${preview?.academy?.name || ""}`;

  return (
    <Modal open={open} onClose={onClose} title={t("Commentaire du directeur sur les bulletins")} size="lg">
      <div className="space-y-4">
        {isAllAcademies && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-sm text-amber-800">
            {t("Sélectionnez d'abord une académie : les commentaires ne s'appliquent jamais à toutes les académies à la fois.")}
          </div>
        )}
        {!isAllAcademies && activeAcademy?.name && (
          <p className="text-xs text-slate-500">{t("Académie")} : <strong>{activeAcademy.name}</strong></p>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="label">{t("Portée")}</label>
            <select className="input" value={scope} onChange={(e) => setScope(e.target.value)} aria-label={t("Portée")}>
              {SCOPES.map((s) => <option key={s.value} value={s.value}>{t(s.label)}</option>)}
            </select>
          </div>
          <div>
            <label className="label">{t("Année scolaire")}</label>
            <select className="input" value={effectiveYear} onChange={(e) => setYearId(e.target.value)} aria-label={t("Année scolaire")}>
              {years.map((y) => <option key={y.id} value={y.id}>{y.name}{y.is_current ? " ✓" : ""}</option>)}
            </select>
          </div>
          <div>
            <label className="label">{t("Période")}</label>
            <select className="input" value={period} onChange={(e) => setPeriod(e.target.value)} aria-label={t("Période")}>
              {PERIODS.map((p) => <option key={p.value} value={p.value}>{t(p.label)}</option>)}
            </select>
          </div>
        </div>

        {scope === "student" && (
          <div>
            <label className="label">{t("Élève")}</label>
            <SearchableSelect options={studentOpts} value={studentId} onChange={setStudentId}
              placeholder={t("Rechercher un élève…")} />
          </div>
        )}
        {scope === "class" && (
          <div>
            <label className="label">{t("Classe")}</label>
            <select className="input" value={classId} onChange={(e) => setClassId(e.target.value)} aria-label={t("Classe")}>
              <option value="">{t("-- Sélectionner --")}</option>
              {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
        )}

        {previewQuery.isFetching && !preview && <p className="text-sm text-slate-500">{t("Chargement…")}</p>}

        {/* Un élève : état du bulletin */}
        {scope === "student" && preview && (
          <div className={`text-sm rounded-xl p-3 flex flex-wrap items-center gap-x-4 gap-y-1 ${
            bulletin?.pdf_url ? "bg-slate-50" : "bg-amber-50 border border-amber-200 text-amber-800"}`}
            data-testid="bulletin-state">
            {bulletin?.pdf_url ? (
              <span>{t("Bulletin généré le")} {bulletin.generated_at ? new Date(bulletin.generated_at).toLocaleString() : "-"}</span>
            ) : (
              <span>
                {t("Bulletin pas encore généré : le commentaire est enregistré et sera imprimé à la génération.")}
                {preview.has_grades === false && ` ${t("Aucune note sur cette période : le PDF ne peut pas encore être produit.")}`}
              </span>
            )}
            {bulletin?.pdf_url && bulletin.pdf_outdated && (
              <span className="text-amber-700 font-medium">{t("PDF à régénérer : il ne contient pas le dernier commentaire.")}</span>
            )}
            {bulletin?.pdf_url && (
              <a href={bulletin.pdf_url} target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-1 text-primary font-medium" data-testid="pdf-link">
                <ExternalLink className="w-3.5 h-3.5" />{t("Ouvrir le PDF")}
              </a>
            )}
          </div>
        )}

        {/* Portée groupée : chiffres du serveur */}
        {scope !== "student" && preview && (
          <div className="text-sm bg-slate-50 rounded-xl p-3 space-y-1" data-testid="scope-preview">
            <p><strong>{scopeLabel}</strong> : {preview.school_year?.name}, {t(PERIODS.find((p) => p.value === period)?.label || "")}</p>
            <p>{t("{n} élève(s)", { n: preview.students })} · {t("Bulletins existants")} : {preview.existing_bulletins}
              {" "}· {t("Avec commentaire")} : {preview.with_comment}</p>
            <p>{t("Bulletins absents")} : {preview.missing_with_grades + preview.missing_without_grades}
              {" "}({t("dont {n} sans aucune note", { n: preview.missing_without_grades })})</p>
          </div>
        )}

        {scope !== "student" && (
          <div className="flex flex-wrap gap-4 text-sm">
            <label className="flex items-center gap-2">
              <input type="radio" name="bc-action" checked={action === "set_comment"} onChange={() => setAction("set_comment")} />
              {t("Ajouter ou remplacer le commentaire")}
            </label>
            <label className="flex items-center gap-2">
              <input type="radio" name="bc-action" checked={action === "clear_comment"} onChange={() => setAction("clear_comment")} />
              {t("Supprimer le commentaire")}
            </label>
          </div>
        )}

        {(scope === "student" || action === "set_comment") && (
          <div>
            <label className="label" htmlFor="bc-text">{t("Commentaire du Directeur / Principal's Comment")}</label>
            <textarea id="bc-text" className="input min-h-[120px]" value={comment} maxLength={COMMENT_MAX + 200}
              readOnly={saveMut.isPending}
              onChange={(e) => setComment(e.target.value)}
              placeholder={t("Saisissez le commentaire imprimé sur le bulletin…")} />
            <p className={`text-xs mt-1 ${tooLong ? "text-danger font-medium" : "text-slate-500"}`}>
              {comment.trim().length} / {COMMENT_MAX}
            </p>
          </div>
        )}

        <div className="flex flex-wrap gap-4 text-sm">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={regenerate} onChange={(e) => setRegenerate(e.target.checked)} />
            {t("Régénérer les PDF")}
          </label>
          {scope !== "student" && action === "set_comment" && (
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={createMissing} onChange={(e) => setCreateMissing(e.target.checked)} />
              {t("Générer aussi les bulletins absents (élèves ayant des notes)")}
            </label>
          )}
        </div>

        {error && <div className="bg-danger-50 border border-danger-200 rounded-xl p-3 text-sm text-danger" role="alert">{error}</div>}
        {!error && saved && !saveMut.isPending && (
          <div className="bg-success-50 border border-success-200 rounded-xl p-3 text-sm text-success-800" role="status"
            data-testid="save-confirmation">
            {t("Enregistré par le serveur")} : {saved}
          </div>
        )}
        {op && <OperationReport op={op} />}

        {confirming && preview && (
          <div className="border border-amber-300 bg-amber-50 rounded-xl p-3 text-sm space-y-2" data-testid="confirm-box">
            <p>
              {action === "clear_comment" ? t("Supprimer le commentaire") : t("Appliquer le commentaire")} -
              {" "}<strong>{scopeLabel}</strong> : {t("{n} bulletin(s) existant(s)", { n: preview.existing_bulletins })}
              {createMissing && action === "set_comment"
                ? `, ${t("{n} bulletin(s) à créer", { n: preview.missing_with_grades })}` : ""}.
            </p>
            <div className="flex gap-2 justify-end">
              <button type="button" className="btn-secondary" onClick={() => setConfirming(false)}>{t("Annuler")}</button>
              <button type="button" className="btn-primary" disabled={opMut.isPending} onClick={() => opMut.mutate()}>
                {t("Confirmer")}
              </button>
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-2 justify-end pt-2">
          <button type="button" className="btn-secondary" onClick={onClose}>{t("Fermer")}</button>
          {scope === "student" && preview && (
            <>
              <button type="button" className="btn-secondary" disabled={busy || !bulletin?.general_comment}
                onClick={() => saveMut.mutate("")}>{t("Supprimer le commentaire")}</button>
              <button type="button" className="btn-primary flex items-center gap-2"
                disabled={busy || tooLong || isAllAcademies || !comment.trim()}
                onClick={() => saveMut.mutate(comment)}>
                <MessageSquare className="w-4 h-4" />
                {saveMut.isPending ? t("Enregistrement…")
                  : regenerate && (bulletin?.pdf_url || preview.has_grades) ? t("Enregistrer et régénérer le PDF")
                  : t("Enregistrer le commentaire")}
              </button>
            </>
          )}
          {scope !== "student" && (
            <button type="button" className="btn-primary"
              disabled={busy || !preview || isAllAcademies || (action === "set_comment" && (!comment.trim() || tooLong))}
              onClick={() => setConfirming(true)}>
              {t("Vérifier et appliquer")}
            </button>
          )}
        </div>
      </div>
    </Modal>
  );
}
