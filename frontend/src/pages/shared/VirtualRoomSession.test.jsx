/**
 * La conférence dans son propre onglet.
 *
 * CE QUE CES TESTS EMPÊCHENT DE REVENIR
 * -------------------------------------
 * La conférence s'ouvrait dans une modale posée sur le tableau de bord.
 * La page dessous rafraîchissait la liste des salles toutes les 30
 * secondes, se rendait à nouveau, et emportait la conférence avec elle.
 * Corriger `JitsiMeeting` ne suffisait pas : tant que la conférence vit
 * dans l'arbre React du tableau de bord, elle reste à la merci de tout ce
 * qui s'y passe.
 *
 * Ces tests portent sur les garanties de la nouvelle route :
 *   - une seule adhésion, même sous StrictMode ;
 *   - un seul départ, quelle que soit la façon dont l'onglet se termine ;
 *   - aucun jeton dans l'URL ;
 *   - aucun élément de mise en page FEBA autour de la conférence.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { StrictMode } from "react";

vi.mock("../../api", () => ({
  virtualAPI: { join: vi.fn(), leave: vi.fn() },
}));
// La portée d'académie est pilotée par le test : c'est elle qui décide
// QUAND la première requête a le droit de partir.
vi.mock("../../context/AcademyContext", () => ({
  useAcademy: () => academie,
}));
// La conférence elle-même est testée dans components/JitsiMeeting.test.jsx.
// Ici on l'observe : quelles props reçoit-elle, et combien de fois ?
vi.mock("../../components/JitsiMeeting", () => ({
  default: (props) => {
    montages.push(props);
    return (
      <div data-testid="jitsi">
        <button onClick={() => props.onClose?.()}>quitter</button>
        <button onClick={() => props.onError?.(new Error("panne"))}>panne</button>
      </div>
    );
  },
}));

import { virtualAPI } from "../../api";
import { useAuthStore } from "../../store/authStore";
import VirtualRoomSession from "./VirtualRoomSession";

/** Props reçues par JitsiMeeting, dans l'ordre des montages. */
let montages = [];
/** Ce que renvoie `useAcademy()` pendant un test. */
let academie = { scopeReady: true, hasAcademyError: false };

const SALLE = {
  id: 7,
  name: "Cours de français — French Ambassadors",
  room_code: "feba-fha-7-abc",
  join_domain: "meet.globalfeba.com",
  jwt: "jeton.signe.par.le.backend",
};

function ouvrir(id = "7") {
  return render(
    <MemoryRouter initialEntries={[`/virtual-room/${id}/join`]}>
      <Routes>
        <Route path="/virtual-room/:id/join" element={<VirtualRoomSession />} />
      </Routes>
    </MemoryRouter>,
  );
}

/** Laisse la promesse d'adhésion se résoudre. */
async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

beforeEach(() => {
  montages = [];
  academie = { scopeReady: true, hasAcademyError: false };
  vi.clearAllMocks();
  virtualAPI.join.mockResolvedValue({ data: SALLE });
  virtualAPI.leave.mockResolvedValue({ data: {} });
  useAuthStore.setState({
    user: { username: "akoffi", first_name: "Awa", last_name: "Koffi" },
  });
});

afterEach(() => {
  useAuthStore.setState({ user: null });
});

describe("VirtualRoomSession — adhésion", () => {
  it("adhère une seule fois et transmet la salle à la conférence", async () => {
    ouvrir();
    await flush();

    expect(virtualAPI.join).toHaveBeenCalledTimes(1);
    expect(virtualAPI.join).toHaveBeenCalledWith("7");

    const props = montages.at(-1);
    expect(props.roomName).toBe(SALLE.room_code);
    expect(props.domain).toBe(SALLE.join_domain);
    expect(props.jwt).toBe(SALLE.jwt);
    expect(props.displayName).toBe("Awa Koffi");
  });

  it("n'adhère qu'une fois sous StrictMode (double montage)", async () => {
    // Sans la garde `joinRequested`, le backend enregistrait DEUX
    // participations pour une seule personne — le « participant en
    // double » observé en réunion.
    render(
      <StrictMode>
        <MemoryRouter initialEntries={["/virtual-room/7/join"]}>
          <Routes>
            <Route path="/virtual-room/:id/join" element={<VirtualRoomSession />} />
          </Routes>
        </MemoryRouter>
      </StrictMode>,
    );
    await flush();
    expect(virtualAPI.join).toHaveBeenCalledTimes(1);
  });
});

describe("VirtualRoomSession — le jeton ne transite pas par l'URL", () => {
  it("l'URL ne contient que l'identifiant de la salle", async () => {
    ouvrir();
    await flush();

    // Un jeton dans l'URL se retrouve dans l'historique du navigateur,
    // les journaux du proxy et les signets.
    expect(window.location.href).not.toContain(SALLE.jwt);
    expect(window.location.search).toBe("");
    expect(window.location.hash).toBe("");
  });

  it("demande le jeton au backend plutôt que de le recevoir en paramètre", async () => {
    ouvrir();
    await flush();
    // Une seule source possible : l'appel `join`, en session same-origin.
    expect(virtualAPI.join).toHaveBeenCalledTimes(1);
    expect(montages.at(-1).jwt).toBe(SALLE.jwt);
  });
});

describe("VirtualRoomSession — départ", () => {
  it("signale le départ une seule fois quand on raccroche", async () => {
    ouvrir();
    await flush();

    // Jitsi émet `videoConferenceLeft` PUIS `readyToClose` quand on
    // raccroche : les deux appellent onClose. Sans la garde `leaveSent`,
    // deux départs partaient pour une seule sortie.
    const { onClose } = montages.at(-1);
    await act(async () => { onClose(); });
    await act(async () => { onClose(); });

    expect(virtualAPI.leave).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(/Vous avez quitté la réunion/i)).toBeTruthy();
  });

  it("signale le départ quand l'onglet est fermé", async () => {
    ouvrir();
    await flush();

    // Sans cela la participation restait « en cours » indéfiniment et
    // faussait les durées de réunion.
    await act(async () => { window.dispatchEvent(new Event("pagehide")); });
    expect(virtualAPI.leave).toHaveBeenCalledTimes(1);
  });

  it("ne signale pas deux fois si on raccroche PUIS ferme l'onglet", async () => {
    ouvrir();
    await flush();
    await act(async () => { montages.at(-1).onClose(); });
    await act(async () => { window.dispatchEvent(new Event("pagehide")); });
    expect(virtualAPI.leave).toHaveBeenCalledTimes(1);
  });

  it("un départ que le backend refuse ne casse pas l'écran", async () => {
    virtualAPI.leave.mockRejectedValue(new Error("réseau"));
    ouvrir();
    await flush();
    await act(async () => { montages.at(-1).onClose(); });
    await flush();
    // Le départ est une trace, pas un blocage.
    expect(await screen.findByText(/Vous avez quitté la réunion/i)).toBeTruthy();
  });
});

describe("VirtualRoomSession — pas de mise en page FEBA", () => {
  it("n'affiche ni barre latérale ni en-tête autour de la conférence", async () => {
    const { container } = ouvrir();
    await flush();

    expect(screen.getByTestId("virtual-room-session")).toBeTruthy();
    // La conférence occupe l'onglet entier : rien de l'application
    // autour, sinon on retrouve exactement le contexte qui la coupait.
    expect(container.querySelector("nav")).toBeNull();
    expect(container.querySelector("aside")).toBeNull();
    expect(container.querySelector("header")).toBeNull();
  });

  it("occupe tout l'écran", async () => {
    ouvrir();
    await flush();
    const cadre = screen.getByTestId("virtual-room-session");
    expect(cadre.className).toContain("fixed");
    expect(cadre.className).toContain("inset-0");
  });
});

describe("VirtualRoomSession — échecs", () => {
  it("dit pourquoi quand le backend refuse l'accès", async () => {
    virtualAPI.join.mockRejectedValue({
      response: { status: 403, data: { detail: "Vous n'êtes pas convié à cette salle." } },
    });
    ouvrir();
    expect(await screen.findByText(/Impossible de rejoindre la salle/i)).toBeTruthy();
    expect(await screen.findByText(/pas convié/i)).toBeTruthy();
    expect(montages).toHaveLength(0);
  });

  it("refuse de basculer vers un service public quand l'académie n'a pas de domaine", async () => {
    // INTERDICTION ABSOLUE : jamais de repli sur meet.jit.si. Une salle
    // sans domaine auto-hébergé ne s'ouvre pas, elle s'explique.
    virtualAPI.join.mockResolvedValue({ data: { ...SALLE, join_domain: null } });
    ouvrir();
    expect(await screen.findByText(/Impossible de rejoindre la salle/i)).toBeTruthy();
    expect(await screen.findByText(/aucune session n'est basculée vers un service public/i))
      .toBeTruthy();
    expect(montages).toHaveLength(0);
  });

  it("une panne de la conférence clôt proprement la participation", async () => {
    ouvrir();
    await flush();
    await act(async () => { montages.at(-1).onError(new Error("panne")); });
    expect(virtualAPI.leave).toHaveBeenCalledTimes(1);
  });
});


describe("VirtualRoomSession — la portée d'académie d'abord", () => {
  /**
   * DEUX DÉFAUTS TROUVÉS EN NAVIGATEUR, PAS EN TEST UNITAIRE.
   *
   * L'onglet restait indéfiniment sur « Ouverture de la salle… », même
   * quand le backend avait répondu « visioconférence indisponible ». Deux
   * causes se superposaient, et chacune suffisait :
   *
   *  1. la garde anti-double-adhésion empêchait la seconde exécution de
   *     l'effet (StrictMode) de relancer la requête, pendant que le
   *     nettoyage de la première posait `cancelled = true` : le résultat
   *     de la SEULE requête en vol était donc jeté ;
   *
   *  2. cette route vit à la racine du routeur, hors du garde
   *     `AcademyScopedOutlet`. `join()` partait sous la portée UNKNOWN et
   *     `setAcademyScope()` l'annulait dès l'arrivée du contexte
   *     d'académie — exactement le scénario que le commentaire de
   *     `AcademyScopedOutlet` décrit pour les écrans métier.
   *
   * Un écran d'attente perpétuel est précisément ce que cette page devait
   * supprimer : ces tests le tiennent.
   */

  it("n'appelle pas join tant que la portée n'est pas posée", async () => {
    academie = { scopeReady: false, hasAcademyError: false };
    ouvrir();
    await flush();
    // Partir trop tôt, c'est partir sous la portée UNKNOWN — et se faire
    // annuler sans jamais réessayer.
    expect(virtualAPI.join).not.toHaveBeenCalled();
    expect(await screen.findByText(/Ouverture de la salle/i)).toBeTruthy();
  });

  it("adhère dès que la portée est posée", async () => {
    academie = { scopeReady: false, hasAcademyError: false };
    const { rerender } = render(
      <MemoryRouter initialEntries={["/virtual-room/7/join"]}>
        <Routes>
          <Route path="/virtual-room/:id/join" element={<VirtualRoomSession />} />
        </Routes>
      </MemoryRouter>,
    );
    await flush();
    expect(virtualAPI.join).not.toHaveBeenCalled();

    academie = { scopeReady: true, hasAcademyError: false };
    rerender(
      <MemoryRouter initialEntries={["/virtual-room/7/join"]}>
        <Routes>
          <Route path="/virtual-room/:id/join" element={<VirtualRoomSession />} />
        </Routes>
      </MemoryRouter>,
    );
    await flush();
    expect(virtualAPI.join).toHaveBeenCalledTimes(1);
  });

  it("affiche l'échec même sous StrictMode (plus d'attente perpétuelle)", async () => {
    // LE DÉFAUT EXACT OBSERVÉ EN NAVIGATEUR : sous StrictMode, le
    // résultat de l'unique requête était jeté et l'onglet ne quittait
    // jamais « Ouverture de la salle… ».
    virtualAPI.join.mockRejectedValue({
      response: { status: 503, data: { detail: "L'instance FEBA n'est pas joignable." } },
    });
    render(
      <StrictMode>
        <MemoryRouter initialEntries={["/virtual-room/7/join"]}>
          <Routes>
            <Route path="/virtual-room/:id/join" element={<VirtualRoomSession />} />
          </Routes>
        </MemoryRouter>
      </StrictMode>,
    );

    expect(await screen.findByText(/Impossible de rejoindre la salle/i)).toBeTruthy();
    expect(await screen.findByText(/pas joignable/i)).toBeTruthy();
    expect(screen.queryByText(/Ouverture de la salle/i)).toBeNull();
  });

  it("affiche la réussite même sous StrictMode", async () => {
    render(
      <StrictMode>
        <MemoryRouter initialEntries={["/virtual-room/7/join"]}>
          <Routes>
            <Route path="/virtual-room/:id/join" element={<VirtualRoomSession />} />
          </Routes>
        </MemoryRouter>
      </StrictMode>,
    );
    expect(await screen.findByTestId("virtual-room-session")).toBeTruthy();
    expect(virtualAPI.join).toHaveBeenCalledTimes(1);
  });

  it("dit quoi faire quand la portée d'académie est introuvable", async () => {
    academie = { scopeReady: false, hasAcademyError: true };
    ouvrir();
    await flush();
    expect(await screen.findByText(/Impossible de rejoindre la salle/i)).toBeTruthy();
    expect(await screen.findByText(/portée d'académie n'a pas pu être déterminée/i)).toBeTruthy();
    expect(virtualAPI.join).not.toHaveBeenCalled();
  });
});
