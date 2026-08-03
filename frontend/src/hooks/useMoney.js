/**
 * useMoney — devise de l'académie affichée.
 *
 * Un écran ne doit jamais coder « FCFA » en dur : il demande ici la devise
 * de l'académie active, que le serveur lui a communiquée dans le contexte
 * d'académie. En mode « Toutes les Académies », il n'y a PAS de devise
 * unique — le hook renvoie donc `null`, et les écrans doivent afficher
 * leurs totaux ventilés par devise plutôt qu'un chiffre agrégé.
 */
import { useCallback, useMemo } from "react";
import { useAcademy } from "../context/AcademyContext";
import { formatMoney, formatMinor, rowAmount, totalsByCurrency, formatTotals } from "../utils/money";

export function useMoney() {
  const { activeAcademy, isAllAcademies } = useAcademy();

  // En mode consolidé, aucune devise ne représente les deux académies.
  const currency = isAllAcademies ? null : activeAcademy?.currency || null;
  const symbol = isAllAcademies ? null : activeAcademy?.currency_symbol || null;

  const format = useCallback((amount) => formatMoney(amount, currency), [currency]);
  const formatMinorAmount = useCallback((minor) => formatMinor(minor, currency), [currency]);
  const amountOf = useCallback((row) => rowAmount(row, currency), [currency]);

  /**
   * Total d'une liste, rendu prêt à l'affichage.
   *
   * En mode consolidé, renvoie « $1,250.00 · 500 000 FCFA » plutôt qu'un
   * nombre : c'est moins commode et c'est le seul rendu honnête.
   */
  const totalOf = useCallback(
    (rows) => formatTotals(totalsByCurrency(rows || [], currency)),
    [currency],
  );

  return useMemo(
    () => ({
      currency,
      symbol,
      isAllAcademies,
      format,
      formatMinor: formatMinorAmount,
      amountOf,
      totalOf,
      totalsOf: (rows) => totalsByCurrency(rows || [], currency),
    }),
    [currency, symbol, isAllAcademies, format, formatMinorAmount, amountOf, totalOf],
  );
}

export default useMoney;
