/**
 * Affectations d'un enseignant : quelles matières il enseigne dans quelles classes.
 * Enregistrer confirme toute la grille, y compris les lignes reprises automatiquement.
 */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { teachersAPI } from "../../api";
import { extractApiError } from "../../utils/errors";
import { t } from "../../i18n";
import Modal from "../ui/Modal";

const cle = (c, s) => `${c}:${s}`;

export default function AffectationsModal({ teacher, onClose }) {
  const qc = useQueryClient();
  const classes = teacher?.classes_detail || [];
  const matieres = teacher?.subjects_detail || [];
  const [coche, setCoche] = useState(new Set());
  const { data, isLoading } = useQuery({
    queryKey: ["teacher-assignments", teacher?.id],
    queryFn: () => teachersAPI.getAssignments(teacher.id),
    enabled: !!teacher,
  });
  const lignes = data?.data || [];
  const aConfirmer = new Set(lignes.filter((l) => l.a_confirmer).map((l) => cle(l.class_id, l.subject_id)));

  useEffect(() => {
    setCoche(new Set((data?.data || []).map((l) => cle(l.class_id, l.subject_id))));
  }, [data]);

  const saveMut = useMutation({
    mutationFn: () => teachersAPI.setAssignments(teacher.id, [...coche].map((k) => {
      const [class_id, subject_id] = k.split(":").map(Number);
      return { class_id, subject_id };
    })),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["teacher-assignments", teacher.id] });
      toast.success(t("Affectations enregistrées."));
      onClose();
    },
    onError: (e) => toast.error(extractApiError(e)),
  });

  const basculer = (k) => setCoche((avant) => {
    const apres = new Set(avant);
    if (apres.has(k)) apres.delete(k); else apres.add(k);
    return apres;
  });

  return (
    <Modal open={!!teacher} onClose={onClose} title={t("Affectations de l'enseignant")}>
      <div className="space-y-4">
        <p className="text-sm text-slate-600">
          {t("Cet enseignant ne peut noter que les matières cochées, dans la classe indiquée.")}
        </p>
        {aConfirmer.size > 0 && (
          <p className="text-sm rounded-lg bg-amber-50 border border-amber-200 text-amber-800 p-3">
            {t("{n} affectation(s) reprise(s) automatiquement, à confirmer.", { n: aConfirmer.size })}
          </p>
        )}
        {!isLoading && (classes.length === 0 || matieres.length === 0) && (
          <p className="text-sm text-slate-500">{t("Attribuez d'abord des classes et des matières à cet enseignant.")}</p>
        )}
        {classes.map((c) => {
          const programme = (c.subjects_detail || []).map((s) => s.id);
          const possibles = programme.length ? matieres.filter((m) => programme.includes(m.id)) : matieres;
          return (
            <fieldset key={c.id} className="border border-slate-200 rounded-lg p-3">
              <legend className="px-1 text-sm font-medium text-slate-700">{c.name}</legend>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {possibles.map((m) => {
                  const k = cle(c.id, m.id);
                  return (
                    <label key={k} className="flex items-center gap-2 text-sm text-slate-700">
                      <input type="checkbox" checked={coche.has(k)} onChange={() => basculer(k)} />
                      <span>{m.name}</span>
                      {aConfirmer.has(k) && <span className="text-xs text-amber-700">{t("À confirmer")}</span>}
                    </label>
                  );
                })}
              </div>
            </fieldset>
          );
        })}
        <div className="flex gap-3 justify-end pt-2">
          <button type="button" onClick={onClose} className="btn-secondary">{t("Annuler")}</button>
          <button type="button" disabled={saveMut.isPending || isLoading} onClick={() => saveMut.mutate()} className="btn-primary">
            {saveMut.isPending ? t("Enregistrement…") : t("Enregistrer et confirmer")}
          </button>
        </div>
      </div>
    </Modal>
  );
}
