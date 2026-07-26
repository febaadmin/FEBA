import axios from "axios";
import { useAuthStore } from "../store/authStore";
import { getLang } from "../i18n";

const API_URL = import.meta.env.VITE_API_URL || "/api";

const api = axios.create({ baseURL: API_URL, headers: { "Content-Type": "application/json" } });

// Attach JWT + langue courante (LocaleMiddleware côté Django localise les
// messages du framework selon cet en-tête)
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  config.headers["Accept-Language"] = getLang();
  return config;
});

// Auto-refresh on 401
// FIX v20: Endpoints "non-critiques" qui ne doivent PAS provoquer une déconnexion
//          en cas de 401 (ex: branding appelé avant hydratation du token)
const NON_CRITICAL_ENDPOINTS = [
  "/schools/branding/",
  "/notifications/",
  "/notifications/unread-count/",
  "/messages/unread-count",
  "/messages/inbox",
];

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const orig = error.config;
    if (error.response?.status === 401 && !orig._retry) {
      // Si l'URL est non-critique ET qu'il n'y a pas de refreshToken, ne pas déconnecter
      const url = orig.url || "";
      const isNonCritical = NON_CRITICAL_ENDPOINTS.some(ep => url.includes(ep));
      const rt = useAuthStore.getState().refreshToken;

      if (!rt && isNonCritical) {
        // Pas de token du tout — laisse React Query gérer l'erreur silencieusement
        return Promise.reject(error);
      }

      orig._retry = true;
      if (rt) {
        try {
          const { data } = await axios.post(`${API_URL}/auth/refresh/`, { refresh: rt });
          useAuthStore.getState().setAuth(useAuthStore.getState().user, data.access, data.refresh || rt);
          orig.headers.Authorization = `Bearer ${data.access}`;
          return api(orig);
        } catch {
          // Refresh échoué — déconnecter seulement si l'endpoint était critique
          if (!isNonCritical) {
            useAuthStore.getState().clearAuth();
            window.location.href = "/login";
          }
        }
      } else {
        // Pas de refreshToken → déconnecter (sauf endpoint non-critique)
        if (!isNonCritical) {
          useAuthStore.getState().clearAuth();
          window.location.href = "/login";
        }
      }
    }
    return Promise.reject(error);
  }
);

export default api;

// Helper: always fetch large lists without pagination limit for admin use
const BIG = { page_size: 1000 };

export const authAPI = {
  login: (d)          => api.post("/auth/login/", d),
  logout: (r)         => api.post("/auth/logout/", { refresh: r }),
  me: ()              => api.get("/auth/me/"),
  updateMe: (d)       => api.patch("/auth/me/", d),
  changePassword: (d) => api.post("/auth/change-password/", d),
  listUsers: (p)      => api.get("/auth/users/", { params: { ...BIG, ...p } }),
  getUser: (id)       => api.get(`/auth/users/${id}/`),
  createUser: (d)     => api.post("/auth/users/", d),
  updateUser: (id, d) => api.patch(`/auth/users/${id}/`, d),
  deleteUser: (id)    => api.delete(`/auth/users/${id}/`),
  toggleActive: (id)  => api.post(`/auth/users/${id}/toggle-active/`),
  adminResetPassword: (id, d) => api.post(`/auth/users/${id}/reset-password/`, d),
  recipients: ()      => api.get("/auth/recipients/"),
};

// Administration du site vitrine public (P4) — permission admin/superadmin.
export const websiteAdminAPI = {
  settings: ()            => api.get("/website/admin/settings/"),
  updateSettings: (d)     => api.patch("/website/admin/settings/", d),
  news: ()                => api.get("/website/admin/news/", { params: BIG }),
  createNews: (d)         => api.post("/website/admin/news/", d),
  updateNews: (id, d)     => api.patch(`/website/admin/news/${id}/`, d),
  deleteNews: (id)        => api.delete(`/website/admin/news/${id}/`),
  contactMessages: ()     => api.get("/website/admin/contact-messages/", { params: BIG }),
  updateContact: (id, d)  => api.patch(`/website/admin/contact-messages/${id}/`, d),
  deleteContact: (id)     => api.delete(`/website/admin/contact-messages/${id}/`),
  preregistrations: ()    => api.get("/website/admin/preregistrations/", { params: BIG }),
  updatePrereg: (id, d)   => api.patch(`/website/admin/preregistrations/${id}/`, d),
  deletePrereg: (id)      => api.delete(`/website/admin/preregistrations/${id}/`),
  heroSlides: ()          => api.get("/website/admin/hero-slides/"),
  updateHeroSlide: (id, d) => api.patch(`/website/admin/hero-slides/${id}/`, d),
};

export const schoolsAPI = {
  list: ()           => api.get("/schools/schools/"),
  get: (id)          => api.get(`/schools/schools/${id}/`),
  update: (id, d)    => api.patch(`/schools/schools/${id}/`, d),
  years: ()          => api.get("/schools/years/", { params: BIG }),
  createYear: (d)    => api.post("/schools/years/", d),
  updateYear: (id,d) => api.patch(`/schools/years/${id}/`, d),
  deleteYear: (id)   => api.delete(`/schools/years/${id}/`),
  activateYear: (id) => api.post(`/schools/years/${id}/set_current/`),
  closeYear: (id)    => api.post(`/schools/years/${id}/close/`),
  levels: ()         => api.get("/schools/levels/", { params: BIG }),
  createLevel: (d)   => api.post("/schools/levels/", d),
  updateLevel: (id,d)=> api.patch(`/schools/levels/${id}/`, d),
  deleteLevel: (id)  => api.delete(`/schools/levels/${id}/`),
  rooms: (p)         => api.get("/schools/rooms/", { params: { ...BIG, ...p } }),
  createRoom: (d)    => api.post("/schools/rooms/", d),
  updateRoom: (id,d) => api.patch(`/schools/rooms/${id}/`, d),
  deleteRoom: (id)   => api.delete(`/schools/rooms/${id}/`),
  // Dynamic room types
  roomTypes: (p)         => api.get("/schools/room-types/", { params: { ...BIG, ...p } }),
  createRoomType: (d)    => api.post("/schools/room-types/", d),
  updateRoomType: (id,d) => api.patch(`/schools/room-types/${id}/`, d),
  deleteRoomType: (id)   => api.delete(`/schools/room-types/${id}/`),
  // Branding / Logo management
  listBranding:     (p)      => api.get("/schools/branding/", { params: { ...BIG, ...p } }),
  activeBranding:   (p)      => api.get("/schools/branding/active/", { params: p }),
  uploadBranding:   (fd)     => api.post("/schools/branding/", fd, { headers: { "Content-Type": "multipart/form-data" } }),
  activateBranding: (id)     => api.post(`/schools/branding/${id}/activate/`),
  deleteBranding:   (id)     => api.delete(`/schools/branding/${id}/`),
};

export const classesAPI = {
  list: (p)         => api.get("/classes/", { params: { ...BIG, ...p } }),
  get: (id)         => api.get(`/classes/${id}/`),
  create: (d)       => api.post("/classes/", d),
  update: (id, d)   => api.patch(`/classes/${id}/`, d),
  delete: (id)      => api.delete(`/classes/${id}/`),
  // Gestion matières M2M
  getSubjects: (id) => api.get(`/classes/${id}/subjects/`),
  setSubjects: (id, subject_ids) => api.post(`/classes/${id}/subjects/`, { subject_ids }),
  removeSubject: (id, subject_id) => api.delete(`/classes/${id}/subjects/`, { data: { subject_id } }),
  mySubjects: () => api.get("/teachers/my_subjects/"),
  myClasses:  () => api.get("/teachers/my_classes/"),
  students:   (id)    => api.get(`/classes/${id}/students/`, { params: BIG }),
  schedule: (id)    => api.get(`/classes/${id}/schedule/`, { params: BIG }),
  homework: (id)    => api.get(`/classes/${id}/homework/`, { params: BIG }),
  copyFromYear: (d)  => api.post(`/classes/copy-from-year/`, d),
};

export const studentsAPI = {
  list: (p)         => api.get("/students/", { params: { ...BIG, ...p } }),
  get: (id)         => api.get(`/students/${id}/`),
  // FIX: send multipart/form-data when payload is FormData (file upload bug fix)
  create: (d)       => d instanceof FormData
    ? api.post("/students/", d, { headers: { "Content-Type": "multipart/form-data" } })
    : api.post("/students/", d),
  update: (id, d)   => d instanceof FormData
    ? api.patch(`/students/${id}/`, d, { headers: { "Content-Type": "multipart/form-data" } })
    : api.patch(`/students/${id}/`, d),
  delete: (id)      => api.delete(`/students/${id}/`),
  bulkDelete: (ids) => api.post(`/students/bulk-delete/`, { ids }),
  // ── Multi-year enrollment ────────────────────────────────────────────────
  enrollments:       (studentId) => api.get("/students/enrollments/", { params: { student: studentId } }),
  addEnrollment:     (d)         => api.post("/students/enrollments/", d),
  updateEnrollment:  (id, d)     => api.patch(`/students/enrollments/${id}/`, d),
  deleteEnrollment:  (id)        => api.delete(`/students/enrollments/${id}/`),
  enroll:            (id, d)     => api.post(`/students/${id}/enroll/`, d),
  removeFromYear:    (id, yearId) => api.post(`/students/${id}/remove-from-year/`, { school_year_id: yearId }),
  bulkRemoveFromYear: (ids, yearId) => api.post(`/students/bulk-remove-from-year/`, { ids, school_year_id: yearId }),
  hardDelete:        (id)        => api.delete(`/students/${id}/`, { params: { hard: true } }),
  reactivate:        (id)        => api.post(`/students/${id}/reactivate/`),
  enrollAllFromYear: (d)         => api.post("/students/enroll-all-from-year/", d),
  enrollClass:       (d)         => api.post("/students/enroll-class/", d),
  promote:           (d)         => api.post("/students/promote/", d),
  grades: (id)      => api.get(`/students/${id}/grades/`),
  attendance: (id)  => api.get(`/students/${id}/attendance/`),
  payments: (id)    => api.get(`/students/${id}/payments/`),
  checkDuplicate: (p) => api.get("/students/check_duplicate/", { params: p }),
  bulletins: (id)   => api.get(`/students/${id}/bulletins/`),
  history: (id)     => api.get(`/students/${id}/history/`),
  endOfYearAssistant: (d) => api.post("/students/end-of-year-assistant/", d),
};

export const teachersAPI = {
  list: (p)         => api.get("/teachers/", { params: { ...BIG, ...p } }),
  get: (id)         => api.get(`/teachers/${id}/`),
  create: (d)       => api.post("/teachers/", d),
  update: (id, d)   => api.patch(`/teachers/${id}/`, d),
  delete: (id)      => api.delete(`/teachers/${id}/`),
  bulkDelete: (ids) => api.post(`/teachers/bulk-delete/`, { ids }),
  schedule: (id)    => api.get(`/teachers/${id}/schedule/`),
  mySubjects: () => api.get("/teachers/my_subjects/"),
  myClasses:  () => api.get("/teachers/my_classes/"),
  students:   (id)    => api.get(`/teachers/${id}/students/`),
};

export const parentsAPI = {
  // ── Helpers ────────────────────────────────────────────────────────────────
  checkChildAssignment: (studentId) =>
    api.get("/parents/check_child_assignment/", { params: { student_id: studentId } }),

  // FIX: assign_child via the global endpoint (detail=False)
  assignChild: (parentId, studentId, rel) =>
    api.post("/parents/assign_child/", {
      parent_id: parentId,
      student_id: studentId,
      relationship: rel || "guardian",
    }),

  removeChild: (parentId, studentId) =>
    api.delete("/parents/remove_child/", { params: { parent_id: parentId, student_id: studentId } }),

  // FIX: linkStudent now calls the detail action POST /parents/{id}/link_student/
  linkStudent: (parentId, studentId, rel) =>
    api.post(`/parents/${parentId}/link_student/`, {
      student_id: studentId,
      relationship: rel || "guardian",
    }),

  // FIX: unlinkStudent now calls the detail action POST /parents/{id}/unlink_student/
  unlinkStudent: (parentId, studentId) =>
    api.post(`/parents/${parentId}/unlink_student/`, { student_id: studentId }),

  // ── CRUD ───────────────────────────────────────────────────────────────────
  list: (p)     => api.get("/parents/", { params: { ...BIG, ...p } }),
  me: ()        => api.get("/parents/me/"),
  get: (id)     => api.get(`/parents/${id}/`),
  create: (d)   => api.post("/parents/", d),
  update: (id, d) => api.patch(`/parents/${id}/`, d),
  delete: (id)  => api.delete(`/parents/${id}/`),
  bulkDelete: (ids) => api.post(`/parents/bulk-delete/`, { ids }),
  children: (id) => api.get(`/parents/${id}/children/`),
};

export const subjectsAPI = {
  list: (p)         => api.get("/subjects/", { params: { ...BIG, ...p } }),
  create: (d)       => api.post("/subjects/", d),
  update: (id, d)   => api.patch(`/subjects/${id}/`, d),
  delete: (id)      => api.delete(`/subjects/${id}/`),
};

export const gradesAPI = {
  list: (p)              => api.get("/grades/", { params: { ...BIG, ...p } }),
  listDeleted: ()        => api.get("/grades/", { params: { ...BIG, show_deleted: 1 } }),
  create: (d)            => api.post("/grades/", d),
  update: (id, d)        => api.patch(`/grades/${id}/`, d),
  // FIX v20: justification obligatoire pour soft-delete (envoyée dans le body)
  delete: (id, justification) => api.delete(`/grades/${id}/`, { data: { justification } }),
  bulkDelete: (ids) => api.post(`/grades/bulk-delete/`, { ids }),
  restore: (id)          => api.post(`/grades/${id}/restore/`),
  history: (id)          => api.get(`/grades/${id}/grade_history/`),
  averages: (p)          => api.get("/grades/averages/", { params: p }),
  classAverages: (p)     => api.get("/grades/class-averages/", { params: p }),
  studentSummary: (sid, p) => api.get("/grades/student-summary/", { params: { student: sid, ...p } }),
  bilingual: (p)         => api.get("/grades/bilingual/", { params: p }),
  bulkSave: (d)          => api.post("/grades/bulk_save/", d),
  bulkCreate: (d)        => api.post("/grades/bulk-create/", d),
  allHistory: (p)        => api.get("/grades/all-history/", { params: p }),
};

export const attendanceAPI = {
  list: (p)         => api.get("/attendance/", { params: { ...BIG, ...p } }),
  create: (d)       => {
    if (d instanceof FormData) {
      return api.post("/attendance/", d, { headers: { "Content-Type": "multipart/form-data" } });
    }
    return api.post("/attendance/", d);
  },
  update: (id, d)   => api.patch(`/attendance/${id}/`, d),
  delete: (id)      => api.delete(`/attendance/${id}/`),
  bulkDelete: (ids) => api.post(`/attendance/bulk-delete/`, { ids }),
  bulk: (d)         => api.post("/attendance/bulk/", d),
  stats: (p)        => api.get("/attendance/stats/", { params: p }),
};

export const scheduleAPI = {
  list: (p)         => api.get("/schedule/", { params: { ...BIG, ...p } }),
  create: (d)       => api.post("/schedule/", d),
  update: (id, d)   => api.patch(`/schedule/${id}/`, d),
  delete: (id)      => api.delete(`/schedule/${id}/`),
  byClass: (id)     => api.get(`/schedule/class/${id}/`, { params: BIG }),
  byTeacher: (id)   => api.get(`/schedule/teacher/${id}/`, { params: BIG }),
};

export const homeworkAPI = {
  list: (p)         => api.get("/homework/", { params: { ...BIG, ...p } }),
  create: (d)       => {
    if (d instanceof FormData) return api.post("/homework/", d, { headers: { "Content-Type": "multipart/form-data" } });
    return api.post("/homework/", d);
  },
  update: (id, d)   => {
    if (d instanceof FormData) return api.patch(`/homework/${id}/`, d, { headers: { "Content-Type": "multipart/form-data" } });
    return api.patch(`/homework/${id}/`, d);
  },
  delete: (id)      => api.delete(`/homework/${id}/`),
  bulkDelete: (ids) => api.post(`/homework/bulk-delete/`, { ids }),
  deleteAttachment: (hwId, attId) => api.delete(`/homework/${hwId}/attachments/${attId}/`),
};

export const paymentsAPI = {
  list: (p)         => api.get("/payments/", { params: { ...BIG, ...p } }),
  listDeleted: ()   => api.get("/payments/", { params: { ...BIG, show_deleted: 1 } }),
  get: (id)         => api.get(`/payments/${id}/`),
  create: (d)       => api.post("/payments/", d),
  update: (id, d)   => api.patch(`/payments/${id}/`, d),
  delete: (id)      => api.delete(`/payments/${id}/`),
  bulkDelete: (ids) => api.post(`/payments/bulk-delete/`, { ids }),
  restore: (id)     => api.post(`/payments/${id}/restore/`),
  cancel: (id, justification) => api.post(`/payments/${id}/cancel/`, { justification }),
  summary: ()       => api.get("/payments/summary/"),
  pending: ()       => api.get("/payments/pending/"),
  generateReceipt: (id) => api.post(`/payments/${id}/generate-receipt/`),
  history: (id)     => api.get(`/payments/${id}/history/`),
};

export const conversationsAPI = {
  list:     ()        => api.get("/messages/conversations/"),
  get:      (id)      => api.get(`/messages/conversations/${id}/`),
  create:   (d)       => {
    if (d instanceof FormData) return api.post("/messages/conversations/", d, { headers: { "Content-Type": "multipart/form-data" } });
    return api.post("/messages/conversations/", d);
  },
  reply:    (id, d)   => {
    if (d instanceof FormData) return api.post(`/messages/conversations/${id}/reply/`, d, { headers: { "Content-Type": "multipart/form-data" } });
    return api.post(`/messages/conversations/${id}/reply/`, d);
  },
  markRead: (id)      => api.put(`/messages/conversations/${id}/mark_read/`),
  unreadCount: ()     => api.get("/messages/conversations/unread_count/"),
};

export const messagesAPI = {
  inbox: ()         => api.get("/messages/inbox/"),
  sent: ()          => api.get("/messages/sent/"),
  unreadCount: ()   => api.get("/messages/unread-count/"),
  send: (d) => {
    if (d instanceof FormData) {
      return api.post("/messages/", d, { headers: { "Content-Type": "multipart/form-data" } });
    }
    return api.post("/messages/", d);
  },
  reply: (id, d) => {
    if (d instanceof FormData) {
      return api.post(`/messages/${id}/reply/`, d, { headers: { "Content-Type": "multipart/form-data" } });
    }
    return api.post(`/messages/${id}/reply/`, d);
  },
  markRead: (id)    => api.put(`/messages/${id}/read/`),
  delete: (id)      => api.delete(`/messages/${id}/`),
};

export const announcementsAPI = {
  list: (p)         => api.get("/announcements/", { params: { ...BIG, ...p } }),
  create: (d, isFile) => isFile
    ? api.post("/announcements/", d, { headers: { "Content-Type": "multipart/form-data" } })
    : api.post("/announcements/", d),
  update: (id, d, isFile) => isFile
    ? api.patch(`/announcements/${id}/`, d, { headers: { "Content-Type": "multipart/form-data" } })
    : api.patch(`/announcements/${id}/`, d),
  delete: (id)      => api.delete(`/announcements/${id}/`),
  bulkDelete: (ids) => api.post(`/announcements/bulk-delete/`, { ids }),
};

export const notificationsAPI = {
  list: ()          => api.get("/notifications/"),
  unreadCount: ()   => api.get("/notifications/unread-count/"),
  markRead: (id)    => api.put(`/notifications/${id}/read/`),
  markAllRead: ()   => api.put("/notifications/read-all/"),
};

// V8 — Incidents techniques (super administrateur uniquement)
export const incidentsAPI = {
  list:    (p)      => api.get("/incidents/", { params: p }),
  detail:  (id)     => api.get(`/incidents/${id}/`),
  stats:   ()       => api.get("/incidents/stats/"),
  update:  (id, d)  => api.patch(`/incidents/${id}/`, d),
  resolve: (id, d)  => api.post(`/incidents/${id}/resolve/`, d || {}),
  reopen:  (id)     => api.post(`/incidents/${id}/reopen/`, {}),
};

export const bulletinsAPI = {
  list: (p)          => api.get("/bulletins/", { params: { ...BIG, ...p } }),
  generate: (d)      => api.post("/bulletins/generate/", d),
  generateClass: (d) => api.post("/bulletins/generate-class/", d),
  generateAll: (d)   => api.post("/bulletins/generate-all/", d),
  delete: (id)       => api.delete(`/bulletins/${id}/`),
  bulkDelete: (ids)  => api.post(`/bulletins/bulk-delete/`, { ids }),
};

export const avatarAPI = {
  upload: (file) => {
    const fd = new FormData();
    fd.append("avatar", file);
    return api.post("/auth/avatar/", fd, { headers: { "Content-Type": "multipart/form-data" } });
  },
  delete: () => api.delete("/auth/avatar/"),
};

export const dashboardAPI = {
  admin:   ()       => api.get("/dashboard/admin/"),
  teacher: ()       => api.get("/dashboard/teacher/"),
  parent:  ()       => api.get("/dashboard/parent/"),
  student: ()       => api.get("/dashboard/student/"),
};

// Module Fichiers Utilisateurs (nouvelle fonctionnalité)
export const userFilesAPI = {
  list:     (params) => api.get("/user-files/", { params }),
  get:      (id)     => api.get(`/user-files/${id}/`),
  create:   (d)      => api.post("/user-files/", d, { headers: { "Content-Type": "multipart/form-data" } }),
  // FIX BUG N°9 : le payload était remplacé par l'objet {headers} —
  // le PATCH envoyait les en-têtes comme données et perdait le contenu.
  update:   (id, d)  => d instanceof FormData
    ? api.patch(`/user-files/${id}/`, d, { headers: { "Content-Type": "multipart/form-data" } })
    : api.patch(`/user-files/${id}/`, d),
  replace:  (id, d)  => api.put(`/user-files/${id}/`, d, { headers: { "Content-Type": "multipart/form-data" } }),
  delete:   (id)     => api.delete(`/user-files/${id}/`),
  download: (id)     => api.get(`/user-files/${id}/download/`, { responseType: "blob" }),
};

/**
 * API de gestion plateforme — superadmin uniquement.
 * Permet la gestion du cycle de vie des établissements clients SaaS
 * (création, suspension, changement de plan...).
 */
export const platformAPI = {
  listSchools: (p)        => api.get("/platform/schools/", { params: p }),
  createSchool: (d)       => api.post("/platform/schools/", d),
  getSchool: (slug)       => api.get(`/platform/schools/${slug}/`),
  updateSchool: (slug, d) => api.patch(`/platform/schools/${slug}/`, d),
  suspendSchool: (slug, reason) =>
    api.post(`/platform/schools/${slug}/suspend/`, { reason }),
  reactivateSchool: (slug) =>
    api.post(`/platform/schools/${slug}/reactivate/`),
  stats: ()               => api.get("/platform/stats/"),
};

/* ── Salles virtuelles (visioconférence Jitsi) ─────────────────────────── */
export const virtualAPI = {
  list: (p)          => api.get("/virtual-rooms/", { params: { ...BIG, ...p } }),
  create: (d)        => api.post("/virtual-rooms/", d),
  update: (id, d)    => api.patch(`/virtual-rooms/${id}/`, d),
  delete: (id)       => api.delete(`/virtual-rooms/${id}/`),
  bulkDelete: (ids)  => api.post(`/virtual-rooms/bulk-delete/`, { ids }),
  join: (id)         => api.post(`/virtual-rooms/${id}/join/`),
  end: (id)          => api.post(`/virtual-rooms/${id}/end/`),
  leave: (id)        => api.post(`/virtual-rooms/${id}/leave/`),
  participants: (id) => api.get(`/virtual-rooms/${id}/participants/`),
};
