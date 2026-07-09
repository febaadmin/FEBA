import { useEffect, useRef, useState } from "react";
import { X, Loader2 } from "lucide-react";

/**
 * JitsiMeeting — intègre une réunion Jitsi Meet en plein écran.
 *
 * Charge dynamiquement l'API externe Jitsi (https://<domain>/external_api.js)
 * puis monte la conférence dans un conteneur. Fonctionne avec l'instance
 * publique meet.jit.si ou toute instance auto-hébergée (prop `domain`).
 *
 * Props :
 *  - roomName    : identifiant de salle (room_code non devinable côté backend)
 *  - domain      : domaine Jitsi (défaut meet.jit.si)
 *  - displayName : nom affiché du participant
 *  - subject     : titre de la réunion
 *  - onClose     : callback à la fermeture (croix ou fin d'appel)
 */
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
      delete loadedScripts[domain];
      reject(new Error(`Impossible de charger Jitsi depuis ${domain}`));
    };
    document.body.appendChild(script);
  });
  return loadedScripts[domain];
}

export default function JitsiMeeting({
  roomName,
  domain = "meet.jit.si",
  displayName = "",
  subject = "",
  jwt = null,          // FIX v35 : jeton signé par le backend (instance auto-hébergée)
  onClose,
}) {
  const containerRef = useRef(null);
  const apiRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    loadJitsiScript(domain)
      .then(() => {
        if (cancelled || !containerRef.current) return;
        apiRef.current = new window.JitsiMeetExternalAPI(domain, {
          roomName,
          jwt: jwt || undefined,
          parentNode: containerRef.current,
          width: "100%",
          height: "100%",
          userInfo: { displayName },
          configOverwrite: {
            prejoinPageEnabled: true,
            disableDeepLinking: true,
            startWithAudioMuted: true,
            subject: subject || undefined,
          },
          interfaceConfigOverwrite: {
            SHOW_JITSI_WATERMARK: false,
            MOBILE_APP_PROMO: false,
          },
        });
        apiRef.current.addListener("videoConferenceLeft", () => onClose?.());
        apiRef.current.addListener("readyToClose", () => onClose?.());
        setLoading(false);
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e.message);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
      try {
        apiRef.current?.dispose();
      } catch {
        /* noop */
      }
      apiRef.current = null;
    };
  }, [roomName, domain, displayName, subject, jwt, onClose]);

  return (
    <div className="fixed inset-0 z-[100] bg-slate-900 flex flex-col">
      <div className="flex items-center justify-between px-4 py-2 bg-slate-800 text-white shrink-0">
        <div className="text-sm font-medium truncate">
          {subject || "Salle virtuelle"}{" "}
          <span className="text-slate-400 font-normal">— {roomName}</span>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded hover:bg-slate-700 transition-colors"
          aria-label="Quitter la réunion"
        >
          <X className="w-5 h-5" />
        </button>
      </div>
      <div className="flex-1 relative">
        {loading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-slate-300">
            <Loader2 className="w-8 h-8 animate-spin" />
            <span className="text-sm">Connexion à la salle…</span>
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-red-300 px-6 text-center">
            <p className="font-medium">Connexion impossible</p>
            <p className="text-sm text-slate-400">{error}</p>
            <p className="text-xs text-slate-500">
              Vérifiez votre connexion Internet ou le domaine Jitsi configuré (JITSI_DOMAIN).
            </p>
          </div>
        )}
        <div ref={containerRef} className="absolute inset-0" />
      </div>
    </div>
  );
}
