// Clôture : remises, exonérations, échéancier personnel, journal, situation par élève,
// export, cloche des notifications (fermeture au clic extérieur) et affichage mobile.
// Données de test locales uniquement ; aucun paiement réel, aucun e-mail.
import { BASE, api, connecter, jeton, ok, unique } from "../outils.mjs";

const S = "finance";
const jour = (d) => new Date(Date.now() + d * 86400000).toISOString().slice(0, 10);

export default async function () {
  const u = unique();
  const jt = await jeton("admin");
  const annees = (await api("GET", "/schools/years/", jt)).donnees;
  const annee = (annees.results || annees).find((a) => a.is_current);
  // Un tarif « examen » de l'année peut subsister d'un passage précédent (unicité) : il est réutilisé.
  const corps = { payment_type: "examen", label: `Examen E2E ${u}`, school_year: annee.id, amount: "20000", is_mandatory: true,
    is_active: true, installments: [{ label: "Unique", due_date: jour(-5), amount: "20000" }] };
  const existant = (await api("GET", "/payments/fee-schedules/", jt)).donnees.find((x) => x.payment_type === "examen" && x.school_year === annee.id && !x.level);
  const tarif = (existant ? await api("PATCH", `/payments/fee-schedules/${existant.id}/`, jt, { ...corps, motif: "Reprise E2E" })
    : await api("POST", "/payments/fee-schedules/", jt, corps)).donnees;
  ok(S, "tarif d'essai prêt", Boolean(tarif.id), JSON.stringify(tarif).slice(0, 160));
  const sit = async (p = "") => (await api("GET", `/payments/situation/?groupe=eleve&nature=examen${p}`, jt)).donnees.academies[0];
  const avant = await sit();
  const eleve = avant.eleves[0];
  ok(S, "API : vue par élève, net = théorique sans ajustement", avant.totaux.net_minor === avant.totaux.theorique_minor && avant.eleves_total > 0);

  // Remise en pourcentage créée par l'interface, sur la nature « examen ».
  const p = await connecter("admin");
  await p.goto(BASE + "/admin/tarifs");
  await p.getByTestId("onglet-remises").click();
  await p.getByTestId("regle-nouvelle").click();
  const f = p.getByTestId("regle-formulaire");
  await f.locator("#r-nom").fill(`Remise E2E ${u}`);
  await f.locator("#r-val").fill("25");
  await f.locator("#r-nature").selectOption("examen");
  await p.getByTestId("regle-enregistrer").click();
  await p.getByTestId("regles-liste").getByText(`Remise E2E ${u}`).waitFor({ timeout: 10000 });
  ok(S, "remise créée depuis l'interface", true);
  const apres = await sit();
  ok(S, "situation : remise de 25 % appliquée à toute la sélection", apres.totaux.remises_minor === Math.round(avant.totaux.theorique_minor * 0.25)
    && apres.totaux.net_minor === avant.totaux.net_minor - apres.totaux.remises_minor, `${apres.totaux.remises_minor}`);

  // Exonération totale pour un élève (justification exigée par le serveur).
  const refus = await api("POST", "/payments/regles-remise/", jt, { nom: "Exo", genre: "exoneration", categorie: "sociale", mode: "pourcentage", pourcentage: "100", student: eleve.id });
  ok(S, "exonération sans justification refusée (400)", refus.statut === 400);
  const exo = await api("POST", "/payments/regles-remise/", jt, { nom: `Exo E2E ${u}`, genre: "exoneration", categorie: "sociale", mode: "pourcentage",
    pourcentage: "100", student: eleve.id, payment_type: "examen", justification: "Décision E2E" });
  ok(S, "exonération totale enregistrée", exo.statut === 201, exo.brut.slice(0, 160));
  const fiche = (await api("GET", `/payments/situation/eleves/${eleve.id}/`, jt)).donnees;
  const examen = fiche.tarifs.find((x) => x.tarif_id === tarif.id);
  ok(S, "fiche : exonération déduite avant la remise (net nul)", examen && examen.net_minor === 0 && examen.exonerations_minor === 20000);

  // Échéancier personnel : délai supplémentaire, sans toucher aux paiements.
  const ep = await api("POST", "/payments/echeanciers-eleves/", jt, { student: avant.eleves[1]?.id ?? eleve.id, fee_schedule: tarif.id, school_year: annee.id,
    motif: "Délai E2E", echeances: [{ label: "Report", due_date: jour(20), montant: "20000" }] });
  ok(S, "échéancier personnel enregistré", ep.statut === 201, ep.brut.slice(0, 160));

  // Journal : création, annulation, avec motif.
  const regle = (await api("GET", "/payments/regles-remise/?genre=remise", jt)).donnees.find((r) => r.nom === `Remise E2E ${u}`);
  await api("POST", `/payments/regles-remise/${regle.id}/annuler/`, jt, { motif: "Fin E2E" });
  const journal = (await api("GET", "/payments/journal-financier/?objet=regle", jt)).donnees;
  ok(S, "journal : création et annulation tracées avec motif", journal.some((j) => j.description.includes(`Remise E2E ${u}`) && j.action === "annulation" && j.motif === "Fin E2E"));
  ok(S, "aucune suppression possible (405)", (await api("DELETE", `/payments/regles-remise/${regle.id}/`, jt)).statut === 405);

  // Situation par élève : recherche, fiche, export.
  await p.goto(BASE + "/admin/situation-financiere");
  await p.getByTestId("groupe-eleve").click();
  await p.getByTestId("filtre-nature").selectOption("examen");
  await p.getByTestId("filtre-q").fill(eleve.nom.split(" ")[0]);
  await p.waitForTimeout(1800);
  const lignes = await p.locator("[data-testid=situation-eleves] tbody tr").count();
  ok(S, "recherche d'un élève", lignes >= 1 && (await p.getByTestId("situation-eleves").innerText()).includes(eleve.nom));
  await p.getByTestId(`eleve-${eleve.id}`).click();
  await p.getByTestId("releve-tarifs").waitFor({ timeout: 10000 });
  ok(S, "fiche : exonération affichée", (await p.getByTestId("releve-tarifs").innerText()).includes(`Exo E2E ${u}`));
  await p.keyboard.press("Escape");
  const [dl] = await Promise.all([p.waitForEvent("download", { timeout: 15000 }), p.getByTestId("situation-export").click()]);
  ok(S, "export CSV téléchargé", (await dl.suggestedFilename()).endsWith(".csv"));

  // Cloche : ouverture, clic extérieur, Échap.
  await p.getByTestId("cloche").click();
  ok(S, "cloche : panneau ouvert", await p.getByTestId("cloche-panneau").count() === 1);
  await p.mouse.click(30, 700);
  await p.waitForTimeout(200);
  ok(S, "cloche : fermée au clic extérieur", await p.getByTestId("cloche-panneau").count() === 0);
  await p.getByTestId("cloche").click();
  await p.keyboard.press("Escape");
  ok(S, "cloche : fermée avec Échap", await p.getByTestId("cloche-panneau").count() === 0);

  // Mobile : pas de défilement horizontal de la page.
  await p.setViewportSize({ width: 375, height: 812 });
  await p.goto(BASE + "/admin/situation-financiere");
  await p.getByTestId("situation-kpi").waitFor({ timeout: 15000 });
  ok(S, "mobile : pas de défilement horizontal", !(await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)));
  await p.getByTestId("cloche").click();
  await p.mouse.click(40, 600);
  ok(S, "mobile : cloche fermée au toucher extérieur", await p.getByTestId("cloche-panneau").count() === 0);

  // Permissions.
  for (const role of ["teacher", "parent", "student"]) {
    ok(S, `${role} : remises refusées (403)`, (await api("GET", "/payments/regles-remise/", await jeton(role))).statut === 403);
  }
  ok(S, "aucune erreur JS ni 5xx", p.erreurs.length === 0, p.erreurs.join(" | "));

  // Nettoyage des données d'essai (base locale) : règles annulées, échéancier rétabli.
  await api("POST", `/payments/regles-remise/${exo.donnees.id}/annuler/`, jt, { motif: "Nettoyage E2E" });
  await api("POST", "/payments/echeanciers-eleves/retablir/", jt, { student: avant.eleves[1]?.id ?? eleve.id, fee_schedule: tarif.id, school_year: annee.id, motif: "Nettoyage E2E" });
  await api("PATCH", `/payments/fee-schedules/${tarif.id}/`, jt, { is_active: false, motif: "Nettoyage E2E" });
}
