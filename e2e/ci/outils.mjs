// Outils communs des tests navigateur de la CI. Aucun mot de passe ici : ils viennent de l'environnement.
import { chromium } from "playwright-core";

export const BASE = process.env.E2E_BASE_URL || "http://127.0.0.1:4173";
export const API = process.env.E2E_API_URL || "http://127.0.0.1:8000/api";

const mdp = (nom) => {
  const v = process.env[nom];
  if (!v) throw new Error(`Variable d'environnement ${nom} absente`);
  return v;
};
export const COMPTES = {
  superadmin: ["superadmin@feba.bj", "E2E_PWD_SUPERADMIN", "/superadmin"],
  admin: ["admin@feba.bj", "E2E_PWD_ADMIN", "/admin"],
  teacher: ["prof.math@feba.bj", "E2E_PWD_TEACHER", "/teacher"],
  parent: ["parent3@feba.bj", "E2E_PWD_PARENT", "/parent"],
  student: ["eleve5@feba.bj", "E2E_PWD_STUDENT", "/student"],
  parentAutre: ["parent1@feba.bj", "E2E_PWD_PARENT", "/parent"],
  studentAutre: ["eleve8@feba.bj", "E2E_PWD_STUDENT", "/student"],
};
export const motDePasse = (role) => mdp(COMPTES[role][1]);

let navigateur;
export async function lancer() {
  navigateur = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH || undefined });
  return navigateur;
}
export const fermer = () => navigateur?.close();

export const resultats = [];
export function ok(scenario, nom, vrai, detail = "") {
  resultats.push({ scenario, nom, vrai: Boolean(vrai), detail: String(detail).slice(0, 300) });
  console.log(`${vrai ? "OK " : "KO "} [${scenario}] ${nom}${vrai || !detail ? "" : " : " + String(detail).slice(0, 300)}`);
}

/** Nouvelle page qui relève les erreurs JS et les réponses 5xx. */
export async function page(options = {}) {
  const contexte = await navigateur.newContext({ viewport: { width: 1366, height: 900 }, ...options });
  const p = await contexte.newPage();
  p.erreurs = [];
  p.on("pageerror", (e) => p.erreurs.push("JS " + e.message.slice(0, 160)));
  p.on("response", (r) => {
    // Le contrôle de santé visio répond 503 sans serveur plugNmeet : attendu en CI.
    if (r.url().includes("/api/") && r.status() >= 500 && !r.url().includes("/virtual-rooms/health")) {
      p.erreurs.push(`${r.status()} ${r.request().method()} ${r.url().split("/api")[1]}`);
    }
  });
  p.contexte = contexte;
  return p;
}

/** Latence réseau simulée sur l'API (le serveur reste réel). */
export async function latence(p, ms, filtre = () => true) {
  await p.route("**/api/**", async (r) => {
    if (filtre(r.request())) await new Promise((fin) => setTimeout(fin, ms));
    await r.continue().catch(() => {});
  });
}

/** Messages affichés (toasts et zones de statut) pendant l'exécution de `action`. */
export async function messages(p, action, attente = 1200) {
  const vus = new Set();
  const minuteur = setInterval(async () => {
    try { for (const t of await p.locator("[role=status]").allInnerTexts()) if (t.trim()) vus.add(t.trim()); } catch { /* page en cours de navigation */ }
  }, 60);
  try { await action(); await p.waitForTimeout(attente); } finally { clearInterval(minuteur); }
  return [...vus];
}

export async function connecter(role, options = {}) {
  const p = options.page || await page(options.contexte);
  const [email, , racine] = COMPTES[role];
  await p.goto(BASE + "/login");
  await p.locator("#login-email").fill(email);
  await p.locator("#login-password").fill(motDePasse(role));
  await p.locator("button[type=submit]").click();
  for (let i = 0; i < 100 && p.url().includes("/login"); i++) await p.waitForTimeout(150);
  await p.waitForTimeout(700);
  p.racine = racine;
  return p;
}

/** Choisit la première option d'une liste à recherche (SearchableSelect). */
export async function choisir(p, zone, nom) {
  await zone.getByRole("button", { name: nom }).first().click();
  await p.waitForTimeout(300);
  const recherche = p.locator('input[placeholder="Rechercher..."]').last();
  await recherche.locator("xpath=ancestor::div[3]").locator(".overflow-y-auto button").first().click();
  await p.waitForTimeout(250);
}

/** Jeton d'API pour les vérifications côté serveur. */
export async function jeton(role) {
  const r = await fetch(API + "/auth/login/", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: COMPTES[role][0], password: motDePasse(role) }) });
  return (await r.json()).access;
}
export async function api(methode, chemin, jt, corps) {
  const r = await fetch(API + chemin, { method: methode, headers: { Authorization: `Bearer ${jt}`, ...(corps instanceof FormData ? {} : { "Content-Type": "application/json" }) },
    body: corps === undefined ? undefined : corps instanceof FormData ? corps : JSON.stringify(corps) });
  const texte = await r.text();
  let donnees = texte;
  try { donnees = JSON.parse(texte); } catch { /* binaire ou vide */ }
  return { statut: r.status, donnees, type: r.headers.get("content-type") || "", brut: texte };
}
export const liste = (d) => (Array.isArray(d) ? d : d?.results || []);
export const unique = () => Date.now() % 1000000;
