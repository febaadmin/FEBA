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
}
