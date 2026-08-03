/**
 * Emploi du temps — onglets explicites FEBA et FEBA FHA.
 *
 * PROBLÈME RÉSOLU (P3)
 * --------------------
 * Une page unique servait les deux académies. On ne savait donc jamais
 * quel emploi du temps on regardait ni dans lequel on créait un créneau —
 * alors que les deux ne planifient pas la même chose :
 *
 *   FEBA      un cours présentiel : classe, salle physique, heure locale
 *             de Cotonou. La contrainte forte est l'occupation des salles.
 *
 *   FEBA FHA  une séance en direct : groupe en ligne, salle virtuelle,
 *             heure stockée en UTC et rappel aux familles. Il n'y a pas de
 *             salle à réserver, mais des participants dans plusieurs
 *             fuseaux horaires.
 *
 * Les onglets sont nommés en toutes lettres, jamais désignés par une
 * simple couleur ou un pictogramme.
 *
 * VISIBILITÉ DES ONGLETS
 * ----------------------
 * Elle est déduite du contexte d'académie servi par l'API, pas d'une
 * valeur locale. Et ce n'est PAS une protection : le serveur refuse de
 * lui-même l'endpoint des séances en ligne à une académie présentielle
 * (403, permission HasEntityFeature). Masquer l'onglet évite un écran
 * inutile, rien de plus.
 */
import { useEffect, useState } from "react";
import { Building2, Globe2 } from "lucide-react";
import PageHeader from "../../components/ui/PageHeader";
import { useAcademy } from "../../context/AcademyContext";
import { t } from "../../i18n";
import { clsx } from "clsx";
import CampusSchedule from "./schedule/CampusSchedule";
import OnlineSchedule from "./schedule/OnlineSchedule";

const TAB_CAMPUS = "campus";
const TAB_ONLINE = "online";

export default function AdminSchedule() {
  const { activeAcademy, allowedAcademies, isAllAcademies, canSwitchAcademy } = useAcademy();

  // Une académie voit d'abord SON propre emploi du temps. En mode
  // consolidé, on part du présentiel, qui est le cas le plus courant.
  const ownType = activeAcademy?.entity_type;

  // Un Super Administrateur peut changer d'académie à tout moment : les
  // DEUX onglets lui restent proposés même quand FEBA est active. En
  // masquer un le laisserait croire que l'emploi du temps FEBA FHA
  // n'existe pas, alors qu'il est à une bascule de distance. L'onglet
  // explique lui-même quelle académie sélectionner.
  const seesBoth = canSwitchAcademy || isAllAcademies;
  const campusAvailable = seesBoth || ownType !== "online";
  const onlineAvailable =
    seesBoth
      ? allowedAcademies.some((a) => a.entity_type === "online")
      : ownType === "online";

  const [tab, setTab] = useState(ownType === "online" ? TAB_ONLINE : TAB_CAMPUS);

  // Après une bascule d'académie, l'onglet sélectionné peut ne plus
  // exister (« Séances en ligne » sur une école présentielle). Le laisser
  // actif afficherait un écran vide sans explication.
  useEffect(() => {
    if (tab === TAB_ONLINE && !onlineAvailable) setTab(TAB_CAMPUS);
    if (tab === TAB_CAMPUS && !campusAvailable) setTab(TAB_ONLINE);
  }, [tab, campusAvailable, onlineAvailable]);

  const tabs = [
    campusAvailable && {
      key: TAB_CAMPUS,
      icon: Building2,
      label: t("FEBA — cours présentiels"),
      hint: t("Classe, salle physique, heure de Cotonou"),
    },
    onlineAvailable && {
      key: TAB_ONLINE,
      icon: Globe2,
      label: t("FEBA FHA — séances en ligne"),
      hint: t("Groupe en ligne, salle virtuelle, heure UTC"),
    },
  ].filter(Boolean);

  const subtitle = isAllAcademies
    ? t("Mode « Toutes les Académies » — chaque ligne porte son académie.")
    : activeAcademy?.name || "";

  return (
    <div className="space-y-6">
      <PageHeader title={t("Emploi du temps")} subtitle={subtitle} />

      {/* Toujours affichée, même avec un seul onglet : la page doit dire
          explicitement de quel emploi du temps il s'agit. C'est
          précisément ce qui manquait quand une page unique servait les
          deux académies. */}
      {tabs.length > 0 && (
        <div role="tablist" aria-label={t("Académie")} className="flex flex-wrap gap-2">
          {tabs.map(({ key, icon: Icon, label, hint }) => {
            const selected = tab === key;
            return (
              <button
                key={key}
                role="tab"
                type="button"
                aria-selected={selected}
                onClick={() => setTab(key)}
                className={clsx(
                  "flex items-start gap-2.5 rounded-xl border px-4 py-2.5 text-left transition-colors",
                  selected
                    ? "border-primary bg-primary text-white"
                    : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50",
                )}
              >
                <Icon className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
                <span className="min-w-0">
                  <span className="block text-sm font-semibold">{label}</span>
                  <span className={clsx("block text-[11px]", selected ? "text-white/80" : "text-slate-400")}>
                    {hint}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      )}

      {/* `key` : changer d'onglet réinitialise filtres et sélections. Les
          deux emplois du temps n'ont pas les mêmes colonnes ; conserver un
          filtre « Classe » en passant aux séances en ligne n'aurait aucun
          sens. */}
      {tab === TAB_ONLINE ? <OnlineSchedule key="online" /> : <CampusSchedule key="campus" />}
    </div>
  );
}
