/** Ouverture des modules pédagogiques, académie par académie. L'accès des familles reste distinct. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { suiviAPI } from "../../api";
import PageHeader from "../../components/ui/PageHeader";
import { extractApiError } from "../../utils/errors";
import { t } from "../../i18n";

const MODULES = [
  ["suivi_pedagogique", "Suivi pédagogique"],
  ["evaluations_en_ligne", "Examens et évaluations"],
  ["suivi_familles", "Accès des élèves et des parents au suivi"],
];

export default function ModulesPedagogiques() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["suivi-activation"], queryFn: () => suiviAPI.activation() });
  const changer = useMutation({
    mutationFn: ({ id, cle, valeur }) => suiviAPI.activer(id, { [cle]: valeur }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["suivi-activation"] }); toast.success(t("Enregistré. Rechargez la page pour voir le menu mis à jour.")); },
    onError: (e) => toast.error(extractApiError(e)),
  });
  return (
    <div className="space-y-4">
      <PageHeader title={t("Modules pédagogiques")} subtitle={t("Désactivés par défaut. Ouvrir l'accès des familles publie le suivi validé aux élèves et aux parents.")} />
      {isLoading && <p className="text-sm text-slate-500">{t("Chargement")}</p>}
      {(data?.data || []).map((a) => (
        <div key={a.id} className="card space-y-2">
          <h2 className="text-sm font-semibold text-slate-900">{a.nom}</h2>
          {MODULES.map(([cle, libelle]) => (
            <label key={cle} className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" checked={a[cle]} disabled={changer.isPending} onChange={(e) => changer.mutate({ id: a.id, cle, valeur: e.target.checked })} />
              {t(libelle)}
            </label>
          ))}
        </div>
      ))}
    </div>
  );
}
