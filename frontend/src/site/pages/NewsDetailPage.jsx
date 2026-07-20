/** Détail d'une actualité ou d'un événement. */
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, CalendarDays, MapPin } from "lucide-react";
import { siteAPI } from "../siteApi";
import Seo from "../components/Seo";
import SiteImage from "../components/SiteImage";
import { Section } from "../components/SiteSection";
import SiteNotFound from "./SiteNotFound";

export default function NewsDetailPage() {
  const { slug } = useParams();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["site-news-detail", slug],
    queryFn: () => siteAPI.newsDetail(slug),
    retry: 1,
  });

  if (isLoading) {
    return (
      <Section tone="white">
        <div className="max-w-3xl mx-auto space-y-4" aria-hidden="true">
          <div className="h-8 bg-feba-cream animate-pulse rounded-xl w-2/3" />
          <div className="h-64 bg-feba-cream animate-pulse rounded-2xl" />
          <div className="h-4 bg-feba-cream animate-pulse rounded w-full" />
          <div className="h-4 bg-feba-cream animate-pulse rounded w-5/6" />
        </div>
      </Section>
    );
  }

  if (isError) {
    if (error?.response?.status === 404) return <SiteNotFound />;
    return (
      <Section tone="white">
        <p className="text-center text-sm py-10">
          Impossible de charger cette publication. Veuillez réessayer plus tard.
        </p>
      </Section>
    );
  }

  const post = data.data;
  return (
    <>
      <Seo title={post.title} description={post.excerpt || post.title}
        image={post.image_src} type="article" />
      <Section tone="white">
        <article className="max-w-3xl mx-auto">
          <Link to="/actualites"
            className="inline-flex items-center gap-2 text-sm font-semibold text-feba-navy hover:text-feba-gold transition-colors mb-6">
            <ArrowLeft className="w-4 h-4" /> Toutes les actualités
          </Link>
          <p className="flex items-center gap-2 text-xs text-feba-gold font-semibold uppercase tracking-wide">
            <CalendarDays className="w-3.5 h-3.5" aria-hidden="true" />
            {post.kind === "event" ? "Événement" : "Actualité"}
            {(post.event_date || post.published_at) && (
              <span className="text-feba-gray font-normal normal-case">
                · {(post.event_date || post.published_at).slice(0, 10)}
              </span>
            )}
          </p>
          <h1 className="text-2xl sm:text-4xl font-bold text-feba-navy mt-3 leading-tight">
            {post.title}
          </h1>
          {post.location && (
            <p className="flex items-center gap-1.5 text-sm text-feba-gray mt-3">
              <MapPin className="w-4 h-4 text-feba-gold" aria-hidden="true" />{post.location}
            </p>
          )}
          {post.image_src && (
            <SiteImage src={post.image_src} alt="" eager position={post.focal} sizes="(min-width:768px) 720px, 100vw"
              className="rounded-2xl shadow-lg w-full object-cover max-h-[420px] mt-6" />
          )}
          {post.excerpt && (
            <p className="text-lg text-feba-navy/80 font-medium mt-6 leading-relaxed">{post.excerpt}</p>
          )}
          {post.body && (
            <div className="mt-5 leading-relaxed space-y-4 whitespace-pre-line text-[15px]">
              {post.body}
            </div>
          )}
        </article>
      </Section>
    </>
  );
}
