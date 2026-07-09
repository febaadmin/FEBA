// FIX v42 — Normalisation des URLs média (avatars, photos, reçus…).
//
// Certaines valeurs héritées en base sont des URLs ABSOLUES pointant vers
// l'hôte interne Docker, ex. « http://backend-dev:8000/media/avatars/x.jpg ».
// Le navigateur ne résout pas « backend-dev » → ERR_NAME_NOT_RESOLVED et
// l'avatar ne s'affiche pas.
//
// On ramène toute URL média à un chemin RELATIF (« /media/... ») qui se
// résout sur l'origine du client : proxy Vite en dev, Nginx en prod. Les
// valeurs déjà relatives et les data:/blob: sont laissées intactes.
export function resolveMediaUrl(url) {
  if (!url) return url;
  if (url.startsWith("data:") || url.startsWith("blob:")) return url;
  // Absolu → ne garder que le chemin (et query éventuelle)
  if (/^https?:\/\//i.test(url)) {
    try {
      const u = new URL(url);
      return u.pathname + u.search;
    } catch {
      // Repli : couper au premier /media
      const idx = url.indexOf("/media");
      return idx >= 0 ? url.slice(idx) : url;
    }
  }
  return url; // déjà relatif
}
