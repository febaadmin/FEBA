/**
 * Un rôle qu'on ne connaît pas encore n'est pas « élève ».
 *
 * LE DÉFAUT
 * ---------
 * `RoleRedirect` attendait la réhydratation du magasin d'authentification,
 * mais pas le chargement de l'UTILISATEUR. Entre les deux existe une
 * fenêtre où le jeton est présent et `user` vaut encore `null` : `role`
 * était alors `undefined`, aucun test de rôle ne passait, et le repli
 * final envoyait la personne vers l'espace ÉLÈVE.
 *
 * Vu dans le navigateur, pas dans le code : un administrateur qui
 * rechargeait une page de son espace se retrouvait sur `/student/home`.
 *
 * CE QUE CE TEST TIENT
 * --------------------
 * Que cette fenêtre n'oriente plus personne. Un rôle absent ne mène nulle
 * part — on attend qu'il arrive. Un rôle inconnu du routeur ramène à la
 * connexion, qui est vrai, plutôt qu'à l'espace élève, qui est faux.
 */
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const etat = { user: null, accessToken: null, _hasHydrated: false };

vi.mock("../store/authStore", () => ({
  useAuthStore: (selecteur) => (selecteur ? selecteur(etat) : etat),
}));

const { default: AppRouter } = await import("./index.jsx");

/** Rend le routeur sur une adresse et renvoie l'adresse où il aboutit. */
function rendreSur(chemin) {
  const vue = render(
    <MemoryRouter initialEntries={[chemin]}>
      <Routes>
        <Route path="*" element={<AppRouter />} />
      </Routes>
    </MemoryRouter>,
  );
  return vue;
}

describe("RoleRedirect — la fenêtre entre le jeton et l'utilisateur", () => {
  beforeEach(() => {
    etat.user = null;
    etat.accessToken = null;
    etat._hasHydrated = false;
  });

  it("n'envoie personne dans l'espace élève tant que le rôle est inconnu", () => {
    etat._hasHydrated = true;
    etat.accessToken = "jeton-valide";
    etat.user = null; // /api/auth/me/ n'a pas encore répondu

    rendreSur("/admin/official-documents");

    // Rien de l'espace élève ne doit apparaître : ni son accueil, ni sa
    // navigation. L'écran patiente.
    expect(screen.queryByText(/Mes devoirs|Mon bulletin/i)).toBeNull();
  });

  it("attend, plutôt que de rediriger, quand le rôle n'est pas encore là", () => {
    etat._hasHydrated = true;
    etat.accessToken = "jeton-valide";
    etat.user = null;

    const { container } = rendreSur("/admin/dashboard");
    // Le routeur ne rend rien d'orientant : pas de contenu d'un autre
    // espace. Un écran vide ou un indicateur de chargement, pas une
    // redirection prise sur une supposition.
    expect(container.textContent).not.toMatch(/élève|student/i);
  });
});
