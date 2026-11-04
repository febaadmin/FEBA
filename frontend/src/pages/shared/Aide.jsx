/**
 * Centre d'aide : un article par fonctionnalité réelle, filtré selon le profil
 * connecté, avec recherche, catégories, FAQ, dépannage et glossaire, en
 * français et en anglais (langue de l'interface). Contenu : src/aide/articles.js.
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ChevronDown, ExternalLink, Search } from "lucide-react";
import { useAuth } from "../../hooks/useAuth";
import { useEntityContext } from "../../hooks/useEntityContext";
import { useI18n } from "../../i18n";
import { isNavItemVisible } from "../../layouts/navFeatures";
import PageHeader from "../../components/ui/PageHeader";
import { LIBELLES_ROLES } from "../../aide/articles";
import { L, articlesPour, categoriesPour, depannagePour, faqPour, glossairePour, lienPour, mots, suggestions } from "../../aide/recherche";

const UI = {
  titre: ["Aide", "Help"],
  sousTitre: ["Guides pas à pas de chaque fonctionnalité, questions fréquentes et glossaire", "Step-by-step guides for each feature, FAQ and glossary"],
  rechercher: ["Rechercher dans l'aide (ex. : bulletin, mot de passe, absence)", "Search help (e.g. report card, password, attendance)"],
  categories: ["Catégories de l'aide", "Help categories"],
  toutes: ["Toutes", "All"],
  aucun: ["Aucun article ne correspond à votre recherche.", "No article matches your search."],
  objet: ["À quoi ça sert", "What it is for"],
  qui: ["Qui peut l'utiliser", "Who can use it"],
  prerequis: ["Prérequis", "Prerequisites"],
  ou: ["Où la trouver", "Where to find it"],
  menu: ["Menu", "Menu"],
  etapes: ["Étapes", "Steps"],
  champs: ["Champs importants", "Important fields"],
  resultat: ["Résultat attendu", "Expected result"],
  erreurs: ["Erreurs fréquentes et solutions", "Common errors and solutions"],
  consequences: ["Effets sur les autres modules", "Effects on other modules"],
  permissions: ["Permissions", "Permissions"],
  ouvrir: ["Ouvrir", "Open"],
  inactif: ["Module non activé pour l'académie sélectionnée.", "Module not enabled for the selected academy."],
  faq: ["Questions fréquentes", "Frequently asked questions"],
  depannage: ["Dépannage", "Troubleshooting"],
  glossaire: ["Glossaire", "Glossary"],
  articles: ["article(s)", "article(s)"],
  resultats: ["résultat(s) pour", "result(s) for"],
  classement: ["Classés par pertinence", "Sorted by relevance"],
  essayez: ["Essayez :", "Try:"],
  tousProfils: ["Vue super administrateur : documentation de tous les profils.", "Super administrator view: documentation for every profile."],
};

function Bloc({ titre, children }) {
  return (
    <div>
      <h4 className="text-xs font-semibold uppercase tracking-wide text-feba-navy/70 mb-1">{titre}</h4>
      <div className="text-sm text-slate-700">{children}</div>
    </div>
  );
}

/** Met en évidence les mots de la recherche (sans accents ni casse) dans un texte. */
function Surligne({ texte, termes }) {
  if (!termes.length) return texte;
  const norm = (c) => c.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const parties = [];
  let i = 0;
  const plat = norm(texte);
  while (i < texte.length) {
    const t = termes.find((m) => plat.startsWith(m, i) && (i === 0 || !/[a-z0-9]/.test(plat[i - 1])));
    if (t) { parties.push(<mark key={i} className="bg-feba-gold/25 text-inherit rounded px-0.5">{texte.slice(i, i + t.length)}</mark>); i += t.length; }
    else { const j = parties.length && typeof parties[parties.length - 1] === "string" ? parties.pop() : ""; parties.push(j + texte[i]); i += 1; }
  }
  return parties;
}

function Article({ a, role, lang, ouvert, basculer, moduleActif, termes = [] }) {
  const lien = moduleActif ? lienPour(a, role) : null;
  const corps = `aide-${a.id}`;
  return (
    <section id={`article-${a.id}`} className="card !p-0 overflow-hidden" data-testid="aide-article" data-article={a.id}>
      <h3>
        <button type="button" onClick={basculer} aria-expanded={ouvert} aria-controls={corps}
          className="w-full flex items-start gap-3 text-left px-5 py-4 hover:bg-feba-cream/40 transition-colors">
          <span className="flex-1 min-w-0">
            <span className="block font-semibold text-slate-900"><Surligne texte={L(a.titre, lang)} termes={termes} /></span>
            <span className="mt-1 inline-block badge bg-primary-50 text-primary">{L(a.module, lang)}</span>
          </span>
          <ChevronDown className={`w-5 h-5 mt-0.5 shrink-0 text-slate-400 transition-transform ${ouvert ? "rotate-180" : ""}`} aria-hidden="true" />
        </button>
      </h3>
      {ouvert && (
        <div id={corps} className="px-5 pb-5 pt-3 grid gap-4 md:grid-cols-2 border-t border-slate-100">
          <Bloc titre={L(UI.objet, lang)}><p>{L(a.objet, lang)}</p></Bloc>
          <Bloc titre={L(UI.qui, lang)}><p>{a.roles.map((r) => L(LIBELLES_ROLES[r], lang)).join(", ")}</p></Bloc>
          {a.prerequis.length > 0 && (
            <Bloc titre={L(UI.prerequis, lang)}><ul className="list-disc pl-5 space-y-0.5">{a.prerequis.map((p, i) => <li key={i}>{L(p, lang)}</li>)}</ul></Bloc>
          )}
          <Bloc titre={L(UI.ou, lang)}>
            <p>{L(UI.menu, lang)} : <strong>{L(a.module, lang)}</strong></p>
            {a.feature && !moduleActif && <p className="text-amber-700 mt-1">{L(UI.inactif, lang)}</p>}
            {lien && (
              <Link to={lien} className="mt-2 inline-flex items-center gap-1.5 text-primary font-medium hover:underline" data-testid="aide-lien">
                <ExternalLink className="w-4 h-4" aria-hidden="true" />{L(UI.ouvrir, lang)} : {L(a.module, lang)}
              </Link>
            )}
          </Bloc>
          <div className="md:col-span-2">
            <Bloc titre={L(UI.etapes, lang)}>
              <ol className="list-decimal pl-5 space-y-1">{a.etapes.map((e, i) => <li key={i}>{L(e, lang)}</li>)}</ol>
            </Bloc>
          </div>
          {a.champs.length > 0 && (
            <Bloc titre={L(UI.champs, lang)}><ul className="list-disc pl-5 space-y-0.5">{a.champs.map((c, i) => <li key={i}>{L(c, lang)}</li>)}</ul></Bloc>
          )}
          <Bloc titre={L(UI.resultat, lang)}><p>{L(a.resultat, lang)}</p></Bloc>
          {a.erreurs.length > 0 && (
            <div className="md:col-span-2">
              <Bloc titre={L(UI.erreurs, lang)}>
                <dl className="space-y-1.5">
                  {a.erreurs.map(([pb, sol], i) => (
                    <div key={i}><dt className="font-medium text-slate-800">{L(pb, lang)}</dt><dd className="text-slate-600">{L(sol, lang)}</dd></div>
                  ))}
                </dl>
              </Bloc>
            </div>
          )}
          {L(a.consequences, lang) && <Bloc titre={L(UI.consequences, lang)}><p>{L(a.consequences, lang)}</p></Bloc>}
          <Bloc titre={L(UI.permissions, lang)}><p>{L(a.permissions, lang)}</p></Bloc>
        </div>
      )}
    </section>
  );
}

function Questions({ titre, items, lang, testid }) {
  if (!items.length) return null;
  return (
    <section className="card" data-testid={testid}>
      <h2 className="text-base font-semibold text-slate-900 mb-3">{titre}</h2>
      <dl className="space-y-3 text-sm">
        {items.map((x, i) => (
          <div key={i}><dt className="font-medium text-slate-800">{L(x.q, lang)}</dt><dd className="text-slate-600">{L(x.r, lang)}</dd></div>
        ))}
      </dl>
    </section>
  );
}

export default function Aide() {
  const { user } = useAuth();
  const { lang } = useI18n();
  const { hasFeature, allEntitiesMode, entities } = useEntityContext();
  const role = user?.role || "student";
  const [params, setParams] = useSearchParams();
  const [requete, setRequete] = useState("");
  const categorie = params.get("categorie");
  const [ouverts, setOuverts] = useState(() => new Set(params.get("article") ? [params.get("article")] : []));

  const actif = (a) => isNavItemVisible(a, { hasFeature, isAllAcademies: allEntitiesMode, allowedAcademies: entities || [] });
  // Le super administrateur voit toute la documentation ; les autres profils, les modules actifs de leur académie.
  const categories = categoriesPour(role, actif);
  const recherche = requete.trim() !== "";
  const resultats = useMemo(() => articlesPour(role, { lang, requete, categorie, moduleActif: actif, avecDetails: true }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [role, lang, requete, categorie, hasFeature, allEntitiesMode, entities]);
  const articles = resultats.map((r) => r.article);
  const termes = recherche ? mots(requete).filter((m) => m.length >= 3) : [];
  const choisir = (id) => {
    const p = new URLSearchParams(params);
    if (id) p.set("categorie", id); else p.delete("categorie");
    setParams(p, { replace: true });
  };
  const basculer = (id) => setOuverts((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  // Une recherche précise ouvre directement les articles trouvés.
  const estOuvert = (id) => ouverts.has(id) || (requete.trim() !== "" && articles.length <= 3);
  const glossaire = glossairePour(lang, requete);
  // Lien direct (?article=…) : l'article demandé est ouvert et amené à l'écran.
  const demande = params.get("article");
  useEffect(() => {
    if (demande) document.getElementById(`article-${demande}`)?.scrollIntoView({ block: "start" });
  }, [demande]);

  return (
    <div className="space-y-4">
      <PageHeader title={L(UI.titre, lang)} subtitle={L(UI.sousTitre, lang)} />

      <div className="card space-y-3">
        <label className="relative block">
          <span className="sr-only">{L(UI.rechercher, lang)}</span>
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" aria-hidden="true" />
          <input type="search" value={requete} onChange={(e) => setRequete(e.target.value)} data-testid="aide-recherche"
            placeholder={L(UI.rechercher, lang)} className="input pl-9" />
        </label>
        <div className="flex flex-wrap gap-2" role="group" aria-label={L(UI.categories, lang)}>
          {[{ id: null, titre: UI.toutes }, ...categories].map((c) => (
            <button key={c.id || "toutes"} type="button" onClick={() => choisir(c.id)} aria-pressed={categorie === c.id}
              data-testid="aide-categorie" data-categorie={c.id || ""}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-colors ${categorie === c.id ? "bg-feba-navy text-white" : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"}`}>
              {L(c.titre, lang)}
            </button>
          ))}
        </div>
        <p className="text-xs text-slate-500" aria-live="polite" data-testid="aide-compte">
          {recherche ? `${articles.length} ${L(UI.resultats, lang)} « ${requete.trim()} » · ${L(UI.classement, lang)}` : `${articles.length} ${L(UI.articles, lang)}`}
        </p>
        {role === "superadmin" && <p className="text-xs text-slate-500">{L(UI.tousProfils, lang)}</p>}
      </div>

      {articles.length === 0 && (
        <div className="card text-sm text-slate-600" data-testid="aide-aucun">
          <p>{L(UI.aucun, lang)}</p>
          {recherche && suggestions(requete, lang).length > 0 && (
            <p className="mt-2">{L(UI.essayez, lang)}{" "}
              {suggestions(requete, lang).map((m) => (
                <button key={m} type="button" onClick={() => setRequete(m)} data-testid="aide-suggestion"
                  className="mr-2 text-primary font-medium hover:underline">{m}</button>
              ))}
            </p>
          )}
        </div>
      )}
      {recherche && articles.length > 0 && (
        <div className="space-y-2" data-testid="aide-resultats">
          {articles.map((a) => (
            <Article key={a.id} a={a} role={role} lang={lang} ouvert={estOuvert(a.id)} basculer={() => basculer(a.id)}
              moduleActif={actif(a)} termes={termes} />
          ))}
        </div>
      )}
      {!recherche && categories.filter((c) => articles.some((a) => a.categorie === c.id)).map((c) => (
        <div key={c.id} className="space-y-2">
          <h2 className="text-sm font-semibold text-feba-navy pt-2">{L(c.titre, lang)}</h2>
          {articles.filter((a) => a.categorie === c.id).map((a) => (
            <Article key={a.id} a={a} role={role} lang={lang} ouvert={estOuvert(a.id)} basculer={() => basculer(a.id)} moduleActif={actif(a)} />
          ))}
        </div>
      ))}

      <Questions titre={L(UI.faq, lang)} items={faqPour(role, lang, requete)} lang={lang} testid="aide-faq" />
      <Questions titre={L(UI.depannage, lang)} items={depannagePour(role, lang, requete)} lang={lang} testid="aide-depannage" />
      {glossaire.length > 0 && (
        <section className="card" data-testid="aide-glossaire">
          <h2 className="text-base font-semibold text-slate-900 mb-3">{L(UI.glossaire, lang)}</h2>
          <dl className="grid gap-x-6 gap-y-2 text-sm md:grid-cols-2">
            {glossaire.map(([mot, def]) => (
              <div key={L(mot, "fr")}><dt className="font-medium text-slate-800">{L(mot, lang)}</dt><dd className="text-slate-600">{L(def, lang)}</dd></div>
            ))}
          </dl>
        </section>
      )}
    </div>
  );
}
