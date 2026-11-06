/**
 * Menu latéral commun aux cinq profils : entrées regroupées par domaine, groupes
 * repliables, groupe de la page active ouvert d'office, choix mémorisé par profil
 * (préférence d'affichage, sans conséquence si le stockage est indisponible).
 */
import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { ChevronDown } from "lucide-react";
import { t } from "../../i18n";

const lire = (cle) => { try { return JSON.parse(localStorage.getItem(cle) || "null"); } catch { return null; } };
const ecrire = (cle, v) => { try { localStorage.setItem(cle, JSON.stringify(v)); } catch { /* préférence non mémorisée */ } };

function actif(pathname, to) {
  return pathname === to || pathname.startsWith(`${to}/`);
}

function Entree({ item, badges, onNavigate }) {
  const n = item.badge ? badges?.[item.badge] || 0 : 0;
  const Icone = item.icon;
  return (
    <NavLink to={item.to} end={item.to.endsWith("/suivi")} onClick={onNavigate}
      className={({ isActive }) => (isActive ? "nav-item-actif" : "nav-item")}>
      <Icone className="w-4 h-4 shrink-0" aria-hidden="true" />
      <span className="flex-1 truncate">{t(item.label)}</span>
      {n > 0 && (
        <span data-testid="badge-messages-menu" aria-label={t("{n} conversation(s) non lue(s)", { n })}
          className="ml-auto min-w-[1.25rem] h-5 px-1 bg-danger text-white text-[10px] rounded-full flex items-center justify-center font-bold shrink-0">
          {n > 9 ? "9+" : n}
        </span>
      )}
    </NavLink>
  );
}

export default function MenuLateral({ menu, profil, visible = () => true, badges, onNavigate }) {
  const { pathname } = useLocation();
  const cle = `feba.menu.${profil}`;
  const [ouverts, setOuverts] = useState(() => lire(cle) || {});
  const basculer = (id, etat) => setOuverts((o) => { const n = { ...o, [id]: !etat }; ecrire(cle, n); return n; });
  return (
    <nav className="flex-1 p-3 overflow-y-auto space-y-1" aria-label={t("Menu principal")} data-testid="menu-lateral">
      {menu.map((x) => {
        if (!x.items) return visible(x) ? <Entree key={x.to} item={x} badges={badges} onNavigate={onNavigate} /> : null;
        const items = x.items.filter(visible);
        if (!items.length) return null;
        const contientActif = items.some((i) => actif(pathname, i.to));
        const badge = items.reduce((s, i) => s + (i.badge ? badges?.[i.badge] || 0 : 0), 0);
        // Par défaut : ouvert si le groupe contient la page affichée, ou si le menu est court.
        const ouvert = contientActif || (ouverts[x.id] ?? menu.length <= 6);
        const Icone = x.icon;
        return (
          <section key={x.id} className="pt-1" data-testid={`menu-groupe-${x.id}`}>
            <button type="button" onClick={() => basculer(x.id, ouvert)} aria-expanded={ouvert} aria-controls={`menu-${profil}-${x.id}`}
              disabled={contientActif} title={contientActif ? t("Groupe de la page affichée") : undefined}
              className="w-full flex items-center gap-2 px-4 py-1.5 rounded-lg text-[12.5px] font-semibold text-slate-400 hover:text-white hover:bg-white/5 transition-colors disabled:cursor-default disabled:hover:bg-transparent disabled:text-feba-gold">
              <Icone className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
              <span className="flex-1 text-left truncate">{t(x.label)}</span>
              {!ouvert && badge > 0 && <span className="w-2 h-2 rounded-full bg-danger" aria-label={t("{n} conversation(s) non lue(s)", { n: badge })} />}
              <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-200 motion-reduce:transition-none ${ouvert ? "" : "-rotate-90"}`} aria-hidden="true" />
            </button>
            <div id={`menu-${profil}-${x.id}`} hidden={!ouvert} className="space-y-0.5 mt-0.5">
              {items.map((i) => <Entree key={i.to} item={i} badges={badges} onNavigate={onNavigate} />)}
            </div>
          </section>
        );
      })}
    </nav>
  );
}
