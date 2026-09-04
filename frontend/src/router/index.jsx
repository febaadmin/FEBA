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
// FEBA French Heritage Academy (ex-« FEBA Online ») : page programme,
// fiche d'inscription en 12 étapes et formulaire de contact dédiés.
const SiteFha = lazy(() => import("../site/pages/FhaPage"));
const SiteFhaEnroll = lazy(() => import("../site/pages/FhaEnrollPage"));
const SiteFhaContact = lazy(() => import("../site/pages/FhaContactPage"));
const SiteFhaPlacement = lazy(() => import("../site/pages/FhaPlacementTestPage"));
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
const AdminCardTransactions = lazy(() => import("../pages/admin/CardTransactions"));
const AdminOfficialDocuments = lazy(() => import("../pages/admin/OfficialDocuments"));
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
const FhaAdmissions = lazy(() => import("../pages/admin/FhaAdmissions"));
const MonthlyReports = lazy(() => import("../pages/admin/MonthlyReports"));
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
const VirtualRoomSession = lazy(() => import("../pages/shared/VirtualRoomSession"));
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

  // Même fenêtre que dans `RoleRedirect` : jeton réhydraté, utilisateur
  // pas encore là. Décider maintenant reviendrait à comparer le rôle
  // attendu à `undefined` — c'est-à-dire à refuser l'accès à quelqu'un
  // qui y a droit, puis à le rediriger sur une supposition.
  if (!user?.role) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="flex flex-col items-center gap-3 text-slate-400">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">Chargement…</span>
        </div>
      </div>
    );
  }

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
//
// UN RÔLE QU'ON NE CONNAÎT PAS ENCORE N'EST PAS « ÉLÈVE ».
//
// La version précédente attendait la réhydratation du magasin, mais pas
// le chargement de l'UTILISATEUR. Entre les deux existe une fenêtre où
// `_hasHydrated` vaut true, le jeton est là, et `user` vaut encore null :
// `role` est alors `undefined`, aucun test ne passe, et le repli final
// envoyait la personne vers l'espace ÉLÈVE.
//
// Vu dans le navigateur : un administrateur qui recharge une page de son
// espace se retrouvait sur /student/home. Ce n'est pas une faille — le
// serveur continue de refuser tout ce que ce compte n'a pas le droit de
// lire, et l'espace élève s'affiche vide — mais l'administrateur est
// éjecté de son travail sans explication, et l'écran lui dit qu'il est
// un élève.
//
// Le repli n'est plus « élève » : c'est « on ne sait pas encore », et on
// n'oriente pas quelqu'un sur une supposition.
function RoleRedirect() {
  const { user, accessToken, _hasHydrated } = useAuthStore();
  if (!_hasHydrated) return null;
  if (!accessToken) return <Navigate to="/login" replace />;
  // Jeton présent, utilisateur pas encore chargé : on patiente.
  if (!user?.role) return null;

  const role = user.role;
  if (role === "superadmin") return <Navigate to="/superadmin/dashboard" replace />;
  if (role === "admin")      return <Navigate to="/admin/dashboard" replace />;
  if (role === "teacher")    return <Navigate to="/teacher/dashboard" replace />;
  if (role === "parent")     return <Navigate to="/parent/home" replace />;
  if (role === "student")    return <Navigate to="/student/home" replace />;
  // Rôle inconnu du routeur : la connexion est valide mais aucun espace
  // ne lui correspond. Le dire vaut mieux que de le déposer au hasard.
  return <Navigate to="/login" replace />;
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

      {/* ── Conférence : un onglet à elle seule ────────────────────────
          Montée À LA RACINE, sans layout : ni barre latérale, ni en-tête,
          ni tableau de bord derrière. Ce n'est pas une préférence
          esthétique. Dans la modale, la conférence vivait dans l'arbre
          React du tableau de bord, dont la liste des salles se
          rafraîchit toutes les 30 secondes : chaque rafraîchissement
          détruisait et recréait la conférence, et l'utilisateur revenait
          à « Rejoindre la réunion » en laissant une identité de plus
          derrière lui. Ici, rien de tout cela ne l'atteint.

          Tous les rôles y ont accès : ce sont `assert_can_join` et le
          JWT signé côté serveur qui décident qui entre réellement, pas
          la route. */}
      <Route path="/virtual-room/:id/join" element={
        <ProtectedRoute allowedRoles={["superadmin", "admin", "teacher", "student", "parent"]}>
          <VirtualRoomSession />
        </ProtectedRoute>
      } />

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
        <Route path="/feba-fha" element={<SiteFha />} />
        <Route path="/feba-fha/enroll" element={<SiteFhaEnroll />} />
        <Route path="/feba-fha/contact" element={<SiteFhaContact />} />
        {/* « Réserver un test » ouvre un parcours PROPRE, plus le
            formulaire d'inscription complet. */}
        <Route path="/feba-fha/placement-test" element={<SiteFhaPlacement />} />
        {/* Ancien lien ?intent=placement : redirigé vers la route dédiée. */}
        <Route path="/feba-fha/enroll/placement" element={<Navigate to="/feba-fha/placement-test" replace />} />
        {/* Redirection permanente de l'ancienne route « FEBA Online » :
            les liens déjà partagés (flyers, réseaux sociaux, e-mails)
            continuent de fonctionner et n'affichent plus l'ancien nom.
            `replace` évite de laisser l'ancienne URL dans l'historique. */}
        <Route path="/feba-online" element={<Navigate to="/feba-fha" replace />} />
        <Route path="/feba-online/*" element={<Navigate to="/feba-fha" replace />} />
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
        <Route path="card-transactions" element={<AdminCardTransactions />} />
        <Route path="official-documents" element={<AdminOfficialDocuments />} />
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
        {/* P2 : les dossiers FHA étaient enregistrés sans écran pour
            les consulter — voici leur back-office dédié. */}
        <Route path="fha-admissions" element={<FhaAdmissions />} />
        {/* P3 : rapports mensuels — académie en ligne uniquement. Le
            backend refuse toute autre académie, l'entrée de menu ne fait
            que suivre. */}
        <Route path="monthly-reports" element={<MonthlyReports />} />
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
        <Route path="card-transactions" element={<AdminCardTransactions />} />
        <Route path="official-documents" element={<AdminOfficialDocuments />} />
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
        {/* P2 : les dossiers FHA étaient enregistrés sans écran pour
            les consulter — voici leur back-office dédié. */}
        <Route path="fha-admissions" element={<FhaAdmissions />} />
        {/* P3 : rapports mensuels — académie en ligne uniquement. Le
            backend refuse toute autre académie, l'entrée de menu ne fait
            que suivre. */}
        <Route path="monthly-reports" element={<MonthlyReports />} />
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
