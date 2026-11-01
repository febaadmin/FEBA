/**
 * Appréciations — barème des bulletins de l'académie active.
 *
 * Le barème se modifie en BROUILLON puis s'enregistre EN ENTIER : le
 * serveur le valide d'un bloc (apps/grades/appreciations.py) et le
 * remplace atomiquement. Rien n'est annoncé comme enregistré avant sa
 * réponse. Les seuils sont des POURCENTAGES de la note maximale : la même
 * règle sert aux bulletins sur 10 (primaire) et sur 20 (secondaire).
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, RotateCcw, Save, Trash2, Undo2 } from "lucide-react";
import toast from "react-hot-toast";
import { appreciationsAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import ConfirmDialog from "../../components/ui/ConfirmDialog";
import { useAcademy } from "../../context/AcademyContext";
import { extractApiError } from "../../utils/errors";
import { t } from "../../i18n";

const SCOPES = [
  ["", "Tous les cycles"],
  ["maternelle", "Maternelle"],
  ["primaire", "Primaire"],
  ["college", "Collège"],
  ["lycee", "Lycée"],
];

const toRow = (r) => ({
  key: `id-${r.id}`, id: r.id, min_percent: r.min_percent, label_fr: r.label_fr,
  label_en: r.label_en || "", is_active: r.is_active, used: r.used_by_bulletins || 0,
});
let draftCounter = 0;
const newRow = (extra = {}) => ({
  key: `new-${(draftCounter += 1)}`, id: null, min_percent: "", label_fr: "", label_en: "",
  is_active: true, used: 0, ...extra,
});

/** Contrôle local, miroir du serveur (qui reste seul juge). */
export function localErrors(rows) {
  const errors = [];
  const active = rows.filter((r) => r.is_active);
  const seen = new Map();
  const labels = new Map();
  rows.forEach((r, i) => {
    const n = Number(r.min_percent);
    if (r.min_percent === "" || Number.isNaN(n) || n < 0 || n > 100)
      errors.push(t("Ligne {n} : seuil entre 0 et 100 %.", { n: i + 1 }));
    if (r.is_active && !r.label_fr.trim())
      errors.push(t("Ligne {n} : libellé français obligatoire.", { n: i + 1 }));
    if (r.is_active && !Number.isNaN(n)) {
      if (seen.has(n)) errors.push(t("Lignes {a} et {b} : même seuil.", { a: seen.get(n), b: i + 1 }));
      seen.set(n, i + 1);
      const label = r.label_fr.trim().toUpperCase();
      if (label && labels.has(label)) errors.push(t("Lignes {a} et {b} : libellé en double.", { a: labels.get(label), b: i + 1 }));
      labels.set(label, i + 1);
    }
  });
  if (!active.length) errors.push(t("Au moins une appréciation active est requise."));
  else if (Math.min(...active.map((r) => Number(r.min_percent))) !== 0)
    errors.push(t("Le seuil le plus bas doit valoir 0 %."));
  return errors;
}

/** Intervalle [seuil, seuil suivant[ de chaque palier actif. */
function intervals(rows) {
  const active = rows.filter((r) => r.is_active && r.min_percent !== "" && !Number.isNaN(Number(r.min_percent)))
    .map((r) => ({ key: r.key, min: Number(r.min_percent) }))
    .sort((a, b) => b.min - a.min);
  const out = {};
  active.forEach((r, i) => { out[r.key] = { min: r.min, max: i === 0 ? 100 : active[i - 1].min, top: i === 0 }; });
  return out;
}

const fmt = (n) => Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });

export default function AdminAppreciations() {
  const qc = useQueryClient();
  const { activeAcademy, isAllAcademies } = useAcademy();
  const academyId = activeAcademy?.id || null;
  const [scope, setScope] = useState("");
  // Brouillon RATTACHÉ à la version du serveur dont il part : quand une
  // nouvelle version arrive (enregistrement, changement de portée), le
  // brouillon périmé est simplement ignoré — sans effet de synchronisation.
  const [edit, setEdit] = useState({ source: null, rows: [], errors: [] });
  const [resetOpen, setResetOpen] = useState(false);
  const [previewValue, setPreviewValue] = useState("");
  const [previewMax, setPreviewMax] = useState("20");

  const query = useQuery({
    queryKey: ["appreciations", academyId, scope],
    queryFn: () => appreciationsAPI.get(scope),
    enabled: Boolean(academyId),
  });
  const payload = query.data?.data;
  const saved = useMemo(() => (payload?.rules || []).map(toRow), [payload]);
  const current = edit.source === saved;
  const rows = current ? edit.rows : saved;
  const serverErrors = current ? edit.errors : [];
  const setRows = (updater) => setEdit((prev) => {
    const base = prev.source === saved ? prev.rows : saved;
    return { source: saved, rows: typeof updater === "function" ? updater(base) : updater, errors: [] };
  });
  const setServerErrors = (errors) => setEdit((prev) => ({
    source: saved, rows: prev.source === saved ? prev.rows : saved, errors,
  }));

  const comparable = (list) => JSON.stringify(
    list.map((r) => [r.id, String(r.min_percent), r.label_fr, r.label_en, r.is_active]));
  const dirty = comparable(rows) !== comparable(saved);
  const errors = localErrors(rows);
  const ranges = intervals(rows);
  const hasOwnScale = saved.length > 0;

  const after = (resp, message) => {
    qc.setQueryData(["appreciations", academyId, scope], resp);
    qc.invalidateQueries({ queryKey: ["appreciation-scale"] });
    toast.success(message);
  };
  const saveMut = useMutation({
    mutationFn: () => appreciationsAPI.save(scope, rows.map((r) => ({
      id: r.id, min_percent: String(r.min_percent), label_fr: r.label_fr.trim(),
      label_en: r.label_en.trim(), is_active: r.is_active,
    }))),
    onSuccess: (resp) => after(resp, t("Barème enregistré.")),
    onError: (e) => {
      const list = e?.response?.data?.errors;
      setServerErrors(Array.isArray(list) ? list : [extractApiError(e)]);
      toast.error(t("Barème non enregistré."));
    },
  });
  const resetMut = useMutation({
    mutationFn: () => appreciationsAPI.reset(scope),
    onSuccess: (resp) => { setResetOpen(false); after(resp, t("Barème par défaut rétabli.")); },
    onError: (e) => { setResetOpen(false); toast.error(extractApiError(e)); },
  });
  const previewMut = useMutation({
    mutationFn: () => appreciationsAPI.preview({
      value: previewValue, max_value: previewMax, cycle: scope,
      rules: rows.map((r) => ({ min_percent: String(r.min_percent), label_fr: r.label_fr,
        label_en: r.label_en, is_active: r.is_active })),
    }),
    onError: (e) => toast.error(extractApiError(e)),
  });

  const update = (key, field, value) =>
    setRows((list) => list.map((r) => (r.key === key ? { ...r, [field]: value } : r)));
  const remove = (key) => setRows((list) => list.filter((r) => r.key !== key));
  const startCycleScale = () =>
    setRows((payload?.effective || []).map((r) => newRow({
      min_percent: r.min_percent, label_fr: r.label_fr, label_en: r.label_en,
    })));

  if (isAllAcademies || !academyId) {
    return (
      <div className="space-y-6">
        <PageHeader title={t("Appréciations")} subtitle={t("Barème des appréciations des bulletins")} />
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800" role="alert">
          {t("Sélectionnez d'abord l'académie dont vous gérez le barème (sélecteur d'académie en haut de page).")}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("Appréciations")}
        subtitle={t("Barème des appréciations des bulletins : {name}", { name: activeAcademy.name })}
        action={
          <div className="flex gap-2">
            <button className="btn-secondary flex items-center gap-2" onClick={() => setResetOpen(true)}
                    disabled={resetMut.isPending} data-testid="appreciations-reset">
              <RotateCcw className="w-4 h-4" />{t("Barème par défaut")}
            </button>
            <button className="btn-primary flex items-center gap-2" onClick={() => saveMut.mutate()}
                    disabled={!dirty || errors.length > 0 || saveMut.isPending} data-testid="appreciations-save">
              <Save className="w-4 h-4" />{saveMut.isPending ? t("Enregistrement…") : t("Enregistrer")}
            </button>
          </div>
        }
      />

      <div className="card space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-sm font-semibold text-slate-700" htmlFor="appr-scope">{t("Portée")}</label>
          <select id="appr-scope" className="input max-w-xs" value={scope} data-testid="appreciations-scope"
                  onChange={(e) => { if (!dirty || window.confirm(t("Abandonner les modifications non enregistrées ?"))) setScope(e.target.value); }}>
            {SCOPES.map(([value, label]) => (
              <option key={value} value={value}>
                {t(label)}{value && payload?.cycles_with_override?.includes(value) ? ` - ${t("barème propre")}` : ""}
              </option>
            ))}
          </select>
          {dirty && <span className="text-xs font-semibold text-amber-700" data-testid="appreciations-dirty">{t("Modifications non enregistrées")}</span>}
        </div>
        <p className="text-xs text-slate-500">
          {t("Seuil bas inclusif, en pourcentage de la note maximale : 95 % = 19/20 = 9,5/10. Une note prend l'appréciation du palier actif le plus élevé qu'elle atteint ; une note exactement sur un seuil prend ce palier.")}
        </p>
      </div>

      {query.isLoading ? (
        <div className="card py-12 text-center text-slate-400">{t("Chargement…")}</div>
      ) : query.isError ? (
        <div className="card py-12 text-center text-danger">{extractApiError(query.error)}</div>
      ) : !hasOwnScale && rows.length === 0 ? (
        <div className="card space-y-3" data-testid="appreciations-inherited">
          <p className="text-sm text-slate-600">
            {scope
              ? t("Ce cycle utilise le barème de l'académie (« Tous les cycles »).")
              : t("Cette académie applique le barème par défaut de la plateforme.")}
          </p>
          <ul className="text-xs text-slate-500 grid sm:grid-cols-3 gap-1">
            {(payload?.effective || []).map((r) => (
              <li key={r.min_percent}>≥ {fmt(r.min_percent)} % : {r.label_fr}</li>
            ))}
          </ul>
          <button className="btn-secondary" onClick={startCycleScale} data-testid="appreciations-customize">
            {scope ? t("Créer un barème propre à ce cycle") : t("Personnaliser le barème de cette académie")}
          </button>
        </div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm" data-testid="appreciations-table">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wider text-slate-500">
                <th className="py-2 px-2">{t("Libellé (français)")}</th>
                <th className="py-2 px-2">{t("Libellé (anglais)")}</th>
                <th className="py-2 px-2">{t("Seuil (%)")}</th>
                <th className="py-2 px-2">{t("Intervalle")}</th>
                <th className="py-2 px-2">{t("Active")}</th>
                <th className="py-2 px-2">{t("Bulletins")}</th>
                <th className="py-2 px-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {rows.map((r, i) => {
                const range = ranges[r.key];
                return (
                  <tr key={r.key} data-testid={`appreciation-row-${i}`}>
                    <td className="py-2 px-2">
                      <input className="input" value={r.label_fr} aria-label={t("Libellé (français)")}
                             onChange={(e) => update(r.key, "label_fr", e.target.value)} />
                    </td>
                    <td className="py-2 px-2">
                      <input className="input" value={r.label_en} aria-label={t("Libellé (anglais)")}
                             onChange={(e) => update(r.key, "label_en", e.target.value)} />
                    </td>
                    <td className="py-2 px-2 w-28">
                      <input className="input" type="number" min="0" max="100" step="0.01" value={r.min_percent}
                             aria-label={t("Seuil (%)")} onChange={(e) => update(r.key, "min_percent", e.target.value)} />
                    </td>
                    <td className="py-2 px-2 text-xs text-slate-600 whitespace-nowrap">
                      {range ? (
                        <>
                          {fmt(range.min)} % → {range.top ? "100 %" : `< ${fmt(range.max)} %`}
                          <span className="block text-slate-400">
                            /20 : {fmt(range.min / 5)}{range.top ? "–20" : `–${fmt(range.max / 5)}`} ·
                            /10 : {fmt(range.min / 10)}{range.top ? "–10" : `–${fmt(range.max / 10)}`}
                          </span>
                        </>
                      ) : "-"}
                    </td>
                    <td className="py-2 px-2">
                      <input type="checkbox" checked={r.is_active} aria-label={t("Active")}
                             onChange={(e) => update(r.key, "is_active", e.target.checked)} />
                    </td>
                    <td className="py-2 px-2 text-xs">{r.used || 0}</td>
                    <td className="py-2 px-2">
                      <button onClick={() => remove(r.key)} disabled={r.used > 0}
                              title={r.used > 0 ? t("Utilisée par des bulletins émis : désactivez-la au lieu de la supprimer.") : t("Supprimer")}
                              className="p-1.5 rounded-lg hover:bg-danger-50 text-slate-500 disabled:opacity-30">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="flex gap-2 mt-3">
            <button className="btn-secondary flex items-center gap-2" onClick={() => setRows((l) => [...l, newRow()])}
                    data-testid="appreciations-add">
              <Plus className="w-4 h-4" />{t("Ajouter une appréciation")}
            </button>
            {dirty && (
              <button className="btn-secondary flex items-center gap-2" onClick={() => setEdit({ source: null, rows: [], errors: [] })}>
                <Undo2 className="w-4 h-4" />{t("Annuler les modifications")}
              </button>
            )}
          </div>
          {(errors.length > 0 || serverErrors.length > 0) && (
            <ul className="mt-3 space-y-1 text-sm text-danger" role="alert" data-testid="appreciations-errors">
              {[...serverErrors, ...errors].map((err) => <li key={err}>• {err}</li>)}
            </ul>
          )}
        </div>
      )}

      <div className="card space-y-3">
        <h2 className="font-semibold text-slate-800">{t("Aperçu")}</h2>
        <div className="flex flex-wrap items-end gap-3">
          <label className="block">
            <span className="label">{t("Note")}</span>
            <input className="input w-28" type="number" min="0" step="0.01" value={previewValue}
                   onChange={(e) => setPreviewValue(e.target.value)} data-testid="appreciations-preview-value" />
          </label>
          <label className="block">
            <span className="label">{t("Sur")}</span>
            <select className="input w-24" value={previewMax} onChange={(e) => setPreviewMax(e.target.value)}>
              <option value="10">10</option>
              <option value="20">20</option>
            </select>
          </label>
          <button className="btn-secondary" disabled={previewValue === "" || errors.length > 0 || previewMut.isPending}
                  onClick={() => previewMut.mutate()} data-testid="appreciations-preview">
            {t("Voir l'appréciation")}
          </button>
          {previewMut.data?.data && (
            <p className="text-sm" data-testid="appreciations-preview-result">
              {previewMut.data.data.value}/{previewMut.data.data.max_value} ({previewMut.data.data.percent} %) →{" "}
              <strong>{previewMut.data.data.label_fr}</strong> / {previewMut.data.data.label_en}
            </p>
          )}
        </div>
        <p className="text-xs text-slate-500">
          {t("L'aperçu applique le barème affiché, même non enregistré. Les bulletins déjà émis gardent leur appréciation ; les bulletins générés ensuite utilisent le barème enregistré.")}
        </p>
      </div>

      <ConfirmDialog
        open={resetOpen}
        onClose={() => setResetOpen(false)}
        loading={resetMut.isPending}
        onConfirm={() => resetMut.mutate()}
        message={scope
          ? t("Supprimer le barème propre à ce cycle ? Le barème de l'académie s'appliquera de nouveau.")
          : t("Rétablir le barème par défaut ? Le barème actuel sera remplacé (les appréciations figurant sur des bulletins émis sont conservées, désactivées).")}
      />
    </div>
  );
}
