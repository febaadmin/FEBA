// Tableau de bord super administrateur : graphique des paiements, comparé à l'API.
import { BASE, api, connecter, jeton, ok } from "../outils.mjs";

const S = "tableau";

export default async function () {
  const jt = await jeton("superadmin");
  const ref = await api("GET", "/payments/tableau-de-bord/?periode=12m", jt);
  ok(S, "API : 200 pour le super administrateur", ref.statut === 200, ref.statut);
  ok(S, "API : 403 pour un administrateur", (await api("GET", "/payments/tableau-de-bord/", await jeton("admin"))).statut === 403);

  for (const vp of [{ width: 1366, height: 900 }, { width: 390, height: 844 }]) {
    const p = await connecter("superadmin", { contexte: { viewport: vp } });
    await p.goto(BASE + "/superadmin/dashboard");
    const carte = p.getByTestId("graphique-paiements");
    await carte.waitFor({ timeout: 15000 });
    await p.waitForTimeout(1500);
    const vide = await p.getByTestId("paiements-vide").count();
    const indicateur = await p.getByTestId("ind-encaisse").count();
    ok(S, `${vp.width}px : carte affichée (indicateurs ou état vide)`, vide + indicateur === 1);
    if (indicateur) {
      ok(S, `${vp.width}px : graphique rendu`, await p.locator("[data-testid=paiements-graphique] svg").count() > 0);
      const nb = ref.donnees.devises[0]?.indicateurs.nb_paiements;
      const texte = await p.getByTestId("ind-encaisse").innerText();
      ok(S, `${vp.width}px : nombre de paiements identique à l'API`, texte.includes(`${nb} `), `${texte} / ${nb}`);
    }
    await p.getByTestId("periode-30j").click();
    await p.waitForTimeout(1200);
    ok(S, `${vp.width}px : période 30 jours`, (await p.getByTestId("periode-30j").getAttribute("aria-pressed")) === "true");
    await p.getByTestId("periode-perso").click();
    ok(S, `${vp.width}px : période personnalisée demande les dates`, await p.getByText(/Choisissez les deux dates/).count() === 1);
    const deborde = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    ok(S, `${vp.width}px : aucun débordement, aucune erreur JS ni 5xx`, !deborde && p.erreurs.length === 0, `${deborde} ${p.erreurs}`);
    await p.contexte.close();
  }

  // Filtres, comparaison, détail d'une barre, export : une académie choisie.
  const entites = (await api("GET", "/auth/entity-context/", jt)).donnees.entities;
  const ecole = entites.find((e) => e.currency === "XOF") || entites[0];
  await api("POST", "/auth/entity-context/switch/", jt, { entity_id: ecole.id });
  try {
    const opts = (await api("GET", "/payments/tableau-de-bord/filtres/", jt)).donnees;
    ok(S, "filtres : structure proposée pour une académie", opts.structure_disponible && opts.niveaux.length > 0);
    // Un niveau qui a des paiements, pour éprouver la comparaison et le détail dans le navigateur.
    let niveau = opts.niveaux[0];
    for (const n of opts.niveaux) {
      const r = await api("GET", `/payments/tableau-de-bord/?periode=12m&niveau=${n.id}`, jt);
      if (r.donnees.devises[0].indicateurs.nb_paiements > 0) { niveau = n; break; }
    }
    const dep = (await api("GET", `/payments/tableau-de-bord/filtres/?niveau=${niveau.id}`, jt)).donnees;
    ok(S, "filtres dépendants : classes du niveau seulement", dep.classes.every((c) => c.niveau_id === niveau.id));
    const tous = (await api("GET", "/payments/tableau-de-bord/?periode=12m", jt)).donnees.devises[0].indicateurs;
    const parMode = await Promise.all(opts.modes.map(async (m) =>
      (await api("GET", `/payments/tableau-de-bord/?periode=12m&mode=${m.id}`, jt)).donnees.devises[0].indicateurs.encaisse_minor));
    ok(S, "API : somme des modes de paiement = total encaissé", parMode.reduce((a, b) => a + b, 0) === tous.encaisse_minor,
      `${parMode} / ${tous.encaisse_minor}`);
    const filtre = await api("GET", `/payments/tableau-de-bord/?periode=12m&niveau=${niveau.id}`, jt);
    const det = await api("GET", `/payments/tableau-de-bord/detail/?periode=12m&niveau=${niveau.id}&statut=confirme`, jt);
    ok(S, "API : détail filtré = indicateur filtré (nombre de paiements)",
      det.donnees.total === filtre.donnees.devises[0].indicateurs.nb_paiements, `${det.donnees.total} / ${filtre.donnees.devises[0].indicateurs.nb_paiements}`);
    const csv = await api("GET", "/payments/tableau-de-bord/detail/?periode=12m&export=csv", jt);
    ok(S, "export CSV", csv.statut === 200 && csv.type.startsWith("text/csv") && csv.brut.includes("Référence"));
    ok(S, "filtre inconnu refusé (400)", (await api("GET", "/payments/tableau-de-bord/?mode=bitcoin", jt)).statut === 400);

    const p = await connecter("superadmin");
    await p.goto(BASE + "/superadmin/dashboard");
    await p.getByTestId("graphique-paiements").waitFor({ timeout: 15000 });
    await p.waitForTimeout(1500);
    await p.getByTestId("filtre-niveau").selectOption(String(niveau.id));
    await p.waitForTimeout(1500);
    ok(S, "écran : puce du filtre actif", (await p.getByTestId("filtres-actifs").innerText()).includes(niveau.nom));
    const nbFiltre = filtre.donnees.devises[0].indicateurs.nb_paiements;
    if (await p.getByTestId("ind-encaisse").count()) {
      ok(S, "écran : indicateur filtré identique à l'API", (await p.getByTestId("ind-encaisse").innerText()).includes(`${nbFiltre} `));
      await p.getByTestId("comparer").check();
      await p.waitForTimeout(1500);
      ok(S, "écran : comparaison avec la période précédente", await p.getByTestId("periode-precedente").count() === 1);
      const serie = filtre.donnees.devises[0].serie;
      const pleine = [...serie].reverse().find((c) => c.encaisse_minor > 0) || serie[serie.length - 1];
      // Clic sur la vraie barre du graphique (la dernière non vide = la dernière case encaissée).
      const barres = p.locator("[data-testid=paiements-graphique] .recharts-bar-rectangle path");
      let derniere = -1;
      for (let i = 0; i < await barres.count(); i++) if ((await barres.nth(i).boundingBox())?.height > 1) derniere = i;
      await barres.nth(derniere).click();
      await p.getByTestId("detail-paiements").waitFor({ timeout: 10000 });
      const attendu = (await api("GET", `/payments/tableau-de-bord/detail/?periode=12m&niveau=${niveau.id}&case=${pleine.date}`, jt)).donnees.total;
      ok(S, "écran : détail d'une barre (même nombre que l'API)", (await p.getByTestId("detail-total").innerText()) === String(attendu));
      await p.keyboard.press("Escape");
    } else {
      ok(S, "écran : état vide explicite avec filtre", (await p.getByTestId("paiements-vide").innerText()).includes("filtres"));
    }
    await p.getByTestId("filtres-reinitialiser").click();
    await p.waitForTimeout(800);
    ok(S, "écran : réinitialisation des filtres", await p.getByTestId("filtres-actifs").count() === 0);
    ok(S, "filtres : aucune erreur JS ni 5xx", p.erreurs.length === 0, p.erreurs.join(" | "));
    await p.contexte.close();
  } finally {
    await api("POST", "/auth/entity-context/switch/", jt, { entity_id: null });
  }
}
