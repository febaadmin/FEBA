// Page « Paiements » (recherche, filtres, tri, pagination, export) et nouveaux filtres du
// graphique du tableau de bord. Chaque chiffre affiché est comparé à l'API, et la page est
// comparée au graphique : un même paiement est compté de la même façon sur les deux écrans.
import { BASE, api, connecter, jeton, ok } from "../outils.mjs";

const S = "paiements";
const sansAccents = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export default async function () {
  const ja = await jeton("admin");
  const liste = await api("GET", "/payments/?all_years=1&page_size=5&tri=-date", ja);
  ok(S, "API : liste paginée avec récapitulatif", liste.statut === 200 && Array.isArray(liste.donnees.totaux), liste.statut);
  const total = liste.donnees.count;
  ok(S, "API : 5 lignes au plus par page", liste.donnees.results.length <= 5);
  const totaux = liste.donnees.totaux;
  ok(S, "API : nombre confirmés + annulés = nombre total",
    totaux.reduce((a, t) => a + t.nb_confirmes + t.nb_annules, 0) === total, `${JSON.stringify(totaux)} / ${total}`);

  const premier = liste.donnees.results[0];
  if (premier) {
    const nom = sansAccents(premier.student_name.split(" ").slice(-1)[0]);
    const r = await api("GET", `/payments/?all_years=1&page_size=200&q=${encodeURIComponent(nom.toUpperCase())}`, ja);
    ok(S, "API : recherche sans accents ni casse retrouve le paiement", r.donnees.results.some((p) => p.id === premier.id), nom);
    const ref = await api("GET", `/payments/?all_years=1&q=${encodeURIComponent(premier.reference_number.toLowerCase())}`, ja);
    ok(S, "API : recherche par référence", ref.donnees.count === 1 && ref.donnees.results[0].id === premier.id);
    const mt = await api("GET", `/payments/?all_years=1&page_size=500&montant=${premier.amount}`, ja);
    ok(S, "API : montant exact", mt.donnees.results.every((p) => Number(p.amount) === Number(premier.amount)) && mt.donnees.count >= 1);
  }
  const p1 = await api("GET", "/payments/?all_years=1&page_size=3&page=1&tri=montant", ja);
  const p2 = await api("GET", "/payments/?all_years=1&page_size=3&page=2&tri=montant", ja);
  const ids = [...p1.donnees.results, ...(p2.donnees.results || [])].map((p) => p.id);
  ok(S, "API : pagination stable (aucun doublon entre deux pages)", new Set(ids).size === ids.length);
  const montants = p1.donnees.results.map((p) => Number(p.amount));
  ok(S, "API : tri par montant croissant", montants.every((m, i) => i === 0 || m >= montants[i - 1]), montants);
  ok(S, "API : paramètre inconnu refusé (400)", (await api("GET", "/payments/?nature=bitcoin", ja)).statut === 400);
  const xlsx = await api("GET", "/payments/?all_years=1&export=xlsx", ja);
  ok(S, "API : export Excel", xlsx.statut === 200 && xlsx.type.includes("spreadsheetml"), xlsx.type);
  const opts = await api("GET", "/payments/filtres/", ja);
  ok(S, "API : options de filtres pour l'administration", opts.statut === 200 && opts.donnees.structure_disponible);
  ok(S, "API : modes proposés = modes réellement utilisés ou configurés", opts.donnees.modes.every((m) => m.nb > 0 || m.id === "card"));
  ok(S, "API : options interdites à un parent (403)", (await api("GET", "/payments/filtres/", await jeton("parent"))).statut === 403);

  // Cohérence graphique du tableau de bord ↔ page Paiements (même académie, mêmes filtres).
  const js = await jeton("superadmin");
  const entites = (await api("GET", "/auth/entity-context/", js)).donnees.entities;
  const ecole = entites.find((e) => e.currency === "XOF") || entites[0];
  await api("POST", "/auth/entity-context/switch/", js, { entity_id: ecole.id });
  try {
    for (const filtre of ["", "&mode=cash", "&nature=mensualite", "&statut=confirme"]) {
      const g = (await api("GET", `/payments/tableau-de-bord/?periode=12m${filtre}`, js)).donnees.devises[0]?.indicateurs;
      const pg = (await api("GET", `/payments/?periode=12m&all_years=1&page_size=1${filtre}`, js)).donnees.totaux;
      const net = pg.reduce((a, t) => a + t.net_minor, 0);
      const nb = pg.reduce((a, t) => a + t.nb_confirmes, 0);
      ok(S, `cohérence tableau de bord / page Paiements${filtre || " (sans filtre)"}`,
        g && g.encaisse_minor === net && g.nb_paiements === nb, `${g?.encaisse_minor}/${net} ${g?.nb_paiements}/${nb}`);
    }
    for (const periode of ["jour", "hier", "semaine", "semaine_prec", "mois", "mois_prec"]) {
      const r = await api("GET", `/payments/tableau-de-bord/?periode=${periode}`, js);
      ok(S, `graphique : période ${periode} (${r.donnees?.periode?.granularite})`, r.statut === 200, r.statut);
    }
    const jour = (await api("GET", "/payments/tableau-de-bord/?periode=jour", js)).donnees;
    ok(S, "graphique : une journée heure par heure (24 cases)", jour.periode.granularite === "heure" && jour.devises[0].serie.length === 24);
    ok(S, "graphique : granularité inadaptée refusée (400)",
      (await api("GET", "/payments/tableau-de-bord/?periode=semaine&granularite=heure", js)).statut === 400);

    const p = await connecter("superadmin");
    await p.goto(BASE + "/superadmin/dashboard");
    await p.getByTestId("graphique-paiements").waitFor({ timeout: 15000 });
    await p.getByTestId("periode-mois").click();
    await p.waitForTimeout(1500);
    if (await p.getByTestId("granularites").count()) {
      ok(S, "écran : granularité proposée selon la période", await p.getByTestId("granularite-semaine").count() === 1);
      await p.getByTestId("granularite-semaine").click();
      await p.waitForTimeout(1200);
      ok(S, "écran : granularité semaine appliquée", (await p.getByTestId("granularite-semaine").getAttribute("aria-pressed")) === "true");
    }
    await p.getByTestId("filtre-mode").click();
    const mode = p.locator("[data-testid^=filtre-mode-]").first();
    if (await mode.count()) {
      await mode.check();
      await p.waitForTimeout(1200);
      ok(S, "écran : puce du mode de paiement choisi", (await p.getByTestId("filtres-actifs").innerText()).includes("Mode de paiement"));
    }
    ok(S, "écran tableau de bord : aucune erreur JS ni 5xx", p.erreurs.length === 0, p.erreurs);
    await p.contexte.close();
  } finally {
    await api("POST", "/auth/entity-context/switch/", js, { entity_id: null });
  }

  for (const vp of [{ width: 1366, height: 900 }, { width: 390, height: 844 }]) {
    const p = await connecter("admin", { contexte: { viewport: vp } });
    await p.goto(BASE + "/admin/payments");
    await p.getByTestId("recherche-paiements").waitFor({ timeout: 15000 });
    await p.waitForTimeout(1500);
    const affiche = await p.getByTestId("paiements-total").innerText();
    const ref = await api("GET", "/payments/?page_size=1", ja);
    ok(S, `${vp.width}px : nombre de paiements identique à l'API`, affiche.includes(`${ref.donnees.count} `), `${affiche} / ${ref.donnees.count}`);
    if (premier) {
      const mot = premier.reference_number;
      await p.getByTestId("paiements-recherche").fill(mot);
      await p.waitForTimeout(1500);
      ok(S, `${vp.width}px : recherche par référence`, (await p.getByTestId("paiements-total").innerText()).startsWith("1 "));
      await p.getByTestId("paiements-recherche").fill("");
    }
    await p.getByTestId("pf-statut").selectOption("annule");
    await p.waitForTimeout(1500);
    const annules = (await api("GET", "/payments/?page_size=1&statut=annule", ja)).donnees.count;
    ok(S, `${vp.width}px : filtre statut = API`, (await p.getByTestId("paiements-total").innerText()).includes(`${annules} `));
    ok(S, `${vp.width}px : puce du filtre actif`, await p.getByTestId("pf-puce-statut").count() === 1);
    await p.getByTestId("pf-reinitialiser").click();
    await p.waitForTimeout(800);
    if (await p.getByTestId("tri-montant").count()) {
      await p.getByTestId("tri-montant").click();
      await p.waitForTimeout(1200);
      ok(S, `${vp.width}px : tri par montant`, (await p.locator("th[aria-sort=ascending]").count()) === 1);
    }
    if (vp.width > 400) {
      const [telechargement] = await Promise.all([p.waitForEvent("download", { timeout: 15000 }), p.getByTestId("paiements-export").click()]);
      ok(S, "export Excel depuis l'écran", telechargement.suggestedFilename().endsWith(".xlsx"), telechargement.suggestedFilename());
    }
    const deborde = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    ok(S, `${vp.width}px : aucun débordement de page, aucune erreur JS ni 5xx`, !deborde && p.erreurs.length === 0, `${deborde} ${p.erreurs}`);
    await p.contexte.close();
  }
}
