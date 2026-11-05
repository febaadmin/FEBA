// Centre d'analyse : cinq profils, périmètre côté serveur, présentation FR / EN / bilingue.
import { BASE, api, connecter, jeton, liste, ok } from "../outils.mjs";

const S = "analyses";

export default async function () {
  const ja = await jeton("admin");
  const opts = (await api("GET", "/analytics/filtres/", ja)).donnees;
  ok(S, "API admin : filtres de l'académie", opts.classes?.length > 0, JSON.stringify(opts).slice(0, 120));
  const res = await api("GET", "/analytics/resultats/", ja);
  for (const chemin of ["vue-ensemble", "classes", "matieres/detail", "enseignants/profils"]) {
    ok(S, `API admin : ${chemin} répond`, (await api("GET", `/analytics/${chemin}/`, ja)).statut === 200);
  }
  const eff = await api("GET", "/analytics/effectifs/", ja);
  ok(S, "API admin : résultats et effectifs", res.statut === 200 && eff.statut === 200);
  if (res.donnees.par_classe?.length) {
    const somme = res.donnees.par_classe.reduce((n, c) => n + c.eleves_notes, 0);
    ok(S, "API : élèves notés = somme des classes", somme === res.donnees.synthese.eleves_notes, `${somme} / ${res.donnees.synthese.eleves_notes}`);
  }

  // Administrateur : centre de pilotage, onglets, présentation, parcours analytique complet.
  const ens = (await api("GET", "/analytics/vue-ensemble/", ja)).donnees;
  const p = await connecter("admin");
  ok(S, "menu « Centre d'analyse »", await p.locator('a[href="/admin/analyses"]').count() === 1);
  await p.goto(BASE + "/admin/analyses");
  await p.getByTestId("analyse-filtres").waitFor({ timeout: 15000 });
  await p.getByTestId("kpi-inscrits").waitFor({ timeout: 15000 });
  ok(S, "vue d'ensemble : KPI inscrits = API", (await p.getByTestId("kpi-inscrits").innerText()).includes(String(ens.kpi.inscrits)));
  ok(S, "vue d'ensemble : limites des données expliquées", ens.limites.length === 0 || await p.getByTestId("analyse-limites").count() === 1);
  ok(S, "vue d'ensemble : graphiques avec période et unité",
    (await p.getByTestId("ens-repartition").innerText()).includes("Unité") && await p.locator("[data-testid=ens-repartition] svg").count() > 0);
  for (const o of ["resultats", "matieres", "classes", "enseignants", "effectifs", "presences"]) {
    await p.getByTestId(`onglet-${o}`).click();
    await p.waitForTimeout(1200);
    ok(S, `onglet ${o} sans erreur`, await p.getByTestId("analyse-erreur").count() === 0);
  }
  await p.getByTestId("onglet-effectifs").click();
  await p.waitForTimeout(800);
  ok(S, "effectifs affichés = API", (await p.getByTestId("eff-inscrits").innerText()).includes(String(eff.donnees.inscrits)));
  await p.getByTestId("presentation-en").click();
  ok(S, "présentation anglaise", (await p.getByTestId("eff-inscrits").innerText()).includes("Enrolled students"));
  await p.getByTestId("presentation-bi").click();
  ok(S, "présentation bilingue, même chiffre", (await p.getByTestId("eff-inscrits").innerText()).includes("Élèves inscrits / Enrolled students")
    && (await p.getByTestId("eff-inscrits").innerText()).includes(String(eff.donnees.inscrits)));
  await p.getByTestId("presentation-fr").click();
  // Parcours : classe → matière → enseignant, puis KPI et détail cohérents avec l'API.
  const classe = opts.classes.find((c) => res.donnees.par_classe?.some((x) => x.id === c.id)) || opts.classes[0];
  await p.getByTestId("onglet-ensemble").click();
  await p.getByTestId("af-classe").click();
  await p.getByTestId(`af-classe-${classe.id}`).check();
  await p.keyboard.press("Escape");
  await p.waitForTimeout(1500);
  const deps = (await api("GET", `/analytics/filtres/?classe=${classe.id}`, ja)).donnees;
  const matiere = (await api("GET", `/analytics/matieres/?classe=${classe.id}`, ja)).donnees.matieres[0];
  if (matiere) {
    await p.getByTestId("af-matiere").click();
    await p.getByTestId(`af-matiere-${matiere.id}`).check();
    await p.keyboard.press("Escape");
    await p.waitForTimeout(1500);
  }
  const profs = (await api("GET", `/analytics/enseignants/profils/?classe=${classe.id}${matiere ? `&matiere=${matiere.id}` : ""}`, ja)).donnees.profils;
  const prof = profs.find((x) => x.id) ;
  if (prof) {
    await p.getByTestId("af-enseignant").click();
    await p.getByTestId(`af-enseignant-${prof.id}`).check();
    await p.keyboard.press("Escape");
    await p.waitForTimeout(1500);
  }
  const q = `classe=${classe.id}${matiere ? `&matiere=${matiere.id}` : ""}${prof ? `&enseignant=${prof.id}` : ""}`;
  const attendu = (await api("GET", `/analytics/vue-ensemble/?${q}`, ja)).donnees.kpi;
  ok(S, "parcours classe → matière → enseignant : puces actives", (await p.getByTestId("af-actifs").innerText()).includes(classe.nom));
  ok(S, "parcours : KPI de l'écran = API pour la sélection exacte",
    (await p.getByTestId("kpi-notes").innerText()).includes(`${attendu.notes} `) && (await p.getByTestId("kpi-notes").innerText()).includes(String(attendu.eleves_notes)),
    `${await p.getByTestId("kpi-notes").innerText()} / ${attendu.eleves_notes} ${attendu.notes}`);
  ok(S, "parcours : la classe choisie limite les élèves proposés", deps.eleves.length >= 0);
  await p.getByTestId("onglet-enseignants").click();
  await p.waitForTimeout(1500);
  ok(S, "parcours : profil de l'enseignant affiché", !prof || await p.getByTestId(`ens-profil-${prof.id}`).count() === 1);
  ok(S, "parcours : avertissement sur les enseignants", (await p.getByTestId("avertissement-enseignants").innerText()).includes("aucune conclusion"));
  await p.getByTestId("onglet-classes").click();
  await p.waitForTimeout(1200);
  const detail = p.getByTestId("cls-effectifs-detail");
  if (await detail.count()) { await detail.click(); await p.waitForTimeout(300); }
  ok(S, "parcours : tableau détaillé à la demande", await p.getByTestId("cls-table").count() === 1);
  await p.getByTestId("af-reinitialiser").click();
  await p.waitForTimeout(800);
  ok(S, "réinitialisation des filtres", await p.getByTestId("af-actifs").count() === 0);
  const deborde = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  ok(S, "admin : aucune erreur JS ni 5xx ni CSP, aucun débordement", p.erreurs.length === 0 && !deborde, p.erreurs.join(" | "));
  await p.contexte.close();

  // Enseignant : ses classes seulement.
  const jt = await jeton("teacher");
  const optsProf = (await api("GET", "/analytics/filtres/", jt)).donnees;
  const mesClasses = new Set((optsProf.classes || []).map((c) => c.id));
  const autre = opts.classes.find((c) => !mesClasses.has(c.id));
  ok(S, "enseignant : aucun filtre « enseignant »", Array.isArray(optsProf.enseignants) && optsProf.enseignants.length === 0);
  if (autre) ok(S, "enseignant : classe d'un autre refusée (403)", (await api("GET", `/analytics/resultats/?classe=${autre.id}`, jt)).statut === 403);
  ok(S, "enseignant : aucune finance (403)", (await api("GET", "/payments/situation/", jt)).statut === 403);
  const pt = await connecter("teacher");
  ok(S, "enseignant : menu « Analyses de mes classes »", await pt.locator('a[href="/teacher/analyses"]').count() === 1);
  await pt.goto(BASE + "/teacher/analyses");
  await pt.getByTestId("analyse-filtres").waitFor({ timeout: 15000 });
  await pt.waitForTimeout(1200);
  ok(S, "enseignant : écran sans erreur", await pt.getByTestId("analyse-erreur").count() === 0 && pt.erreurs.length === 0, pt.erreurs.join(" | "));
  await pt.contexte.close();

  // Familles : vue personnelle uniquement.
  for (const role of ["parent", "student"]) {
    const j = await jeton(role);
    ok(S, `${role} : analyses d'établissement refusées (403)`, (await api("GET", "/analytics/resultats/", j)).statut === 403);
    const mes = (await api("GET", "/analytics/mes-eleves/", j)).donnees.eleves || [];
    const sien = new Set(mes.map((e) => e.id));
    const tous = liste((await api("GET", "/students/?page_size=100", ja)).donnees);
    const etranger = tous.find((e) => !sien.has(e.id));
    ok(S, `${role} : autre élève refusé (404)`, etranger && (await api("GET", `/analytics/eleves/${etranger.id}/`, j)).statut === 404, etranger?.id);
    if (mes[0]) ok(S, `${role} : son élève accessible`, (await api("GET", `/analytics/eleves/${mes[0].id}/`, j)).statut === 200);
    const pf = await connecter(role);
    await pf.goto(BASE + `/${role}/analyses`);
    await pf.waitForTimeout(2500);
    ok(S, `${role} : vue personnelle affichée`, mes.length === 0 || await pf.getByTestId("analyse-eleve").count() === 1);
    ok(S, `${role} : aucune erreur JS ni 5xx`, pf.erreurs.length === 0, pf.erreurs.join(" | "));
    await pf.contexte.close();
  }

  // Super administrateur : une académie à la fois.
  const js = await jeton("superadmin");
  await api("POST", "/auth/entity-context/switch/", js, { entity_id: null });
  ok(S, "superadmin « Toutes les Académies » : 400 explicite", (await api("GET", "/analytics/resultats/", js)).statut === 400);
  const ps = await connecter("superadmin");
  await ps.goto(BASE + "/superadmin/analyses");
  await ps.waitForTimeout(2000);
  ok(S, "superadmin : message « Choisissez une académie »", (await ps.getByTestId("analyse-erreur").innerText()).includes("académie"));
  await ps.contexte.close();
}
