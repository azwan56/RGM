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
  custom_avatar_url?: string;
  strava_profile_url?: string;
}

interface Props {
  persona: PersonaData;
  loading?: boolean;
  displayName?: string;   // User-set display name (priority)
  stravaName?: string;    // Strava firstname + lastname (fallback)
}

// ── Avatar image — prefer custom > strava > gender-based placeholder ─────────
function avatarImage(persona: PersonaData): string {
  if (persona.custom_avatar_url) return persona.custom_avatar_url;
  if (persona.strava_profile_url) return persona.strava_profile_url;

  // Fallback to generic level-based placeholder
  const FEMALE_IMGS = ["/personas/lv0.png","/personas/lv1.png","/personas/lv2.png",
                       "/personas/lv3.png","/personas/lv4.png","/personas/lv5.png"];
  const MALE_IMGS   = ["/personas/m_lv0.png","/personas/m_lv1.png","/personas/m_lv2.png",
                       "/personas/m_lv3.png","/personas/m_lv4.png","/personas/m_lv5.png"];
  const idx = Math.min(persona.level, 5);
  if (persona.gender === "male") return MALE_IMGS[idx];
  return FEMALE_IMGS[idx];
}

// ── Shimmer loading skeleton ──────────────────────────────────────────────────
function LoadingSkeleton() {
  return (
    <div className="rounded-3xl border border-white/8 bg-white/3 overflow-hidden">
      <div className="p-6 md:p-8">
        <div className="flex flex-col sm:flex-row items-center gap-6">
          <div className="w-28 h-28 rounded-full bg-white/6 animate-pulse flex-shrink-0" />
          <div className="flex-1 space-y-3 w-full">
            <div className="h-7 w-48 bg-white/6 rounded-full animate-pulse" />
            <div className="h-4 w-32 bg-white/4 rounded-full animate-pulse" />
            <div className="flex gap-3 mt-2">
              <div className="h-16 flex-1 bg-white/5 rounded-2xl animate-pulse" />
              <div className="h-16 flex-1 bg-white/5 rounded-2xl animate-pulse" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function RunnerPersona({ persona, loading, displayName, stravaName }: Props) {
  if (loading) return <LoadingSkeleton />;

  const imgSrc = avatarImage(persona);
  const name   = displayName || stravaName || "跑者";
  const accentColor = "#FC4C02"; // Strava brand orange for consistent look

  return (
    <div
      className="rounded-3xl border overflow-hidden relative"
      style={{
        borderColor: `${accentColor}30`,
        background: `linear-gradient(140deg, ${accentColor}0a 0%, #09090b 55%)`,
      }}
    >
      {/* Ambient glow */}
      <div
        className="absolute -top-16 -left-16 w-64 h-64 rounded-full blur-[90px] pointer-events-none"
        style={{ background: accentColor, opacity: 0.07 }}
      />

      <div className="relative z-10 p-6 md:p-8">
        <div className="flex flex-col sm:flex-row items-center gap-6">

          {/* ── Avatar ──────────────────────────────────────────────────── */}
          <div
            className="relative w-28 h-28 rounded-full overflow-hidden flex-shrink-0"
            style={{ boxShadow: `0 0 30px ${accentColor}25`, outline: `2px solid ${accentColor}40`, outlineOffset: '2px' }}
          >
            <Image
              src={imgSrc}
              alt={name}
              fill
              className="object-cover"
              sizes="112px"
              priority
            />
          </div>

          {/* ── Name + Stats ────────────────────────────────────────────── */}
          <div className="flex-1 text-center sm:text-left">
            {/* Display name */}
            <h2 className="text-2xl md:text-3xl font-black text-white mb-1">
              {name}
            </h2>

            {/* Subtitle: years running + gender tag */}
            <p className="text-sm text-zinc-400 mb-4">
              {persona.years_running && persona.years_running >= 1
                ? `跑龄 ${persona.years_running} 年`
                : "跑步新手"}
              {persona.gender === "male" ? " · 男" : persona.gender === "female" ? " · 女" : ""}
            </p>

            {/* VDOT + Monthly km data chips */}
            {(persona.vdot || persona.monthly_km !== undefined) && (
              <div className="flex gap-3 justify-center sm:justify-start">
                {persona.vdot && (
                  <div className="rounded-2xl px-5 py-3 text-center"
                    style={{ background: `${accentColor}12`, border: `1px solid ${accentColor}25` }}>
                    <p className="text-zinc-500 text-[10px] uppercase tracking-wider">当前跑力</p>
                    <p className="text-2xl font-black text-white mt-0.5">{persona.vdot.toFixed(1)}</p>
                    <p className="text-zinc-600 text-[10px]">VDOT</p>
                  </div>
                )}
                {persona.monthly_km !== undefined && (
                  <div className="rounded-2xl px-5 py-3 text-center"
                    style={{ background: `${accentColor}12`, border: `1px solid ${accentColor}25` }}>
                    <p className="text-zinc-500 text-[10px] uppercase tracking-wider">本月跑量</p>
                    <p className="text-2xl font-black text-white mt-0.5">{persona.monthly_km}</p>
                    <p className="text-zinc-600 text-[10px]">km</p>
                  </div>
                )}
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
