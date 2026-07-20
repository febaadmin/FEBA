/** Actualités & événements — publications réelles administrées, avec filtre. */
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CalendarDays, MapPin, Newspaper } from "lucide-react";
import { siteAPI } from "../siteApi";
import Seo from "../components/Seo";
import SiteImage from "../components/SiteImage";
import { Section, PageBanner } from "../components/SiteSection";

const FILTERS = [
  { value: "", label: "Tout" },
  { value: "news", label: "Actualités" },
  { value: "event", label: "Événements" },
];

export default function NewsPage() {
  const [kind, setKind] = useState("");
  const { data, isLoading, isError } = useQuery({
    queryKey: ["site-news", kind],
    queryFn: () => siteAPI.news(kind ? { kind } : {}),
    staleTime: 120000, retry: 1,
  });
  const raw = data?.data;
  const posts = raw?.results || raw || [];

  return (
    <>
      <Seo title="Actualités et événements"
        description="Les actualités et les événements de la vie de l'école FEBA à Cotonou." />
      <PageBanner title="Actualités & événements"
        intro="La vie de l'école, au fil des semaines."
        image="/site/img/activite-expression-1600.webp" />

      <Section tone="white">
        <div className="flex gap-2 flex-wrap mb-8" role="group" aria-label="Filtrer les publications">
          {FILTERS.map((f) => (
            <button key={f.value} onClick={() => setKind(f.value)}
              aria-pressed={kind === f.value}
              className={`px-4 py-2 rounded-xl text-sm font-semibold transition-colors ${
                kind === f.value
                  ? "bg-feba-navy text-white"
                  : "bg-feba-cream text-feba-navy hover:bg-feba-gold/20"
              }`}>
              {f.label}
            </button>
          ))}
        </div>

        {isLoading && (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6" aria-hidden="true">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="rounded-2xl bg-feba-cream animate-pulse h-72" />
            ))}
          </div>
        )}

        {isError && (
          <p className="text-center text-sm text-feba-gray py-10">
            Impossible de charger les actualités pour le moment. Veuillez réessayer plus tard.
          </p>
        )}

        {!isLoading && !isError && posts.length === 0 && (
          <div className="text-center py-16">
            <Newspaper className="w-10 h-10 text-feba-gold mx-auto mb-4" aria-hidden="true" />
            <p className="font-semibold text-feba-navy">Aucune publication pour le moment</p>
            <p className="text-sm mt-2">
              Les prochaines actualités et les événements de l'école paraîtront ici.
            </p>
          </div>
        )}

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {posts.map((post) => (
            <article key={post.id} className="rounded-2xl bg-feba-cream shadow-md overflow-hidden hover:shadow-xl transition-shadow flex flex-col">
              {post.image_src && (
                <Link to={`/actualites/${post.slug}`} className="block h-44 overflow-hidden">
                  <SiteImage src={post.image_src} alt="" position={post.focal} sizes="(min-width:1024px) 33vw, 100vw"
                    className="w-full h-full object-cover" />
                </Link>
              )}
              <div className="p-5 flex-1 flex flex-col">
                <p className="flex items-center gap-2 text-xs text-feba-gold font-semibold uppercase tracking-wide">
                  <CalendarDays className="w-3.5 h-3.5" aria-hidden="true" />
                  {post.kind === "event" ? "Événement" : "Actualité"}
                  {(post.event_date || post.published_at) && (
                    <span className="text-feba-gray font-normal normal-case">
                      · {(post.event_date || post.published_at).slice(0, 10)}
                    </span>
                  )}
                </p>
                <h2 className="font-bold text-feba-navy mt-2 leading-snug">
                  <Link to={`/actualites/${post.slug}`} className="hover:text-feba-gold transition-colors">
                    {post.title}
                  </Link>
                </h2>
                {post.excerpt && <p className="text-sm mt-2 leading-relaxed flex-1">{post.excerpt}</p>}
                {post.location && (
                  <p className="flex items-center gap-1.5 text-xs text-feba-gray mt-3">
                    <MapPin className="w-3.5 h-3.5 text-feba-gold" aria-hidden="true" />{post.location}
                  </p>
                )}
              </div>
            </article>
          ))}
        </div>
      </Section>
    </>
  );
}
