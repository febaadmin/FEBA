/**
 * Infobulle commune des graphiques : titre, pastille de couleur, valeur formatée,
 * texte à l'encre (jamais à la couleur de la série).
 */
export default function Infobulle({ active, payload, label, format = (v) => v, titre }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white/95 px-2.5 py-1.5 text-xs shadow-lg backdrop-blur-sm">
      {(titre || label) && <p className="font-semibold text-slate-800 mb-0.5">{titre ? titre(payload[0]?.payload, label) : label}</p>}
      {payload.map((p) => (
        <p key={`${p.dataKey}-${p.name}`} className="flex items-center gap-1.5 text-slate-700">
          <span className="w-2 h-2 rounded-full shrink-0" style={{ background: p.color || p.payload?.fill }} aria-hidden="true" />
          <span>{p.name}</span> : <strong className="tabular-nums">{format(p.value, p)}</strong>
        </p>
      ))}
    </div>
  );
}

/** Légende : libellé à l'encre du texte, la couleur reste portée par la pastille. */
export const encre = (valeur) => <span className="text-slate-700">{valeur}</span>;
