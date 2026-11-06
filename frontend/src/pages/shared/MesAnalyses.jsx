/**
 * Analyse personnelle (parent, élève) : moyennes par période et par matière,
 * présences. Uniquement l'élève concerné : aucune donnée d'un autre élève,
 * aucun classement.
 */
import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { analyticsAPI } from "../../api";
import { isCanceledError } from "../../api/academyScope";
import PageHeader from "../../components/ui/PageHeader";
import { PresentationProvider, useT } from "../../components/analytics/presentation";
import ActionsAnalyse from "../../components/analytics/ActionsAnalyse";
import { AXE, GRILLE, OR, useAnimation } from "../../theme/graphiques";

const PERIODES = { T1: "Trimestre 1", T2: "Trimestre 2", T3: "Trimestre 3", exam: "Examen" };

function Fiche({ id }) {
  const t = useT();
  const anim = useAnimation();
  const q = useQuery({ queryKey: ["analyse-eleve", id], queryFn: () => analyticsAPI.eleve(id) });
  if (q.isError && !isCanceledError(q.error)) {
    return <p role="alert" className="text-sm text-red-700">{q.error?.response?.data?.detail || t("L'analyse n'a pas pu être chargée.")}</p>;
  }
  if (q.isPending) return <div className="h-40 rounded-xl bg-slate-100 animate-pulse" aria-label={t("Chargement…")} />;
  const r = q.data.data;
  const b = r.bareme;
  const periodes = Object.keys(PERIODES).filter((p) => r.moyennes_generales.some((m) => m.periode === p));
  const p = r.presences;
  return (
    <div className="space-y-4" data-testid="analyse-eleve">
      <p className="text-sm text-slate-600">{r.eleve.nom}{r.eleve.classe ? ` · ${r.eleve.classe}` : ""} · {r.annee.nom}</p>
      {r.moyennes_generales.length === 0 ? (
        <p className="text-sm text-slate-500">{t("Aucune note pour cette année.")}</p>
      ) : (
        <>
          <ul className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="eleve-moyennes">
            {r.moyennes_generales.map((m) => (
              <li key={m.periode} className="rounded-xl border border-slate-100 bg-slate-50/60 p-3">
                <p className="text-xs text-slate-500">{t(PERIODES[m.periode])}</p>
                <p className="text-lg font-bold tabular-nums">{m.moyenne} / {b}</p>
                <p className="text-xs text-slate-500">{m.notes} {t("notes")}</p>
              </li>
            ))}
          </ul>
          {r.moyennes_generales.length > 1 && (
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={r.moyennes_generales.map((m) => ({ periode: t(PERIODES[m.periode]), moyenne: m.moyenne }))} margin={{ top: 8, right: 12 }}>
                  <defs><linearGradient id="degrade-moyenne" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={OR} stopOpacity={0.28} /><stop offset="100%" stopColor={OR} stopOpacity={0.02} />
                  </linearGradient></defs>
                  <CartesianGrid {...GRILLE} vertical={false} />
                  <XAxis dataKey="periode" tick={AXE} />
                  <YAxis domain={[0, b]} tick={AXE} width={32} />
                  <Tooltip formatter={(v) => [`${v} / ${b}`, t("Moyenne générale")]} />
                  <Area type="monotone" dataKey="moyenne" stroke={OR} strokeWidth={2} fill="url(#degrade-moyenne)" dot={{ r: 4, strokeWidth: 2, fill: "#fff" }}
                    activeDot={{ r: 6 }} {...anim} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="eleve-matieres">
              <thead><tr className="text-left text-xs text-slate-500">
                <th className="py-1.5 pr-3 font-medium">{t("Matière")}</th>
                <th className="py-1.5 pr-3 font-medium text-right">{t("Coef.")}</th>
                {periodes.map((pp) => <th key={pp} className="py-1.5 pr-3 font-medium text-right">{t(PERIODES[pp])}</th>)}
              </tr></thead>
              <tbody>
                {r.matieres.map((m) => (
                  <tr key={m.id} className="border-t border-slate-100">
                    <td className="py-1.5 pr-3">{m.nom}</td>
                    <td className="py-1.5 pr-3 text-right">{m.coefficient}</td>
                    {periodes.map((pp) => (
                      <td key={pp} className="py-1.5 pr-3 text-right tabular-nums">
                        {m.periodes[pp] ? `${m.periodes[pp].moyenne} / ${b}` : <span className="text-slate-400">{t("Non noté")}</span>}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <div className="rounded-xl border border-slate-100 p-3 text-sm" data-testid="eleve-presences">
        <p className="font-semibold text-slate-700 mb-1">{t("Présences")}</p>
        {p.appels ? (
          <p>{t("Taux de présence")} : <strong>{p.taux_presence} %</strong> · {t("Absences")} {p.absent} · {t("Retards")} {p.late} · {t("Absences excusées")} {p.excused}</p>
        ) : <p className="text-slate-500">{t("Aucun appel enregistré pour cette année.")}</p>}
      </div>
      <p className="text-xs text-slate-500">{t("Moyennes calculées comme sur le bulletin : chaque note compte pareil, les matières sont pondérées par leur coefficient.")}</p>
    </div>
  );
}

function Contenu() {
  const t = useT();
  const q = useQuery({ queryKey: ["analyse-mes-eleves"], queryFn: () => analyticsAPI.mesEleves() });
  const eleves = q.data?.data?.eleves || [];
  const [choisi, setChoisi] = useState(null);
  const rapport = useRef(null);
  const id = choisi ?? eleves[0]?.id;
  return (
    <div className="space-y-4">
      <PageHeader title={t("Analyse des résultats")} subtitle={t("Moyennes par période et par matière, présences")} action={<ActionsAnalyse rapport={rapport} onglet="eleve" profil="famille" nomFichier="analyse-resultats"
        entete={[t("Analyse des résultats"), `${t("Exporté le")} ${new Date().toLocaleString()}`]} />} />
      <div className="card print:shadow-none print:border-0 print:p-0" ref={rapport}>
        {q.isPending ? <div className="h-24 rounded-xl bg-slate-100 animate-pulse" aria-label={t("Chargement…")} />
          : eleves.length === 0 ? <p className="text-sm text-slate-500">{t("Aucun élève rattaché à ce compte.")}</p>
          : (
            <>
              {eleves.length > 1 && (
                <div className="flex flex-wrap gap-1.5 mb-4" role="group" aria-label={t("Enfant")}>
                  {eleves.map((e) => (
                    <button key={e.id} type="button" onClick={() => setChoisi(e.id)} aria-pressed={e.id === id} data-testid={`enfant-${e.id}`}
                      className={e.id === id ? "onglet-actif" : "onglet"}>
                      {e.nom}
                    </button>
                  ))}
                </div>
              )}
              <Fiche id={id} />
            </>
          )}
      </div>
    </div>
  );
}

export default function MesAnalyses() {
  return <PresentationProvider><Contenu /></PresentationProvider>;
}
