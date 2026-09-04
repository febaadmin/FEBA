/**
 * Le cycle de vie de la conférence.
 *
 * CE QUE CES TESTS EMPÊCHENT DE REVENIR
 * -------------------------------------
 * Un participant était renvoyé à l'écran « Rejoindre la réunion » toutes
 * les 30 secondes, en laissant une identité Jitsi de plus derrière lui à
 * chaque fois. La cause tenait à une seule ligne :
 *
 *     }, [roomName, domain, displayName, subject, jwt, onClose]);
 *
 * `onClose` était une fonction fléchée créée par le parent — donc une
 * nouvelle identité à chaque rendu — et le parent se rendait tout seul
 * toutes les 30 secondes (`refetchInterval` de la liste des salles). La
 * conférence était donc détruite et recréée pendant qu'on parlait dedans.
 *
 * Ces tests portent sur ce qui compte : COMBIEN de conférences sont
 * créées, et QUAND l'ancienne est détruite.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, act } from "@testing-library/react";

import JitsiMeeting from "./JitsiMeeting";

/** Instances créées pendant un test, dans l'ordre. */
let instances = [];

class FakeJitsiApi {
  constructor(domain, options) {
    this.domain = domain;
    this.options = options;
    this.listeners = new Map();
    this.disposed = false;
    instances.push(this);
  }
  addListener(event, handler) {
    if (!this.listeners.has(event)) this.listeners.set(event, []);
    this.listeners.get(event).push(handler);
  }
  removeListener(event, handler) {
    const list = this.listeners.get(event) || [];
    const i = list.indexOf(handler);
    if (i >= 0) list.splice(i, 1);
  }
  emit(event, payload) {
    for (const h of this.listeners.get(event) || []) h(payload);
  }
  /** Nombre total d'écouteurs encore branchés, tous événements confondus. */
  listenerCount() {
    let n = 0;
    for (const list of this.listeners.values()) n += list.length;
    return n;
  }
  dispose() {
    this.disposed = true;
  }
}

const PROPS = {
  roomName: "feba-fha-salle-1",
  domain: "meet.globalfeba.com",
  jwt: "jeton-signe-par-le-backend",
  displayName: "Awa Koffi",
  subject: "French Ambassadors",
};

/** Laisse la promesse de chargement du script se résoudre. */
async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

beforeEach(() => {
  instances = [];
  // `external_api.js` est déjà « chargé » : le composant n'insère alors
  // aucune balise script et va droit à la création de la conférence.
  window.JitsiMeetExternalAPI = FakeJitsiApi;
});

afterEach(() => {
  delete window.JitsiMeetExternalAPI;
  vi.restoreAllMocks();
});

describe("JitsiMeeting — création de la conférence", () => {
  it("crée exactement une conférence", async () => {
    render(<JitsiMeeting {...PROPS} onClose={() => {}} />);
    await flush();
    expect(instances).toHaveLength(1);
    expect(instances[0].options.roomName).toBe(PROPS.roomName);
    expect(instances[0].options.jwt).toBe(PROPS.jwt);
  });

  it("ne crée rien tant que la salle ou le domaine manquent", async () => {
    const { rerender } = render(
      <JitsiMeeting {...PROPS} roomName="" onClose={() => {}} />,
    );
    await flush();
    expect(instances).toHaveLength(0);

    rerender(<JitsiMeeting {...PROPS} domain="" onClose={() => {}} />);
    await flush();
    expect(instances).toHaveLength(0);
  });
});

describe("JitsiMeeting — le défaut d'origine", () => {
  it("un onClose d'identité NOUVELLE ne détruit pas la conférence", async () => {
    // Reproduit exactement le parent fautif : une fonction fléchée
    // recréée à chaque rendu.
    const { rerender } = render(
      <JitsiMeeting {...PROPS} onClose={() => {}} />,
    );
    await flush();
    const premiere = instances[0];

    for (let i = 0; i < 5; i++) {
      rerender(<JitsiMeeting {...PROPS} onClose={() => {}} />);
      await flush();
    }

    expect(instances).toHaveLength(1);
    expect(premiere.disposed).toBe(false);
  });

  it("un rerender du parent ne crée aucune conférence supplémentaire", async () => {
    const { rerender } = render(
      <JitsiMeeting {...PROPS} onClose={() => {}} onJoined={() => {}} />,
    );
    await flush();

    // Ce que fait le `refetchInterval` de la liste des salles : le parent
    // se rend à nouveau, avec des rappels neufs à chaque fois.
    for (let i = 0; i < 10; i++) {
      rerender(
        <JitsiMeeting {...PROPS} onClose={() => {}} onJoined={() => {}} />,
      );
      await flush();
    }
    expect(instances).toHaveLength(1);
    expect(instances[0].disposed).toBe(false);
  });

  it("changer le libellé affiché ne coupe pas la conférence", async () => {
    const { rerender } = render(
      <JitsiMeeting {...PROPS} onClose={() => {}} />,
    );
    await flush();
    rerender(
      <JitsiMeeting {...PROPS} displayName="Autre nom" subject="Autre sujet" onClose={() => {}} />,
    );
    await flush();
    expect(instances).toHaveLength(1);
    expect(instances[0].disposed).toBe(false);
  });

  it("appelle TOUJOURS la dernière version de onClose", async () => {
    const premier = vi.fn();
    const dernier = vi.fn();
    const { rerender } = render(<JitsiMeeting {...PROPS} onClose={premier} />);
    await flush();
    rerender(<JitsiMeeting {...PROPS} onClose={dernier} />);
    await flush();

    act(() => instances[0].emit("readyToClose"));

    // Le rappel n'est pas figé à la valeur du premier rendu : c'est ce que
    // garantit la ref, et c'est ce qui permet de le sortir des dépendances.
    expect(premier).not.toHaveBeenCalled();
    expect(dernier).toHaveBeenCalledTimes(1);
  });
});

describe("JitsiMeeting — changement réel de salle", () => {
  it("recrée la conférence et détruit l'ancienne", async () => {
    const { rerender } = render(<JitsiMeeting {...PROPS} onClose={() => {}} />);
    await flush();
    const premiere = instances[0];

    rerender(<JitsiMeeting {...PROPS} roomName="une-autre-salle" onClose={() => {}} />);
    await flush();

    expect(instances).toHaveLength(2);
    expect(premiere.disposed).toBe(true);
    expect(instances[1].options.roomName).toBe("une-autre-salle");
  });

  it("recrée la conférence quand le jeton change", async () => {
    const { rerender } = render(<JitsiMeeting {...PROPS} onClose={() => {}} />);
    await flush();
    rerender(<JitsiMeeting {...PROPS} jwt="autre-jeton" onClose={() => {}} />);
    await flush();
    expect(instances).toHaveLength(2);
    expect(instances[0].disposed).toBe(true);
  });
});

describe("JitsiMeeting — démontage", () => {
  it("détruit la conférence une seule fois", async () => {
    const { unmount } = render(<JitsiMeeting {...PROPS} onClose={() => {}} />);
    await flush();
    const api = instances[0];
    const dispose = vi.spyOn(api, "dispose");

    unmount();

    expect(dispose).toHaveBeenCalledTimes(1);
  });

  it("retire ses écouteurs au démontage", async () => {
    const { unmount } = render(
      <JitsiMeeting {...PROPS} onClose={() => {}} onJoined={() => {}} onError={() => {}} />,
    );
    await flush();
    const api = instances[0];
    expect(api.listenerCount()).toBeGreaterThan(0);

    unmount();

    // Des écouteurs laissés derrière retiennent le composant démonté et
    // rappellent des `setState` sur un arbre qui n'existe plus.
    expect(api.listenerCount()).toBe(0);
  });

  it("n'accumule pas d'écouteurs au fil des rerenders", async () => {
    const { rerender } = render(<JitsiMeeting {...PROPS} onClose={() => {}} />);
    await flush();
    const depart = instances[0].listenerCount();

    for (let i = 0; i < 5; i++) {
      rerender(<JitsiMeeting {...PROPS} onClose={() => {}} />);
      await flush();
    }
    expect(instances[0].listenerCount()).toBe(depart);
  });
});

describe("JitsiMeeting — erreurs", () => {
  it("affiche un message, jamais un écran noir muet", async () => {
    delete window.JitsiMeetExternalAPI;

    // Le script ne se charge jamais. On n'intercepte QUE les balises
    // <script> : un mock global d'appendChild empêcherait aussi
    // testing-library d'attacher son conteneur, et le composant n'aurait
    // même pas la chance de s'afficher.
    const original = document.body.appendChild.bind(document.body);
    const ajout = vi
      .spyOn(document.body, "appendChild")
      .mockImplementation((node) => {
        if (node.tagName === "SCRIPT") {
          setTimeout(() => node.onerror?.(), 0);
          return node;
        }
        return original(node);
      });

    const { findByText } = render(
      <JitsiMeeting {...PROPS} domain="instance-injoignable.test" onClose={() => {}} />,
    );

    // Message explicite, pas un écran noir muet.
    expect(await findByText(/Visioconférence indisponible/i)).toBeTruthy();
    ajout.mockRestore();
  });
});
