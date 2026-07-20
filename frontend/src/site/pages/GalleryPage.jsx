/** Galerie photos & vidéos — mosaïque par album + visionneuse plein écran. */
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { PlayCircle } from "lucide-react";
import { siteAPI } from "../siteApi";
import Seo from "../components/Seo";
import Lightbox from "../components/Lightbox";
import { Section, PageBanner } from "../components/SiteSection";
import { DEFAULT_ALBUMS } from "../siteDefaults";

export default function GalleryPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["site-gallery"], queryFn: siteAPI.gallery, staleTime: 300000, retry: 1,
  });
  // V6 : la galerie n'est JAMAIS vide. On préfère les albums administrés ;
  // si l'API est vide ou en erreur, on affiche les albums de repli bâtis sur
  // les médias RÉELS packagés (aucun « bientôt disponible » tant qu'il existe
  // des médias). Filtre les albums sans média actif.
  const albums = useMemo(() => {
    const fromApi = (data?.data || []).filter((a) => a.items?.length);
    return fromApi.length ? fromApi : DEFAULT_ALBUMS;
  }, [data]);
  // Visionneuse : liste plate des médias + index courant.
  const [viewer, setViewer] = useState(null); // { items, index }

  return (
    <>
      <Seo title="Galerie photos et vidéos"
        description="La galerie de FEBA : vie de classe, activités, campus et moments forts de l'école, en photos et en vidéo." />
      <PageBanner title="Galerie"
        intro="L'école en images : la vie de classe, les activités et notre campus."
        image="/site/img/galerie-mosaique-1-1600.webp" />

      <Section tone="white">
        {isLoading && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3" aria-hidden="true">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="rounded-xl bg-feba-cream animate-pulse h-40" />
            ))}
          </div>
        )}

        <div className="space-y-14">
          {albums.map((album) => (
            <div key={album.id}>
              <h2 className="text-xl sm:text-2xl font-bold text-feba-navy">{album.title}</h2>
              {album.description && (
                <p className="text-sm text-feba-gray mt-1">{album.description}</p>
              )}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 mt-5">
                {album.items.map((item, i) => (
                  <button key={item.id ?? i} type="button"
                    onClick={() => setViewer({ items: album.items, index: i })}
                    aria-label={item.kind === "video"
                      ? `Lire la vidéo : ${item.caption || "vidéo FEBA"}`
                      : `Agrandir la photo : ${item.caption || "photo FEBA"}`}
                    className="relative rounded-xl overflow-hidden h-36 sm:h-44 group focus-visible:ring-4 ring-feba-gold/60">
                    <img src={item.image_src} loading="lazy" width="400" height="300"
                      alt={item.alt_text || item.caption || ""}
                      style={{ objectPosition: item.focal || "50% 50%" }}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
                    {item.kind === "video" && (
                      <span className="absolute inset-0 bg-feba-navy/40 flex items-center justify-center">
                        <PlayCircle className="w-12 h-12 text-white drop-shadow" aria-hidden="true" />
                      </span>
                    )}
                    {item.caption && (
                      <span className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-feba-navy/80 to-transparent text-white text-[11px] px-2.5 py-2 text-left truncate">
                        {item.caption}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Section>

      {viewer && (
        <Lightbox items={viewer.items} index={viewer.index}
          onNavigate={(i) => setViewer((v) => ({ ...v, index: i }))}
          onClose={() => setViewer(null)} />
      )}
    </>
  );
}
