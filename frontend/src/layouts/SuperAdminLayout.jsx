
import { useNonLusMessagerie } from "../hooks/useNonLusMessagerie";
import { useState, useEffect } from "react";
import { LogOut, Menu, X } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import AcademyLogo from "../components/AcademyLogo";
import AcademyName from "../components/AcademyName";
import { useAcademy } from "../context/AcademyContext";
import { isNavItemVisible } from "./navFeatures";
import { clsx } from "clsx";
import { motion, AnimatePresence } from "framer-motion";
import { useAuthStore } from "../store/authStore";
import { t } from "../i18n";
import MenuLateral from "../components/navigation/MenuLateral";
import { useEchap } from "../hooks/useEchap";
import { MENU_SUPERADMIN } from "./menus";
import LanguageSwitcher from "../components/ui/LanguageSwitcher";
import NotificationBell from "../components/NotificationBell";
import EntitySwitcher from "../components/EntitySwitcher";
import AcademyScopedOutlet from "../components/AcademyScopedOutlet";

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", handler);
    return () => window.removeEventListener("resize", handler);
  }, []);
  return isMobile;
}

export default function SuperAdminLayout() {
  // P4 : remonte tout le sous-arbre à chaque bascule d'académie —
  // aucune donnée de l'académie précédente ne peut rester affichée,
  // et aucun rechargement manuel du navigateur n'est nécessaire.

  // Entrées liées à une fonctionnalité (admissions en ligne, rapports
  // mensuels) : affichées d'après la matrice servie par l'API, jamais
  // d'après le nom d'une académie.
  const academy = useAcademy();

  const isMobile = useIsMobile();
  const [open, setOpen] = useState(!isMobile);
  const { user, logout } = useAuth();
  const { user: storeUser } = useAuthStore();

  useEffect(() => {
    if (isMobile) setOpen(false);
    else setOpen(true);
  }, [isMobile]);

  // Même compteur que les autres profils (avant : ancienne route « inbox », qui
  // ignorait archives et corbeille et n'était jamais rafraîchie par la messagerie).
  const unreadCount = useNonLusMessagerie(storeUser?.id);

  const closeSidebarOnMobile = () => { if (isMobile) setOpen(false); };
  // Téléphone : Échap ferme le menu ouvert.
  useEchap(isMobile && open, () => setOpen(false));

  return (
    <div className="flex h-screen fond-app overflow-hidden">
      <AnimatePresence>
        {isMobile && open && (
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-sidebar/50 z-[16]"
            onClick={() => setOpen(false)}
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {open && (
          <motion.aside
            key="sidebar"
            initial={{ x: -260 }} animate={{ x: 0 }} exit={{ x: -260 }}
            transition={{ duration: 0.2 }}
            className={clsx(
              "w-64 bg-gradient-to-b from-sidebar to-sidebar-2 flex flex-col h-full shrink-0 z-20 shadow-2xl",
              isMobile && "fixed inset-y-0 left-0"
            )}
          >
            <div className="p-5 flex items-center gap-3 border-b border-white/10">
              <div className="w-9 h-9 rounded-xl overflow-hidden bg-white border-2 border-white/40 flex items-center justify-center shrink-0">
                <AcademyLogo />
              </div>
              <div className="flex-1 min-w-0">
                <AcademyName className="text-white font-bold text-sm leading-tight" />
                <p className="text-feba-gold text-xs font-semibold tracking-wide">{t("SUPER ADMIN")}</p>
              </div>
              {isMobile && (
                <button onClick={() => setOpen(false)} className="text-slate-400 hover:text-white ml-auto">
                  <X className="w-5 h-5" />
                </button>
              )}
            </div>

            <MenuLateral menu={MENU_SUPERADMIN} profil="superadmin" visible={(item) => isNavItemVisible(item, academy)} badges={{ messages: unreadCount }} onNavigate={closeSidebarOnMobile} />

            <div className="p-3 border-t border-white/10">
              <div className="flex items-center gap-2 px-4 py-2 mb-1">
                <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-primary to-secondary-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
                  {user?.first_name?.[0]}{user?.last_name?.[0]}
                </div>
                <div className="min-w-0">
                  <p className="text-white text-xs font-semibold truncate">{user?.first_name} {user?.last_name}</p>
                  <p className="text-feba-gold text-[10px]">{t("Super Administrateur")}</p>
                </div>
              </div>
              <button onClick={logout} className="flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-all w-full">
                <LogOut className="w-4 h-4" /><span>{t("Déconnexion")}</span>
              </button>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="barre-haute px-3 sm:px-6 py-3 flex items-center justify-between shrink-0 ">
          <button type="button" onClick={() => setOpen(!open)} aria-label={t("Ouvrir ou fermer le menu")} aria-expanded={open} className="btn-icone">
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-3">
            {/* Indicateur PERMANENT de l'entité active + bascule.
                L'entité affichée vient du serveur : elle reflète toujours
                la portée réelle des données consultées. */}
            <EntitySwitcher />
            <LanguageSwitcher />
            <NotificationBell toutVoir="/superadmin/incidents" toutVoirLibelle={t("Voir les incidents techniques →")} />
            <span className="text-xs font-bold px-3 py-1 rounded-full bg-gradient-to-r from-primary-50 to-primary-100 text-primary">
              Super Admin
            </span>
            <div className="hidden sm:flex items-center gap-2 pl-3 border-l border-slate-100">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-primary to-secondary-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
                {user?.first_name?.[0]}{user?.last_name?.[0]}
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-800 truncate max-w-[120px]">{user?.first_name} {user?.last_name}</p>
                <p className="text-xs text-slate-400">{t("Super Admin")}</p>
              </div>
            </div>
          </div>
        </header>
        <main className="relative flex-1 overflow-y-auto p-3 sm:p-6">
          <AcademyScopedOutlet />
        </main>
      </div>
    </div>
  );
}
