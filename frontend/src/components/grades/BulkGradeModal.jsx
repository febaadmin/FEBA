/**
 * BulkGradeModal — saisie GROUPÉE de notes (V6).
 *
 * Un élève, une année, plusieurs matières enregistrées en UNE opération
 * atomique (POST /api/grades/bulk-create/). La saisie simple existante n'est
 * pas modifiée : ce modal est une option supplémentaire, ouverte par un
 * bouton « Saisie groupée » distinct.
 *
 * - desktop : lignes façon tableau ; mobile : cartes empilées (pas de scroll
 *   horizontal) ;
 * - ajout / duplication / suppression de lignes ;
 * - aperçu d'appréciation par ligne (le backend reste la source de vérité) ;
 * - erreurs renvoyées par ligne (grades.i.champ) affichées au bon endroit ;
 * - double-soumission empêchée ; à la réussite : résumé + rafraîchissement.
 *
 * Réutilisé par l'enseignant, l'administrateur et le super administrateur —
 * les permissions réelles (matières/classes autorisées) sont appliquées par
 * le backend ; ce composant ne propose que les matières transmises en props.
 */
import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Plus, Trash2, Copy, Save, Loader2, AlertCircle } from "lucide-react";
import toast from "react-hot-toast";
import { gradesAPI } from "../../api";
import Modal from "../ui/Modal";
import SearchableSelect from "../ui/SearchableSelect";
import { appreciationPreview } from "../../utils/appreciation";
import { t } from "../../i18n";

const NOTE_TYPES = [
  { value: "devoir", label: "Devoir" },
  { value: "interrogation", label: "Interrogation / Devoir de classe" },
  { value: "controle", label: "Contrôle" },
  { value: "examen", label: "Examen / Évaluation" },
  { value: "tp", label: "Travaux Pratiques" },
  { value: "autre", label: "Autre" },
];
const PERIODS = [
  { value: "T1", label: "Trimestre 1" },
  { value: "T2", label: "Trimestre 2" },
  { value: "T3", label: "Trimestre 3" },
  { value: "exam", label: "Examen" },
];

const emptyRow = (period = "T1") => ({
  subject: "", period, value: "", note_type: "devoir",
  note_coefficient: 1, comment: "",
});

export default function BulkGradeModal({
  open, onClose, onSaved,
  studentOptions = [], subjectOptions = [], classOptions = [],
  schoolYearId, periodDefault = "T1",
}) {
  const [classFilter, setClassFilter] = useState("");
  const [studentId, setStudentId] = useState("");
  const [rows, setRows] = useState([emptyRow(periodDefault)]);
  const [rowErrors, setRowErrors] = useState({}); // { index: { field: msg } }
  const [topError, setTopError] = useState("");

  const visibleStudents = useMemo(() => {
    if (!classFilter) return studentOptions;
    return studentOptions.filter((s) => String(s.classId) === String(classFilter));
  }, [studentOptions, classFilter]);

  const reset = () => {
    setClassFilter(""); setStudentId(""); setRows([emptyRow(periodDefault)]);
    setRowErrors({}); setTopError("");
  };

  const close = () => { reset(); onClose(); };

  const setRow = (i, patch) => {
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
    setRowErrors((e) => { const n = { ...e }; delete n[i]; return n; });
  };
  const addRow = () => setRows((rs) => [...rs, emptyRow(rows[rows.length - 1]?.period || periodDefault)]);
  const dupRow = (i) => setRows((rs) => [...rs.slice(0, i + 1), { ...rs[i] }, ...rs.slice(i + 1)]);
  const delRow = (i) => setRows((rs) => (rs.length > 1 ? rs.filter((_, idx) => idx !== i) : rs));

  const mut = useMutation({
    mutationFn: (payload) => gradesAPI.bulkCreate(payload),
    onSuccess: (resp) => {
      toast.success(resp.data?.detail || t("Notes enregistrées."));
      onSaved?.(resp.data);
      close();
    },
    onError: (e) => {
      const data = e?.response?.data || {};
      // Erreurs par ligne : { grades: [ {champ:[...]}, ... ] }
      if (Array.isArray(data.grades)) {
        const map = {};
        data.grades.forEach((errs, idx) => {
          if (errs && Object.keys(errs).length) {
            map[idx] = Object.fromEntries(
              Object.entries(errs).map(([k, v]) => [k, Array.isArray(v) ? v[0] : String(v)]),
            );
          }
        });
        setRowErrors(map);
        setTopError(t("Certaines lignes comportent des erreurs. Corrigez-les puis réessayez."));
      } else {
        // Erreur de haut niveau (élève, année…)
        const first = data.student?.[0] || data.school_year?.[0] || data.detail || data.grades;
        setTopError(Array.isArray(first) ? first[0] : (first || t("Une erreur est survenue.")));
      }
    },
  });

  const submit = () => {
    setTopError("");
    if (!studentId) { setTopError(t("Sélectionnez un élève.")); return; }
    // Validation légère côté client (le backend reste l'autorité)
    const localErrors = {};
    rows.forEach((r, i) => {
      const e = {};
      if (!r.subject) e.subject = t("Matière obligatoire.");
      if (r.value === "" || r.value == null) e.value = t("Note obligatoire.");
      else if (Number(r.value) < 0 || Number(r.value) > 20) e.value = t("Note entre 0 et 20.");
      if (!r.note_coefficient || Number(r.note_coefficient) < 1) e.note_coefficient = t("Coefficient ≥ 1.");
      if (Object.keys(e).length) localErrors[i] = e;
    });
    if (Object.keys(localErrors).length) {
      setRowErrors(localErrors);
      setTopError(t("Complétez les champs obligatoires."));
      return;
    }
    mut.mutate({
      student: Number(studentId),
      ...(schoolYearId ? { school_year: Number(schoolYearId) } : {}),
      grades: rows.map((r) => ({
        subject: Number(r.subject),
        period: r.period,
        value: String(r.value),
        note_type: r.note_type,
        note_coefficient: Number(r.note_coefficient),
        comment: r.comment || "",
      })),
    });
  };

  const inputCls = (err) =>
    `w-full border rounded-lg px-2.5 py-2 text-sm bg-white ${err ? "border-red-400" : "border-slate-200"}`;

  return (
    <Modal open={open} onClose={close} title={t("Saisie groupée de notes")} size="xl">
      <div className="space-y-4">
        <p className="text-sm text-slate-500">
          {t("Enregistrez plusieurs matières pour un même élève en une seule opération. Tout est enregistré ensemble, ou rien en cas d'erreur.")}
        </p>

        {topError && (
          <div className="rounded-xl bg-red-50 border border-red-200 p-3 flex items-start gap-2 text-sm text-red-700">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" /> {topError}
          </div>
        )}

        {/* Sélection élève */}
        <div className="grid sm:grid-cols-2 gap-3">
          {classOptions.length > 0 && (
            <div>
              <label className="label">{t("Classe (filtre élèves)")}</label>
              <select className="input" value={classFilter}
                onChange={(e) => { setClassFilter(e.target.value); setStudentId(""); }}>
                <option value="">{t("Toutes les classes")}</option>
                {classOptions.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
          )}
          <div>
            <label className="label">{t("Élève *")}</label>
            <SearchableSelect
              options={visibleStudents}
              value={studentId}
              onChange={setStudentId}
              placeholder={t("Choisir un élève…")}
            />
          </div>
        </div>

        {/* En-tête des lignes (desktop) */}
        <div className="hidden lg:grid grid-cols-[1.4fr_0.9fr_0.7fr_1.1fr_0.7fr_1.2fr_auto] gap-2 px-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
          <span>{t("Matière")}</span><span>{t("Période")}</span><span>{t("Note /20")}</span>
          <span>{t("Type")}</span><span>{t("Coeff.")}</span><span>{t("Appréciation")}</span><span></span>
        </div>

        {/* Lignes : tableau sur desktop, cartes sur mobile */}
        <div className="space-y-3">
          {rows.map((r, i) => {
            const err = rowErrors[i] || {};
            const appr = appreciationPreview(r.value);
            return (
              <div key={i}
                className="lg:grid lg:grid-cols-[1.4fr_0.9fr_0.7fr_1.1fr_0.7fr_1.2fr_auto] lg:gap-2 lg:items-start
                           grid grid-cols-2 gap-2 p-3 lg:p-0 rounded-xl lg:rounded-none border lg:border-0 border-slate-200 bg-slate-50 lg:bg-transparent">
                <div className="col-span-2 lg:col-span-1">
                  <span className="lg:hidden label">{t("Matière")}</span>
                  <SearchableSelect options={subjectOptions} value={r.subject}
                    onChange={(v) => setRow(i, { subject: v })} placeholder={t("Matière…")} />
                  {err.subject && <p className="text-xs text-red-600 mt-1">{err.subject}</p>}
                </div>
                <div>
                  <span className="lg:hidden label">{t("Période")}</span>
                  <select className={inputCls(err.period)} value={r.period}
                    onChange={(e) => setRow(i, { period: e.target.value })}>
                    {PERIODS.map((p) => <option key={p.value} value={p.value}>{t(p.label)}</option>)}
                  </select>
                </div>
                <div>
                  <span className="lg:hidden label">{t("Note /20")}</span>
                  <input type="number" step="0.01" min="0" max="20" className={inputCls(err.value)}
                    value={r.value} onChange={(e) => setRow(i, { value: e.target.value })} placeholder="0–20" />
                  {err.value && <p className="text-xs text-red-600 mt-1">{err.value}</p>}
                </div>
                <div>
                  <span className="lg:hidden label">{t("Type")}</span>
                  <select className={inputCls()} value={r.note_type}
                    onChange={(e) => setRow(i, { note_type: e.target.value })}>
                    {NOTE_TYPES.map((nt) => <option key={nt.value} value={nt.value}>{t(nt.label)}</option>)}
                  </select>
                </div>
                <div>
                  <span className="lg:hidden label">{t("Coeff.")}</span>
                  <input type="number" min="1" className={inputCls(err.note_coefficient)}
                    value={r.note_coefficient} onChange={(e) => setRow(i, { note_coefficient: e.target.value })} />
                  {err.note_coefficient && <p className="text-xs text-red-600 mt-1">{err.note_coefficient}</p>}
                </div>
                <div className="col-span-2 lg:col-span-1 flex items-center">
                  <span className="lg:hidden label mr-2">{t("Appréciation")}</span>
                  <span className={`text-xs font-semibold ${appr ? "text-feba-navy" : "text-slate-300"}`}>
                    {appr ? t(appr) : "—"}
                  </span>
                </div>
                <div className="col-span-2 lg:col-span-1 flex gap-1 justify-end lg:justify-start">
                  <button type="button" onClick={() => dupRow(i)} title={t("Dupliquer la ligne")}
                    className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 hover:text-primary">
                    <Copy className="w-4 h-4" />
                  </button>
                  <button type="button" onClick={() => delRow(i)} title={t("Supprimer la ligne")}
                    disabled={rows.length === 1}
                    className="p-1.5 rounded-lg text-slate-400 hover:bg-red-50 hover:text-danger disabled:opacity-30">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                {/* Commentaire optionnel (pleine largeur) */}
                <div className="col-span-2 lg:col-span-7">
                  <input className={`${inputCls()} text-xs`} value={r.comment}
                    onChange={(e) => setRow(i, { comment: e.target.value })}
                    placeholder={t("Commentaire (optionnel)")} />
                </div>
              </div>
            );
          })}
        </div>

        <button type="button" onClick={addRow}
          className="inline-flex items-center gap-2 text-sm font-semibold text-primary hover:underline">
          <Plus className="w-4 h-4" /> {t("Ajouter une matière")}
        </button>

        {/* Résumé + actions */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-100">
          <p className="text-sm text-slate-500">
            {t("{n} note(s) à enregistrer").replace("{n}", rows.length)}
          </p>
          <div className="flex gap-3">
            <button type="button" onClick={close} className="btn-secondary">{t("Annuler")}</button>
            <button type="button" onClick={submit} disabled={mut.isPending}
              className="btn-primary min-w-[200px] flex items-center justify-center gap-2">
              {mut.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              {mut.isPending ? t("Enregistrement…") : t("Enregistrer toutes les notes")}
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}
