/**
 * Cloche des notifications internes — UN seul composant pour les cinq profils.
 *
 * Compteur des non lues, panneau des 10 dernières, clic vers l'élément concerné.
 * Ouvrir le panneau marque les notifications lues (comportement existant) ;
 * le FERMER ne change rien à leur statut.
 *
 * Fermeture (défaut corrigé, novembre 2026) : le panneau ne se fermait qu'avec
 * sa croix ou en recliquant sur la cloche. Il n'existait AUCUN écouteur de clic
 * extérieur, et quatre copies du panneau vivaient dans les mises en page.
 * Désormais :
 *  - même règle que le sélecteur d'académie (`useFermetureExterieure`) : clic ou
 *    toucher en dehors du panneau ET de la cloche, en phase de CAPTURE (un
 *    stopPropagation ailleurs ne l'empêche pas), Échap, focus parti ailleurs,
 *    changement de page ;
 *  - un clic à l'intérieur ne ferme pas avant l'action (test `contains`) ;
 *  - Échap rend le focus à la cloche.
 */
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { notificationsAPI } from "../api";
import { usePretPourDonnees } from "../hooks/useNonLusMessagerie";
import { useFermetureExterieure } from "../hooks/useFermetureExterieure";
import { safeInternalPath } from "../utils/safePath";
import { t } from "../i18n";

export default function NotificationBell({ toutVoir, toutVoirLibelle }) {
  const [ouvert, setOuvert] = useState(false);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const pret = usePretPourDonnees();
  const zone = useRef(null);
  const cloche = useRef(null);
  const { data: compte } = useQuery({ queryKey: ["notif-count"], queryFn: notificationsAPI.unreadCount, refetchInterval: 30000, enabled: pret });
  const { data: liste } = useQuery({ queryKey: ["notif-list"], queryFn: notificationsAPI.list, enabled: ouvert, staleTime: 0 });
  const toutLire = useMutation({
    mutationFn: () => notificationsAPI.markAllRead(),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["notif-count"] }); qc.invalidateQueries({ queryKey: ["notif-list"] }); },
  });
  const nonLues = compte?.data?.count || 0;
  const notifications = liste?.data?.results || liste?.data || [];

  // Fermeture commune aux menus déroulants (clic ou toucher extérieur en phase de
  // capture, Échap, focus parti ailleurs, changement de page).
  const fermer = () => setOuvert(false);
  useFermetureExterieure(zone, ouvert, fermer);
  // Échap rend en plus le focus à la cloche (clavier).
  useEffect(() => {
    if (!ouvert) return undefined;
    const touche = (e) => { if (e.key === "Escape") cloche.current?.focus(); };
    document.addEventListener("keydown", touche);
    return () => document.removeEventListener("keydown", touche);
  }, [ouvert]);

  const ouvrir = () => {
    setOuvert(true);
    if (nonLues > 0) toutLire.mutate();
  };
  const aller = (chemin) => { setOuvert(false); const to = safeInternalPath(chemin); if (to) navigate(to); };

  return (
    <div className="relative" ref={zone}>
      <button type="button" ref={cloche} onClick={() => (ouvert ? setOuvert(false) : ouvrir())} aria-expanded={ouvert}
        aria-haspopup="dialog" aria-controls="panneau-notifications"
        aria-label={nonLues ? `${t("Notifications")} (${nonLues})` : t("Notifications")} data-testid="cloche"
        className="p-2 rounded-xl hover:bg-slate-100 text-slate-600 relative">
        <Bell className="w-5 h-5" aria-hidden="true" />
        {nonLues > 0 && (
          <span className="absolute top-1 right-1 w-4 h-4 bg-danger text-white text-[10px] rounded-full flex items-center justify-center font-bold" data-testid="cloche-compte">
            {nonLues > 9 ? "9+" : nonLues}
          </span>
        )}
      </button>
      {ouvert && (
        <div id="panneau-notifications" role="dialog" aria-label={t("Notifications")}
          className="absolute right-0 top-10 w-[min(20rem,calc(100vw-1.5rem))] bg-white rounded-2xl shadow-2xl border border-slate-100 z-50"
          data-testid="cloche-panneau">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
            <p className="font-bold text-slate-800 text-sm">{t("Notifications")}</p>
            <button type="button" onClick={() => setOuvert(false)} aria-label={t("Fermer")} className="text-slate-400 hover:text-slate-600 text-lg leading-none">×</button>
          </div>
          <div className="max-h-72 overflow-y-auto divide-y divide-slate-50">
            {notifications.length === 0 ? (
              <p className="text-center text-slate-400 py-8 text-sm">{t("Aucune notification")}</p>
            ) : notifications.slice(0, 10).map((n) => (
              <button type="button" key={n.id} onClick={() => aller(n.related_url)}
                className={`block w-full text-left px-4 py-3 hover:bg-slate-50 transition-colors ${!n.is_read ? "bg-primary-50/30" : ""}`}>
                <span className="block text-sm font-medium text-slate-800">{n.title}</span>
                <span className="block text-xs text-slate-500 mt-0.5 line-clamp-2">{n.message}</span>
                <span className="block text-xs text-slate-400 mt-1">{n.created_at?.slice(0, 16)?.replace("T", " ")}</span>
              </button>
            ))}
          </div>
          {toutVoir && (
            <div className="p-3 border-t border-slate-100">
              <button type="button" onClick={() => aller(toutVoir)} className="w-full text-center text-xs text-primary font-medium hover:underline">
                {toutVoirLibelle}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
