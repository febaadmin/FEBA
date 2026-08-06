/**
 * Régression P1 — « tableau de bord Super Admin à zéro après actualisation ».
 *
 * SYMPTÔME REPRODUIT ICI
 * ----------------------
 * Au premier chargement les chiffres étaient corrects ; après un Cmd+R ils
 * tombaient tous à 0 (utilisateurs, admins, enseignants, parents, élèves,
 * comptes actifs) et ne revenaient qu'après sélection manuelle d'une
 * académie.
 *
 * ENCHAÎNEMENT FAUTIF (avant correction)
 * --------------------------------------
 *   1. Au rechargement, le Dashboard se montait AVANT que
 *      `/auth/entity-context/` ait répondu : la portée valait UNKNOWN.
 *   2. Il émettait `/auth/users/` sous cette portée indéterminée.
 *   3. L'arrivée du contexte déclenchait `setAcademyScope(ALL)`, qui avorte
 *      toutes les requêtes en vol — dont celle-ci.
 *   4. `retry: false` sur ERR_CANCELED : React Query ne la relançait pas.
 *   5. `data` restait `undefined`, et `data?.data?.results || []` repliait
 *      cet « inconnu » sur un tableau vide → six zéros parfaitement
 *      crédibles et parfaitement faux.
 *
 * Les tests ci-dessous verrouillent les deux garanties qui l'empêchent :
 * l'ORDRE (aucune requête métier avant que la portée soit établie) et
 * l'HONNÊTETÉ D'AFFICHAGE (une donnée absente n'est jamais rendue « 0 »).
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api", () => ({
  default: { get: vi.fn(), post: vi.fn() },
  authAPI: { listUsers: vi.fn() },
}));

import api, { authAPI } from "../api";
import { AcademyProvider, resetEntityContextDedup, fetchEntityContext } from "./AcademyContext";
import { resetAcademyScope, getAcademyScope } from "../api/academyScope";
import { useAuthStore } from "../store/authStore";
import SuperAdminDashboard from "../pages/superadmin/Dashboard";
import AcademyScopedOutlet from "../components/AcademyScopedOutlet";

/** Promesse dont on contrôle la résolution, pour ordonnancer la course. */
function deferred() {
  let resolve;
  const promise = new Promise((r) => {
    resolve = r;
  });
  return { promise, resolve };
}

const CONTEXT_ALL = {
  active_entity: null,
  all_entities_mode: true,
  entities: [{ id: 1, code: "FEBA" }, { id: 2, code: "FEBA_FHA" }],
  can_switch: true,
  features: {},
};

const contextFor = (code) => ({
  ...CONTEXT_ALL,
  active_entity: { id: code === "FEBA" ? 1 : 2, code },
  all_entities_mode: false,
});

/** 7 utilisateurs : 1 superadmin, 1 admin, 2 teachers, 2 parents, 1 student. */
const USERS = [
  { id: 1, role: "superadmin", is_active: true },
  { id: 2, role: "admin", is_active: true },
  { id: 3, role: "teacher", is_active: true },
  { id: 4, role: "teacher", is_active: false },
  { id: 5, role: "parent", is_active: true },
  { id: 6, role: "parent", is_active: true },
  { id: 7, role: "student", is_active: true },
];

function renderDashboard() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AcademyProvider>
          <SuperAdminDashboard />
        </AcademyProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  resetAcademyScope();
  resetEntityContextDedup();
  useAuthStore.setState({
    user: { id: 1, role: "superadmin" },
    accessToken: "jwt-access",
    refreshToken: "jwt-refresh",
    _hasHydrated: true,
  });
});

describe("ordre de démarrage — aucune requête métier avant la portée", () => {
  it("n'appelle pas /auth/users/ tant que /auth/entity-context/ n'a pas répondu", async () => {
    const ctx = deferred();
    api.get.mockReturnValue(ctx.promise.then((data) => ({ data })));
    authAPI.listUsers.mockResolvedValue({ data: { results: USERS } });

    renderDashboard();

    // Le contexte n'a pas encore répondu : la portée est indéterminée.
    // C'est exactement l'instant où l'ancienne version tirait sa requête.
    await waitFor(() => expect(api.get).toHaveBeenCalled());
    expect(authAPI.listUsers).not.toHaveBeenCalled();

    ctx.resolve(CONTEXT_ALL);

    // Une fois la portée établie, et seulement là, la requête métier part.
    await waitFor(() => expect(authAPI.listUsers).toHaveBeenCalledTimes(1));
    expect(getAcademyScope()).toBe("ALL");
  });

  it("applique la portée AVANT d'autoriser la requête métier", async () => {
    const scopesSeen = [];
    api.get.mockResolvedValue({ data: CONTEXT_ALL });
    authAPI.listUsers.mockImplementation(() => {
      scopesSeen.push(getAcademyScope());
      return Promise.resolve({ data: { results: USERS } });
    });

    renderDashboard();

    await waitFor(() => expect(authAPI.listUsers).toHaveBeenCalled());
    // Aucune requête métier n'a jamais été émise sous UNKNOWN.
    expect(scopesSeen).not.toContain("UNKNOWN");
    expect(scopesSeen).toEqual(["ALL"]);
  });
});

describe("le tableau de bord n'affiche jamais de faux zéro", () => {
  it("affiche les chiffres réels après actualisation en portée ALL", async () => {
    api.get.mockResolvedValue({ data: CONTEXT_ALL });
    authAPI.listUsers.mockResolvedValue({ data: { results: USERS } });

    renderDashboard();

    // 7 utilisateurs au total — et surtout pas 0.
    await waitFor(() => expect(screen.getByText("7")).toBeInTheDocument());
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it.each(["FEBA", "FEBA_FHA"])(
    "affiche les chiffres réels après actualisation en portée %s",
    async (code) => {
      api.get.mockResolvedValue({ data: contextFor(code) });
      authAPI.listUsers.mockResolvedValue({ data: { results: USERS } });

      renderDashboard();

      await waitFor(() => expect(screen.getByText("7")).toBeInTheDocument());
      expect(getAcademyScope()).toBe(code);
    },
  );

  it("reste en attente — sans afficher 0 — quand la requête est annulée", async () => {
    api.get.mockResolvedValue({ data: CONTEXT_ALL });
    const canceled = Object.assign(new Error("canceled"), { code: "ERR_CANCELED" });
    authAPI.listUsers.mockRejectedValue(canceled);

    renderDashboard();

    await waitFor(() => expect(authAPI.listUsers).toHaveBeenCalled());

    // L'écran ne doit contenir AUCUN compteur à zéro : une requête annulée
    // n'est pas une donnée. C'est le cœur de la régression.
    await waitFor(() => {
      expect(screen.queryByText("0")).not.toBeInTheDocument();
    });
    expect(screen.queryByText("Total utilisateurs")).not.toBeInTheDocument();
  });

  it("survit à dix actualisations consécutives sans jamais tomber à zéro", async () => {
    api.get.mockResolvedValue({ data: CONTEXT_ALL });
    authAPI.listUsers.mockResolvedValue({ data: { results: USERS } });

    for (let i = 0; i < 10; i += 1) {
      resetAcademyScope();
      resetEntityContextDedup();
      const { unmount } = renderDashboard();
      await waitFor(() => expect(screen.getByText("7")).toBeInTheDocument());
      expect(screen.queryByText("0")).not.toBeInTheDocument();
      unmount();
    }
  });
});

describe("garde de portée du sous-arbre routé", () => {
  function renderOutlet() {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <AcademyProvider>
            <AcademyScopedOutlet />
          </AcademyProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  it("affiche une attente explicite tant que la portée n'est pas prête", async () => {
    const ctx = deferred();
    api.get.mockReturnValue(ctx.promise.then((data) => ({ data })));

    renderOutlet();

    expect(screen.getByRole("status")).toBeInTheDocument();

    ctx.resolve(CONTEXT_ALL);
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
  });
});

describe("déduplication de /auth/entity-context/", () => {
  it("ne lance qu'une seule requête réseau pour des appels concurrents", async () => {
    let resolveCtx;
    api.get.mockReturnValue(
      new Promise((r) => {
        resolveCtx = () => r({ data: CONTEXT_ALL });
      }),
    );

    const a = fetchEntityContext();
    const b = fetchEntityContext();
    const c = fetchEntityContext();

    expect(api.get).toHaveBeenCalledTimes(1);

    resolveCtx();
    await expect(Promise.all([a, b, c])).resolves.toEqual([
      CONTEXT_ALL,
      CONTEXT_ALL,
      CONTEXT_ALL,
    ]);
  });

  it("relance une requête après résolution de la précédente", async () => {
    api.get.mockResolvedValue({ data: CONTEXT_ALL });

    await fetchEntityContext();
    await fetchEntityContext();

    expect(api.get).toHaveBeenCalledTimes(2);
  });
});
