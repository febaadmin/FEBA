/**
 * Paiements du tableau de bord super administrateur : indicateurs et évolution.
 *
 * Tous les calculs sont faits par le serveur (/api/payments/tableau-de-bord/).
 * Une devise est affichée à la fois : XOF et USD ne s'additionnent jamais.
 * Sans échéancier configuré, « attendu » et « restant » sont « non calculables »,
 * jamais 0.
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { paymentsAPI } from "../../api";
import { isCanceledError } from "../../api/academyScope";
import { useAcademy } from "../../context/AcademyContext";
import { currencyRules, formatMinor } from "../../utils/money";
import { dateLocale, t, useI18n } from "../../i18n";

const PERIODES = [
  ["7j", "7 jours"], ["30j", "30 jours"], ["3m", "3 mois"], ["6m", "6 mois"],
  ["12m", "12 mois"], ["annee", "Année scolaire"], ["perso", "Personnalisée"],
];
const COULEUR_ENCAISSE = "#0E2A63";   // bleu marine FEBA
const COULEUR_ATTENDU = "#D89B16";    // or FEBA

function Indicateur({ titre, valeur, detail, testid }) {
  return (
    <div className="rounded-xl border border-slate-100 bg-slate-50/60 p-3" data-testid={testid}>
      <p className="text-xs text-slate-500">{titre}</p>
      <p className="mt-0.5 text-base font-bold text-slate-900 tabular-nums">{valeur}</p>
      {detail && <p className="text-xs text-slate-500 mt-0.5">{detail}</p>}
    </div>
  );
}

export default function GraphiquePaiements() {
  useI18n(); // rendu à chaque changement de langue
  const { academyKey, businessDataEnabled } = useAcademy();
  const [periode, setPeriode] = useState("12m");
  const [du, setDu] = useState("");
  const [au, setAu] = useState("");
  const [devise, setDevise] = useState(null);
  const persoPret = periode !== "perso" || (du && au);

  const { data, isPending, isError, error } = useQuery({
    queryKey: ["tableau-paiements", academyKey, periode, du, au],
    queryFn: () => paymentsAPI.tableauDeBord({ periode, ...(periode === "perso" ? { du, au } : {}) }),
    enabled: businessDataEnabled && Boolean(persoPret),
  });

  const r = data?.data;
  const devises = r?.devises || [];
  const courante = devises.find((d) => d.devise === devise) || devises[0];
  const code = courante?.devise;
  const decimales = currencyRules(code)?.decimals ?? 0;
  const m = (v) => (v === null || v === undefined ? t("Non calculable") : formatMinor(v, code));
  const enMonnaie = (v) => (v === null || v === undefined ? null : v / 10 ** decimales);
  const fmtCase = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString(dateLocale(),
    r?.periode?.granularite === "jour" ? { day: "2-digit", month: "short" } : { month: "short", year: "2-digit" });
  const serie = (courante?.serie || []).map((c) => ({
    date: fmtCase(c.date), encaisse: enMonnaie(c.encaisse_minor), attendu: enMonnaie(c.attendu_minor),
  }));
  const ind = courante?.indicateurs;
  const vide = courante && ind.nb_paiements === 0 && !courante.echeancier_configure && !ind.nb_en_attente && !ind.nb_echoues;
  const erreur = isError && !isCanceledError(error);

  return (
    <section className="card" aria-labelledby="titre-paiements" data-testid="graphique-paiements">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <h2 id="titre-paiements" className="font-bold text-slate-800">{t("Paiements")}</h2>
          <p className="text-xs text-slate-500">
            {r ? `${new Date(r.periode.du).toLocaleDateString(dateLocale())} → ${new Date(r.periode.au).toLocaleDateString(dateLocale())}` : t("Encaissements réels, par devise")}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label={t("Période")}>
          {PERIODES.map(([v, libelle]) => (
            <button key={v} type="button" onClick={() => setPeriode(v)} aria-pressed={periode === v}
              data-testid={`periode-${v}`}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${periode === v ? "bg-feba-navy text-white" : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"}`}>
              {t(libelle)}
            </button>
          ))}
        </div>
      </div>

      {periode === "perso" && (
        <div className="flex flex-wrap gap-3 mb-4 text-sm">
          <label className="flex items-center gap-2">{t("Du")}<input type="date" value={du} onChange={(e) => setDu(e.target.value)} className="input !py-1" /></label>
          <label className="flex items-center gap-2">{t("Au")}<input type="date" value={au} onChange={(e) => setAu(e.target.value)} className="input !py-1" /></label>
        </div>
      )}

      {devises.length > 1 && (
        <div className="flex gap-1.5 mb-4" role="group" aria-label={t("Devise")}>
          {devises.map((d) => (
            <button key={d.devise} type="button" onClick={() => setDevise(d.devise)} aria-pressed={d.devise === code}
              data-testid={`devise-${d.devise}`}
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold ${d.devise === code ? "bg-feba-gold text-white" : "bg-white border border-slate-200 text-slate-600"}`}>
              {d.devise} · {d.academies.map((a) => a.nom).join(", ")}
            </button>
          ))}
        </div>
      )}

      {!persoPret ? (
        <p className="text-sm text-slate-500 py-8 text-center">{t("Choisissez les deux dates de la période.")}</p>
      ) : erreur ? (
        <p role="alert" className="text-sm text-red-700 py-8 text-center">
          {error?.response?.data?.detail || t("Les paiements n'ont pas pu être chargés. Rechargez la page.")}
        </p>
      ) : isPending || !r ? (
        <div className="h-64 rounded-xl bg-slate-100 animate-pulse" data-testid="paiements-chargement" aria-label={t("Chargement…")} />
      ) : !courante || vide ? (
        <p className="text-sm text-slate-500 py-8 text-center" data-testid="paiements-vide">{t("Aucun paiement sur cette période.")}</p>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <Indicateur testid="ind-encaisse" titre={t("Encaissé (net des remboursements)")} valeur={m(ind.encaisse_minor)}
              detail={`${ind.nb_paiements} ${t("paiement(s)")}${ind.rembourse_minor ? ` · ${t("remboursé")} ${m(ind.rembourse_minor)}` : ""}`} />
            <Indicateur testid="ind-attendu" titre={t("Attendu (échéances de la période)")} valeur={m(ind.attendu_minor)}
              detail={courante.echeancier_configure ? null : t("Aucun échéancier configuré")} />
            <Indicateur testid="ind-restant" titre={t("Restant à payer (échéances passées)")} valeur={m(ind.restant_minor)}
              detail={ind.taux_recouvrement !== null && ind.taux_recouvrement !== undefined ? `${t("Recouvrement")} ${ind.taux_recouvrement} %` : null} />
            <Indicateur testid="ind-attente" titre={t("En attente / échoués (carte)")} valeur={`${m(ind.en_attente_minor)} / ${m(ind.echoue_minor)}`}
              detail={`${ind.nb_en_attente} / ${ind.nb_echoues} · ${t("annulés")} ${ind.nb_annules} (${m(ind.annule_minor)})`} />
          </div>
          <div className="h-64" data-testid="paiements-graphique">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={serie} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#64748b" }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 11, fill: "#64748b" }} width={70}
                  tickFormatter={(v) => formatMinor(v * 10 ** decimales, code)} />
                <Tooltip formatter={(v, nom) => [v === null ? t("Non calculable") : formatMinor(v * 10 ** decimales, code), nom]} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="encaisse" name={t("Encaissé")} fill={COULEUR_ENCAISSE} radius={[4, 4, 0, 0]} maxBarSize={36} isAnimationActive={false} />
                {courante.echeancier_configure && (
                  <Line dataKey="attendu" name={t("Attendu")} stroke={COULEUR_ATTENDU} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          {r.par_academie.length > 1 && (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm" data-testid="paiements-par-academie">
                <thead><tr className="text-left text-xs text-slate-500">
                  <th className="py-1.5 font-medium">{t("Académie")}</th>
                  <th className="py-1.5 font-medium text-right">{t("Encaissé")}</th>
                  <th className="py-1.5 font-medium text-right">{t("Paiements")}</th>
                  <th className="py-1.5 font-medium text-right">{t("Restant à payer")}</th>
                </tr></thead>
                <tbody>
                  {r.par_academie.map((a) => (
                    <tr key={a.id} className="border-t border-slate-100">
                      <td className="py-1.5">{a.nom}</td>
                      <td className="py-1.5 text-right tabular-nums">{formatMinor(a.encaisse_minor, a.devise)}</td>
                      <td className="py-1.5 text-right tabular-nums">{a.nb_paiements}</td>
                      <td className="py-1.5 text-right tabular-nums">{a.restant_minor === null ? t("Non calculable") : formatMinor(a.restant_minor, a.devise)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  );
}
