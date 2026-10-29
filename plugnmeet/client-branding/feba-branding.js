/*
 * Identité FEBA de l'onglet du client plugNmeet : titre exact et favicon de
 * l'académie à laquelle appartient la salle.
 *
 * Injecté dans le client plugNmeet (dist/index.html) par
 * scripts/plugnmeet_setup.sh, qui recopie ce fichier dans
 * plugnmeet/runtime/client/dist/assets/feba/ : la personnalisation survit
 * aux redémarrages et se reconstruit à chaque installation du client.
 *
 * Pourquoi un script : le client plugNmeet impose `document.title` = titre
 * de la salle à chaque mise à jour des métadonnées
 * (`setWindowTitle(metadata.roomTitle)`). Modifier le titre sur la page FEBA
 * AVANT la redirection n'avait donc aucun effet.
 *
 * Sécurité : l'académie n'est jamais lue dans l'URL. Le jeton d'adhésion
 * plugNmeet (JWT signé par le secret de l'API, lu là où le client le lit :
 * paramètre `access_token`, puis cookie `pnm_access_token`) est envoyé à
 * FEBA, qui vérifie sa signature et répond avec l'identité publique de
 * l'académie de la salle. Un jeton modifié est refusé.
 */
(function () {
  "use strict";
  var script = document.currentScript;
  var api = (script && script.getAttribute("data-feba-api")) || "";
  var STORE = "feba-meeting-branding";

  function cookie(name) {
    var m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[1]) : null;
  }
  var token = new URLSearchParams(window.location.search).get("access_token") || cookie("pnm_access_token");

  // ── Titre verrouillé ──────────────────────────────────────────────────
  var native = Object.getOwnPropertyDescriptor(Document.prototype, "title");
  var wanted = null;
  try {
    Object.defineProperty(document, "title", {
      configurable: true,
      get: function () { return native.get.call(document); },
      set: function (value) { native.set.call(document, wanted || value); },
    });
  } catch (e) { /* navigateur ancien : le MutationObserver ci-dessous suffit */ }

  function setIcon(size, href, rel) {
    if (!href) return;
    var sel = 'link[data-feba-favicon="' + size + '"]';
    var link = document.head.querySelector(sel);
    if (!link) {
      link = document.createElement("link");
      link.setAttribute("data-feba-favicon", size);
      link.rel = rel;
      link.type = "image/png";
      link.setAttribute("sizes", size + "x" + size);
      document.head.appendChild(link);
    }
    link.href = href;
  }

  function apply(identity) {
    if (!identity || !identity.meeting_title) return;
    wanted = identity.meeting_title;
    native.set.call(document, wanted);
    // L'icône d'origine du client (favicon.ico de plugNmeet) est retirée.
    var icons = document.head.querySelectorAll("link[rel~='icon']:not([data-feba-favicon])");
    for (var i = 0; i < icons.length; i++) icons[i].parentNode.removeChild(icons[i]);
    setIcon(32, identity.favicon_32_url, "icon");
    setIcon(16, identity.favicon_16_url, "icon");
    setIcon(180, identity.apple_touch_icon_url, "apple-touch-icon");
  }

  // Si le client remplace l'élément <title>, le titre voulu est rétabli.
  new MutationObserver(function () {
    if (wanted && native.get.call(document) !== wanted) native.set.call(document, wanted);
  }).observe(document.head, { childList: true, subtree: true, characterData: true });

  // Rechargement de l'onglet : identité déjà vérifiée pour CE jeton.
  try {
    var cached = JSON.parse(sessionStorage.getItem(STORE) || "null");
    if (cached && token && cached.token === token) apply(cached.identity);
  } catch (e) { /* stockage indisponible */ }

  if (!token || !api) return;
  fetch(api.replace(/\/$/, "") + "/api/virtual-rooms/meeting-branding/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ access_token: token }),
    credentials: "omit",
    referrerPolicy: "no-referrer",
  }).then(function (r) { return r.ok ? r.json() : null; })
    .then(function (identity) {
      if (!identity) return;
      apply(identity);
      try { sessionStorage.setItem(STORE, JSON.stringify({ token: token, identity: identity })); }
      catch (e) { /* facultatif */ }
    })
    .catch(function () { /* FEBA injoignable : le client fonctionne normalement */ });
})();
