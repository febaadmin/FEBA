/**
 * JitsiInfrastructureBanner — état réel de l'instance de visioconférence.
 *
 * Remplace l'ancienne bannière « Mode démonstration (meet.jit.si) — appels
 * limités à 5 minutes ». Il n'existe plus d'instance publique de repli :
 * l'application utilise exclusivement l'instance FEBA auto-hébergée.
 *
 * La bannière n'apparaît QUE lorsqu'il y a un problème réel :
 *   - « operational » → rien n'est affiché ;
 *   - « degraded »    → instance configurée mais injoignable ;
 *   - « unavailable » → instance non configurée.
 *
 * Le diagnostic technique détaillé est réservé aux administrateurs : un
 * enseignant voit un message actionnable, pas une trace d'infrastructure.
 */
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ServerCrash, Video } from "lucide-react";
import api from "../api";
import { t } from "../i18n";
import { useAuthStore } from "../store/authStore";

export default function JitsiInfrastructureBanner() {
  const user = useAuthStore((s) => s.user);
  const isAdmin = ["admin", "superadmin"].includes(user?.role);

  const { data, isLoading } = useQuery({
    queryKey: ["jitsi-health"],
    // Le endpoint répond 503 quand l'instance est en panne : on récupère
    // le corps de la réponse plutôt que de traiter cela comme une erreur.
    queryFn: () =>
      api
        .get("/virtual-rooms/health/")
        .then((r) => r.data)
        .catch((err) => err?.response?.data || { status: "unavailable", detail: "" }),
    staleTime: 60 * 1000,
    retry: false,
  });

  if (isLoading || !data) return null;
  if (data.status === "operational") return null;

  const degraded = data.status === "degraded";
  const Icon = degraded ? AlertTriangle : ServerCrash;

  return (
    <div
      role="status"
      className={`flex items-start gap-3 rounded-xl border p-4 text-sm ${
        degraded
          ? "border-amber-200 bg-amber-50 text-amber-800"
          : "border-red-200 bg-red-50 text-red-800"
      }`}
    >
      <Icon className="w-5 h-5 mt-0.5 shrink-0" aria-hidden="true" />
      <div className="min-w-0">
        <p className="font-semibold">
          {degraded
            ? t("Visioconférence dégradée — instance FEBA injoignable")
            : t("Visioconférence indisponible — instance FEBA non configurée")}
        </p>
        <p className="mt-0.5">
          {t(
            "Les cours en direct ne peuvent pas démarrer pour le moment. Aucune session n'est basculée vers un service public : les échanges restent sur l'infrastructure FEBA.",
          )}
        </p>

        {/* Diagnostic technique : administrateurs uniquement. */}
        {isAdmin && data.detail && (
          <p className="mt-2 text-xs opacity-90 break-words">
            <span className="font-semibold">{t("Diagnostic")} : </span>
            {data.detail}
          </p>
        )}
        {isAdmin && (
          <p className="mt-1 text-xs opacity-90">
            <Video className="w-3 h-3 inline mr-1" aria-hidden="true" />
            {t("Relancez l'instance avec")}{" "}
            <code className="bg-black/10 px-1 rounded">make jitsi-up</code>{" "}
            {t("puis vérifiez avec")}{" "}
            <code className="bg-black/10 px-1 rounded">make jitsi-health</code>.
          </p>
        )}
      </div>
    </div>
  );
}
