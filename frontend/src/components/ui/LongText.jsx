import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { t } from "../../i18n";

/**
 * P6 — Affichage d'un texte saisi par un utilisateur, JAMAIS tronqué.
 *
 * LE DÉFAUT CORRIGÉ
 * -----------------
 * Le message d'un visiteur s'affichait dans un `<p>` en `whitespace-pre-line`.
 * Cela conserve les retours à la ligne, mais ne coupe PAS un mot : une URL
 * de 300 caractères, ou un mot collé sans espace, élargissait le bloc
 * au-delà de la fenêtre. Le texte partait à droite, hors de l'écran, sans
 * barre de défilement et sans le moindre signe qu'il manquait quelque chose.
 * Un message reçu paraissait complet alors qu'il était coupé.
 *
 * CE QUE FAIT CE COMPOSANT
 * ------------------------
 *  - `whitespace-pre-wrap` : les retours à la ligne ET les espaces multiples
 *    du visiteur sont conservés, et le texte se replie ;
 *  - `overflow-wrap: anywhere` + `word-break: break-word` : un mot ou une
 *    URL sans espace se coupe plutôt que de déborder ;
 *  - hauteur maximale avec DÉFILEMENT VERTICAL interne : un message de
 *    5 000 caractères ne repousse pas les boutons hors de la fenêtre ;
 *  - `overflow-x: hidden` : rien ne peut sortir latéralement ;
 *  - une action « Copier » : le texte intégral part dans le presse-papiers,
 *    y compris la partie qu'il faut faire défiler pour voir.
 *
 * CE QU'IL NE FAIT JAMAIS
 * -----------------------
 * Pas de `text-overflow: ellipsis`, pas de `line-clamp`, pas de `slice()`.
 * Trois petits points à la place de la fin d'un message ne signalent pas un
 * problème d'affichage : ils font croire que le visiteur s'est arrêté là.
 *
 * Le contenu est rendu comme du TEXTE (`{value}`), jamais avec
 * `dangerouslySetInnerHTML` : React échappe, et un message contenant
 * « <script>alert(1)</script> » s'affiche tel quel, littéralement.
 */
export default function LongText({
  value,
  className = "",
  // `maxHeight` accepte `null` ou `"none"` : le bloc prend alors toute sa
  // hauteur naturelle, sans défilement interne. C'est le réglage attendu
  // dans une vue de détail officielle, où le panneau défile déjà : deux
  // zones de défilement imbriquées cachent le texte du bas aussi
  // sûrement qu'une troncature, parce que rien n'indique que la molette
  // agit sur le bloc intérieur.
  maxHeight = "24rem",
  copyable = true,
  emptyLabel = "—",
  // `plain` retire le fond gris et les marges de la carte : le composant
  // devient un simple bloc de texte, utilisable au fil d'une fiche.
  plain = false,
}) {
  const [copied, setCopied] = useState(false);
  const text = value == null ? "" : String(value);
  const scrolls = maxHeight != null && maxHeight !== "none";

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // Presse-papiers refusé (contexte non sécurisé, permission) : on ne
      // prétend pas avoir copié. Le texte reste sélectionnable à la souris.
      setCopied(false);
    }
  };

  if (!text.trim()) {
    return <p className={`text-slate-400 italic ${className}`}>{emptyLabel}</p>;
  }

  return (
    <div className={`relative ${className}`}>
      {copyable && (
        <button
          type="button"
          onClick={copy}
          title={t("Copier le texte intégral")}
          aria-label={t("Copier le texte intégral")}
          className="absolute top-2 right-2 z-10 p-1.5 rounded-lg bg-white/90 border border-slate-200 text-slate-500 hover:text-slate-700 hover:bg-white shadow-sm"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-success" />
                  : <Copy className="w-3.5 h-3.5" />}
        </button>
      )}
      <div
        data-testid="long-text"
        className={[
          "text-longform text-sm",
          plain
            ? "text-slate-700"
            : "bg-slate-50 rounded-xl p-4 text-slate-700",
          copyable ? (plain ? "pr-8" : "pr-10") : "",
          scrolls ? "overflow-y-auto overflow-x-hidden" : "overflow-x-hidden",
        ].filter(Boolean).join(" ")}
        // Les trois règles sont posées EN LIGNE en plus de la classe
        // `.text-longform`. Ce n'est pas une redondance : la classe vit
        // dans une feuille Tailwind soumise au « purge », et un jour où
        // elle n'apparaîtrait plus dans aucun fichier scanné, elle
        // disparaîtrait du CSS produit sans qu'aucun test ne le voie.
        // Le style en ligne, lui, part avec le composant.
        style={{
          whiteSpace: "pre-wrap",
          overflowWrap: "anywhere",
          wordBreak: "break-word",
          minWidth: 0,
          maxWidth: "100%",
          ...(scrolls ? { maxHeight } : null),
        }}
      >
        {text}
      </div>
    </div>
  );
}
