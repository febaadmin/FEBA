/**
 * EntitySwitcher — sélecteur d'entité du Super Administrateur.
 *
 * Affiche en permanence l'entité active (indicateur visuel obligatoire) et
 * permet de basculer entre FEBA, FEBA French Heritage Academy et le mode
 * « Toutes les Académies ».
 *
 * La bascule est une opération SERVEUR (POST /auth/entity-context/switch/)
 * qui vérifie le rôle et journalise le changement. Le composant ne fait que
 * la déclencher ; il ne stocke aucune entité localement.
 *
 * Pour un utilisateur mono-entité (admin, enseignant, parent, élève), seul
 * le badge de l'entité est rendu — aucun sélecteur, donc aucun écran de
 * choix inutile.
 */
import { useState } from "react";
import { AlertTriangle, Building2, Check, ChevronDown, Layers, Loader2 } from "lucide-react";
import toast from "react-hot-toast";
import { useEntityContext, useEntitySwitch } from "../hooks/useEntityContext";
import { getLang } from "../i18n";

/** Libellés bilingues du sélecteur (FR/EN selon la langue de l'ERP). */
function t(fr, en) {
  return getLang() === "en" ? en : fr;
}

export default function EntitySwitcher({ compact = false }) {
  const { activeEntity, entities, canSwitch, allEntitiesMode, isLoading } =
    useEntityContext();
  const switcher = useEntitySwitch();
  const [open, setOpen] = useState(false);

  if (isLoading) return null;

  const label = allEntitiesMode
    ? t("Toutes les Académies", "All Academies")
    : activeEntity?.name || "Aucune entité";

  // Utilisateur mono-entité : badge informatif, sans sélecteur.
  if (!canSwitch) {
    if (!activeEntity) return null;
    return (
      <span
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-feba-navy/5 text-feba-navy text-xs font-semibold"
        title={activeEntity.legal_name || activeEntity.name}
      >
        <Building2 className="w-3.5 h-3.5" aria-hidden="true" />
        {compact ? activeEntity.code || activeEntity.name : label}
      </span>
    );
  }

  function switchTo(entityId) {
    setOpen(false);
    switcher.mutate(entityId, {
      onSuccess: (data) => {
        toast.success(
          data.active_entity
            ? `Entité active : ${data.active_entity.name}`
            : t("Mode « Toutes les Académies »", "All Academies mode"),
        );
      },
      onError: () => toast.error("Impossible de changer d'entité."),
    });
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="listbox"
        disabled={switcher.isPending}
        className="inline-flex items-center gap-2 px-3 py-2 rounded-xl border border-feba-navy/20 bg-white text-feba-navy text-xs font-semibold hover:bg-feba-cream transition-colors disabled:opacity-60"
      >
        {switcher.isPending ? (
          <Loader2 className="w-4 h-4 text-feba-gold animate-spin" aria-hidden="true" />
        ) : allEntitiesMode ? (
          <Layers className="w-4 h-4 text-feba-gold" aria-hidden="true" />
        ) : (
          <Building2 className="w-4 h-4 text-feba-gold" aria-hidden="true" />
        )}
        <span className="max-w-[13rem] truncate">
          {/* Le libellé ne bascule PAS avant le serveur : afficher tout de
              suite le nom de la nouvelle académie alors que les données sont
              encore celles de l'ancienne est précisément ce qui donnait
              l'impression d'un filtre incorrect. */}
          {switcher.isPending ? t("Changement en cours…", "Switching…") : label}
        </span>
        <ChevronDown className="w-3.5 h-3.5 opacity-60" aria-hidden="true" />
      </button>

      {/* Échec de bascule : l'académie affichée reste l'ancienne, il faut le
          dire explicitement plutôt que de laisser croire au changement. */}
      {switcher.error && !switcher.isPending && (
        <p
          role="alert"
          className="absolute right-0 mt-1 z-40 w-72 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[11px] text-red-800 flex items-start gap-2"
        >
          <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-px" aria-hidden="true" />
          <span>
            {t(
              "Changement d'académie refusé. L'académie affichée n'a pas changé.",
              "Academy switch refused. The academy shown has not changed.",
            )}
          </span>
        </p>
      )}

      {open && (
        <>
          {/* Zone de fermeture au clic extérieur. */}
          <div
            className="fixed inset-0 z-30"
            aria-hidden="true"
            onClick={() => setOpen(false)}
          />
          <ul
            role="listbox"
            className="absolute right-0 z-40 mt-2 w-72 rounded-xl border border-feba-navy/15 bg-white shadow-xl overflow-hidden"
          >
            {entities.map((entity) => {
              const selected = !allEntitiesMode && activeEntity?.id === entity.id;
              return (
                <li key={entity.id} role="option" aria-selected={selected}>
                  <button
                    type="button"
                    onClick={() => switchTo(entity.id)}
                    className="w-full text-left px-4 py-3 hover:bg-feba-cream transition-colors flex items-start gap-2.5"
                  >
                    <Building2
                      className="w-4 h-4 text-feba-gold shrink-0 mt-0.5"
                      aria-hidden="true"
                    />
                    <span className="flex-1 min-w-0">
                      <span className="block text-sm font-semibold text-feba-navy truncate">
                        {entity.name}
                      </span>
                      <span className="block text-[11px] text-feba-gray">
                        {entity.code} ·{" "}
                        {entity.entity_type === "online"
                          ? t("Académie en ligne", "Online academy")
                          : t("École présentielle", "On-campus school")}
                      </span>
                    </span>
                    {selected && (
                      <Check className="w-4 h-4 text-feba-green shrink-0" aria-hidden="true" />
                    )}
                  </button>
                </li>
              );
            })}

            <li role="option" aria-selected={allEntitiesMode} className="border-t border-feba-navy/10">
              <button
                type="button"
                onClick={() => switchTo(null)}
                className="w-full text-left px-4 py-3 hover:bg-feba-cream transition-colors flex items-start gap-2.5"
              >
                <Layers className="w-4 h-4 text-feba-gold shrink-0 mt-0.5" aria-hidden="true" />
                <span className="flex-1 min-w-0">
                  <span className="block text-sm font-semibold text-feba-navy">
                    {t("Toutes les Académies", "All Academies")}
                  </span>
                  <span className="block text-[11px] text-feba-gray">
                    {t("Vue consolidée, séparée par académie", "Consolidated view, split by academy")}
                  </span>
                </span>
                {allEntitiesMode && (
                  <Check className="w-4 h-4 text-feba-green shrink-0" aria-hidden="true" />
                )}
              </button>
            </li>
          </ul>
        </>
      )}
    </div>
  );
}
