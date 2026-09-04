/**
 * JitsiMeeting — la conférence, et rien d'autre.
 *
 * LE DÉFAUT CORRIGÉ
 * -----------------
 * Un utilisateur entrait dans la salle, puis revenait à l'écran
 * « Rejoindre la réunion » au bout de quelques secondes — parfois
 * plusieurs fois, en laissant derrière lui plusieurs identités Jitsi du
 * même participant.
 *
 * Ce n'était ni le réseau, ni le JWT, ni Jitsi. C'était ceci :
 *
 *     }, [roomName, domain, displayName, subject, jwt, onClose]);
 *                                                    ^^^^^^^
 *
 * `onClose` était passé en fonction fléchée par le parent : une NOUVELLE
 * identité à chaque rendu. Et le parent se rendait tout seul, toutes les
 * 30 secondes, à cause du `refetchInterval` de la liste des salles. Donc
 * toutes les 30 secondes : effet nettoyé → `dispose()` → nouvelle
 * `JitsiMeetExternalAPI`. La conférence était détruite et recréée pendant
 * qu'on parlait dedans, et chaque recréation ouvrait une participation de
 * plus.
 *
 * LA RÈGLE QUI EN DÉCOULE
 * -----------------------
 * L'effet qui crée la conférence ne dépend QUE de ce qui définit la
 * conférence : la salle, le domaine, le jeton. Les rappels (`onClose`,
 * `onJoined`…) vivent dans des refs, mises à jour à chaque rendu : le
 * composant appelle toujours la dernière version sans jamais se recréer
 * pour autant.
 *
 * `displayName` et `subject` sont eux aussi sortis des dépendances : ce
 * sont des ornements. Changer un libellé n'est pas une raison de couper
 * la parole à quelqu'un.
 */
import { useEffect, useRef, useState } from "react";

/** Scripts `external_api.js` déjà chargés, par domaine. */
const loadedScripts = {};

function loadJitsiScript(domain) {
  if (loadedScripts[domain]) return loadedScripts[domain];

  loadedScripts[domain] = new Promise((resolve, reject) => {
    if (window.JitsiMeetExternalAPI) return resolve();
    const script = document.createElement("script");
    script.src = `https://${domain}/external_api.js`;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      // Un échec ne doit pas rester mémorisé : la tentative suivante doit
      // pouvoir réessayer plutôt que de recevoir la promesse rejetée.
      delete loadedScripts[domain];
      reject(new Error(`Impossible de charger l'interface Jitsi depuis ${domain}.`));
    };
    document.body.appendChild(script);
  });

  return loadedScripts[domain];
}

export default function JitsiMeeting({
  roomName,
  domain,
  displayName = "",
  subject = "",
  jwt = null,
  onClose,
  onJoined,
  onError,
}) {
  const containerRef = useRef(null);
  const apiRef = useRef(null);
  // `loading`/`error` décrivent LA conférence en cours. L'appelant
  // remonte le composant via une clé quand la salle change (voir
  // VirtualRoomSession) : inutile — et interdit — de les réinitialiser
  // par un setState synchrone au début de l'effet, ce qui déclenchait un
  // rendu en cascade à chaque montage.
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // ── Rappels stables ───────────────────────────────────────────────────
  // Mis à jour à chaque rendu, mais jamais dépendances de l'effet : c'est
  // toute la correction. Le composant appelle la dernière version connue
  // sans que son changement d'identité ne détruise la conférence.
  const onCloseRef = useRef(onClose);
  const onJoinedRef = useRef(onJoined);
  const onErrorRef = useRef(onError);
  const displayNameRef = useRef(displayName);
  const subjectRef = useRef(subject);
  useEffect(() => {
    onCloseRef.current = onClose;
    onJoinedRef.current = onJoined;
    onErrorRef.current = onError;
    displayNameRef.current = displayName;
    subjectRef.current = subject;
  });

  useEffect(() => {
    // Rien à faire tant que la salle n'est pas connue : monter une
    // conférence sur un domaine vide produit l'écran noir.
    if (!roomName || !domain) return undefined;

    let cancelled = false;
    // Les écouteurs sont retenus pour être retirés un par un : `dispose()`
    // seul laissait des fermetures vivantes si l'API était déjà détruite.
    const listeners = [];

    loadJitsiScript(domain)
      .then(() => {
        if (cancelled || !containerRef.current) return;

        // GARDE ANTI-DOUBLE MONTAGE (React StrictMode monte, démonte et
        // remonte chaque composant en développement). Sans elle, deux
        // conférences se créaient et l'utilisateur apparaissait deux fois
        // dans sa propre réunion.
        if (apiRef.current) return;

        const api = new window.JitsiMeetExternalAPI(domain, {
          roomName,
          jwt: jwt || undefined,
          parentNode: containerRef.current,
          width: "100%",
          height: "100%",
          userInfo: { displayName: displayNameRef.current },
          configOverwrite: {
            prejoinPageEnabled: false,
            disableDeepLinking: true,
            startWithAudioMuted: true,
            subject: subjectRef.current || undefined,
          },
          interfaceConfigOverwrite: {
            SHOW_JITSI_WATERMARK: false,
            MOBILE_APP_PROMO: false,
          },
        });
        apiRef.current = api;

        const on = (event, handler) => {
          api.addListener(event, handler);
          listeners.push([event, handler]);
        };

        on("videoConferenceJoined", () => onJoinedRef.current?.());
        on("videoConferenceLeft", () => onCloseRef.current?.());
        on("readyToClose", () => onCloseRef.current?.());
        on("errorOccurred", (e) => onErrorRef.current?.(e));

        setLoading(false);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e.message);
        setLoading(false);
        onErrorRef.current?.(e);
      });

    return () => {
      cancelled = true;
      const api = apiRef.current;
      apiRef.current = null;
      if (!api) return;
      for (const [event, handler] of listeners) {
        try {
          api.removeListener(event, handler);
        } catch {
          /* l'API peut déjà être détruite : rien à retirer */
        }
      }
      try {
        api.dispose();
      } catch {
        /* noop */
      }
    };
    // DÉPENDANCES VOLONTAIREMENT RÉDUITES À L'IDENTITÉ DE LA CONFÉRENCE.
    // Y remettre un rappel ou un libellé ferait réapparaître le défaut.
  }, [roomName, domain, jwt]);

  if (error) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-slate-900 p-6">
        <div className="max-w-md text-center text-slate-200">
          <p className="font-semibold mb-2">Visioconférence indisponible</p>
          <p className="text-sm opacity-90">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full bg-slate-900">
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center text-slate-300 text-sm">
          Connexion à la salle…
        </div>
      )}
      <div ref={containerRef} className="w-full h-full" data-testid="jitsi-container" />
    </div>
  );
}
