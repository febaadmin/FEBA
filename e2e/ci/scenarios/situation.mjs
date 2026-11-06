// Situation financière : personnel (totaux, classes, relevé), parent (ses enfants), refus des autres profils.
import { BASE, api, connecter, jeton, ok, unique } from "../outils.mjs";

const S = "situation";
const jour = (decalage) => new Date(Date.now() + decalage * 86400000).toISOString().slice(0, 10);

export default async function () {
  const jt = await jeton("admin");
  const annees = (await api("GET", "/schools/years/", jt)).donnees;
  const annee = (annees.results || annees).find((a) => a.is_current);
  const tarif = await api("POST", "/payments/fee-schedules/", jt, {
    payment_type: "activites", label: `Sorties E2E ${unique()}`, school_year: annee.id, amount: "10000", is_mandatory: true,
    installments: [{ label: "Tranche échue", due_date: jour(-10), amount: "6000" }, { label: "Tranche à venir", due_date: jour(30), amount: "4000" }],
  });
  ok(S, "tarif d'essai créé (année en cours, tous niveaux)", tarif.statut === 201, tarif.brut.slice(0, 200));

  const situation = await api("GET", "/payments/situation/?groupe=classe", jt);
  const a = situation.donnees.academies?.[0];
  ok(S, "API : situation calculée", situation.statut === 200 && a?.echeancier_configure && a.groupes.length > 0);
  const somme = (cle) => a.groupes.reduce((n, g) => n + g[cle], 0);
  ok(S, "API : total académie = somme des classes", a.totaux.restant_minor === somme("restant_minor") && a.totaux.attendu_minor === somme("attendu_minor"));

  const p = await connecter("admin");
  ok(S, "entrée « Situation financière » au menu", await p.locator('a[href="/admin/situation-financiere"]').count() === 1);
  await p.goto(BASE + "/admin/situation-financiere");
  await p.getByTestId("situation-kpi").waitFor({ timeout: 15000 });
  ok(S, "écran : KPI et classes", await p.locator("[data-testid=situation-groupes] tbody tr").count() === a.groupes.length);
  ok(S, "graphiques affichés", await p.getByTestId("graph-repartition").count() === 1 && await p.getByTestId("graph-groupes").count() === 1);
  await p.getByTestId("groupe-eleve").click();
  await p.getByTestId("filtre-statut").selectOption("en_retard");
  await p.waitForTimeout(1500);
  const enRetard = await p.locator("[data-testid=situation-eleves] tbody tr").count();
  ok(S, "filtre « En retard » : élèves avec tranche échue", enRetard > 0 && enRetard === Math.min(50, a.kpi.eleves_en_retard), `${enRetard}/${a.kpi.eleves_en_retard}`);
  await p.locator("[data-testid=situation-eleves] tbody tr button").first().click();
  await p.getByTestId("releve-eleve").waitFor({ timeout: 10000 });
  ok(S, "fiche d'un élève : échéances, calcul expliqué", await p.getByTestId("releve-echeances").count() === 1
    && (await p.getByTestId("releve-echeances").innerText()).includes("Tranche échue") && await p.getByTestId("releve-explication").count() === 1);
  await p.keyboard.press("Escape");
  await p.getByTestId("filtre-statut").selectOption("");
  await p.getByTestId("groupe-niveau").click();
  await p.waitForTimeout(1200);
  ok(S, "regroupement par niveau", (await p.locator("[data-testid=situation-groupes] th").first().innerText()).toLowerCase().includes("niveau"));
  ok(S, "aucune erreur JS ni 5xx (personnel)", p.erreurs.length === 0, p.erreurs.join(" | "));
  await p.contexte.close();

  // Parent : ses enfants seulement.
  const parent = await connecter("parent");
  await parent.goto(BASE + "/parent/payments");
  await parent.waitForTimeout(2000);
  ok(S, "parent : situation de ses enfants affichée", await parent.getByTestId("situation-enfants").count() === 1 && await parent.getByTestId("releve-eleve").count() >= 1);
  ok(S, "aucune erreur JS ni 5xx (parent)", parent.erreurs.length === 0, parent.erreurs.join(" | "));
  await parent.contexte.close();

  const autreEleve = a.eleves.find((e) => true);
  const jtParentAutre = await jeton("parentAutre");
  const lienParent = (await api("GET", "/parents/me/", jtParentAutre)).donnees;
  const sesEnfants = new Set((lienParent.children_links || []).map((l) => l.student));
  const etranger = a.eleves.find((e) => !sesEnfants.has(e.id));
  ok(S, "parent : enfant d'une autre famille refusé (404)", (await api("GET", `/payments/situation/eleves/${etranger.id}/`, jtParentAutre)).statut === 404);
  for (const role of ["teacher", "student"]) {
    ok(S, `${role} : situation refusée (403)`, (await api("GET", `/payments/situation/eleves/${autreEleve.id}/`, await jeton(role))).statut === 403);
  }
  ok(S, "parent : vue d'ensemble refusée (403)", (await api("GET", "/payments/situation/", jtParentAutre)).statut === 403);
  await api("DELETE", `/payments/fee-schedules/${tarif.donnees.id}/`, jt, { motif: "Nettoyage E2E" });
}
