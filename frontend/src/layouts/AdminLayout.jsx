import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useState, useEffect, useRef } from "react";
import {
  LayoutDashboard, Users, GraduationCap, UserCheck, BookOpen,
  ClipboardList, DollarSign, Calendar, FileText, Bell, MessageSquare,
  Megaphone, Settings, LogOut, School, Menu, X, UserCog, Layers, FolderOpen,
  ClipboardCheck, Video } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useBranding } from "../hooks/useBranding";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { notificationsAPI, conversationsAPI } from "../api";
import { motion, AnimatePresence } from "framer-motion";
import { clsx } from "clsx";
import { useAuthStore } from "../store/authStore";
import logoFeba from "../assets/logo_feba.jpeg"; // fallback only

const nav = [
  { label: "Tableau de bord", icon: LayoutDashboard, to: "/admin/dashboard" },
  { label: "Élèves",          icon: GraduationCap,   to: "/admin/students" },
  { label: "Enseignants",     icon: UserCheck,        to: "/admin/teachers" },
  { label: "Parents",         icon: Users,            to: "/admin/parents" },
  { label: "Inscriptions",    icon: ClipboardCheck,   to: "/admin/enrollments" },
  { label: "Classes",         icon: BookOpen,         to: "/admin/classes" },
  { label: "Niveaux",         icon: Layers,           to: "/admin/levels" },
  { label: "Notes",           icon: ClipboardList,    to: "/admin/grades" },
  { label: "Bulletins",       icon: FileText,         to: "/admin/bulletins" },
  { label: "Absences",        icon: Calendar,         to: "/admin/attendance" },
  { label: "Emploi du temps", icon: Calendar,         to: "/admin/schedule" },
  { label: "Salles virtuelles", icon: Video,          to: "/admin/virtual" },
  { label: "Devoirs",         icon: BookOpen,         to: "/admin/homework" },
  { label: "Paiements",       icon: DollarSign,       to: "/admin/payments" },
  { label: "Messages",        icon: MessageSquare,    to: "/admin/messages" },
  { label: "Annonces",        icon: Megaphone,        to: "/admin/announcements" },
  { label: "Utilisateurs",    icon: UserCog,          to: "/admin/users" },
  { label: "Fichiers",         icon: FolderOpen,       to: "/admin/user-files" },
  { label: "Branding & Logo",  icon: School,           to: "/admin/branding" },
  { label: "Paramètres",      icon: Settings,         to: "/admin/settings" },
];

// Responsive: start open on desktop, closed on mobile
function useIsMobile() {
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", handler);
    return () => window.removeEventListener("resize", handler);
  }, []);
  return isMobile;
}

export default function AdminLayout() {
  const isMobile = useIsMobile();
  const [sidebarOpen, setSidebarOpen] = useState(!isMobile);
  const [notifOpen, setNotifOpen] = useState(false);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { user, logout } = useAuth();
  const { logoSrc } = useBranding();

  // Close sidebar on mobile when screen resizes to mobile
  useEffect(() => {
    if (isMobile) setSidebarOpen(false);
    else setSidebarOpen(true);
  }, [isMobile]);

  const { data: notifData, refetch: refetchCount } = useQuery({
    queryKey: ["notif-count"],
    queryFn: notificationsAPI.unreadCount,
    refetchInterval: 30000,
  });
  const { data: notifListData, refetch: refetchList } = useQuery({
    queryKey: ["notif-list"],
    queryFn: notificationsAPI.list,
    enabled: notifOpen,
  });
  const markAllMut = useMutation({
    mutationFn: notificationsAPI.markAllRead,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["notif-count"] }); qc.invalidateQueries({ queryKey: ["notif-list"] }); },
  });

  const { data: msgCountData } = useQuery({ queryKey: ["msg-count-a"], queryFn: conversationsAPI.unreadCount, refetchInterval: 15000 });
  const msgUnread = msgCountData?.data?.count || 0;
  const unread = notifData?.data?.count || 0;
  const notifications = notifListData?.data?.results || notifListData?.data || [];

  const openNotifPanel = () => {
    setNotifOpen(true);
    refetchList();
    if (unread > 0) markAllMut.mutate();
  };

  const closeSidebarOnMobile = () => {
    if (isMobile) setSidebarOpen(false);
  };

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden">
      {/* Mobile backdrop */}
      <AnimatePresence>
        {isMobile && sidebarOpen && (
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 z-10"
            onClick={() => setSidebarOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.aside
            key="sidebar"
            initial={{ x: -260 }} animate={{ x: 0 }} exit={{ x: -260 }}
            transition={{ duration: 0.2 }}
            className={clsx(
              "w-64 bg-[#0F172A] flex flex-col h-full shrink-0 z-20 shadow-2xl",
              isMobile && "fixed inset-y-0 left-0"
            )}>
            <div className="p-5 flex items-center gap-3 border-b border-white/10">
              <div className="w-10 h-10 rounded-full overflow-hidden border-2 border-yellow-400 shrink-0 bg-white">
                <img src={logoSrc} alt="FEBA" className="w-full h-full object-contain" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-white font-bold text-sm leading-tight">FEBA Academy</p>
                <p className="text-yellow-400 text-xs">Administrateur</p>
              </div>
              {isMobile && (
                <button onClick={() => setSidebarOpen(false)} className="text-slate-400 hover:text-white ml-auto">
                  <X className="w-5 h-5" />
                </button>
              )}
            </div>
            <nav className="flex-1 p-3 overflow-y-auto space-y-0.5">
              {nav.map(item => (
                <NavLink key={item.to} to={item.to}
                  onClick={closeSidebarOnMobile}
                  className={({ isActive }) => clsx(
                    "flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm transition-all",
                    isActive
                      ? "text-white bg-primary/70 shadow-lg"
                      : "text-slate-400 hover:text-white hover:bg-white/10"
                  )}>
                  <item.icon className="w-4 h-4 shrink-0" />
                  <span className="truncate">{item.label}</span>
                  {/* Message badge on nav item */}
                  {item.to === "/admin/messages" && msgUnread > 0 && (
                    <span className="ml-auto w-5 h-5 bg-danger text-white text-[10px] rounded-full flex items-center justify-center font-bold shrink-0">
                      {msgUnread > 9 ? "9+" : msgUnread}
                    </span>
                  )}
                </NavLink>
              ))}
            </nav>
            <div className="p-3 border-t border-white/10">
              <div className="flex items-center gap-2 px-4 py-2 mb-1">
                <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center text-white text-xs font-bold shrink-0">
                  {user?.first_name?.[0]}{user?.last_name?.[0]}
                </div>
                <div className="min-w-0">
                  <p className="text-white text-xs font-semibold truncate">{user?.first_name} {user?.last_name}</p>
                  <p className="text-slate-400 text-[10px]">Administrateur</p>
                </div>
              </div>
              <button onClick={logout} className="flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-all w-full">
                <LogOut className="w-4 h-4" /><span>Déconnexion</span>
              </button>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="bg-white border-b border-slate-100 px-3 sm:px-6 py-3 flex items-center justify-between shrink-0 shadow-sm">
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-2 rounded-xl hover:bg-slate-100 text-slate-600">
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-3">
            <div className="relative">
              <button onClick={openNotifPanel} className="p-2 rounded-xl hover:bg-slate-100 text-slate-600 relative">
                <Bell className="w-5 h-5" />
                {unread > 0 && (
                  <span className="absolute top-1 right-1 w-4 h-4 bg-danger text-white text-[10px] rounded-full flex items-center justify-center font-bold">
                    {unread > 9 ? "9+" : unread}
                  </span>
                )}
              </button>
              {notifOpen && (
                <div className="absolute right-0 top-10 w-72 sm:w-80 bg-white rounded-2xl shadow-2xl border border-slate-100 z-50">
                  <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
                    <p className="font-bold text-slate-800 text-sm">Notifications</p>
                    <button onClick={() => setNotifOpen(false)} className="text-slate-400 hover:text-slate-600 text-lg leading-none">×</button>
                  </div>
                  <div className="max-h-72 overflow-y-auto divide-y divide-slate-50">
                    {notifications.length === 0 ? (
                      <p className="text-center text-slate-400 py-8 text-sm">Aucune notification</p>
                    ) : notifications.slice(0, 10).map(n => (
                      <div key={n.id} onClick={() => { setNotifOpen(false); if (n.related_url) navigate(n.related_url); }}
                        className={`px-4 py-3 cursor-pointer hover:bg-slate-50 transition-colors ${!n.is_read ? "bg-primary-50/30" : ""}`}>
                        <p className="text-sm font-medium text-slate-800">{n.title}</p>
                        <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{n.message}</p>
                        <p className="text-xs text-slate-400 mt-1">{n.created_at?.slice(0,16)?.replace("T"," ")}</p>
                      </div>
                    ))}
                  </div>
                  <div className="p-3 border-t border-slate-100">
                    <button onClick={() => { setNotifOpen(false); navigate("/admin/announcements"); }}
                      className="w-full text-center text-xs text-primary font-medium hover:underline">
                      Voir toutes les annonces →
                    </button>
                  </div>
                </div>
              )}
            </div>
            <div className="flex items-center gap-2 pl-3 border-l border-slate-100">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center text-white text-xs font-bold shrink-0">
                {user?.first_name?.[0]}{user?.last_name?.[0]}
              </div>
              <div className="hidden sm:block">
                <p className="text-sm font-semibold text-slate-800 truncate max-w-[120px]">{user?.first_name} {user?.last_name}</p>
                <p className="text-xs text-slate-400">Administrateur</p>
              </div>
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-3 sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
