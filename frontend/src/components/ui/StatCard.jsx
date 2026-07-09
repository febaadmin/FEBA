import { motion } from "framer-motion";
import { TrendingUp, TrendingDown } from "lucide-react";
import { clsx } from "clsx";

export default function StatCard({ title, value, icon: Icon, trend, trendValue, color = "primary", delay = 0 }) {
  const colors = {
    primary: "from-primary to-primary-700 text-white",
    success: "from-success-500 to-emerald-600 text-white",
    accent: "from-accent-500 to-amber-600 text-white",
    danger: "from-danger-500 to-red-600 text-white",
    secondary: "from-secondary-500 to-violet-600 text-white",
  };
  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay, duration: 0.4 }}
      className={clsx("rounded-2xl p-6 bg-gradient-to-br shadow-md", colors[color])}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm opacity-80 font-medium">{title}</p>
          <p className="text-3xl font-bold mt-1">{value}</p>
          {trendValue !== undefined && (
            <div className="flex items-center gap-1 mt-2 text-xs opacity-80">
              {trend === "up" ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
              <span>{trendValue}</span>
            </div>
          )}
        </div>
        {Icon && <div className="p-3 rounded-xl bg-white/20"><Icon className="w-6 h-6" /></div>}
      </div>
    </motion.div>
  );
}