import { NavLink } from "react-router-dom";
import { useNonLusMessagerie } from "../hooks/useNonLusMessagerie";
import NotificationBell from "../components/NotificationBell";
import { BarChart3, LayoutDashboard, BookOpen, ClipboardList, Calendar, FileText, MessageSquare, User, LogOut, School, Menu, X, Megaphone, Video, TrendingUp, ClipboardCheck, CircleHelp, ListTree } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import AcademyLogo from "../components/AcademyLogo";
import AcademyName from "../components/AcademyName";
import { clsx } from "clsx";
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { t } from "../i18n";
import LanguageSwitcher from "../components/ui/LanguageSwitcher";
import { useEntityContext } from "../hooks/useEntityContext";
import EntitySwitcher from "../components/EntitySwitcher";
import AcademyScopedOutlet from "../components/AcademyScopedOutlet";

const nav = [
  { label: "Tableau de bord", icon: LayoutDashboard, to: "/teacher/dashboard" },
  { label: "Mes classes",      icon: BookOpen,        to: "/teacher/classes" },
  { label: "Notes",            icon: ClipboardList,   to: "/teacher/grades" },
  { label: "Analyses de mes classes", icon: BarChart3, to: "/teacher/analyses" },
  { label: "Suivi pédagogique", icon: TrendingUp,     to: "/teacher/suivi", feature: "suivi_pedagogique" },
  { label: "Compétences", icon: ListTree, to: "/teacher/suivi/referentiels", feature: "suivi_pedagogique" },
  { label: "Examens et évaluations", icon: ClipboardCheck, to: "/teacher/evaluations", feature: "evaluations_en_ligne" },
  { label: "Aide", icon: CircleHelp, to: "/teacher/aide" },
  { label: "Absences",         icon: Calendar,        to: "/teacher/attendance" },
  { label: "Devoirs",          icon: FileText,        to: "/teacher/homework" },
  { label: "Emploi du temps",  icon: Calendar,        to: "/teacher/schedule" },
  // Fonctionnalité conditionnelle : réservée aux entités « académie en
  // ligne » (FEBA FHA). Masquée pour FEBA — et refusée par l\'API.
  { label: "Salles virtuelles", icon: Video,          to: "/teacher/virtual", feature: "virtual_classrooms" },
  { label: "Messages",         icon: MessageSquare,   to: "/teacher/messages" },
  { label: "Annonces",         icon: Megaphone,       to: "/teacher/announcements" },
  { label: "Mon profil",       icon: User,            to: "/teacher/profile" },
];

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", handler);
    return () => window.removeEventListener("resize", handler);
  }, []);
  return isMobile;
}

export default function TeacherLayout() {
  // P4 : remonte tout le sous-arbre à chaque bascule d'académie —
  // aucune donnée de l'académie précédente ne peut rester affichée,
  // et aucun rechargement manuel du navigateur n'est nécessaire.

  // Le menu ne montre que les fonctionnalités auxquelles l'entité de
  // l'utilisateur a droit. Ce filtrage est un CONFORT D'AFFICHAGE : la
  // protection réelle est côté serveur (permission HasEntityFeature),
  // qui refuse l'endpoint même si l'URL est saisie à la main.
  const { hasFeature } = useEntityContext();
  const visibleNav = nav.filter((item) => !item.feature || hasFeature(item.feature));

  const { user, logout } = useAuth();
  const isMobile = useIsMobile();
  const [open, setOpen] = useState(!window || window.innerWidth >= 768);

  useEffect(() => {
    if (isMobile) setOpen(false);
    else setOpen(true);
  }, [isMobile]);

  const msgUnread = useNonLusMessagerie(user?.id);

  const closeSidebarOnMobile = () => { if (isMobile) setOpen(false); };

  return (
    <div className="flex h-screen fond-app overflow-hidden">
      {/* Mobile backdrop */}
      <AnimatePresence>
        {isMobile && open && (
          <motion.div key="backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-sidebar/50 z-[16]" onClick={() => setOpen(false)} />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <AnimatePresence>
        {open && (
          <motion.aside key="sidebar" initial={{ x: -260 }} animate={{ x: 0 }} exit={{ x: -260 }} transition={{ duration: 0.2 }}
            className={clsx("w-64 bg-gradient-to-b from-sidebar to-sidebar-2 flex flex-col h-full shrink-0 z-20 shadow-2xl", isMobile && "fixed inset-y-0 left-0")}>
            <div className="p-5 flex items-center gap-3 border-b border-white/10">
              <div className="w-9 h-9 rounded-xl overflow-hidden bg-white border-2 border-emerald-400 flex items-center justify-center shrink-0">
                <AcademyLogo />
              </div>
              <div className="flex-1 min-w-0">
                <AcademyName className="text-white font-bold text-sm" />
                <p className="text-slate-400 text-xs">{t("Espace Enseignant")}</p>
              </div>
              {isMobile && (
                <button onClick={() => setOpen(false)} className="text-slate-400 hover:text-white">
                  <X className="w-5 h-5" />
                </button>
              )}
            </div>
            <nav className="flex-1 p-3 overflow-y-auto space-y-0.5">
              {visibleNav.map(item => (
                <NavLink key={item.to} to={item.to} end={item.to.endsWith("/suivi")} onClick={closeSidebarOnMobile}
                  className={({ isActive }) => (isActive ? "nav-item-actif" : "nav-item")}>
                  <item.icon className="w-4 h-4 shrink-0" />
                  <span className="truncate">{t(item.label)}</span>
                  {/* FIX: message unread badge on nav item */}
                  {item.to === "/teacher/messages" && msgUnread > 0 && (
                    <span data-testid="badge-messages-menu" aria-label={t("{n} conversation(s) non lue(s)", { n: msgUnread })} className="ml-auto w-5 h-5 bg-danger text-white text-[10px] rounded-full flex items-center justify-center font-bold shrink-0">
                      {msgUnread > 9 ? "9+" : msgUnread}
                    </span>
                  )}
                </NavLink>
              ))}
            </nav>
            <div className="p-3 border-t border-white/10">
              <div className="flex items-center gap-2 px-4 py-2 mb-1">
                <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
                  {user?.first_name?.[0]}{user?.last_name?.[0]}
                </div>
                <div className="min-w-0">
                  <p className="text-white text-xs font-semibold truncate">{user?.first_name} {user?.last_name}</p>
                  <p className="text-slate-400 text-[10px]">{t("Enseignant")}</p>
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
        <header className="bg-white border-b border-slate-100 px-3 sm:px-6 py-3 flex items-center justify-between shrink-0">
          <button type="button" onClick={() => setOpen(!open)} aria-label={t("Ouvrir ou fermer le menu")} aria-expanded={open} className="btn-icone"><Menu className="w-5 h-5" /></button>
          <div className="flex items-center gap-3">
            <LanguageSwitcher />
            <NotificationBell />
            <div className="flex items-center gap-2 pl-3 border-l border-slate-100">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
                {user?.first_name?.[0]}{user?.last_name?.[0]}
              </div>
              <div className="hidden sm:block">
                <p className="text-sm font-semibold text-slate-800 truncate max-w-[120px]">{user?.first_name} {user?.last_name}</p>
                <p className="text-xs text-slate-400">{t("Enseignant")}</p>
              </div>
            </div>
          </div>
        </header>
        <main className="relative flex-1 overflow-y-auto p-3 sm:p-6"><AcademyScopedOutlet /></main>
      </div>
    </div>
  );
}
