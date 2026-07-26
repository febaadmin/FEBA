import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuthStore } from "../store/authStore";

// ── Site vitrine public (P4 v4) — chargé en lazy pour ne pas alourdir le
// bundle de l'ERP (code splitting : le chunk "site" n'est téléchargé que
// pour les visiteurs du site public, et réciproquement).
const SiteLayout = lazy(() => import("../site/SiteLayout"));
const SiteHome = lazy(() => import("../site/pages/HomePage"));
const SiteAbout = lazy(() => import("../site/pages/AboutPage"));
const SiteCampus = lazy(() => import("../site/pages/CampusPage"));
const SiteAcademics = lazy(() => import("../site/pages/AcademicsPage"));
const SiteAdmissions = lazy(() => import("../site/pages/AdmissionsPage"));
const SiteSchoolLife = lazy(() => import("../site/pages/SchoolLifePage"));
const SiteOnline = lazy(() => import("../site/pages/OnlinePage"));
const SiteNews = lazy(() => import("../site/pages/NewsPage"));
const SiteNewsDetail = lazy(() => import("../site/pages/NewsDetailPage"));
const SiteGallery = lazy(() => import("../site/pages/GalleryPage"));
const SiteContact = lazy(() => import("../site/pages/ContactPage"));
const SiteLegal = lazy(() => import("../site/pages/LegalPages").then(m => ({ default: m.LegalPage })));
const SitePrivacy = lazy(() => import("../site/pages/LegalPages").then(m => ({ default: m.PrivacyPage })));
const SiteNotFound = lazy(() => import("../site/pages/SiteNotFound"));

function SiteFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#F7F2E8]">
      <div className="w-8 h-8 border-2 border-[#071D49] border-t-transparent rounded-full animate-spin"
        role="status" aria-label="Chargement" />
    </div>
  );
}

// Layouts
const SuperAdminLayout = lazy(() => import("../layouts/SuperAdminLayout"));
const AdminLayout = lazy(() => import("../layouts/AdminLayout"));
const TeacherLayout = lazy(() => import("../layouts/TeacherLayout"));
const ParentLayout = lazy(() => import("../layouts/ParentLayout"));
const StudentLayout = lazy(() => import("../layouts/StudentLayout"));

// Auth
const LoginPage = lazy(() => import("../pages/LoginPage"));

// SuperAdmin pages
const SuperAdminDashboard = lazy(() => import("../pages/superadmin/Dashboard"));
const SuperAdminUsers = lazy(() => import("../pages/superadmin/Users"));
const SuperAdminAdmins = lazy(() => import("../pages/superadmin/Admins"));
const SuperAdminProfile = lazy(() => import("../pages/superadmin/Profile"));
const SuperAdminIncidents = lazy(() => import("../pages/superadmin/Incidents"));

// Admin pages
const AdminDashboard = lazy(() => import("../pages/admin/Dashboard"));
const AdminStudents = lazy(() => import("../pages/admin/Students"));
const AdminTeachers = lazy(() => import("../pages/admin/Teachers"));
const AdminParents = lazy(() => import("../pages/admin/Parents"));
const AdminClasses = lazy(() => import("../pages/admin/Classes"));
const AdminGrades = lazy(() => import("../pages/admin/Grades"));
const AdminPayments = lazy(() => import("../pages/admin/Payments"));
const AdminAttendance = lazy(() => import("../pages/admin/Attendance"));
const AdminHomework = lazy(() => import("../pages/admin/Homework"));
const AdminAnnouncements = lazy(() => import("../pages/admin/Announcements"));
const AdminMessages = lazy(() => import("../pages/admin/Messages"));
const AdminBulletins = lazy(() => import("../pages/admin/Bulletins"));
const AdminSchedule = lazy(() => import("../pages/admin/Schedule"));
const AdminSettings = lazy(() => import("../pages/admin/Settings"));
const AdminUserFiles = lazy(() => import("../pages/admin/UserFiles"));
const AdminUsers = lazy(() => import("../pages/admin/Users"));
const AdminLevels = lazy(() => import("../pages/admin/Levels"));
const AdminBranding = lazy(() => import("../pages/admin/Branding"));
const AdminEnrollments = lazy(() => import("../pages/admin/Enrollments"));
const AdminProfile = lazy(() => import("../pages/admin/Profile"));
const AdminWebsite = lazy(() => import("../pages/admin/Website"));

// Teacher pages
const TeacherDashboard = lazy(() => import("../pages/teacher/Dashboard"));
const TeacherClasses = lazy(() => import("../pages/teacher/Classes"));
const TeacherGrades = lazy(() => import("../pages/teacher/Grades"));
const TeacherAttendance = lazy(() => import("../pages/teacher/Attendance"));
const TeacherHomework = lazy(() => import("../pages/teacher/Homework"));
const TeacherSchedule = lazy(() => import("../pages/teacher/Schedule"));
const TeacherMessages = lazy(() => import("../pages/teacher/Messages"));
const TeacherProfile = lazy(() => import("../pages/teacher/Profile"));

// Parent pages
const ParentHome = lazy(() => import("../pages/parent/Home"));
const ParentChildren = lazy(() => import("../pages/parent/Children"));
const ParentGrades = lazy(() => import("../pages/parent/Grades"));
const ParentAttendance = lazy(() => import("../pages/parent/Attendance"));
const ParentHomework = lazy(() => import("../pages/parent/Homework"));
const ParentPayments = lazy(() => import("../pages/parent/Payments"));
const ParentBulletins = lazy(() => import("../pages/parent/Bulletins"));
const ParentMessages = lazy(() => import("../pages/parent/Messages"));
const ParentSchedule = lazy(() => import("../pages/parent/Schedule"));
const ParentProfile = lazy(() => import("../pages/parent/Profile"));

// Student pages
const StudentHome = lazy(() => import("../pages/student/Home"));
const StudentGrades = lazy(() => import("../pages/student/Grades"));
const StudentAttendance = lazy(() => import("../pages/student/Attendance"));
const StudentHomework = lazy(() => import("../pages/student/Homework"));
const StudentSchedule = lazy(() => import("../pages/student/Schedule"));
const StudentBulletins = lazy(() => import("../pages/student/Bulletins"));
const StudentMessages = lazy(() => import("../pages/student/Messages"));
const StudentProfile = lazy(() => import("../pages/student/Profile"));

// Shared pages
const SharedAnnouncements = lazy(() => import("../pages/shared/Announcements"));
const VirtualRooms = lazy(() => import("../pages/shared/VirtualRooms"));
const ForcePasswordChange = lazy(() => import("../pages/shared/ForcePasswordChange"));

// ── Guard: vérifie l'authentification et le rôle ──────────────────────────
function ProtectedRoute({ children, allowedRoles }) {
  const { user, accessToken, _hasHydrated } = useAuthStore();

  // FIX v25: Wait until Zustand has rehydrated from localStorage.
  // Without this, the first render always sees user=null → redirect to /login
  // even when the user IS authenticated.
  if (!_hasHydrated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="flex flex-col items-center gap-3 text-slate-400">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">Chargement…</span>
        </div>
      </div>
    );
  }

  if (!accessToken) return <Navigate to="/login" replace />;

  // P2 : mot de passe réinitialisé par un administrateur — l'utilisateur ne
  // peut pas naviguer dans son espace tant qu'il n'a pas choisi son propre
  // mot de passe (le backend lève le drapeau après change-password).
  if (user?.must_change_password)
    return <Navigate to="/change-password-required" replace />;

  // FIX (notifications / redirections) : un related_url mal formé (rôle
  // erroné, ressource d'un autre espace) amenait ici. Renvoyer un
  // utilisateur AUTHENTIFIÉ vers /login est trompeur : il n'est PAS
  // déconnecté (son token reste valide), mais l'écran de connexion lui
  // laisse croire le contraire. On le renvoie plutôt vers SON propre
  // tableau de bord, qui reste accessible en un clic.
  if (allowedRoles && !allowedRoles.includes(user?.role))
    return <RoleRedirect />;
  return children;
}

// ── Redirige vers le tableau de bord selon le rôle ────────────────────────
function RoleRedirect() {
  const { user, accessToken, _hasHydrated } = useAuthStore();
  if (!_hasHydrated) return null;
  if (!accessToken) return <Navigate to="/login" replace />;
  const role = user?.role;
  if (role === "superadmin") return <Navigate to="/superadmin/dashboard" replace />;
  if (role === "admin")      return <Navigate to="/admin/dashboard" replace />;
  if (role === "teacher")    return <Navigate to="/teacher/dashboard" replace />;
  if (role === "parent")     return <Navigate to="/parent/home" replace />;
  return <Navigate to="/student/home" replace />;
}

// ── P2 : écran de changement de mot de passe obligatoire ──────────────────
// Accessible uniquement authentifié ; si le drapeau n'est pas (ou plus)
// levé, retour au tableau de bord du rôle.
function ForcePasswordChangeRoute() {
  const { user, accessToken, _hasHydrated } = useAuthStore();
  if (!_hasHydrated) return null;
  if (!accessToken) return <Navigate to="/login" replace />;
  if (!user?.must_change_password) return <RoleRedirect />;
  return <ForcePasswordChange />;
}

export default function AppRouter() {
  return (
    <Suspense fallback={<SiteFallback />}>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/change-password-required" element={<ForcePasswordChangeRoute />} />

      {/* ── Site vitrine public (P4) : « / » est désormais le site public.
          La connexion à l'ERP se fait via le bouton « Connexion » du menu.
          Un utilisateur déjà authentifié conserve l'accès direct à son
          espace (routes /superadmin, /admin, /teacher, /parent, /student). */}
      <Route element={<SiteLayout />}>
        <Route path="/" element={<SiteHome />} />
        <Route path="/a-propos" element={<SiteAbout />} />
        <Route path="/campus" element={<SiteCampus />} />
        <Route path="/academique" element={<SiteAcademics />} />
        <Route path="/admissions" element={<SiteAdmissions />} />
        <Route path="/vie-scolaire" element={<SiteSchoolLife />} />
        <Route path="/feba-online" element={<SiteOnline />} />
        <Route path="/actualites" element={<SiteNews />} />
        <Route path="/actualites/:slug" element={<SiteNewsDetail />} />
        <Route path="/galerie" element={<SiteGallery />} />
        <Route path="/contact" element={<SiteContact />} />
        <Route path="/mentions-legales" element={<SiteLegal />} />
        <Route path="/confidentialite" element={<SitePrivacy />} />
      </Route>

      {/* ── SuperAdmin ── */}
      <Route path="/superadmin" element={
        <ProtectedRoute allowedRoles={["superadmin"]}>
          <SuperAdminLayout />
        </ProtectedRoute>
      }>
        <Route path="dashboard"     element={<SuperAdminDashboard />} />
        <Route path="users"         element={<SuperAdminUsers />} />
        <Route path="admins"        element={<SuperAdminAdmins />} />
        <Route path="messages"      element={<AdminMessages />} />
        <Route path="students"      element={<AdminStudents />} />
        <Route path="teachers"      element={<AdminTeachers />} />
        <Route path="parents"       element={<AdminParents />} />
        <Route path="classes"       element={<AdminClasses />} />
        <Route path="levels"        element={<AdminLevels />} />
        <Route path="grades"        element={<AdminGrades />} />
        <Route path="bulletins"     element={<AdminBulletins />} />
        <Route path="payments"      element={<AdminPayments />} />
        <Route path="attendance"    element={<AdminAttendance />} />
        <Route path="homework"      element={<AdminHomework />} />
        <Route path="schedule"      element={<AdminSchedule />} />
        <Route path="announcements" element={<AdminAnnouncements />} />
        <Route path="settings"      element={<AdminSettings />} />
        <Route path="user-files"    element={<AdminUserFiles />} />
        <Route path="branding"      element={<AdminBranding />} />
        <Route path="enrollments"   element={<AdminEnrollments />} />
        <Route path="virtual"       element={<VirtualRooms />} />
        <Route path="website"       element={<AdminWebsite />} />
        <Route path="incidents"     element={<SuperAdminIncidents />} />
        <Route path="incidents/:id" element={<SuperAdminIncidents />} />
        <Route path="profile"       element={<SuperAdminProfile />} />
      </Route>

      {/* ── Admin ── */}
      <Route path="/admin" element={
        <ProtectedRoute allowedRoles={["admin"]}>
          <AdminLayout />
        </ProtectedRoute>
      }>
        <Route path="dashboard"     element={<AdminDashboard />} />
        <Route path="students"      element={<AdminStudents />} />
        <Route path="teachers"      element={<AdminTeachers />} />
        <Route path="parents"       element={<AdminParents />} />
        <Route path="classes"       element={<AdminClasses />} />
        <Route path="levels"        element={<AdminLevels />} />
        <Route path="grades"        element={<AdminGrades />} />
        <Route path="payments"      element={<AdminPayments />} />
        <Route path="attendance"    element={<AdminAttendance />} />
        <Route path="homework"      element={<AdminHomework />} />
        <Route path="announcements" element={<AdminAnnouncements />} />
        <Route path="messages"      element={<AdminMessages />} />
        <Route path="bulletins"     element={<AdminBulletins />} />
        <Route path="schedule"      element={<AdminSchedule />} />
        <Route path="settings"      element={<AdminSettings />} />
        <Route path="users"         element={<AdminUsers />} />
        <Route path="user-files"    element={<AdminUserFiles />} />
        <Route path="branding"      element={<AdminBranding />} />
        <Route path="enrollments"   element={<AdminEnrollments />} />
        <Route path="virtual"       element={<VirtualRooms />} />
        <Route path="website"       element={<AdminWebsite />} />
        <Route path="profile"       element={<AdminProfile />} />
      </Route>
      <Route path="/teacher" element={
        <ProtectedRoute allowedRoles={["teacher"]}>
          <TeacherLayout />
        </ProtectedRoute>
      }>
        <Route path="dashboard"     element={<TeacherDashboard />} />
        <Route path="classes"       element={<TeacherClasses />} />
        <Route path="grades"        element={<TeacherGrades />} />
        <Route path="attendance"    element={<TeacherAttendance />} />
        <Route path="homework"      element={<TeacherHomework />} />
        <Route path="schedule"      element={<TeacherSchedule />} />
        <Route path="messages"      element={<TeacherMessages />} />
        <Route path="profile"       element={<TeacherProfile />} />
        <Route path="announcements" element={<SharedAnnouncements />} />
        <Route path="virtual"       element={<VirtualRooms />} />
      </Route>

      {/* ── Parent ── */}
      <Route path="/parent" element={
        <ProtectedRoute allowedRoles={["parent"]}>
          <ParentLayout />
        </ProtectedRoute>
      }>
        <Route path="home"          element={<ParentHome />} />
        <Route path="children"      element={<ParentChildren />} />
        <Route path="grades"        element={<ParentGrades />} />
        <Route path="attendance"    element={<ParentAttendance />} />
        <Route path="homework"      element={<ParentHomework />} />
        <Route path="payments"      element={<ParentPayments />} />
        <Route path="bulletins"     element={<ParentBulletins />} />
        <Route path="messages"      element={<ParentMessages />} />
        <Route path="schedule"      element={<ParentSchedule />} />
        <Route path="profile"       element={<ParentProfile />} />
        <Route path="announcements" element={<SharedAnnouncements />} />
        <Route path="virtual"       element={<VirtualRooms />} />
      </Route>

      {/* ── Student ── */}
      <Route path="/student" element={
        <ProtectedRoute allowedRoles={["student"]}>
          <StudentLayout />
        </ProtectedRoute>
      }>
        <Route path="home"          element={<StudentHome />} />
        <Route path="grades"        element={<StudentGrades />} />
        <Route path="attendance"    element={<StudentAttendance />} />
        <Route path="homework"      element={<StudentHomework />} />
        <Route path="schedule"      element={<StudentSchedule />} />
        <Route path="bulletins"     element={<StudentBulletins />} />
        <Route path="messages"      element={<StudentMessages />} />
        <Route path="profile"       element={<StudentProfile />} />
        <Route path="announcements" element={<SharedAnnouncements />} />
        <Route path="virtual"       element={<VirtualRooms />} />
      </Route>

      {/* URL inconnue → 404 PUBLIQUE du site vitrine (P4). Un utilisateur
          authentifié n'est jamais renvoyé vers /login (pas de fausse
          impression de déconnexion : le header du site affiche « Mon
          espace » et sa session reste intacte). */}
      <Route element={<SiteLayout />}>
        <Route path="*" element={<SiteNotFound />} />
      </Route>
    </Routes>
    </Suspense>
  );
}
