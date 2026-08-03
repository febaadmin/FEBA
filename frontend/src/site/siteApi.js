/**
 * API du site vitrine PUBLIC.
 *
 * Instance axios SÉPARÉE de src/api/index.js : le site public ne doit ni
 * envoyer de jeton d'authentification, ni déclencher les intercepteurs de
 * rafraîchissement/déconnexion de l'ERP (un visiteur anonyme ne doit jamais
 * être redirigé vers /login par un 401 de fond).
 */
import axios from "axios";

const publicApi = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
  timeout: 15000,
});

export const siteAPI = {
  settings: () => publicApi.get("/website/settings/"),
  heroSlides: () => publicApi.get("/website/hero-slides/"),
  news: (params) => publicApi.get("/website/news/", { params }),
  newsDetail: (slug) => publicApi.get(`/website/news/${slug}/`),
  gallery: () => publicApi.get("/website/gallery/"),
  // Formulaires FEBA (entité FEBA, imposée côté serveur).
  sendContact: (d) => publicApi.post("/website/contact/", d),
  sendPreRegistration: (d) => publicApi.post("/website/preregistrations/", d),

  // Formulaires FEBA French Heritage Academy — ROUTES DISTINCTES.
  // L'entité FEBA_FHA est déduite de la route par le backend : aucun
  // identifiant d'entité n'est transmis depuis le navigateur.
  fhaProgram: () => publicApi.get("/website/fha/program/"),
  sendFhaContact: (d) => publicApi.post("/website/fha/contact/", d),
  // Réservation d'un test de placement : parcours DISTINCT de l'inscription.
  sendFhaPlacementTest: (d) => publicApi.post("/website/fha/placement-test/", d),
  sendFhaEnrollment: (d) =>
    publicApi.post("/website/fha/enroll/", d, {
      // La fiche accepte une photo facultative : on laisse axios choisir
      // le Content-Type lorsqu'il s'agit d'un FormData.
      headers: d instanceof FormData ? { "Content-Type": "multipart/form-data" } : undefined,
    }),
};

export default publicApi;
