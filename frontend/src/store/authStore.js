import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * FIX v25: add _hasHydrated guard.
 * Zustand persist is async — on mount, user is null for one render tick.
 * Without this guard, ProtectedRoute would redirect to /login on every navigation.
 * Solution: track hydration; ProtectedRoute shows a loading spinner until hydrated.
 *
 * FIX v29 (multi-tenant):
 * Le JWT expose désormais `school_id` et `school_slug` (claims ajoutés côté
 * backend dans CustomTokenObtainPairSerializer). Le frontend ne FAIT PAS
 * CONFIANCE à ces claims pour les décisions de sécurité (il reçoit les
 * objets API filtrés par le backend) — il les utilise uniquement pour :
 *  1. Afficher le nom de l'école dans la navigation sans appel API
 *     supplémentaire au chargement.
 *  2. Faciliter un éventuel routage futur par sous-domaine (school_slug).
 *  3. Permettre au superadmin de visualiser son école "courante" quand il
 *     navigue avec ?school_id= dans l'URL de l'admin plateforme.
 */
const useAuthStore = create(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      // Claims JWT de tenant (lus une seule fois au login, non mutable par l'UI)
      schoolId: null,
      schoolSlug: null,
      _hasHydrated: false,

      setAuth: (user, accessToken, refreshToken) => {
        // Extraire les claims tenant du payload JWT sans vérification
        // cryptographique côté client (le backend le vérifiera à chaque
        // requête) — uniquement pour l'affichage.
        let schoolId = null;
        let schoolSlug = null;
        try {
          const payload = JSON.parse(atob(accessToken.split(".")[1]));
          schoolId = payload.school_id ?? null;
          schoolSlug = payload.school_slug ?? null;
        } catch (_) {
          // JWT mal formé ou absence de claims tenant — silencieux
        }
        set({ user, accessToken, refreshToken, schoolId, schoolSlug });
      },

      clearAuth: () =>
        set({ user: null, accessToken: null, refreshToken: null, schoolId: null, schoolSlug: null }),

      setHasHydrated: (v) => set({ _hasHydrated: v }),

      isAuthenticated: () => !!get().accessToken,
      isSuperAdmin:    () => get().user?.role === "superadmin",
      isAdminOrAbove:  () => (get().user?.role_level ?? 0) >= 80,
      isTeacherOrAbove:() => (get().user?.role_level ?? 0) >= 50,
    }),
    {
      name: "feba-auth",
      partialize: (s) => ({
        user:         s.user,
        accessToken:  s.accessToken,
        refreshToken: s.refreshToken,
        schoolId:     s.schoolId,
        schoolSlug:   s.schoolSlug,
        // _hasHydrated intentionally NOT persisted — always starts false
      }),
      onRehydrateStorage: () => (state) => {
        if (state) state.setHasHydrated(true);
      },
    }
  )
);

export { useAuthStore };
