/**
 * Dates et heures des transactions — affichage dans le fuseau DE L'ACADÉMIE.
 *
 * Le serveur renvoie `paid_at` (instant UTC) et `academy_timezone`. On
 * formate avec Intl dans ce fuseau : un administrateur à Cotonou qui
 * consulte un paiement FHA voit l'heure de New York, celle à laquelle le
 * parent a payé — pas l'heure de son propre navigateur.
 *
 * Format de référence (fr) : JJ/MM/AAAA HH:mm. En anglais, la locale
 * active (`dateLocale()`) décide de l'ordre jour/mois.
 *
 * Quand l'heure n'a jamais été enregistrée (`paid_at` nul — paiements
 * antérieurs ou antidatés), on affiche la date seule : on n'invente pas
 * « 00:00 ».
 */
import { dateLocale } from "../i18n";

function safeFormatter(options, timeZone) {
  try {
    return new Intl.DateTimeFormat(dateLocale(), { ...options, timeZone: timeZone || undefined });
  } catch {
    // Fuseau inconnu du navigateur : on retombe sur le fuseau local plutôt
    // que de ne rien afficher.
    return new Intl.DateTimeFormat(dateLocale(), options);
  }
}

const DATE_OPTS = { day: "2-digit", month: "2-digit", year: "numeric" };
const DATETIME_OPTS = { ...DATE_OPTS, hour: "2-digit", minute: "2-digit", hourCycle: "h23" };

/** « 09/10/2026 14:37 » pour un instant ISO, dans le fuseau donné. */
export function formatDateTime(iso, timeZone) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return safeFormatter(DATETIME_OPTS, timeZone).format(d).replace(",", "");
}

/** « 09/10/2026 » pour une date calendaire AAAA-MM-JJ (sans conversion de fuseau). */
export function formatCalendarDate(ymd) {
  if (!ymd) return "";
  const [y, m, d] = String(ymd).slice(0, 10).split("-").map(Number);
  if (!y || !m || !d) return String(ymd);
  // Midi UTC formaté en UTC : aucun fuseau ne peut décaler le jour.
  return safeFormatter(DATE_OPTS, "UTC").format(new Date(Date.UTC(y, m - 1, d, 12)));
}

/** Libellé de la colonne « Date » d'un paiement. */
export function paymentDateTimeText(row) {
  if (!row) return "";
  if (row.paid_at) return formatDateTime(row.paid_at, row.academy_timezone);
  return formatCalendarDate(row.payment_date);
}

/** Clé de tri chronologique (ms). Sans heure connue : début du jour (rangé après les heures connues en tri décroissant). */
export function paymentSortValue(row) {
  if (!row) return null;
  if (row.paid_at) return Date.parse(row.paid_at);
  if (row.payment_date) return Date.parse(`${String(row.payment_date).slice(0, 10)}T00:00:00Z`);
  return null;
}

/** Date du jour AAAA-MM-JJ dans le fuseau du navigateur (pas en UTC). */
export function localTodayISO() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** Heure courante HH:MM dans le fuseau du navigateur. */
export function localNowTime() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

/**
 * Date (AAAA-MM-JJ) et heure (HH:MM) courantes DANS LE FUSEAU DE
 * L'ACADÉMIE. Le formulaire de paiement les propose par défaut :
 * `new Date().toISOString().slice(0, 10)` donnait la date UTC, donc le
 * lendemain pour un encaissement saisi le soir à New York.
 */
export function academyNowParts(timeZone, now = new Date()) {
  try {
    const parts = Object.fromEntries(
      new Intl.DateTimeFormat("en-CA", {
        timeZone: timeZone || undefined, year: "numeric", month: "2-digit", day: "2-digit",
        hour: "2-digit", minute: "2-digit", hourCycle: "h23",
      }).formatToParts(now).map((p) => [p.type, p.value]),
    );
    return { date: `${parts.year}-${parts.month}-${parts.day}`, time: `${parts.hour}:${parts.minute}` };
  } catch {
    return { date: localTodayISO(), time: localNowTime() };
  }
}
