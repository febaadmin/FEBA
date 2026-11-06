/**
 * Barème officiel disponible (ex. affiche « Frais de scolarité 2026-2027 ») :
 * aperçu complet, points à confirmer, puis import par l'administration, sur
 * confirmation explicite. Seuls les tarifs absents sont créés ; rien n'est remplacé.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { AlertTriangle, FileSpreadsheet } from "lucide-react";
import { baremesAPI } from "../../api";
import { useAcademyKey } from "../../hooks/useEntityContext";
import { t } from "../../i18n";
import { extractApiError } from "../../utils/errors";
import { formatCalendarDate } from "../../utils/datetime";

export default function ImportBareme() {
  const academyKey = useAcademyKey();
  const qc = useQueryClient();
  const [ouvert, setOuvert] = useState(null);
  const [verifie, setVerifie] = useState(false);
  const q = useQuery({ queryKey: ["baremes", academyKey], queryFn: baremesAPI.list });
  const importer = useMutation({
    mutationFn: (fichier) => baremesAPI.importer(fichier),
    onSuccess: (r) => {
      ["fee-schedules", "baremes", "journal-financier"].forEach((k) => qc.invalidateQueries({ queryKey: [k, academyKey] }));
      qc.invalidateQueries({ queryKey: ["situation"] });
      toast.success(t("{n} tarif(s) créé(s).", { n: r.data.crees }));
      setOuvert(null);
    },
    onError: (e) => toast.error(extractApiError(e)),
  });
  const baremes = q.data?.data || [];
  if (!baremes.length) return null;
  return (
    <div className="space-y-2" data-testid="import-bareme">
      {baremes.map((b) => {
        const aCreer = b.lignes.filter((l) => l.action === "creer").length;
        return (
          <div key={b.fichier} className="rounded-xl border border-feba-navy/15 bg-feba-navy/5 p-3 space-y-2">
            <p className="text-sm text-slate-700 flex items-start gap-2">
              <FileSpreadsheet className="w-4 h-4 mt-0.5 text-feba-navy shrink-0" aria-hidden="true" />
              <span><strong>{t("Barème disponible")} {b.annee}</strong> · {b.source}</span>
            </p>
            {ouvert !== b.fichier ? (
              <button type="button" className="btn-secondary text-sm" onClick={() => { setOuvert(b.fichier); setVerifie(false); }}
                data-testid="bareme-apercu">{t("Voir le barème")} ({aCreer} {t("tarif(s) à créer")})</button>
            ) : (
              <>
                {b.a_confirmer.length > 0 && (
                  <div className="rounded-lg bg-amber-50 border border-amber-200 p-2 text-xs text-amber-900" role="note">
                    <p className="font-semibold flex items-center gap-1"><AlertTriangle className="w-3.5 h-3.5" aria-hidden="true" />{t("À vérifier avant l'import")}</p>
                    <ul className="list-disc pl-5 mt-1 space-y-0.5">{b.a_confirmer.map((n) => <li key={n}>{n}</li>)}</ul>
                  </div>
                )}
                {!b.annee_trouvee && <p role="alert" className="text-xs text-red-700">{t("L'année scolaire du barème n'existe pas dans cette académie : créez-la d'abord.")}</p>}
                <div className="overflow-x-auto max-h-80">
                  <table className="w-full text-xs bg-white rounded-lg">
                    <thead><tr className="text-left text-slate-500">
                      {["Nature", "Libellé", "Niveau", "Montant", "Échéances", "Action"].map((h) => <th key={h} className="py-1.5 px-2 font-medium">{t(h)}</th>)}
                    </tr></thead>
                    <tbody>
                      {b.lignes.map((l, i) => (
                        <tr key={i} className="border-t border-slate-100 align-top">
                          <td className="py-1.5 px-2">{l.nature}</td><td className="py-1.5 px-2">{l.libelle}</td>
                          <td className="py-1.5 px-2">{l.niveau || t("Tous niveaux")}</td><td className="py-1.5 px-2 tabular-nums">{l.montant}</td>
                          <td className="py-1.5 px-2">{l.echeances.map((e) => `${e.label} ${formatCalendarDate(e.date)} ${e.montant}`).join(" · ")}</td>
                          <td className="py-1.5 px-2">{l.action === "creer" ? t("Créer") : t("Existe déjà (inchangé)")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {b.niveaux_sans_tarif.length > 0 && (
                  <p className="text-xs text-slate-600">{t("Niveaux sans tarif de scolarité dans ce barème")} : {b.niveaux_sans_tarif.join(", ")}</p>
                )}
                <label className="flex items-start gap-2 text-sm">
                  <input type="checkbox" className="mt-1" checked={verifie} onChange={(e) => setVerifie(e.target.checked)} data-testid="bareme-verifie" />
                  <span>{t("J'ai vérifié les montants, les dates et les points signalés.")}</span>
                </label>
                <div className="flex gap-2">
                  <button type="button" className="btn-secondary text-sm" onClick={() => setOuvert(null)}>{t("Fermer")}</button>
                  <button type="button" className="btn-primary text-sm" disabled={!verifie || !aCreer || !b.annee_trouvee || importer.isPending}
                    onClick={() => importer.mutate(b.fichier)} data-testid="bareme-importer">{t("Importer")} {aCreer} {t("tarif(s)")}</button>
                </div>
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}
