/**
 * useBranding — v25
 * - FIX v20: ne lance la requête que si le token est présent
 * - FIX v25: met à jour le favicon de l'onglet dynamiquement depuis le logo école
 */
import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { schoolsAPI } from "../api";
import { useAuthStore } from "../store/authStore";
import logoFeba from "../assets/logo_feba.jpeg";
import { resolveMediaUrl } from "../utils/media";

function updateFavicon(url) {
  try {
    let link = document.querySelector("link[rel~='icon']");
    if (!link) { link = document.createElement("link"); link.rel = "icon"; document.head.appendChild(link); }
    link.href = url;
  } catch (e) { /* cosmetic only */ }
}

export function useBranding() {
  const token = useAuthStore(s => s.accessToken);

  const { data: activeData, error } = useQuery({
    queryKey: ["branding-active"],
    queryFn: () => schoolsAPI.activeBranding(),
    staleTime: 5 * 60_000,
    enabled: !!token,
    retry: (failureCount, err) => {
      const status = err?.response?.status;
      if (status === 401 || status === 403) return false;
      return failureCount < 1;
    },
    throwOnError: false,
  });

  const activeLogo = !error ? resolveMediaUrl(activeData?.data?.logo_url) : null;
  const logoSrc    = activeLogo || logoFeba;

  // FIX v25: update browser tab favicon from school logo
  useEffect(() => {
    if (activeLogo) updateFavicon(activeLogo);
  }, [activeLogo]);

  return {
    logoSrc,
    isDynamic:    !!activeLogo,
    brandingData: activeData?.data,
    hasError:     !!error,
  };
}
