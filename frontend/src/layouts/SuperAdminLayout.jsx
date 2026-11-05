import { NavLink } from "react-router-dom";
import { useState, useEffect } from "react";
import {
  BarChart3, Building2, Star, Stamp, FileBarChart, LayoutDashboard, Users, Shield, GraduationCap, UserCheck, Users2, BookOpen, DollarSign, Megaphone, Settings, LogOut, Menu, X, MessageSquare, Layers, ClipboardList, FileText, Calendar, UserCog, FolderOpen, Image, ClipboardCheck, CircleHelp, ListTree, Video, Globe, AlertTriangle, CreditCard, Award, Mail, BellRing, Inbox, TrendingUp, ReceiptText, Wallet } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import AcademyLogo from "../components/AcademyLogo";
import AcademyName from "../components/AcademyName";
import { useAcademy } from "../context/AcademyContext";
import { isNavItemVisible } from "./navFeatures";
import { clsx } from "clsx";
import { motion, AnimatePresence } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "../store/authStore";
import { t } from "../i18n";
import LanguageSwitcher from "../components/ui/LanguageSwitcher";
import NotificationBell from "../components/NotificationBell";
import EntitySwitcher from "../components/EntitySwitcher";
import AcademyScopedOutlet from "../components/AcademyScopedOutlet";

const nav = [
  { section: "SuperAdmin", items: [
    { label: "Tableau de bord",       icon: LayoutDashboard, to: "/superadmin/dashboard" },
    { label: "Tous les utilisateurs", icon: Users,            to: "/superadmin/users" },
    { label: "Académies",             icon: Building2,        to: "/superadmin/academies" },
    { label: "Gestion Admins",        icon: Shield,           to: "/superadmin/admins" },
    { label: "Messages",              icon: MessageSquare,    to: "/superadmin/messages", badge: true },
    { label: "E-mails groupés", icon: Mail, to: "/superadmin/emails" },
    { label: "Boîte d'envoi", icon: Inbox, to: "/superadmin/outbox" },
    { label: "Incidents techniques",  icon: AlertTriangle,    to: "/superadmin/incidents" },
    { label: "Mon profil",            icon: UserCog,          to: "/superadmin/profile" },
  ]},
  { section: "Gestion École", items: [
    { label: "Élèves",            icon: GraduationCap, to: "/superadmin/students" },
    { label: "Enseignants",       icon: UserCheck,     to: "/superadmin/teachers" },
    { label: "Parents",           icon: Users2,        to: "/superadmin/parents" },
    { label: "Inscriptions",      icon: ClipboardCheck, CircleHelp, to: "/superadmin/enrollments" },
    { label: "Classes",           icon: BookOpen,      to: "/superadmin/classes" },
    { label: "Niveaux",           icon: Layers,        to: "/superadmin/levels" },
    { label: "Notes",             icon: ClipboardList, to: "/superadmin/grades" },
    { label: "Bulletins",         icon: FileText,      to: "/superadmin/bulletins" },
  { label: "Centre d'analyse", icon: BarChart3, to: "/superadmin/analyses" },
    { label: "Appréciations",     icon: Star,          to: "/superadmin/appreciations" },
    { label: "Paiements",         icon: DollarSign,    to: "/superadmin/payments" },
  { label: "Transactions carte", icon: CreditCard, to: "/superadmin/card-transactions" },
  { label: "Tarifs et échéances", icon: ReceiptText, to: "/superadmin/tarifs" },
  { label: "Situation financière", icon: Wallet, to: "/superadmin/situation-financiere" },
  { label: "Relances de paiement", icon: BellRing, to: "/superadmin/payment-reminders" },
  { label: "Documents officiels", icon: Award, to: "/superadmin/official-documents" },
  { label: "Gabarits des documents", icon: Stamp, to: "/superadmin/document-templates" },
    { label: "Absences",          icon: Calendar,      to: "/superadmin/attendance" },
    { label: "Devoirs",           icon: BookOpen,      to: "/superadmin/homework" },
    { label: "Emploi du temps",   icon: Calendar,      to: "/superadmin/schedule" },
    { label: "Salles virtuelles", icon: Video,         to: "/superadmin/virtual" },
    { label: "Annonces",          icon: Megaphone,     to: "/superadmin/announcements" },
    { label: "Paramètres",        icon: Settings,      to: "/superadmin/settings" },
    { label: "Fichiers",           icon: FolderOpen,    to: "/superadmin/user-files" },
    { label: "Admissions en ligne", icon: ClipboardList, to: "/superadmin/fha-admissions", feature: "online_admissions" },
    { label: "Modules pédagogiques", icon: ClipboardCheck, CircleHelp, to: "/superadmin/modules" },
    { label: "Suivi pédagogique", icon: TrendingUp, to: "/superadmin/suivi", feature: "suivi_pedagogique" },
    { label: "Compétences", icon: ListTree, to: "/superadmin/suivi/referentiels", feature: "suivi_pedagogique" },
    { label: "Examens et évaluations", icon: ClipboardCheck, CircleHelp, to: "/superadmin/evaluations", feature: "evaluations_en_ligne" },
    { label: "Aide", icon: CircleHelp, to: "/superadmin/aide" },
    { label: "Rapports mensuels", icon: FileBarChart, to: "/superadmin/monthly-reports", feature: "monthly_reports" },
  { label: "Site vitrine",       icon: Globe,         to: "/superadmin/website" },
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

  const { data: inboxData } = useQuery({
    queryKey: ["inbox", storeUser?.id],
    queryFn: () => import("../api").then(m => m.messagesAPI.inbox()),
    refetchInterval: 30000,
  });
  const unreadCount = (inboxData?.data || []).filter(m => !m.is_read).length;

  const closeSidebarOnMobile = () => { if (isMobile) setOpen(false); };

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

            <nav className="flex-1 p-3 overflow-y-auto space-y-4">
              {nav.map(section => (
                <div key={t(section.section)}>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 px-4 mb-1">
                    {t(section.section)}
                  </p>
                  <div className="space-y-0.5">
                    {section.items.filter((item) => isNavItemVisible(item, academy)).map(item => (
                      <NavLink
                        key={item.to} to={item.to} end={item.to.endsWith("/suivi")}
                        onClick={closeSidebarOnMobile}
                        className={({ isActive }) => (isActive ? "nav-item-actif" : "nav-item")}
                      >
                        <item.icon className="w-4 h-4 shrink-0" />
                        <span className="flex-1 truncate">{t(item.label)}</span>
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
