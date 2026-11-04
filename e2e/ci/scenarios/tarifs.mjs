// Tarifs et échéances : création depuis la grille, échéancier, historique, effet sur le graphique.
import { BASE, api, connecter, jeton, ok, unique } from "../outils.mjs";

const S = "tarifs";

export default async function () {
  const jt = await jeton("admin");
  const niveaux = (await api("GET", "/schools/levels/", jt)).donnees;
  const niveau = (niveaux.results || niveaux)[0];
  const annees = (await api("GET", "/schools/years/", jt)).donnees;
  const annee = (annees.results || annees).find((a) => a.is_current) || (annees.results || annees)[0];
  ok(S, "données de départ : niveau et année", Boolean(niveau && annee));

  const p = await connecter("admin");
  ok(S, "entrée « Tarifs et échéances » au menu", await p.locator('a[href="/admin/tarifs"]').count() === 1);
  await p.goto(BASE + "/admin/tarifs");
  await p.waitForTimeout(1200);
  const libelle = `Examen E2E ${unique()}`;
  // Le premier tarif se crée depuis l'état vide, les suivants depuis la grille.
  if (await p.getByTestId("tarifs-vide").count()) await p.getByRole("button", { name: "Créer le premier tarif" }).click();
  else await p.getByTestId(`cellule-${niveau.id}-mensualite`).click().catch(async () => p.getByTestId("onglet-tarifs").click());
  await p.waitForTimeout(500);
  const dialogue = p.locator("[role=dialog]");
  await dialogue.locator("select").nth(0).selectOption("examen");
  await dialogue.locator("input").nth(0).fill(libelle);
  await dialogue.locator("select").nth(1).selectOption(String(annee.id));
  await dialogue.locator("select").nth(2).selectOption(String(niveau.id));
  await dialogue.locator("input").nth(1).fill("20000");
  await dialogue.getByRole("button", { name: "Ajouter une échéance" }).click();
  await dialogue.getByRole("button", { name: "Ajouter une échéance" }).click();
  const lignes = dialogue.locator(".grid-cols-\\[1fr_auto_auto_auto\\]");
  const debut = annee.start_date || "2026-09-01";
  for (const [i, montant] of [[0, "12000"], [1, "8000"]]) {
    await lignes.nth(i).locator("input").nth(0).fill(`Tranche ${i + 1}`);
    await lignes.nth(i).locator("input").nth(1).fill(i === 0 ? debut : debut.replace(/-\d\d$/, "-28"));
    await lignes.nth(i).locator("input").nth(2).fill(montant);
  }
  await dialogue.getByTestId("tarif-motif").fill("Création E2E");
  await dialogue.locator("button[type=submit]").click();
  await p.waitForTimeout(1500);
  const fees = (await api("GET", "/payments/fee-schedules/", jt)).donnees;
  const cree = fees.find((x) => x.label === libelle);
  ok(S, "tarif enregistré avec ses deux échéances", cree && cree.installments.length === 2 && cree.is_consistent, JSON.stringify(cree || {}).slice(0, 200));
  await p.getByTestId("onglet-grille").click();
  await p.waitForTimeout(600);
  ok(S, "grille : montant affiché pour le niveau", (await p.getByTestId(`cellule-${niveau.id}-examen`).innerText()).includes("20"));
  await p.getByTestId("onglet-historique").click();
  await p.waitForTimeout(800);
  ok(S, "historique : création tracée avec motif", (await p.getByTestId("tarifs-historique").innerText()).includes("Création E2E"));

  // Montant d'un tarif payé : motif exigé (API).
  const sansMotif = await api("PATCH", `/payments/fee-schedules/${cree.id}/`, jt, { amount: "21000" });
  ok(S, "modification sans motif d'un tarif non payé acceptée", sansMotif.statut === 200, sansMotif.statut);
  const refus = await api("GET", "/payments/fee-schedules/historique/", await jeton("teacher"));
  ok(S, "historique refusé à un enseignant", refus.statut === 403, refus.statut);
  ok(S, "aucune erreur JS ni 5xx", p.erreurs.length === 0, p.erreurs.join(" | "));
  await p.contexte.close();

  // Le graphique du super administrateur peut maintenant calculer l'attendu de l'académie.
  const sa = await jeton("superadmin");
  await api("POST", "/auth/entity-context/switch/", sa, { entity_id: null });
  const tb = await api("GET", "/payments/tableau-de-bord/?periode=annee", sa);
  ok(S, "graphique : attendu calculable avec un échéancier", tb.statut === 200 && tb.donnees.devises.some((d) => d.echeancier_configure && d.indicateurs.attendu_minor !== null),
    JSON.stringify(tb.donnees?.devises?.map((d) => [d.devise, d.echeancier_configure])));
  await api("DELETE", `/payments/fee-schedules/${cree.id}/`, jt, { motif: "Nettoyage E2E" });
}
