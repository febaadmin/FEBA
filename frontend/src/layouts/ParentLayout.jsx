import { NavLink, useNavigate } from "react-router-dom";
import { Home, Users, ClipboardList, Calendar, FileText, MessageSquare, DollarSign, BookOpen, User, LogOut, School, Menu, X, Bell, Megaphone, Video } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useBranding } from "../hooks/useBranding";
import { clsx } from "clsx";
import { useState, useEffect } from "react";
import logoFeba from "../assets/logo_feba.jpeg";
import { motion, AnimatePresence } from "framer-motion";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { notificationsAPI, conversationsAPI } from "../api";
import { t } from "../i18n";
import LanguageSwitcher from "../components/ui/LanguageSwitcher";
import { useEntityContext } from "../hooks/useEntityContext";
import EntitySwitcher from "../components/EntitySwitcher";
import AcademyScopedOutlet from "../components/AcademyScopedOutlet";

const nav = [
  { label: "Accueil",           icon: Home,           to: "/parent/home" },
  { label: "Mes enfants",       icon: Users,          to: "/parent/children" },
  { label: "Notes",             icon: ClipboardList,  to: "/parent/grades" },
  { label: "Absences",          icon: Calendar,       to: "/parent/attendance" },
  { label: "Emploi du temps",   icon: Calendar,       to: "/parent/schedule" },
  // Fonctionnalité conditionnelle : réservée aux entités « académie en
  // ligne » (FEBA FHA). Masquée pour FEBA — et refusée par l\'API.
  { label: "Salles virtuelles",  icon: Video,          to: "/parent/virtual", feature: "virtual_classrooms" },
  { label: "Devoirs",           icon: FileText,       to: "/parent/homework" },
  { label: "Paiements",         icon: DollarSign,     to: "/parent/payments" },
  { label: "Bulletins",         icon: BookOpen,       to: "/parent/bulletins" },
  { label: "Messages",          icon: MessageSquare,  to: "/parent/messages" },
  { label: "Mon profil",        icon: User,           to: "/parent/profile" },
  { label: "Annonces",          icon: Megaphone,      to: "/parent/announcements" },
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

export default function ParentLayout() {
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
  const { logoSrc } = useBranding();
  const qc = useQueryClient();
  const isMobile = useIsMobile();
  const [open, setOpen] = useState(window.innerWidth >= 768);
  const [notifOpen, setNotifOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (isMobile) setOpen(false);
    else setOpen(true);
  }, [isMobile]);

  const { data: notifData } = useQuery({ queryKey: ["notif-count"], queryFn: notificationsAPI.unreadCount, refetchInterval: 30000 });
  const { data: notifListData, refetch: refetchList } = useQuery({ queryKey: ["notif-list"], queryFn: notificationsAPI.list, enabled: notifOpen });
  const markAllMut = useMutation({ mutationFn: notificationsAPI.markAllRead, onSuccess: () => { qc.invalidateQueries({ queryKey: ["notif-count"] }); qc.invalidateQueries({ queryKey: ["notif-list"] }); } });
  const { data: msgCountData } = useQuery({ queryKey: ["msg-count-p"], queryFn: conversationsAPI.unreadCount, refetchInterval: 15000 });
  const msgUnread = msgCountData?.data?.count || 0;
  const unread = notifData?.data?.count || 0;
  const notifications = notifListData?.data?.results || notifListData?.data || [];
  const openNotifPanel = () => { setNotifOpen(true); refetchList(); if (unread > 0) markAllMut.mutate(); };
  const closeSidebarOnMobile = () => { if (isMobile) setOpen(false); };

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden">
      <AnimatePresence>
        {isMobile && open && (
          <motion.div key="backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 z-10" onClick={() => setOpen(false)} />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {open && (
          <motion.aside key="sidebar" initial={{ x: -260 }} animate={{ x: 0 }} exit={{ x: -260 }} transition={{ duration: 0.2 }}
            className={clsx("w-64 bg-[#0F172A] flex flex-col h-full shrink-0 z-20 shadow-2xl", isMobile && "fixed inset-y-0 left-0")}>
            <div className="p-5 flex items-center gap-3 border-b border-white/10">
              <div className="w-9 h-9 rounded-xl overflow-hidden bg-white border-2 border-amber-400 flex items-center justify-center shrink-0">
                <img src={logoSrc} alt={t("FEBA")} className="w-full h-full object-contain" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-white font-bold text-sm">{t("FEBA")}</p>
                <p className="text-slate-400 text-xs">{t("Espace Parent")}</p>
              </div>
              {isMobile && <button onClick={() => setOpen(false)} className="text-slate-400 hover:text-white"><X className="w-5 h-5" /></button>}
            </div>
            <nav className="flex-1 p-3 overflow-y-auto space-y-0.5">
              {visibleNav.map(item => (
                <NavLink key={item.to} to={item.to} onClick={closeSidebarOnMobile}
                  className={({ isActive }) => clsx("flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm transition-all",
                    isActive ? "text-white bg-amber-600/70 shadow-lg" : "text-slate-400 hover:text-white hover:bg-white/10")}>
                  <item.icon className="w-4 h-4 shrink-0" />
                  <span className="truncate">{t(item.label)}</span>
                  {item.to === "/parent/messages" && msgUnread > 0 && (
                    <span className="ml-auto w-5 h-5 bg-danger text-white text-[10px] rounded-full flex items-center justify-center font-bold shrink-0">
                      {msgUnread > 9 ? "9+" : msgUnread}
                    </span>
                  )}
                </NavLink>
              ))}
            </nav>
            <div className="p-3 border-t border-white/10">
              <div className="flex items-center gap-2 px-4 py-2 mb-1">
                <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
                  {user?.first_name?.[0]}{user?.last_name?.[0]}
                </div>
                <div className="min-w-0">
                  <p className="text-white text-xs font-semibold truncate">{user?.first_name} {user?.last_name}</p>
                  <p className="text-slate-400 text-[10px]">{t("Parent")}</p>
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
          <button onClick={() => setOpen(!open)} className="p-2 rounded-xl hover:bg-slate-100 text-slate-600"><Menu className="w-5 h-5" /></button>
          <div className="flex items-center gap-3">
            <LanguageSwitcher />
            <div className="relative">
              <button onClick={openNotifPanel} className="p-2 rounded-xl hover:bg-slate-100 text-slate-600 relative">
                <Bell className="w-5 h-5" />
                {unread > 0 && <span className="absolute top-1 right-1 w-4 h-4 bg-danger text-white text-[10px] rounded-full flex items-center justify-center font-bold">{unread > 9 ? "9+" : unread}</span>}
              </button>
              {notifOpen && (
                <div className="absolute right-0 top-10 w-72 sm:w-80 bg-white rounded-2xl shadow-2xl border border-slate-100 z-50">
                  <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
                    <p className="font-bold text-slate-800 text-sm">{t("Notifications")}</p>
                    <button onClick={() => setNotifOpen(false)} className="text-slate-400 hover:text-slate-600 text-lg">×</button>
                  </div>
                  <div className="max-h-72 overflow-y-auto divide-y divide-slate-50">
                    {notifications.length === 0 ? <p className="text-center text-slate-400 py-8 text-sm">{t("Aucune notification")}</p>
                      : notifications.slice(0, 10).map(n => (
                        <div key={n.id} onClick={() => { setNotifOpen(false); if (n.related_url) navigate(n.related_url); }}
                          className={`px-4 py-3 cursor-pointer hover:bg-slate-50 ${!n.is_read ? "bg-primary-50/30" : ""}`}>
                          <p className="text-sm font-medium">{n.title}</p>
                          <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{n.message}</p>
                          <p className="text-xs text-slate-400 mt-1">{n.created_at?.slice(0,16)?.replace("T"," ")}</p>
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </div>
            <div className="flex items-center gap-2 pl-3 border-l border-slate-100">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
                {user?.first_name?.[0]}{user?.last_name?.[0]}
              </div>
              <div className="hidden sm:block">
                <p className="text-sm font-semibold text-slate-800 truncate max-w-[120px]">{user?.first_name} {user?.last_name}</p>
                <p className="text-xs text-slate-400">{t("Parent")}</p>
              </div>
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-3 sm:p-6"><AcademyScopedOutlet /></main>
      </div>
    </div>
  );
}
