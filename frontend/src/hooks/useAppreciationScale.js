/**
 * Barème d'appréciations EFFECTIF de l'académie active (lecture seule).
 * Repli sur le barème par défaut tant qu'il n'est pas chargé ou si la
 * lecture échoue (l'aperçu reste indicatif ; le serveur fait foi).
 */
import { useQuery } from "@tanstack/react-query";
import { appreciationsAPI } from "../api";
import { useAcademy } from "../context/AcademyContext";
import { DEFAULT_SCALE } from "../utils/appreciation";

export function useAppreciationScale(cycle = "") {
  const { activeAcademy, isAllAcademies } = useAcademy();
  const academyId = activeAcademy?.id || null;
  const { data } = useQuery({
    queryKey: ["appreciation-scale", academyId, cycle],
    queryFn: () => appreciationsAPI.get(cycle),
    enabled: Boolean(academyId) && !isAllAcademies,
    staleTime: 60_000,
  });
  return data?.data?.effective?.length ? data.data.effective : DEFAULT_SCALE;
}
