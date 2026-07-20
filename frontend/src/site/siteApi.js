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
  sendContact: (d) => publicApi.post("/website/contact/", d),
  sendPreRegistration: (d) => publicApi.post("/website/preregistrations/", d),
};

export default publicApi;
