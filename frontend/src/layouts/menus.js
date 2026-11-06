/**
 * Menus des cinq profils, regroupés par domaine métier (une seule définition).
 *
 * Aucune entrée n'a été retirée par rapport aux anciens menus : seules leur
 * place et leur regroupement changent. `feature` : entrée affichée selon les
 * fonctionnalités de l'académie (le serveur refuse de toute façon l'API).
 * `badge: "messages"` : compteur de conversations non lues.
 */
import {
  AlertTriangle, Award, BarChart3, BellRing, BookOpen, Building2, Calendar, CalendarClock, CircleHelp, ClipboardCheck,
  ClipboardList, CreditCard, DollarSign, FileBarChart, FileText, FolderOpen, Globe, GraduationCap, Home, Image, Inbox,
  Layers, LayoutDashboard, ListTree, Mail, Megaphone, MessageSquare, ReceiptText, Settings, Shield, Stamp, Star,
  TrendingUp, User, UserCheck, UserCog, Users, Users2, Video, Wallet, Wrench, BookMarked, Landmark, Briefcase,
  MessagesSquare, FolderArchive, School,
} from "lucide-react";

const G = (id, label, icon, items) => ({ id, label, icon, items });
const I = (label, icon, to, extra = {}) => ({ label, icon, to, ...extra });

function personnel(r, { superadmin }) {
  return [
    I("Tableau de bord", LayoutDashboard, `${r}/dashboard`),
    G("administration", "Administration", Shield, superadmin ? [
      I("Tous les utilisateurs", Users, `${r}/users`), I("Académies", Building2, `${r}/academies`),
      I("Gestion Admins", Shield, `${r}/admins`), I("Incidents techniques", AlertTriangle, `${r}/incidents`),
    ] : [I("Utilisateurs", UserCog, `${r}/users`)]),
    G("vie-scolaire", "Vie scolaire", GraduationCap, [
      I("Élèves", GraduationCap, `${r}/students`), I("Enseignants", UserCheck, `${r}/teachers`),
      I("Parents", Users2, `${r}/parents`), I("Inscriptions", ClipboardCheck, `${r}/enrollments`),
      I("Admissions en ligne", ClipboardList, `${r}/fha-admissions`, { feature: "online_admissions" }),
      I("Classes", BookOpen, `${r}/classes`), I("Niveaux", Layers, `${r}/levels`),
    ]),
    G("pedagogie", "Pédagogie et apprentissages", BookMarked, [
      I("Notes", ClipboardList, `${r}/grades`), I("Bulletins", FileText, `${r}/bulletins`),
      I("Appréciations", Star, `${r}/appreciations`), I("Devoirs", BookOpen, `${r}/homework`),
      I("Examens et évaluations", ClipboardCheck, `${r}/evaluations`, { feature: "evaluations_en_ligne" }),
      I("Suivi pédagogique", TrendingUp, `${r}/suivi`, { feature: "suivi_pedagogique" }),
      I("Compétences", ListTree, `${r}/suivi/referentiels`, { feature: "suivi_pedagogique" }),
      ...(superadmin ? [I("Modules pédagogiques", ClipboardCheck, `${r}/modules`)] : []),
      I("Centre d'analyse", BarChart3, `${r}/analyses`),
      I("Rapports mensuels", FileBarChart, `${r}/monthly-reports`, { feature: "monthly_reports" }),
    ]),
    G("organisation", "Organisation scolaire", CalendarClock, [
      I("Absences", Calendar, `${r}/attendance`), I("Emploi du temps", Calendar, `${r}/schedule`),
      I("Salles virtuelles", Video, `${r}/virtual`, superadmin ? {} : { feature: "virtual_classrooms" }),
      I("Annonces", Megaphone, `${r}/announcements`),
    ]),
    G("finances", "Finances et paiements", Landmark, [
      I("Paiements", DollarSign, `${r}/payments`), I("Transactions carte", CreditCard, `${r}/card-transactions`),
      I("Tarifs et échéances", ReceiptText, `${r}/tarifs`), I("Situation financière", Wallet, `${r}/situation-financiere`),
      I("Relances de paiement", BellRing, `${r}/payment-reminders`),
    ]),
    G("communication", "Communication", MessagesSquare, [
      I("Messages", MessageSquare, `${r}/messages`, { badge: "messages" }),
      I("Espace d'envoi d'e-mails", Mail, `${r}/emails`), I("Boîte mail contact", Inbox, `${r}/outbox`),
      I("Site vitrine", Globe, `${r}/website`),
    ]),
    G("documents", "Documents et ressources", FolderArchive, [
      I("Documents officiels", Award, `${r}/official-documents`), I("Gabarits des documents", Stamp, `${r}/document-templates`),
      I("Fichiers", FolderOpen, `${r}/user-files`),
    ]),
    G("configuration", "Configuration et assistance", Wrench, [
      I("Paramètres", Settings, `${r}/settings`),
      I(superadmin ? "Logo & Branding" : "Branding & Logo", superadmin ? Image : School, `${r}/branding`),
      I("Mon profil", UserCog, `${r}/profile`), I("Aide", CircleHelp, `${r}/aide`),
    ]),
  ];
}

export const MENU_SUPERADMIN = personnel("/superadmin", { superadmin: true });
export const MENU_ADMIN = personnel("/admin", { superadmin: false });

export const MENU_ENSEIGNANT = [
  I("Tableau de bord", LayoutDashboard, "/teacher/dashboard"),
  G("enseignement", "Enseignement", Briefcase, [
    I("Mes classes", BookOpen, "/teacher/classes"), I("Notes", ClipboardList, "/teacher/grades"),
    I("Devoirs", FileText, "/teacher/homework"),
    I("Examens et évaluations", ClipboardCheck, "/teacher/evaluations", { feature: "evaluations_en_ligne" }),
    I("Suivi pédagogique", TrendingUp, "/teacher/suivi", { feature: "suivi_pedagogique" }),
    I("Compétences", ListTree, "/teacher/suivi/referentiels", { feature: "suivi_pedagogique" }),
    I("Analyses de mes classes", BarChart3, "/teacher/analyses"),
  ]),
  G("organisation", "Organisation scolaire", CalendarClock, [
    I("Absences", Calendar, "/teacher/attendance"), I("Emploi du temps", Calendar, "/teacher/schedule"),
    I("Salles virtuelles", Video, "/teacher/virtual", { feature: "virtual_classrooms" }),
  ]),
  G("communication", "Communication", MessagesSquare, [
    I("Messages", MessageSquare, "/teacher/messages", { badge: "messages" }), I("Annonces", Megaphone, "/teacher/announcements"),
  ]),
  G("compte", "Mon compte", User, [I("Mon profil", User, "/teacher/profile"), I("Aide", CircleHelp, "/teacher/aide")]),
];

export const MENU_PARENT = [
  I("Accueil", Home, "/parent/home"),
  G("scolarite", "Scolarité de mes enfants", GraduationCap, [
    I("Mes enfants", Users, "/parent/children"), I("Notes", ClipboardList, "/parent/grades"), I("Bulletins", BookOpen, "/parent/bulletins"),
    I("Analyse des résultats", BarChart3, "/parent/analyses"),
    I("Suivi pédagogique", TrendingUp, "/parent/suivi", { feature: "suivi_familles" }),
    I("Résultats des épreuves", ClipboardCheck, "/parent/evaluations", { feature: "evaluations_en_ligne" }),
    I("Devoirs", FileText, "/parent/homework"),
  ]),
  G("organisation", "Vie scolaire", CalendarClock, [
    I("Absences", Calendar, "/parent/attendance"), I("Emploi du temps", Calendar, "/parent/schedule"),
    I("Salles virtuelles", Video, "/parent/virtual", { feature: "virtual_classrooms" }),
  ]),
  G("finances", "Finances", Landmark, [I("Paiements", DollarSign, "/parent/payments")]),
  G("communication", "Communication", MessagesSquare, [
    I("Messages", MessageSquare, "/parent/messages", { badge: "messages" }), I("Annonces", Megaphone, "/parent/announcements"),
  ]),
  G("compte", "Mon compte", User, [I("Mon profil", User, "/parent/profile"), I("Aide", CircleHelp, "/parent/aide")]),
];

export const MENU_ELEVE = [
  I("Accueil", Home, "/student/home"),
  G("etudes", "Mes études", GraduationCap, [
    I("Mes notes", ClipboardList, "/student/grades"), I("Bulletins", BookOpen, "/student/bulletins"),
    I("Analyse des résultats", BarChart3, "/student/analyses"),
    I("Mon suivi", TrendingUp, "/student/suivi", { feature: "suivi_familles" }),
    I("Mes épreuves", ClipboardCheck, "/student/evaluations", { feature: "evaluations_en_ligne" }),
    I("Devoirs", FileText, "/student/homework"),
  ]),
  G("organisation", "Vie scolaire", CalendarClock, [
    I("Absences", Calendar, "/student/attendance"), I("Emploi du temps", Calendar, "/student/schedule"),
    I("Salles virtuelles", Video, "/student/virtual", { feature: "virtual_classrooms" }),
  ]),
  G("communication", "Communication", MessagesSquare, [
    I("Messages", MessageSquare, "/student/messages", { badge: "messages" }), I("Annonces", Megaphone, "/student/announcements"),
  ]),
  G("compte", "Mon compte", User, [I("Mon profil", User, "/student/profile"), I("Aide", CircleHelp, "/student/aide")]),
];

/** Toutes les entrées (à plat) : contrôle de non-régression du contenu des menus. */
export const entrees = (menu) => menu.flatMap((x) => (x.items ? x.items : [x]));
