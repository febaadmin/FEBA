import { useState, useEffect, useMemo } from "react";
import { ChevronUp, ChevronDown, Search, ChevronLeft, ChevronRight, Trash2, Inbox } from "lucide-react";
import { clsx } from "clsx";
import { t } from "../../i18n";
import AcademyBadge from "../AcademyBadge";
import ConfirmDialog from "./ConfirmDialog";
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
const DATE = /^\d{4}-\d{2}-\d{2}/;

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
          <AcademyBadge code={row.academy_code} name={row.academy_name} shortName={row.academy_short_name} />
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
  const [bulkOpen, setBulkOpen] = useState(false);

  useEffect(() => { setSelected(new Set()); }, [data]);

  const filtered = data.filter(row =>
    tableColumns.some(col => String(col.accessor ? (row[col.accessor] ?? "") : "").toLowerCase().includes(search.toLowerCase()))
  );
  // Tri : une colonne peut fournir `sortValue(row)` (date réelle, âge
  // numérique…). Sans cela, le tri textuel classait « 10 ans » avant
  // « 9 ans » et une date « 09/10/2026 » avant « 10/01/2025 ». Les valeurs
  // inconnues (null) restent en fin de liste dans les deux sens.
  const sortKeyOf = c => c.sortKey || c.accessor || (c.sortValue ? c.key : undefined);
  const sortColumn = tableColumns.find(c => sortKeyOf(c) === sortCol);
  const valueOf = row => (sortColumn?.sortValue ? sortColumn.sortValue(row) : row[sortCol]);
  const sorted = sortCol
    ? [...filtered].sort((a, b) => {
        const av = valueOf(a); const bv = valueOf(b);
        const aMissing = av === null || av === undefined || av === "";
        const bMissing = bv === null || bv === undefined || bv === "";
        if (aMissing || bMissing) return aMissing === bMissing ? 0 : (aMissing ? 1 : -1);
        const cmp = (typeof av === "number" && typeof bv === "number")
          ? av - bv
          : String(av).localeCompare(String(bv), undefined, { numeric: true });
        return sortDir === "asc" ? cmp : -cmp;
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
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
          <input value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} placeholder={t("Rechercher...")} className="input pl-9" />
        </div>
        {selectable && onBulkDelete && selected.size > 0 && (
          <button onClick={() => setBulkOpen(true)} disabled={bulkDeletePending} className="btn-danger flex items-center gap-2">
            <Trash2 className="w-4 h-4" />
            {bulkDeletePending ? t("Suppression...") : `${t(bulkDeleteLabel)} (${selected.size})`}
          </button>
        )}
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-200/80 bg-white">
        <table className="w-full text-sm table-cartes">
          <thead className="bg-slate-50/80 border-b border-slate-200 sticky top-0">
            <tr>
              {selectable && (
                <th className="px-4 py-3 w-10">
                  <input type="checkbox" checked={allPageChecked}
                    ref={el => { if (el) el.indeterminate = someChecked && !allPageChecked; }}
                    onChange={toggleAll} className="w-4 h-4 accent-primary cursor-pointer" title={t("Tout sélectionner cette page")} />
                </th>
              )}
              {tableColumns.map(col => (
                <th key={col.key} scope="col" aria-sort={sortCol && sortCol === sortKeyOf(col) ? (sortDir === "asc" ? "ascending" : "descending") : undefined}
                  tabIndex={col.sortable !== false && sortKeyOf(col) ? 0 : undefined}
                  onKeyDown={e => { const k = sortKeyOf(col); if ((e.key === "Enter" || e.key === " ") && col.sortable !== false && k) { e.preventDefault(); toggleSort(k); } }}
                  onClick={() => { const k = sortKeyOf(col); if (col.sortable !== false && k) toggleSort(k); }}
                  className={clsx("px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500", col.sortable !== false && "cursor-pointer hover:text-primary select-none")}>
                  <div className="flex items-center gap-1">
                    {col.label}
                    {sortCol && sortCol === sortKeyOf(col) && (sortDir === "asc" ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />)}
                  </div>
                </th>
              ))}
              {actions && <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">{t("Actions")}</th>}
            </tr>
          </thead>
          {/* Changement de page ou de tri : apparition brève (coupée si moins d'animations est demandé). */}
          <tbody key={`${page}-${sortCol}-${sortDir}`} className="divide-y divide-slate-100 animate-apparition motion-reduce:animate-none">
            {paged.length === 0 ? (
              <tr><td colSpan={colSpanTotal} className="px-4 py-0 whitespace-pre-line"><span className="etat-vide"><Inbox className="w-7 h-7 text-slate-300" aria-hidden="true" />{emptyMessage || t("Aucun résultat")}</span></td></tr>
            ) : paged.map((row, i) => {
              const isSel = selectable && row.id && selected.has(row.id);
              return (
                <tr key={row.id || i} onClick={() => onRowClick && onRowClick(row)}
                  className={clsx("transition-colors", isSel ? "bg-primary-50" : "hover:bg-primary-50/40", onRowClick && "cursor-pointer")}>
                  {selectable && (
                    <td className="px-4 py-3 w-10" onClick={e => e.stopPropagation()}>
                      <input type="checkbox" checked={isSel} onChange={() => row.id && toggleOne(row.id)} className="w-4 h-4 accent-primary cursor-pointer" />
                    </td>
                  )}
                  {tableColumns.map(col => (
                    <td key={col.key} data-label={typeof col.label === "string" ? col.label : ""} className={clsx("px-4 py-3 text-slate-700", DATE.test(String(row[col.accessor] ?? "")) && "whitespace-nowrap tabular-nums")}>{col.render ? col.render(row) : row[col.accessor]}</td>
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
          <span>{t("{n} résultat(s)", { n: filtered.length })}{selected.size > 0 && <span className="ml-2 text-primary font-medium">· {selected.size} {t("sélectionné(s)")}</span>}</span>
          {totalPages > 1 && (
            <div className="flex items-center gap-2">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} aria-label={t("Page précédente")} className="p-2 rounded-lg hover:bg-slate-100 disabled:opacity-40"><ChevronLeft className="w-4 h-4" /></button>
              <span>{t("Page")} {page} / {totalPages}</span>
              <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} aria-label={t("Page suivante")} className="p-2 rounded-lg hover:bg-slate-100 disabled:opacity-40"><ChevronRight className="w-4 h-4" /></button>
            </div>
          )}
        </div>
      )}
      <ConfirmDialog open={bulkOpen} onClose={() => setBulkOpen(false)} loading={bulkDeletePending}
        title="Supprimer la sélection"
        message={bulkConfirmMessage ? bulkConfirmMessage(selected.size) : t("Supprimer {n} élément(s) sélectionné(s) ?", { n: selected.size })}
        onConfirm={() => { onBulkDelete([...selected]); setSelected(new Set()); setBulkOpen(false); }} />
    </div>
  );
}
