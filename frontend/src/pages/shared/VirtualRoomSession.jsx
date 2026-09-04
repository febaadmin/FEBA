/**
 * VirtualRoomSession — la conférence, seule, dans son propre onglet.
 *
 * CE QUI REMPLACE LA MODALE
 * -------------------------
 * La conférence s'ouvrait par-dessus le tableau de bord : une modale,
 * posée sur une page qui continuait de vivre derrière elle. Cette page
 * rafraîchissait la liste des salles toutes les 30 secondes, se rendait à
 * nouveau, et détruisait la conférence au passage (voir
 * `components/JitsiMeeting.jsx`).
 *
 * Corriger le composant ne suffisait pas : tant que la conférence vit
 * dans l'arbre React du tableau de bord, elle reste à la merci de tout ce
 * qui s'y passe — un poll, une invalidation de cache, une navigation.
 * Cette route la met hors de portée. Elle est montée à la RACINE du
 * routeur, sans layout : ni barre latérale, ni en-tête, ni tableau de
 * bord derrière, ni modale. Jitsi occupe l'onglet entier.
 *
 * LE JETON NE TRANSITE PAS PAR L'URL
 * ----------------------------------
 * L'onglet est ouvert en same-origin ; la session FEBA y est donc déjà
 * valide. Cette page appelle elle-même `virtualAPI.join(id)`, reçoit le
 * JWT signé par le backend, et le garde en mémoire. L'URL ne contient que
 * l'identifiant de la salle — rien qui traîne dans un historique, un
 * journal de proxy ou un signet.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import JitsiMeeting from "../../components/JitsiMeeting";
import { virtualAPI } from "../../api";
import { useAuthStore } from "../../store/authStore";
import { extractApiError } from "../../utils/errors";

/**
 * Pourquoi l'accès a été refusé, dans les mots du backend.
 *
 * `extractApiError` répond « Vous n'avez pas la permission d'effectuer
 * cette action » à tout 403 — une généralisation utile ailleurs, où
 * l'utilisateur peut revenir en arrière et essayer autre chose. Ici
 * l'onglet est un cul-de-sac : il ne contient rien d'autre que la
 * conférence. Un enseignant à qui l'on répond « pas la permission »
 * n'apprend pas que la classe ne lui est pas affectée, et rien à l'écran
 * ne le lui dira.
 *
 * Les messages de `assert_can_join` sont écrits pour être lus par
 * l'utilisateur et ne divulguent aucun détail interne ; on les affiche
 * tels quels, et on retombe sur le message générique sinon.
 */
function raisonDuRefus(e) {
  const detail = e?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  return extractApiError(e);
}

const PHASE = {
  JOINING: "joining",
  IN_CALL: "in_call",
  LEFT: "left",
  ERROR: "error",
};

export default function VirtualRoomSession() {
  const { id } = useParams();
  const user = useAuthStore((s) => s.user);

  const [phase, setPhase] = useState(PHASE.JOINING);
  const [meeting, setMeeting] = useState(null);
  const [error, setError] = useState("");

  // GARDE ANTI-DOUBLE ADHÉSION.
  //
  // React StrictMode exécute chaque effet deux fois en développement, et
  // un rafraîchissement rapide de l'onglet peut relancer la séquence. Sans
  // cette garde, le backend enregistrait deux participations pour une
  // seule personne — le « participant en double » observé en réunion.
  const joinRequested = useRef(false);
  // Le départ est signalé au plus une fois, quelle que soit la façon dont
  // l'onglet se termine (bouton raccrocher, fermeture, rechargement).
  const leaveSent = useRef(false);

  useEffect(() => {
    if (joinRequested.current || !id) return;
    joinRequested.current = true;

    let cancelled = false;
    virtualAPI
      .join(id)
      .then(({ data }) => {
        if (cancelled) return;
        if (!data?.join_domain) {
          setError(
            "La visioconférence n'est pas configurée pour cette académie. " +
            "Contactez l'administration : aucune session n'est basculée vers " +
            "un service public.",
          );
          setPhase(PHASE.ERROR);
          return;
        }
        setMeeting(data);
        setPhase(PHASE.IN_CALL);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(raisonDuRefus(e));
        setPhase(PHASE.ERROR);
      });

    return () => {
      cancelled = true;
    };
  }, [id]);

  /**
   * Signale le départ au backend, une seule fois.
   *
   * `useCallback` plutôt qu'une ref assignée pendant le rendu : écrire
   * dans une ref au moment du rendu est interdit par React (le rendu doit
   * rester pur) et se voit à l'exécution en mode concurrent.
   */
  const sendLeave = useCallback(() => {
    if (leaveSent.current || !id) return;
    leaveSent.current = true;
    virtualAPI.leave(id).catch(() => {
      /* le départ est une trace, pas un blocage : on ne dérange pas
         l'utilisateur si elle n'a pas pu être enregistrée */
    });
  }, [id]);

  // Fermeture de l'onglet ou rechargement : la participation doit être
  // close, sinon elle reste « en cours » indéfiniment et fausse les durées.
  useEffect(() => {
    const onUnload = () => sendLeave();
    window.addEventListener("pagehide", onUnload);
    return () => window.removeEventListener("pagehide", onUnload);
  }, [sendLeave]);

  const titre = meeting?.name || "Salle virtuelle";
  useEffect(() => {
    document.title = `${titre} — FEBA`;
  }, [titre]);

  if (phase === PHASE.ERROR) {
    return (
      <Plein>
        <div className="max-w-lg text-center">
          <h1 className="text-lg font-semibold text-white mb-3">
            Impossible de rejoindre la salle
          </h1>
          <p className="text-slate-300 text-sm leading-relaxed">{error}</p>
          <button
            type="button"
            onClick={() => window.close()}
            className="mt-6 px-4 py-2 rounded-lg bg-slate-700 text-white text-sm hover:bg-slate-600"
          >
            Fermer cet onglet
          </button>
        </div>
      </Plein>
    );
  }

  if (phase === PHASE.LEFT) {
    return (
      <Plein>
        <div className="max-w-lg text-center">
          <h1 className="text-lg font-semibold text-white mb-3">
            Vous avez quitté la réunion
          </h1>
          <p className="text-slate-300 text-sm">{titre}</p>
          <button
            type="button"
            onClick={() => window.close()}
            className="mt-6 px-4 py-2 rounded-lg bg-slate-700 text-white text-sm hover:bg-slate-600"
          >
            Fermer cet onglet
          </button>
        </div>
      </Plein>
    );
  }

  if (phase === PHASE.JOINING || !meeting) {
    return (
      <Plein>
        <p className="text-slate-300 text-sm">Ouverture de la salle…</p>
      </Plein>
    );
  }

  return (
    <div
      className="fixed inset-0 w-screen h-screen bg-slate-900 overflow-hidden"
      data-testid="virtual-room-session"
    >
      <JitsiMeeting
        // Clé de remontage : si la salle change, on veut une conférence
        // NEUVE, pas une mutation de l'existante.
        key={`${meeting.join_domain}:${meeting.room_code}`}
        roomName={meeting.room_code}
        domain={meeting.join_domain}
        jwt={meeting.jwt || null}
        subject={meeting.name}
        displayName={
          user
            ? `${user.first_name || ""} ${user.last_name || ""}`.trim() || user.username
            : ""
        }
        onClose={() => {
          sendLeave();
          setPhase(PHASE.LEFT);
        }}
        onError={() => sendLeave()}
      />
    </div>
  );
}

/** Écran plein, sans layout : même cadre pour tous les états. */
function Plein({ children }) {
  return (
    <div className="fixed inset-0 w-screen h-screen bg-slate-900 flex items-center justify-center p-6">
      {children}
    </div>
  );
}
