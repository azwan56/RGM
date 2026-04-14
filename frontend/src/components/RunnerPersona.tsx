"use client";

import Image from "next/image";

// ── Types ─────────────────────────────────────────────────────────────────────
interface PersonaData {
  level: number;
  emoji: string;
  title: string;
  subtitle: string;
  description: string;
  fun_fact: string;
  stats: Record<string, number>;
  color: string;
  gender?: string;   // "male" | "female" | "other"
  vdot?: number;
  monthly_km?: number;
  fm_pb_sec?: number;
  years_running?: number;
}

interface Props {
  persona: PersonaData;
  loading?: boolean;
}

// ── Persona image map — gender-aware ─────────────────────────────────────────
// Female / default set (already generated)
const FEMALE_IMGS = ["/personas/lv0.png","/personas/lv1.png","/personas/lv2.png",
                     "/personas/lv3.png","/personas/lv4.png","/personas/lv5.png"];
// Male set — same fallback until male images generated
const MALE_IMGS   = ["/personas/m_lv0.png","/personas/m_lv1.png","/personas/m_lv2.png",
                     "/personas/m_lv3.png","/personas/m_lv4.png","/personas/m_lv5.png"];

function personaImage(level: number, gender?: string): string {
  const idx = Math.min(level, 5);
  // Use male set if gender is "male" AND image is expected to exist
  if (gender === "male") return MALE_IMGS[idx];
  return FEMALE_IMGS[idx];
}

// ── Fuzzy vibe labels (no rigid tier feel) ────────────────────────────────────
const VIBE_TAGS: Record<number, string[]> = {
  0: ["刚起步", "潜力无限", "终点？不存在的"],
  1: ["认真跑起来了", "跑圈新成员", "已脱离沙发"],
  2: ["月跑量稳了", "周末战士", "慢慢来比较快"],
  3: ["节奏感十足", "配速有谱了", "超越大多数人"],
  4: ["破风选手", "别人在你旁边才觉得自己在慢跑", "跑量三位数玩家"],
  5: ["已不需要等级定义", "传说中的那种人", "路人眼中的风"],
};

// ── Stat Bar ──────────────────────────────────────────────────────────────────
function StatBar({ label, value, color, max = 5 }: { label: string; value: number; color: string; max?: number }) {
  const pct = Math.round((value / max) * 100);
  return (
    <div className="flex items-center gap-3">
      <span className="text-zinc-400 text-xs w-16 shrink-0">{label}</span>
      <div className="flex-1 bg-white/6 rounded-full h-1.5 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-1000"
          style={{ width: `${pct}%`, background: `linear-gradient(90deg, ${color}aa, ${color})` }}
        />
      </div>
      <span className="text-[11px] font-mono text-zinc-500 tabular-nums w-5 text-right">{value}</span>
    </div>
  );
}

// ── Shimmer loading skeleton ──────────────────────────────────────────────────
function LoadingSkeleton() {
  return (
    <div className="rounded-3xl border border-white/8 bg-white/3 overflow-hidden">
      <div className="p-6 md:p-8">
        <div className="grid md:grid-cols-2 gap-6">
          <div className="flex flex-col items-center gap-4">
            <div className="w-44 h-44 rounded-3xl bg-white/6 animate-pulse" />
            <div className="h-6 w-32 bg-white/6 rounded-full animate-pulse" />
            <div className="h-4 w-24 bg-white/4 rounded-full animate-pulse" />
          </div>
          <div className="space-y-4">
            <div className="h-20 bg-white/5 rounded-2xl animate-pulse" />
            <div className="h-16 bg-white/4 rounded-2xl animate-pulse" />
            <div className="space-y-2">
              {[1,2,3,4].map(i => <div key={i} className="h-4 bg-white/4 rounded-full animate-pulse" />)}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function RunnerPersona({ persona, loading }: Props) {
  if (loading) return <LoadingSkeleton />;

  const imgSrc   = personaImage(persona.level, persona.gender);
  const vibeTags = VIBE_TAGS[persona.level] ?? [];

  return (
    <div
      className="rounded-3xl border overflow-hidden relative"
      style={{
        borderColor: `${persona.color}30`,
        background: `linear-gradient(140deg, ${persona.color}0a 0%, #09090b 55%)`,
      }}
    >
      {/* Ambient glow */}
      <div
        className="absolute -top-16 -left-16 w-64 h-64 rounded-full blur-[90px] pointer-events-none"
        style={{ background: persona.color, opacity: 0.07 }}
      />
      <div
        className="absolute -bottom-16 -right-16 w-48 h-48 rounded-full blur-[80px] pointer-events-none"
        style={{ background: persona.color, opacity: 0.05 }}
      />

      <div className="relative z-10 p-6 md:p-8">
        <div className="grid md:grid-cols-2 gap-8">

          {/* ── Left: Cartoon + identity ──────────────────────────────────── */}
          <div className="flex flex-col items-center gap-4">
            {/* AI cartoon image */}
            <div
              className="relative w-44 h-44 rounded-3xl overflow-hidden"
              style={{ boxShadow: `0 0 40px ${persona.color}30` }}
            >
              <Image
                src={imgSrc}
                alt={persona.title}
                fill
                className="object-cover"
                sizes="176px"
                priority
              />
            </div>

            {/* Title block */}
            <div className="text-center">
              <div className="flex items-center justify-center gap-2 mb-1.5">
                <span className="text-3xl">{persona.emoji}</span>
                <h2 className="text-2xl font-black text-white">{persona.title}</h2>
              </div>
              <p className="text-sm font-medium" style={{ color: persona.color }}>
                {persona.subtitle}
              </p>
            </div>

            {/* Fuzzy vibe tags — no level numbers */}
            <div className="flex flex-wrap justify-center gap-1.5">
              {vibeTags.map(tag => (
                <span
                  key={tag}
                  className="px-2.5 py-1 rounded-full text-[11px] font-semibold"
                  style={{ background: `${persona.color}18`, color: persona.color }}
                >
                  {tag}
                </span>
              ))}
            </div>

            {/* VDOT + Monthly km data chips */}
            {(persona.vdot || persona.monthly_km) && (
              <div className="flex gap-3 w-full mt-1">
                {persona.vdot && (
                  <div className="flex-1 rounded-2xl p-3 text-center"
                    style={{ background: `${persona.color}12`, border: `1px solid ${persona.color}25` }}>
                    <p className="text-zinc-500 text-[10px] uppercase tracking-wider">当前跑力</p>
                    <p className="text-2xl font-black text-white mt-0.5">{persona.vdot.toFixed(1)}</p>
                    <p className="text-zinc-600 text-[10px]">VDOT</p>
                  </div>
                )}
                {persona.monthly_km !== undefined && (
                  <div className="flex-1 rounded-2xl p-3 text-center"
                    style={{ background: `${persona.color}12`, border: `1px solid ${persona.color}25` }}>
                    <p className="text-zinc-500 text-[10px] uppercase tracking-wider">本月跑量</p>
                    <p className="text-2xl font-black text-white mt-0.5">{persona.monthly_km}</p>
                    <p className="text-zinc-600 text-[10px]">km</p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* ── Right: Description + Stats ───────────────────────────────── */}
          <div className="flex flex-col justify-center gap-5">
            {/* Description */}
            <div className="bg-white/4 border border-white/8 rounded-2xl p-4">
              <p className="text-zinc-300 text-sm leading-relaxed">{persona.description}</p>
            </div>

            {/* Fun quote */}
            <div
              className="rounded-2xl p-4"
              style={{ background: `${persona.color}12`, border: `1px solid ${persona.color}25` }}
            >
              <span className="text-zinc-500 text-[10px] uppercase tracking-wider block mb-1.5">跑者实录</span>
              <p className="text-zinc-200 text-sm">💬 {persona.fun_fact}</p>
            </div>

            {/* Capability index — RETAINED ─────────────────────────────── */}
            <div className="space-y-2.5">
              <p className="text-zinc-500 text-[10px] uppercase tracking-wider mb-2 flex items-center gap-2">
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                能力指数
              </p>
              {Object.entries(persona.stats).map(([label, val]) => (
                <StatBar key={label} label={label} value={val} color={persona.color} />
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
