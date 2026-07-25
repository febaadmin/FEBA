/**
 * SEO du site vitrine — titres, méta-descriptions, Open Graph, canonical.
 * Sans dépendance externe : manipulation directe du <head> (SPA).
 */
import { useEffect } from "react";

function upsertMeta(attr, key, content) {
  if (!content) return;
  let el = document.head.querySelector(`meta[${attr}="${key}"]`);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  el.setAttribute("content", content);
}

function upsertCanonical(href) {
  let el = document.head.querySelector('link[rel="canonical"]');
  if (!el) {
    el = document.createElement("link");
    el.setAttribute("rel", "canonical");
    document.head.appendChild(el);
  }
  el.setAttribute("href", href);
}

export default function Seo({ title, description, image, type = "website" }) {
  useEffect(() => {
    const fullTitle = title
      ? `${title} — FEBA | Faith & Excellence Bilingual Academy`
      : "FEBA — Faith & Excellence Bilingual Academy | École bilingue à Cotonou";
    document.title = fullTitle;
    const url = window.location.origin + window.location.pathname;
    upsertMeta("name", "description", description);
    upsertMeta("property", "og:title", fullTitle);
    upsertMeta("property", "og:description", description);
    upsertMeta("property", "og:type", type);
    upsertMeta("property", "og:url", url);
    if (image) {
      const abs = image.startsWith("http") ? image : window.location.origin + image;
      upsertMeta("property", "og:image", abs);
      upsertMeta("name", "twitter:card", "summary_large_image");
      upsertMeta("name", "twitter:image", abs);
    }
    upsertCanonical(url);
  }, [title, description, image, type]);
  return null;
}
