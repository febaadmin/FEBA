import { Outlet, NavLink } from "react-router-dom";
import { useState, useEffect } from "react";
import {
  LayoutDashboard, Users, Shield, GraduationCap, UserCheck,
  Users2, BookOpen, DollarSign, Megaphone, Settings, LogOut,
  Menu, X, MessageSquare, Layers, ClipboardList, FileText,
  Calendar, UserCog, FolderOpen, Image, ClipboardCheck, Video } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useBranding } from "../hooks/useBranding";
import { clsx } from "clsx";
import { motion, AnimatePresence } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import logoFeba from "../assets/logo_feba.jpeg";
import { useAuthStore } from "../store/authStore";

const nav = [
  { section: "SuperAdmin", items: [
    { label: "Tableau de bord",       icon: LayoutDashboard, to: "/superadmin/dashboard" },
    { label: "Tous les utilisateurs", icon: Users,            to: "/superadmin/users" },
    { label: "Gestion Admins",        icon: Shield,           to: "/superadmin/admins" },
    { label: "Messages",              icon: MessageSquare,    to: "/superadmin/messages", badge: true },
  ]},
  { section: "Gestion École", items: [
    { label: "Élèves",            icon: GraduationCap, to: "/superadmin/students" },
    { label: "Enseignants",       icon: UserCheck,     to: "/superadmin/teachers" },
    { label: "Parents",           icon: Users2,        to: "/superadmin/parents" },
    { label: "Inscriptions",      icon: ClipboardCheck, to: "/superadmin/enrollments" },
    { label: "Classes",           icon: BookOpen,      to: "/superadmin/classes" },
    { label: "Niveaux",           icon: Layers,        to: "/superadmin/levels" },
    { label: "Notes",             icon: ClipboardList, to: "/superadmin/grades" },
    { label: "Bulletins",         icon: FileText,      to: "/superadmin/bulletins" },
    { label: "Paiements",         icon: DollarSign,    to: "/superadmin/payments" },
    { label: "Absences",          icon: Calendar,      to: "/superadmin/attendance" },
    { label: "Devoirs",           icon: BookOpen,      to: "/superadmin/homework" },
    { label: "Emploi du temps",   icon: Calendar,      to: "/superadmin/schedule" },
    { label: "Salles virtuelles", icon: Video,         to: "/superadmin/virtual" },
    { label: "Annonces",          icon: Megaphone,     to: "/superadmin/announcements" },
    { label: "Paramètres",        icon: Settings,      to: "/superadmin/settings" },
    { label: "Fichiers",           icon: FolderOpen,    to: "/superadmin/user-files" },
    { label: "Logo & Branding",    icon: Image,         to: "/superadmin/branding" },
  ]},
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

export default function SuperAdminLayout() {
  const isMobile = useIsMobile();
  const [open, setOpen] = useState(!isMobile);
  const { user, logout } = useAuth();
  const { user: storeUser } = useAuthStore();
  const { logoSrc } = useBranding();

  useEffect(() => {
    if (isMobile) setOpen(false);
    else setOpen(true);
  }, [isMobile]);

  const { data: inboxData } = useQuery({
    queryKey: ["inbox", storeUser?.id],
    queryFn: () => import("../api").then(m => m.messagesAPI.inbox()),
    refetchInterval: 30000,
  });
  const unreadCount = (inboxData?.data || []).filter(m => !m.is_read).length;

  const closeSidebarOnMobile = () => { if (isMobile) setOpen(false); };

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden">
      <AnimatePresence>
        {isMobile && open && (
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 z-10"
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
              "w-64 bg-[#0F172A] flex flex-col h-full shrink-0 z-20 shadow-2xl",
              isMobile && "fixed inset-y-0 left-0"
            )}
          >
            <div className="p-5 flex items-center gap-3 border-b border-white/10">
              <div className="w-9 h-9 rounded-xl overflow-hidden bg-white border-2 border-purple-400 flex items-center justify-center shrink-0">
                <img src={logoSrc} alt="FEBA" className="w-full h-full object-contain" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-white font-bold text-sm leading-tight">FEBA</p>
                <p className="text-purple-400 text-xs font-semibold tracking-wide">SUPER ADMIN</p>
              </div>
              {isMobile && (
                <button onClick={() => setOpen(false)} className="text-slate-400 hover:text-white ml-auto">
                  <X className="w-5 h-5" />
                </button>
              )}
            </div>

            <nav className="flex-1 p-3 overflow-y-auto space-y-4">
              {nav.map(section => (
                <div key={section.section}>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 px-4 mb-1">
                    {section.section}
                  </p>
                  <div className="space-y-0.5">
                    {section.items.map(item => (
                      <NavLink
                        key={item.to} to={item.to}
                        onClick={closeSidebarOnMobile}
                        className={({ isActive }) =>
                          clsx(
                            "flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm transition-all cursor-pointer",
                            isActive
                              ? "text-white bg-gradient-to-r from-purple-600/80 to-pink-600/60 shadow-lg"
                              : "text-slate-400 hover:text-white hover:bg-white/10"
                          )
                        }
                      >
                        <item.icon className="w-4 h-4 shrink-0" />
                        <span className="flex-1 truncate">{item.label}</span>
                        {item.badge && unreadCount > 0 && (
                          <span className="bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center shrink-0">
                            {unreadCount}
                          </span>
                        )}
                      </NavLink>
                    ))}
                  </div>
                </div>
              ))}
            </nav>

            <div className="p-3 border-t border-white/10">
              <div className="flex items-center gap-2 px-4 py-2 mb-1">
                <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-purple-600 to-pink-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
                  {user?.first_name?.[0]}{user?.last_name?.[0]}
                </div>
                <div className="min-w-0">
                  <p className="text-white text-xs font-semibold truncate">{user?.first_name} {user?.last_name}</p>
                  <p className="text-purple-400 text-[10px]">Super Administrateur</p>
                </div>
              </div>
              <button onClick={logout} className="flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-all w-full">
                <LogOut className="w-4 h-4" /><span>Déconnexion</span>
              </button>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="bg-white border-b border-slate-100 px-3 sm:px-6 py-3 flex items-center justify-between shrink-0 shadow-sm">
          <button onClick={() => setOpen(!open)} className="p-2 rounded-xl hover:bg-slate-100 text-slate-600">
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-3">
            <span className="text-xs font-bold px-3 py-1 rounded-full bg-gradient-to-r from-purple-100 to-pink-100 text-purple-700">
              🛡️ Super Admin
            </span>
            <div className="hidden sm:flex items-center gap-2 pl-3 border-l border-slate-100">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-purple-600 to-pink-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
                {user?.first_name?.[0]}{user?.last_name?.[0]}
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-800 truncate max-w-[120px]">{user?.first_name} {user?.last_name}</p>
                <p className="text-xs text-slate-400">Super Admin</p>
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
