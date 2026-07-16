import { Routes, Route, Navigate } from "react-router-dom";
import { useAuthStore } from "../store/authStore";

// Layouts
import SuperAdminLayout from "../layouts/SuperAdminLayout";
import AdminLayout from "../layouts/AdminLayout";
import TeacherLayout from "../layouts/TeacherLayout";
import ParentLayout from "../layouts/ParentLayout";
import StudentLayout from "../layouts/StudentLayout";

// Auth
import LoginPage from "../pages/LoginPage";

// SuperAdmin pages
import SuperAdminDashboard from "../pages/superadmin/Dashboard";
import SuperAdminUsers from "../pages/superadmin/Users";
import SuperAdminAdmins from "../pages/superadmin/Admins";
import SuperAdminProfile from "../pages/superadmin/Profile";

// Admin pages
import AdminDashboard from "../pages/admin/Dashboard";
import AdminStudents from "../pages/admin/Students";
import AdminTeachers from "../pages/admin/Teachers";
import AdminParents from "../pages/admin/Parents";
import AdminClasses from "../pages/admin/Classes";
import AdminGrades from "../pages/admin/Grades";
import AdminPayments from "../pages/admin/Payments";
import AdminAttendance from "../pages/admin/Attendance";
import AdminHomework from "../pages/admin/Homework";
import AdminAnnouncements from "../pages/admin/Announcements";
import AdminMessages from "../pages/admin/Messages";
import AdminBulletins from "../pages/admin/Bulletins";
import AdminSchedule from "../pages/admin/Schedule";
import AdminSettings from "../pages/admin/Settings";
import AdminUserFiles from "../pages/admin/UserFiles";
import AdminUsers from "../pages/admin/Users";
import AdminLevels from "../pages/admin/Levels";
import AdminBranding from "../pages/admin/Branding";
import AdminEnrollments from "../pages/admin/Enrollments";
import AdminProfile from "../pages/admin/Profile";

// Teacher pages
import TeacherDashboard from "../pages/teacher/Dashboard";
import TeacherClasses from "../pages/teacher/Classes";
import TeacherGrades from "../pages/teacher/Grades";
import TeacherAttendance from "../pages/teacher/Attendance";
import TeacherHomework from "../pages/teacher/Homework";
import TeacherSchedule from "../pages/teacher/Schedule";
import TeacherMessages from "../pages/teacher/Messages";
import TeacherProfile from "../pages/teacher/Profile";

// Parent pages
import ParentHome from "../pages/parent/Home";
import ParentChildren from "../pages/parent/Children";
import ParentGrades from "../pages/parent/Grades";
import ParentAttendance from "../pages/parent/Attendance";
import ParentHomework from "../pages/parent/Homework";
import ParentPayments from "../pages/parent/Payments";
import ParentBulletins from "../pages/parent/Bulletins";
import ParentMessages from "../pages/parent/Messages";
import ParentSchedule from "../pages/parent/Schedule";
import ParentProfile from "../pages/parent/Profile";

// Student pages
import StudentHome from "../pages/student/Home";
import StudentGrades from "../pages/student/Grades";
import StudentAttendance from "../pages/student/Attendance";
import StudentHomework from "../pages/student/Homework";
import StudentSchedule from "../pages/student/Schedule";
import StudentBulletins from "../pages/student/Bulletins";
import StudentMessages from "../pages/student/Messages";
import StudentProfile from "../pages/student/Profile";

// Shared pages
import SharedAnnouncements from "../pages/shared/Announcements";
import VirtualRooms from "../pages/shared/VirtualRooms";
import NotFoundPage from "../pages/shared/NotFound";

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

// ── URL inconnue : ne jamais faire croire à une déconnexion ──────────────
function NotFoundOrLogin() {
  const { accessToken, _hasHydrated } = useAuthStore();
  if (!_hasHydrated) return null;
  if (!accessToken) return <Navigate to="/login" replace />;
  return <NotFoundPage />;
}

export default function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<RoleRedirect />} />

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

      {/* FIX (notifications / redirections) : une URL inconnue ne doit
          jamais renvoyer un utilisateur authentifié vers /login (cela
          ressemble à une déconnexion forcée). On affiche une page "introuvable"
          avec un lien de retour ; seul un utilisateur non authentifié est
          envoyé vers /login. */}
      <Route path="*" element={<NotFoundOrLogin />} />
    </Routes>
  );
}
