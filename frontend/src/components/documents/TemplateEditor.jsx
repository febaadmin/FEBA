/**
 * Éditeur d'un gabarit de document : placement des champs sur le fond réel.
 *
 * Les zones sont stockées en millimètres (voir utils/templateLayout.js).
 * L'aperçu affiche le fond renvoyé par le serveur ; glisser une zone ou sa
 * poignée la déplace / la redimensionne, les champs numériques permettent
 * un réglage au dixième de millimètre. Rien n'est « enregistré » avant la
 * réponse du serveur, qui revalide tout.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Eye, Plus, Save, ShieldCheck, Trash2 } from "lucide-react";
import toast from "react-hot-toast";
import { documentTemplatesAPI } from "../../api";
import Modal from "../ui/Modal";
import { extractApiError } from "../../utils/errors";
import {
  blobErrorDetail, boxStyle, clampBox, layoutProblems, newField, pxToMm,
} from "../../utils/templateLayout";
import { t } from "../../i18n";

const FONT_LABELS = {
  serif: "Serif (Crimson Pro)",
  serif_italic: "Serif italique (Crimson Pro)",
  sans: "Sans serif (Helvetica)",
  sans_bold: "Sans serif gras (Helvetica)",
  times: "Times",
};
const RULE_LABELS = {
  admin_decision: "Décision de l'administration (aucune condition automatique)",
  annual_average: "Moyenne annuelle minimale",
  enrolled: "Élève inscrit dans une classe pour l'année",
};
const TEXT_OPTIONS = [
  ["document_title", "Intitulé du document"],
  ["signatory_name", "Nom du signataire"],
  ["signatory_title", "Fonction du signataire"],
];

export default function TemplateEditor({ template, catalog, rules, onClose }) {
  const qc = useQueryClient();
  const page = { width_mm: template.page_width_mm, height_mm: template.page_height_mm };
  const [fields, setFields] = useState(() => template.fields.map((f) => ({ ...f })));
  const [options, setOptions] = useState(() => ({
    document_title: "", signatory_name: "", signatory_title: "", certificate_purpose: "",
    ...template.options,
    eligibility: template.options?.eligibility || { rule: rules[0] },
  }));
  const [pageIndex, setPageIndex] = useState(template.page_index || 0);
  const [selected, setSelected] = useState(fields[0]?.name || null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const surface = useRef(null);
  const drag = useRef(null);
  const editable = template.is_editable;

  const kindCatalog = catalog.filter((c) => c.kinds.includes(template.kind));
  const labelOf = (name) => t(kindCatalog.find((c) => c.name === name)?.label || name);
  const problems = useMemo(() => layoutProblems(fields, page, labelOf),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [fields, page.width_mm, page.height_mm]);
  const flagged = new Set(problems.flatMap((p) => p.names));

  const { data: background } = useQuery({
    queryKey: ["template-background", template.id, template.page_index],
    queryFn: async () => URL.createObjectURL((await documentTemplatesAPI.background(template.id)).data),
    staleTime: Infinity,
  });
  useEffect(() => () => { if (background) URL.revokeObjectURL(background); }, [background]);
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);

  const payload = () => {
    const opts = { ...options };
    if (template.kind !== "certificate") delete opts.certificate_purpose;
    delete opts.page_sizes;
    delete opts.page_format;
    if (template.page_count > 1) opts.page_index = Number(pageIndex);
    return { fields, options: opts };
  };

  const refresh = () => qc.invalidateQueries({ queryKey: ["document-templates"] });

  const save = useMutation({
    mutationFn: () => documentTemplatesAPI.configure(template.id, payload()),
    onSuccess: () => { toast.success(t("Configuration enregistrée. Vérifiez le gabarit avant de l'activer.")); refresh(); },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const verify = useMutation({
    mutationFn: async () => {
      await documentTemplatesAPI.configure(template.id, payload());
      return documentTemplatesAPI.action(template.id, "validate");
    },
    onSuccess: (response) => {
      const report = response.data.report;
      if (report.ok) toast.success(t("Gabarit vérifié : rendu d'essai conforme. Il peut être activé."));
      else toast.error(report.errors.join(" "));
      refresh();
      onClose();
    },
    onError: (err) => toast.error(extractApiError(err)),
  });

  const preview = useMutation({
    mutationFn: async () => {
      if (editable) await documentTemplatesAPI.configure(template.id, payload());
      return documentTemplatesAPI.preview(template.id, { frames: true, format: "png" });
    },
    onSuccess: (response) => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setPreviewUrl(URL.createObjectURL(response.data));
      refresh();
    },
    onError: async (err) => toast.error((await blobErrorDetail(err)) || extractApiError(err)),
  });

  const update = (name, patch) =>
    setFields((list) => list.map((f) => (f.name === name ? clampBox({ ...f, ...patch }, page) : f)));

  const startDrag = (event, name, mode) => {
    if (!editable) return;
    event.preventDefault();
    event.stopPropagation();
    const rect = surface.current.getBoundingClientRect();
    const field = fields.find((f) => f.name === name);
    drag.current = { name, mode, startX: event.clientX, startY: event.clientY, origin: { ...field },
      widthPx: rect.width, heightPx: rect.height };
    setSelected(name);
    const move = (e) => {
      const d = drag.current;
      if (!d) return;
      const dx = pxToMm(e.clientX - d.startX, d.widthPx, page.width_mm);
      const dy = pxToMm(e.clientY - d.startY, d.heightPx, page.height_mm);
      update(d.name, d.mode === "move"
        ? { x_mm: d.origin.x_mm + dx, y_mm: d.origin.y_mm + dy }
        : { width_mm: d.origin.width_mm + dx, height_mm: d.origin.height_mm + dy });
    };
    const up = () => {
      drag.current = null;
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  const current = fields.find((f) => f.name === selected) || null;
  const available = kindCatalog.filter((c) => !fields.some((f) => f.name === c.name));
  const textOptions = template.kind === "certificate"
    ? [...TEXT_OPTIONS, ["certificate_purpose", "Objet du certificat"]] : TEXT_OPTIONS;
  const placed = new Set(fields.map((f) => f.name));

  return (
    <Modal open onClose={onClose} size="xl"
           title={t("{k} — version n° {v}", { k: t(template.kind_display), v: template.version })}>
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-3 min-w-0">
          <p className="text-xs text-slate-500">
            {t("Page {w} × {h} mm. Faites glisser une zone pour la déplacer, sa poignée pour la redimensionner.",
               { w: page.width_mm, h: page.height_mm })}
          </p>
          <div ref={surface} data-testid="template-surface"
               className="relative w-full border border-slate-300 bg-slate-100 select-none touch-none overflow-hidden"
               style={{ aspectRatio: `${page.width_mm} / ${page.height_mm}` }}
               onPointerDown={() => setSelected(null)}>
            {background && (
              <img src={background} alt={t("Fond du gabarit")} draggable={false}
                   className="absolute inset-0 w-full h-full object-contain pointer-events-none" />
            )}
            {fields.map((f) => (
              <div key={f.name} data-testid={`zone-${f.name}`}
                   className={`absolute border-2 ${flagged.has(f.name) ? "border-red-500 bg-red-500/15"
                     : selected === f.name ? "border-blue-600 bg-blue-500/15" : "border-blue-400/80 bg-blue-400/10"}
                     ${editable ? "cursor-move" : ""}`}
                   style={boxStyle(f, page)}
                   onPointerDown={(e) => startDrag(e, f.name, "move")}>
                <span className="absolute -top-4 left-0 text-[10px] leading-none font-medium text-blue-800 bg-white/80 px-1 whitespace-nowrap">
                  {labelOf(f.name)}
                </span>
                {editable && (
                  <span className="absolute -right-1.5 -bottom-1.5 w-3 h-3 bg-blue-600 cursor-se-resize rounded-sm"
                        onPointerDown={(e) => startDrag(e, f.name, "resize")} />
                )}
              </div>
            ))}
          </div>

          {problems.length > 0 && (
            <ul className="text-sm text-red-700 space-y-1">
              {problems.map((p, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                  {p.type === "overlap" && t("Zones superposées : {l}", { l: p.label })}
                  {p.type === "outside" && t("Zone hors de la page : {l}", { l: p.label })}
                  {p.type === "missing_name" && t("Le nom de l'élève doit être placé.")}
                </li>
              ))}
            </ul>
          )}

          {previewUrl && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-slate-600">
                {t("Aperçu rendu par le serveur (valeurs d'exemple, cadres des zones en pointillés)")}
              </p>
              <img src={previewUrl} alt={t("Aperçu du document")} className="w-full border border-slate-200" />
            </div>
          )}
        </div>

        <div className="space-y-4 text-sm">
          {!editable && (
            <p className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-slate-700">
              {t("Cette version est en lecture seule. Créez une nouvelle version pour modifier sa configuration.")}
            </p>
          )}

          {template.page_count > 1 && (
            <label className="block">
              <span className="block text-xs text-slate-500 mb-1">{t("Page du PDF utilisée comme fond")}</span>
              <select className="input" disabled={!editable} value={pageIndex}
                      onChange={(e) => setPageIndex(e.target.value)}>
                {Array.from({ length: template.page_count }, (_, i) => (
                  <option key={i} value={i}>{t("Page {n} sur {c}", { n: i + 1, c: template.page_count })}</option>
                ))}
              </select>
              <span className="block text-xs text-slate-500 mt-1">
                {t("Le document remis ne contient que cette page. Enregistrez puis rouvrez l'éditeur pour voir son fond.")}
              </span>
            </label>
          )}

          <fieldset className="space-y-2" disabled={!editable}>
            <legend className="text-xs font-semibold text-slate-600 uppercase">{t("Textes du gabarit")}</legend>
            {textOptions.map(([key, label]) => (
              <label key={key} className="block">
                <span className="block text-xs text-slate-500 mb-0.5">
                  {t(label)}{placed.has(key) ? " *" : ""}
                </span>
                <input className="input" value={options[key] || ""} maxLength={200}
                       onChange={(e) => setOptions({ ...options, [key]: e.target.value })} />
              </label>
            ))}
          </fieldset>

          <fieldset className="space-y-2" disabled={!editable}>
            <legend className="text-xs font-semibold text-slate-600 uppercase">{t("Règle d'émission")}</legend>
            <select className="input" aria-label={t("Règle d'émission")} value={options.eligibility?.rule}
                    onChange={(e) => setOptions({ ...options, eligibility: { rule: e.target.value,
                      ...(e.target.value === "annual_average" ? { min_average: 10 } : {}) } })}>
              {rules.map((rule) => <option key={rule} value={rule}>{t(RULE_LABELS[rule])}</option>)}
            </select>
            {options.eligibility?.rule === "annual_average" && (
              <label className="block">
                <span className="block text-xs text-slate-500 mb-0.5">
                  {t("Moyenne minimale, sur 20 (convertie sur 10 pour le primaire)")}
                </span>
                <input type="number" min="0" max="20" step="0.25" className="input"
                       value={options.eligibility.min_average ?? 10}
                       onChange={(e) => setOptions({ ...options,
                         eligibility: { rule: "annual_average", min_average: e.target.value } })} />
              </label>
            )}
          </fieldset>

          {editable && available.length > 0 && (
            <div className="flex gap-2">
              <select className="input" aria-label={t("Champ à placer")} id="add-field" defaultValue="">
                <option value="" disabled>{t("Champ à placer…")}</option>
                {available.map((c) => <option key={c.name} value={c.name}>{t(c.label)}</option>)}
              </select>
              <button type="button" className="btn-secondary px-3" title={t("Placer ce champ")}
                      onClick={() => {
                        const select = document.getElementById("add-field");
                        if (!select.value) return;
                        setFields((list) => [...list, newField(select.value, page, list)]);
                        setSelected(select.value);
                        select.value = "";
                      }}>
                <Plus className="w-4 h-4" />
              </button>
            </div>
          )}

          <ul className="space-y-1">
            {fields.map((f) => (
              <li key={f.name}>
                <button type="button" onClick={() => setSelected(f.name)}
                        className={`w-full text-left px-2 py-1 rounded-lg ${selected === f.name
                          ? "bg-blue-50 text-blue-800" : "hover:bg-slate-50"} ${flagged.has(f.name) ? "text-red-700" : ""}`}>
                  {labelOf(f.name)}{f.required ? " *" : ""}
                </button>
              </li>
            ))}
          </ul>

          {current && (
            <fieldset className="space-y-2 border-t border-slate-100 pt-3" disabled={!editable}>
              <legend className="text-xs font-semibold text-slate-600 uppercase">{labelOf(current.name)}</legend>
              <div className="grid grid-cols-2 gap-2">
                {[["x_mm", "X (mm)"], ["y_mm", "Y (mm)"], ["width_mm", "Largeur (mm)"], ["height_mm", "Hauteur (mm)"],
                  ["font_size_pt", "Taille (pt)"], ["min_font_size_pt", "Taille min. (pt)"]].map(([key, label]) => (
                  <label key={key} className="block">
                    <span className="block text-xs text-slate-500">{t(label)}</span>
                    <input type="number" step="0.5" className="input" value={current[key]}
                           onChange={(e) => update(current.name, { [key]: Number(e.target.value) })} />
                  </label>
                ))}
              </div>
              <label className="block">
                <span className="block text-xs text-slate-500">{t("Police")}</span>
                <select className="input" value={current.font}
                        onChange={(e) => update(current.name, { font: e.target.value })}>
                  {Object.entries(FONT_LABELS).map(([key, label]) => <option key={key} value={key}>{t(label)}</option>)}
                </select>
              </label>
              <div className="grid grid-cols-3 gap-2">
                <label className="block col-span-1">
                  <span className="block text-xs text-slate-500">{t("Alignement")}</span>
                  <select className="input" value={current.align}
                          onChange={(e) => update(current.name, { align: e.target.value })}>
                    <option value="left">{t("Gauche")}</option>
                    <option value="center">{t("Centré")}</option>
                    <option value="right">{t("Droite")}</option>
                  </select>
                </label>
                <label className="block">
                  <span className="block text-xs text-slate-500">{t("Lignes")}</span>
                  <select className="input" value={current.max_lines}
                          onChange={(e) => update(current.name, { max_lines: Number(e.target.value) })}>
                    <option value={1}>1</option>
                    <option value={2}>2</option>
                  </select>
                </label>
                <label className="block">
                  <span className="block text-xs text-slate-500">{t("Couleur")}</span>
                  <input type="color" className="input h-10 p-1" value={current.color}
                         onChange={(e) => update(current.name, { color: e.target.value })} />
                </label>
              </div>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={Boolean(current.required)}
                       disabled={!editable || current.name === "student_name"}
                       onChange={(e) => update(current.name, { required: e.target.checked })} />
                <span>{t("Obligatoire (production refusée si la donnée manque)")}</span>
              </label>
              {editable && (
                <button type="button" className="flex items-center gap-1 text-red-600 text-xs hover:underline"
                        onClick={() => { setFields((list) => list.filter((f) => f.name !== current.name)); setSelected(null); }}>
                  <Trash2 className="w-3 h-3" />{t("Retirer ce champ")}
                </button>
              )}
            </fieldset>
          )}

          <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-100">
            <button type="button" className="btn-secondary flex items-center gap-1.5"
                    disabled={preview.isPending || (editable && problems.length > 0)}
                    onClick={() => preview.mutate()}>
              <Eye className="w-4 h-4" />{preview.isPending ? t("Rendu…") : t("Aperçu")}
            </button>
            {editable && (
              <>
                <button type="button" className="btn-secondary flex items-center gap-1.5"
                        disabled={save.isPending || problems.length > 0} onClick={() => save.mutate()}>
                  <Save className="w-4 h-4" />{t("Enregistrer")}
                </button>
                <button type="button" className="btn-primary flex items-center gap-1.5"
                        disabled={verify.isPending || problems.length > 0} onClick={() => verify.mutate()}>
                  <ShieldCheck className="w-4 h-4" />{verify.isPending ? t("Vérification…") : t("Enregistrer et vérifier")}
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </Modal>
  );
}
