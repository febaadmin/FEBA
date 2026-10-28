/**
 * VirtualRoomSession — la conférence, seule, dans son propre onglet.
 *
 * PLUGNMEET (moteur par défaut)
 * -----------------------------
 * Cette page demande au backend `virtualAPI.join(id)`. Le backend vérifie
 * les droits FEBA (académie, rôle, classe, état de la salle), ouvre ou
 * retrouve la réunion plugNmeet et renvoie une URL contenant un jeton
 * d'adhésion À USAGE UNIQUE. L'onglet s'y rend aussitôt
 * (`location.replace` : le jeton ne reste pas dans l'historique, le
 * bouton « Précédent » ne le rejoue pas). Ni la clé ni le secret de l'API
 * plugNmeet n'existent dans le navigateur.
 *
 * À la sortie, plugNmeet renvoie l'onglet vers /virtual-room/:id/ended
 * (page FEBA) — la session FEBA n'a jamais été touchée : les jetons FEBA
 * restent dans le stockage partagé, maintenus à jour par l'onglet FEBA
 * principal (hooks/useSessionKeepAlive) et renouvelés au besoin ici.
 *
 * JITSI (retour arrière, VIDEO_PROVIDER=jitsi)
 * --------------------------------------------
 * La conférence est intégrée dans la page (components/JitsiMeeting), comme
 * dans les versions précédentes.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import JitsiMeeting from "../../components/JitsiMeeting";
import { virtualAPI } from "../../api";
import { useAcademy } from "../../context/AcademyContext";
import { t } from "../../i18n";
import { useBranding } from "../../hooks/useBranding";
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
  REDIRECTING: "redirecting",
  IN_CALL: "in_call",
  LEFT: "left",
  ERROR: "error",
};

export default function VirtualRoomSession() {
  const { id } = useParams();
  const user = useAuthStore((s) => s.user);
  // LA PORTÉE D'ACADÉMIE DOIT ÊTRE POSÉE AVANT LA PREMIÈRE REQUÊTE.
  //
  // Les écrans métier sont montés sous `AcademyScopedOutlet`, qui ne les
  // rend qu'une fois `scopeReady`. Cette route-ci vit à la RACINE du
  // routeur — c'est tout son intérêt, elle n'a ni barre latérale ni
  // en-tête — et échappait donc à ce garde.
  //
  // Conséquence observée en navigateur : `join()` partait sous la portée
  // UNKNOWN, `setAcademyScope()` l'annulait à l'arrivée du contexte
  // (`abortInflightRequests`), et l'onglet restait indéfiniment sur
  // « Ouverture de la salle… ». Le garde n'est pas contourné ici : il est
  // simplement appliqué à la main, faute de pouvoir hériter de l'Outlet.
  const { scopeReady, hasAcademyError } = useAcademy();

  const [phase, setPhase] = useState(PHASE.JOINING);
  const [meeting, setMeeting] = useState(null);
  const [error, setError] = useState("");

  // GARDE ANTI-DOUBLE ADHÉSION.
  //
  // React StrictMode exécute chaque effet deux fois en développement, et
  // un rafraîchissement rapide de l'onglet peut relancer la séquence. Sans
  // cette garde, le backend enregistrait deux participations pour une
  // seule personne — le « participant en double » observé en réunion.
  //
  // ELLE RETIENT L'IDENTIFIANT, PAS UN BOOLÉEN. Un booléen bloquait aussi
  // le changement de salle : l'onglet resté ouvert sur /virtual-room/3
  // puis mené vers /virtual-room/8 n'adhérait jamais à la seconde.
  const demandePour = useRef(null);
  // Le départ est signalé au plus une fois, quelle que soit la façon dont
  // l'onglet se termine (bouton raccrocher, fermeture, rechargement).
  const leaveSent = useRef(false);

  useEffect(() => {
    if (!scopeReady || !id || demandePour.current === id) return;
    demandePour.current = id;

    // PAS DE DRAPEAU `cancelled` ICI, ET C'EST LE CŒUR DU CORRECTIF.
    //
    // Le nettoyage de l'effet posait `cancelled = true`, et la garde
    // anti-double-adhésion empêchait la seconde exécution de relancer la
    // requête. En développement, React StrictMode monte, démonte puis
    // remonte : la SEULE requête en vol voyait donc son résultat jeté par
    // un `cancelled` devenu vrai entre-temps, et l'onglet restait
    // indéfiniment sur « Ouverture de la salle… » — y compris quand le
    // backend avait répondu « visioconférence indisponible ». Un écran
    // d'attente perpétuel est exactement ce que cette page devait
    // supprimer.
    //
    // La comparaison porte sur la salle demandée : une réponse qui
    // concerne une autre salle que celle affichée est ignorée, ce qui est
    // la seule chose que le drapeau protégeait réellement.
    const pourCetteSalle = () => demandePour.current === id;

    virtualAPI
      .join(id)
      .then(({ data }) => {
        if (!pourCetteSalle()) return;
        if (data?.provider === "plugnmeet") {
          if (!data.join_url) {
            setError("La visioconférence n'est pas configurée pour cette académie. " +
              "Contactez l'administration.");
            setPhase(PHASE.ERROR);
            return;
          }
          // Le départ sera constaté par plugNmeet (webhook) : pas de
          // « leave » envoyé par cette page quand elle s'efface.
          leaveSent.current = true;
          setPhase(PHASE.REDIRECTING);
          // Titre de l'académie de la salle (fourni par le serveur). Sur la
          // page plugNmeet, c'est feba-branding.js qui l'impose.
          if (data.meeting_title) document.title = data.meeting_title;
          window.location.replace(data.join_url);
          return;
        }
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
        if (!pourCetteSalle()) return;
        setError(raisonDuRefus(e));
        setPhase(PHASE.ERROR);
      });
  }, [id, scopeReady]);

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

  // Onglet : titre exact et favicon de l'ACADÉMIE de la salle (« FEBA -
  // Faith & Excellence Bilingual Academy », « FEBA FHA - FEBA »), et non le
  // nom de la salle.
  const { brandingData } = useBranding(meeting?.academy_code || undefined);
  const titre = meeting?.meeting_title || brandingData?.meeting_title || meeting?.academy_name || t("Visioconférence");
  useEffect(() => {
    document.title = titre;
  }, [titre]);

  if (phase === PHASE.ERROR) {
    return (
      <Plein>
        <div className="max-w-lg text-center">
          <h1 className="text-lg font-semibold text-white mb-3">
            {t("Impossible de rejoindre la salle")}
          </h1>
          <p className="text-slate-300 text-sm leading-relaxed">{error}</p>
          <button
            type="button"
            onClick={() => window.close()}
            className="mt-6 px-4 py-2 rounded-lg bg-slate-700 text-white text-sm hover:bg-slate-600"
          >
            {t("Fermer cet onglet")}
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
            {t("Vous avez quitté la réunion")}
          </h1>
          <p className="text-slate-300 text-sm">{meeting?.name || "Salle virtuelle"}</p>
          <button
            type="button"
            onClick={() => window.close()}
            className="mt-6 px-4 py-2 rounded-lg bg-slate-700 text-white text-sm hover:bg-slate-600"
          >
            {t("Fermer cet onglet")}
          </button>
        </div>
      </Plein>
    );
  }

  if (hasAcademyError) {
    return (
      <Plein>
        <div className="max-w-lg text-center">
          <h1 className="text-lg font-semibold text-white mb-3">
            {t("Impossible de rejoindre la salle")}
          </h1>
          <p className="text-slate-300 text-sm leading-relaxed">
            Votre portée d'académie n'a pas pu être déterminée. Rechargez
            cet onglet ; si le problème persiste, contactez l'administration.
          </p>
        </div>
      </Plein>
    );
  }

  if (phase === PHASE.REDIRECTING) {
    return (
      <Plein>
        <p className="text-slate-300 text-sm">{t("Connexion à la salle de classe…")}</p>
      </Plein>
    );
  }

  if (phase === PHASE.JOINING || !meeting) {
    return (
      <Plein>
        <p className="text-slate-300 text-sm">{t("Ouverture de la salle…")}</p>
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
