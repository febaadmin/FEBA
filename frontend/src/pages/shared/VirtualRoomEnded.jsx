/**
 * VirtualRoomEnded — retour dans FEBA après une réunion plugNmeet.
 *
 * plugNmeet y renvoie l'onglet de la réunion (`logout_url`). Rien ici ne
 * touche à la session FEBA : on ne vide ni les jetons ni le stockage.
 * Le départ est signalé une fois au backend (filet de sécurité : la
 * présence est d'abord close par l'événement plugNmeet).
 */
import { useEffect, useRef } from "react";
import { Link, useParams } from "react-router-dom";
import { virtualAPI } from "../../api";
import { useAuthStore } from "../../store/authStore";
import { useBranding } from "../../hooks/useBranding";

const HOME = {
  superadmin: "/superadmin/dashboard", admin: "/admin/dashboard", teacher: "/teacher/dashboard",
  parent: "/parent/home", student: "/student/home",
};

export default function VirtualRoomEnded() {
  const { id } = useParams();
  const role = useAuthStore((s) => s.user?.role);
  const sent = useRef(false);

  // Titre de l'académie de l'utilisateur (celle de la salle) : « FEBA -
  // Faith & Excellence Bilingual Academy » ou « FEBA FHA - FEBA », et favicon.
  const { brandingData } = useBranding();
  const meetingTitle = brandingData?.meeting_title;
  useEffect(() => {
    if (meetingTitle) document.title = meetingTitle;
  }, [meetingTitle]);

  useEffect(() => {
    if (sent.current || !id) return;
    sent.current = true;
    virtualAPI.leave(id).catch(() => { /* trace, pas un blocage */ });
  }, [id]);

  return (
    <div className="fixed inset-0 w-screen h-screen bg-slate-900 flex items-center justify-center p-6"
         data-testid="virtual-room-ended">
      <div className="max-w-lg text-center">
        <h1 className="text-lg font-semibold text-white mb-3">Vous avez quitté la réunion</h1>
        <p className="text-slate-300 text-sm">
          Votre session FEBA est toujours ouverte.
        </p>
        <div className="mt-6 flex flex-wrap gap-3 justify-center">
          <Link to={`/virtual-room/${id}/join`} replace
                className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm hover:bg-indigo-500">
            Rejoindre à nouveau
          </Link>
          <Link to={HOME[role] || "/login"}
                className="px-4 py-2 rounded-lg bg-slate-700 text-white text-sm hover:bg-slate-600">
            Retour à FEBA
          </Link>
          <button type="button" onClick={() => window.close()}
                  className="px-4 py-2 rounded-lg bg-slate-800 text-slate-200 text-sm hover:bg-slate-700">
            Fermer cet onglet
          </button>
        </div>
      </div>
    </div>
  );
}
