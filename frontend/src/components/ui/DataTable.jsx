import { useState, useEffect, useMemo } from "react";
import { ChevronUp, ChevronDown, Search, ChevronLeft, ChevronRight, Trash2 } from "lucide-react";
import { clsx } from "clsx";
import { t } from "../../i18n";
import AcademyBadge from "../AcademyBadge";
import { useAcademy } from "../../context/AcademyContext";

/**
 * DataTable with optional bulk-select support.
 * New props:
 *   selectable        {boolean}  – show checkboxes
 *   onBulkDelete      {fn}       – called with array of selected ids
 *   bulkDeleteLabel   {string}   – label (default "Supprimer la sélection")
 *   bulkDeletePending {boolean}  – loading state
 *   academyColumn     {boolean}  – false pour désactiver la colonne Académie
 *
 * COLONNE « ACADÉMIE » AUTOMATIQUE (P2)
 * -------------------------------------
 * En mode « Toutes les Académies », les listes renvoyaient l'union des deux
 * académies sans qu'aucune colonne ne dise à laquelle chaque ligne
 * appartenait : deux élèves homonymes de deux académies étaient
 * indiscernables, et rien n'empêchait de modifier le mauvais.
 *
 * La colonne est ajoutée ICI plutôt que dans chaque écran : une trentaine
 * de tableaux passent par ce composant, et les annoter un par un aurait
 * garanti d'en oublier. Elle n'apparaît que si deux conditions sont
 * réunies — le mode consolidé est actif ET les lignes portent réellement
 * `academy_code` — de sorte qu'un tableau sans rapport avec les académies
 * (historique d'une note, participants d'une salle) n'hérite pas d'une
 * colonne vide.
 */
export default function DataTable({
  columns, data = [], loading, actions, onRowClick, pageSize = 15,
  selectable = false, onBulkDelete, bulkDeleteLabel = "Supprimer la sélection", bulkDeletePending = false, bulkConfirmMessage, emptyMessage,
  academyColumn = true,
}) {
  const { isAllAcademies } = useAcademy();

  const showAcademy =
    academyColumn && isAllAcademies && data.some((row) => row && "academy_code" in row);

  const tableColumns = useMemo(() => {
    if (!showAcademy) return columns;
    return [
      {
        key: "__academy",
        // `accessor` renseigné pour que la recherche et le tri portent aussi
        // sur l'académie : filtrer « FEBA FHA » doit fonctionner.
        accessor: "academy_short_name",
        label: t("Académie"),
        render: (row) => (
          <AcademyBadge code={row.academy_code} name={row.academy_name} />
        ),
      },
      ...columns,
    ];
  }, [columns, showAcademy]);
  const [search, setSearch]     = useState("");
  const [sortCol, setSortCol]   = useState(null);
  const [sortDir, setSortDir]   = useState("asc");
  const [page, setPage]         = useState(1);
  const [selected, setSelected] = useState(new Set());

  useEffect(() => { setSelected(new Set()); }, [data]);

  const filtered = data.filter(row =>
    tableColumns.some(col => String(col.accessor ? (row[col.accessor] ?? "") : "").toLowerCase().includes(search.toLowerCase()))
  );
  const sorted = sortCol
    ? [...filtered].sort((a, b) => {
        const av = a[sortCol] ?? ""; const bv = b[sortCol] ?? "";
        return sortDir === "asc" ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
      })
    : filtered;

  const totalPages = Math.ceil(sorted.length / pageSize);
  const paged = sorted.slice((page - 1) * pageSize, page * pageSize);
  const toggleSort = col => { if (sortCol === col) setSortDir(d => d === "asc" ? "desc" : "asc"); else { setSortCol(col); setSortDir("asc"); } };

  const pagedIds = paged.map(r => r.id).filter(Boolean);
  const allPageChecked = pagedIds.length > 0 && pagedIds.every(id => selected.has(id));
  const someChecked = pagedIds.some(id => selected.has(id));
  const toggleAll = () => { const n = new Set(selected); if (allPageChecked) pagedIds.forEach(id => n.delete(id)); else pagedIds.forEach(id => n.add(id)); setSelected(n); };
  const toggleOne = id => { const n = new Set(selected); n.has(id) ? n.delete(id) : n.add(id); setSelected(n); };

  if (loading) return <div className="space-y-3">{[...Array(6)].map((_, i) => <div key={i} className="skeleton h-12 w-full" />)}</div>;

  const colSpanTotal = tableColumns.length + (actions ? 1 : 0) + (selectable ? 1 : 0);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3 justify-between">
        <div className="relative w-72">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
          <input value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} placeholder={t("Rechercher...")} className="input pl-9" />
        </div>
        {selectable && onBulkDelete && selected.size > 0 && (
          <button onClick={() => { if (window.confirm(bulkConfirmMessage ? bulkConfirmMessage(selected.size) : `Supprimer ${selected.size} élément(s) sélectionné(s) ?`)) { onBulkDelete([...selected]); setSelected(new Set()); } }} disabled={bulkDeletePending}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50 transition shadow-sm">
            <Trash2 className="w-4 h-4" />
            {bulkDeletePending ? "Suppression…" : `${bulkDeleteLabel} (${selected.size})`}
          </button>
        )}
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-100">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-100">
            <tr>
              {selectable && (
                <th className="px-4 py-3 w-10">
                  <input type="checkbox" checked={allPageChecked}
                    ref={el => { if (el) el.indeterminate = someChecked && !allPageChecked; }}
                    onChange={toggleAll} className="w-4 h-4 accent-blue-600 cursor-pointer" title={t("Tout sélectionner cette page")} />
                </th>
              )}
              {tableColumns.map(col => (
                <th key={col.key} onClick={() => col.sortable !== false && toggleSort(col.accessor)}
                  className={clsx("px-4 py-3 text-left font-semibold text-slate-600", col.sortable !== false && "cursor-pointer hover:text-primary select-none")}>
                  <div className="flex items-center gap-1">
                    {col.label}
                    {sortCol === col.accessor && (sortDir === "asc" ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />)}
                  </div>
                </th>
              ))}
              {actions && <th className="px-4 py-3 text-right font-semibold text-slate-600">{t("Actions")}</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {paged.length === 0 ? (
              <tr><td colSpan={colSpanTotal} className="px-4 py-12 text-center text-slate-400 whitespace-pre-line">{emptyMessage || "Aucun résultat"}</td></tr>
            ) : paged.map((row, i) => {
              const isSel = selectable && row.id && selected.has(row.id);
              return (
                <tr key={row.id || i} onClick={() => onRowClick && onRowClick(row)}
                  className={clsx("transition-colors", isSel ? "bg-blue-50" : "hover:bg-slate-50", onRowClick && "cursor-pointer")}>
                  {selectable && (
                    <td className="px-4 py-3 w-10" onClick={e => e.stopPropagation()}>
                      <input type="checkbox" checked={isSel} onChange={() => row.id && toggleOne(row.id)} className="w-4 h-4 accent-blue-600 cursor-pointer" />
                    </td>
                  )}
                  {tableColumns.map(col => (
                    <td key={col.key} className="px-4 py-3 text-slate-700">{col.render ? col.render(row) : row[col.accessor]}</td>
                  ))}
                  {actions && <td className="px-4 py-3 text-right" onClick={e => e.stopPropagation()}>{actions(row)}</td>}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {(totalPages > 1 || selected.size > 0) && (
        <div className="flex items-center justify-between mt-4 text-sm text-slate-500">
          <span>{filtered.length} résultat(s){selected.size > 0 && <span className="ml-2 text-blue-600 font-medium">· {selected.size} {t("sélectionné(s)")}</span>}</span>
          {totalPages > 1 && (
            <div className="flex items-center gap-2">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="p-1 rounded hover:bg-slate-100 disabled:opacity-40"><ChevronLeft className="w-4 h-4" /></button>
              <span>{t("Page")} {page} / {totalPages}</span>
              <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="p-1 rounded hover:bg-slate-100 disabled:opacity-40"><ChevronRight className="w-4 h-4" /></button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
