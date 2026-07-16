import { useState, useRef, useEffect } from "react";
import { Search, ChevronDown, X } from "lucide-react";
import { clsx } from "clsx";
import { t } from "../../i18n";

export default function SearchableSelect({
  options = [],
  value,
  onChange,
  placeholder = "Sélectionner...",
  labelKey = "label",
  valueKey = "value",
  disabled = false,
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const ref = useRef(null);
  const listRef = useRef(null);

  const selected = options.find(o => String(o[valueKey]) === String(value));

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Flip dropdown up if not enough space below
  const [flipUp, setFlipUp] = useState(false);
  useEffect(() => {
    if (!open || !ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    setFlipUp(spaceBelow < 260);
  }, [open]);

  // FIX v33 : recherche insensible a la casse ET aux accents ("eleve" trouve "Eleve")
  const norm = (s) =>
    String(s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  const filtered = options.filter(o => norm(o[labelKey]).includes(norm(search)));

  // Navigation clavier (accessibilite) : fleches + Entree + Echap
  const [highlight, setHighlight] = useState(0);
  useEffect(() => { setHighlight(0); }, [search, open]);
  const onKeyDown = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setHighlight(h => Math.min(h + 1, filtered.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setHighlight(h => Math.max(h - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); if (filtered[highlight]) select(filtered[highlight]); }
    else if (e.key === "Escape") { setOpen(false); setSearch(""); }
  };

  const select = (opt) => { onChange(opt[valueKey]); setOpen(false); setSearch(""); };
  const clear = (e) => { e.stopPropagation(); onChange(""); setSearch(""); };

  return (
    <div ref={ref} className="relative w-full">
      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setOpen(!open)}
        className={clsx(
          "input w-full text-left flex items-center justify-between min-h-[42px]",
          disabled && "opacity-50 cursor-not-allowed"
        )}
      >
        <span className={clsx("truncate flex-1 text-sm", !selected && "text-slate-400")}>
          {selected ? selected[labelKey] : placeholder}
        </span>
        <div className="flex items-center gap-1 shrink-0 ml-2">
          {selected && (
            <X
              className="w-3.5 h-3.5 text-slate-400 hover:text-slate-600"
              onClick={clear}
            />
          )}
          <ChevronDown className={clsx("w-4 h-4 text-slate-400 transition-transform", open && "rotate-180")} />
        </div>
      </button>

      {open && (
        <div
          className={clsx(
            "absolute z-[9999] left-0 right-0 bg-white border border-slate-200 rounded-xl shadow-xl flex flex-col",
            "max-h-64",
            flipUp ? "bottom-full mb-1" : "top-full mt-1"
          )}
          style={{ minWidth: "100%" }}
        >
          <div className="p-2 border-b border-slate-100 shrink-0">
            <div className="relative">
              <Search className="absolute left-2.5 top-2 w-4 h-4 text-slate-400" />
              <input
                ref={listRef}
                autoFocus
                value={search}
                onChange={e => setSearch(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder={t("Rechercher...")}
                className="input pl-8 py-1.5 text-sm w-full"
              />
            </div>
          </div>
          <div className="overflow-y-auto flex-1">
            {filtered.length === 0 ? (
              <div className="px-4 py-3 text-sm text-slate-400 text-center">{t("Aucun résultat")}</div>
            ) : (
              filtered.map((opt, i) => (
                <button
                  key={opt[valueKey]}
                  type="button"
                  onClick={() => select(opt)}
                  onMouseEnter={() => setHighlight(i)}
                  className={clsx(
                    "w-full text-left px-4 py-2.5 text-sm transition-colors",
                    i === highlight && "bg-primary-50 text-primary",
                    String(opt[valueKey]) === String(value) && "bg-primary-50 text-primary font-medium"
                  )}
                >
                  {opt[labelKey]}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
