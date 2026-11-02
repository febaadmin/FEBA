import { motion } from "framer-motion";
import { TrendingUp, TrendingDown } from "lucide-react";
import { clsx } from "clsx";

const TUILES = {
  primary: "from-primary-500 to-sidebar-2",
  success: "from-emerald-400 to-emerald-600",
  accent: "from-amber-400 to-amber-600",
  danger: "from-red-400 to-red-600",
  secondary: "from-secondary-500 to-secondary-600",
};

export default function StatCard({ title, value, icon: Icon, trend, trendValue, color = "primary", delay = 0 }) {
  return (
    <motion.div initial={{ opacity: 0.6, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay, duration: 0.3, ease: "easeOut" }}
      className="card carte-active !p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-slate-500 font-medium">{title}</p>
          <p className="text-xl 2xl:text-2xl font-bold mt-1 text-slate-900 tabular-nums">{value}</p>
          {trendValue !== undefined && (
            <div className={clsx("flex items-center gap-1 mt-2 text-xs font-medium", trend === "up" ? "text-emerald-700" : "text-red-700")}>
              {trend === "up" ? <TrendingUp className="w-3 h-3" aria-hidden="true" /> : <TrendingDown className="w-3 h-3" aria-hidden="true" />}
              <span>{trendValue}</span>
            </div>
          )}
        </div>
        {Icon && <div className={clsx("p-2.5 rounded-xl text-white shrink-0 bg-gradient-to-br shadow-carte", TUILES[color] || TUILES.primary)}><Icon className="w-5 h-5" aria-hidden="true" /></div>}
      </div>
    </motion.div>
  );
}
