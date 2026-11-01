/**
 * Emploi du temps — un onglet par TYPE de planification, nommé d'après les
 * académies réelles servies par l'API.
 *
 *   présentiel  un cours : classe, salle physique, heure locale de
 *               l'académie. La contrainte forte est l'occupation des salles.
 *   en ligne    une séance en direct : groupe, salle virtuelle, heure
 *               stockée en UTC, participants dans plusieurs fuseaux.
 *
 * AUCUN NOM D'ACADÉMIE ÉCRIT EN DUR
 * ---------------------------------
 * Les onglets s'appelaient « FEBA — cours présentiels » et « FEBA FHA —
 * séances en ligne » : une troisième académie (présentielle ou en ligne)
 * voyait son emploi du temps sous le nom d'une autre. Désormais :
 *   - une académie active : un seul onglet, à SON nom, pour SON type ;
 *     un super administrateur voit en plus quelles autres académies il
 *     peut sélectionner (aucun onglet vide ni refusé) ;
 *   - « Toutes les Académies » : un onglet par type effectivement présent,
 *     qui énumère les académies concernées — 2, 7 ou 19, la mise en page
 *     reste la même (liste abrégée, nombre total).
 *
 * Ce n'est PAS une protection : le serveur refuse l'endpoint des séances en
 * ligne à une académie présentielle (403, HasEntityFeature).
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
const typeOf = (academy) => (academy?.entity_type === "online" ? TAB_ONLINE : TAB_CAMPUS);
const nameOf = (academy) => academy?.short_name || academy?.name || "";

/** « A, B, C et 16 autres » : lisible quel que soit le nombre d'académies. */
export function academyList(academies, max = 3) {
  const names = academies.map(nameOf).filter(Boolean);
  if (names.length <= max) return names.join(", ");
  return t("{noms} et {n} autres", { noms: names.slice(0, max).join(", "), n: names.length - max });
}

export default function AdminSchedule() {
  const { activeAcademy, allowedAcademies, isAllAcademies, canSwitchAcademy } = useAcademy();
  const academies = allowedAcademies || [];
  const byType = {
    [TAB_CAMPUS]: academies.filter((a) => typeOf(a) === TAB_CAMPUS),
    [TAB_ONLINE]: academies.filter((a) => typeOf(a) === TAB_ONLINE),
  };

  const ownType = activeAcademy ? typeOf(activeAcademy) : null;
  const available = isAllAcademies
    ? [TAB_CAMPUS, TAB_ONLINE].filter((type) => byType[type].length > 0)
    : ownType ? [ownType] : [];

  const [tab, setTab] = useState(ownType || available[0] || TAB_CAMPUS);

  // Après une bascule, l'onglet choisi peut ne plus exister pour la
  // nouvelle académie : on revient à celui qu'elle a réellement.
  useEffect(() => {
    if (available.length > 0 && !available.includes(tab)) setTab(available[0]);
  }, [tab, available.join("|")]); // eslint-disable-line react-hooks/exhaustive-deps

  const TYPE_TEXT = {
    [TAB_CAMPUS]: { icon: Building2, what: t("cours présentiels"), hint: t("Classe, salle physique, heure locale") },
    [TAB_ONLINE]: { icon: Globe2, what: t("séances en ligne"), hint: t("Groupe en ligne, salle virtuelle, heure UTC") },
  };
  const tabs = available.map((type) => {
    const { icon, what, hint } = TYPE_TEXT[type];
    if (!isAllAcademies) {
      return { key: type, icon, label: `${nameOf(activeAcademy)} - ${what}`, hint };
    }
    const list = byType[type];
    return {
      key: type, icon,
      label: `${what.charAt(0).toUpperCase()}${what.slice(1)} - ${t("{n} académie(s)", { n: list.length })}`,
      hint: academyList(list),
      title: list.map(nameOf).join(", "),
    };
  });

  // Super administrateur sur une académie : les académies de l'AUTRE type
  // sont à une bascule — on les nomme au lieu d'afficher un onglet vide.
  const others = !isAllAcademies && canSwitchAcademy && ownType
    ? academies.filter((a) => typeOf(a) !== ownType)
    : [];

  const subtitle = isAllAcademies
    ? t("Mode « Toutes les Académies » : chaque ligne porte son académie.")
    : activeAcademy?.name || "";

  return (
    <div className="space-y-6">
      <PageHeader title={t("Emploi du temps")} subtitle={subtitle} />

      {/* Toujours affichée, même avec un seul onglet : la page doit dire
          explicitement de quel emploi du temps il s'agit. C'est
          précisément ce qui manquait quand une page unique servait les
          deux académies. */}
      {tabs.length > 0 && (
        <div role="tablist" aria-label={t("Emploi du temps")} className="flex flex-wrap gap-2">
          {tabs.map(({ key, icon: Icon, label, hint, title }) => {
            const selected = tab === key;
            return (
              <button
                key={key}
                role="tab"
                type="button"
                aria-selected={selected}
                onClick={() => setTab(key)}
                title={title}
                data-testid={`schedule-tab-${key}`}
                className={clsx(
                  "flex items-start gap-2.5 rounded-xl border px-4 py-2.5 text-left transition-colors max-w-full min-w-0",
                  selected
                    ? "border-primary bg-primary text-white"
                    : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50",
                )}
              >
                <Icon className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
                <span className="min-w-0">
                  <span className="block text-sm font-semibold break-words">{label}</span>
                  <span className={clsx("block text-[11px] break-words", selected ? "text-white/80" : "text-slate-400")}>
                    {hint}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      )}

      {others.length > 0 && (
        <p className="text-xs text-slate-500" data-testid="schedule-other-academies">
          {t("Autres emplois du temps ({type}) : sélectionnez {noms} dans le sélecteur d'académie.", {
            type: TYPE_TEXT[ownType === TAB_ONLINE ? TAB_CAMPUS : TAB_ONLINE].what,
            noms: academyList(others),
          })}
        </p>
      )}

      {/* `key` : changer d'onglet réinitialise filtres et sélections. Les
          deux emplois du temps n'ont pas les mêmes colonnes ; conserver un
          filtre « Classe » en passant aux séances en ligne n'aurait aucun
          sens. */}
      {tab === TAB_ONLINE ? <OnlineSchedule key="online" /> : <CampusSchedule key="campus" />}
    </div>
  );
}
