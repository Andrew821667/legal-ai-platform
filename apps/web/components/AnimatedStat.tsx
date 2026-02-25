"use client";

import { useCountUp } from "@/lib/hooks/useCountUp";

interface AnimatedStatProps {
  value: number;
  suffix?: string;
  label: string;
  duration?: number;
}

export default function AnimatedStat({ value, suffix = '', label, duration = 2000 }: AnimatedStatProps) {
  const { ref, displayValue } = useCountUp({
    end: value,
    duration,
    suffix
  });

  return (
    <div ref={ref} className="bg-white/10 backdrop-blur-sm rounded-lg p-4 border border-white/20 hover:bg-white/15 hover:border-amber-400/50 hover:scale-105 transition-all duration-300">
      <div className="text-3xl font-bold text-amber-400 mb-1">{displayValue}</div>
      <div className="text-sm text-slate-300">{label}</div>
    </div>
  );
}
