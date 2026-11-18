<template>
  <image
    class="rgm-vec-icon"
    :src="iconUri"
    :style="{ width: size + 'rpx', height: size + 'rpx' }"
    mode="aspectFit"
  />
</template>

<script setup lang="ts">
import { computed } from "vue";
import { isVolt } from "../utils/theme";

const props = withDefaults(
  defineProps<{
    name: string;
    size?: number;
    color?: string;
    strokeWidth?: number;
  }>(),
  {
    size: 32,
    color: "text",
    strokeWidth: 1.8,
  }
);

const DARK_COLORS: Record<string, string> = {
  text: "#F4F4F6",
  text2: "#A1A1AA",
  muted: "#71717A",
  brand: "#FC4C02",
  green: "#10B981",
  blue: "#38BDF8",
  purple: "#A855F7",
  amber: "#F59E0B",
  red: "#EF4444",
  white: "#FFFFFF",
};

const VOLT_COLORS: Record<string, string> = {
  text: "#0F172A",
  text2: "#475569",
  muted: "#64748B",
  brand: "#FC4C02",
  green: "#059669",
  blue: "#0284C7",
  purple: "#7C3AED",
  amber: "#D97706",
  red: "#DC2626",
  white: "#FFFFFF",
};

const resolvedColor = computed(() => {
  const c = props.color || "text";
  if (c.startsWith("#") || c.startsWith("rgb")) return c;
  const table = isVolt.value ? VOLT_COLORS : DARK_COLORS;
  return table[c] || table.text;
});

function buildShapes(name: string, c: string, sw: number): string {
  const common = `fill="none" stroke="${c}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round"`;
  switch (name) {
    case "watch":
      return (
        `<rect x="7" y="6" width="10" height="12" rx="2.5" ${common}/>` +
        `<line x1="9" y1="6" x2="9" y2="2.5" ${common}/>` +
        `<line x1="15" y1="6" x2="15" y2="2.5" ${common}/>` +
        `<line x1="9" y1="18" x2="9" y2="21.5" ${common}/>` +
        `<line x1="15" y1="18" x2="15" y2="21.5" ${common}/>` +
        `<polyline points="12,9.5 12,12 14,13.5" ${common}/>`
      );
    case "bell":
      return (
        `<path d="M6.5 15L7.6 10A4.4 4.4 0 0 1 16.4 10L17.5 15L19 17H5Z" ${common}/>` +
        `<circle cx="12" cy="19.5" r="1.4" fill="${c}"/>`
      );
    case "battery":
      return (
        `<rect x="4" y="7" width="14" height="10" rx="2.5" ${common}/>` +
        `<line x1="20" y1="10" x2="20" y2="14" ${common}/>` +
        `<rect x="6.5" y="9.5" width="9" height="5" rx="1" fill="${c}"/>`
      );
    case "pulse":
      return `<polyline points="2.5,12 6.5,12 9,6.5 12,17.5 15,9 17.5,12 21.5,12" ${common}/>`;
    case "gauge":
      return (
        `<path d="M5.2 17A8 8 0 1 1 18.8 17" ${common}/>` +
        `<line x1="12" y1="13" x2="16.2" y2="8.8" ${common}/>` +
        `<circle cx="12" cy="13" r="1.6" fill="${c}"/>`
      );
    case "trophy":
      return (
        `<path d="M7.5 5H16.5L15.6 11A3.6 3.6 0 0 1 8.4 11Z" ${common}/>` +
        `<path d="M7.5 6.5C4.5 6.5 4.5 10.2 7.8 10.2" ${common}/>` +
        `<path d="M16.5 6.5C19.5 6.5 19.5 10.2 16.2 10.2" ${common}/>` +
        `<line x1="12" y1="14.5" x2="12" y2="18.5" ${common}/>` +
        `<line x1="8.5" y1="18.5" x2="15.5" y2="18.5" ${common}/>`
      );
    case "shield":
      return (
        `<path d="M12 3L19 6V11.5C19 16 15.8 19.4 12 21C8.2 19.4 5 16 5 11.5V6Z" ${common}/>` +
        `<polyline points="9,12 11.2,14.2 15.2,9.8" ${common}/>`
      );
    case "sliders":
      return (
        `<line x1="4" y1="8.5" x2="20" y2="8.5" ${common}/>` +
        `<circle cx="9.5" cy="8.5" r="2.2" fill="${c}"/>` +
        `<line x1="4" y1="15.5" x2="20" y2="15.5" ${common}/>` +
        `<circle cx="14.5" cy="15.5" r="2.2" fill="${c}"/>`
      );
    case "chat":
      return `<path d="M4.5 6.5A2.5 2.5 0 0 1 7 4H17A2.5 2.5 0 0 1 19.5 6.5V14A2.5 2.5 0 0 1 17 16.5H10.5L6.5 20L7.3 16.5H7A2.5 2.5 0 0 1 4.5 14Z" ${common}/>`;
    case "share":
      return (
        `<rect x="5" y="10.5" width="14" height="9" rx="2" ${common}/>` +
        `<line x1="12" y1="14" x2="12" y2="4.5" ${common}/>` +
        `<polyline points="8.5,7.8 12,4.2 15.5,7.8" ${common}/>`
      );
    case "calendar":
      return (
        `<rect x="4.5" y="6" width="15" height="13.5" rx="2.2" ${common}/>` +
        `<line x1="4.5" y1="10.5" x2="19.5" y2="10.5" ${common}/>` +
        `<line x1="8.5" y1="3.8" x2="8.5" y2="7.5" ${common}/>` +
        `<line x1="15.5" y1="3.8" x2="15.5" y2="7.5" ${common}/>`
      );
    case "pin":
      return (
        `<path d="M12 20.5C6.5 14.8 5.5 10.6 5.5 9.5A6.5 6.5 0 1 1 18.5 9.5C18.5 10.6 17.5 14.8 12 20.5Z" ${common}/>` +
        `<circle cx="12" cy="9.5" r="2.2" fill="${c}"/>`
      );
    case "users":
      return (
        `<circle cx="9.2" cy="8.2" r="2.8" ${common}/>` +
        `<path d="M4.2 18.2C4.8 13.8 13.6 13.8 14.2 18.2" ${common}/>` +
        `<circle cx="16.2" cy="9" r="2.2" ${common}/>` +
        `<path d="M15.4 17.8C16.6 14.6 19.6 14.8 20.2 17.8" ${common}/>`
      );
    case "zap":
      return `<polygon points="13.2,3.5 6.2,13 11.4,13 9.8,20.5 17.8,10.8 12.6,10.8" fill="${c}"/>`;
    case "check":
      return `<polyline points="5.5,12.2 10,16.8 18.5,7.5" ${common}/>`;
    case "chevron-right":
      return `<polyline points="9,6.5 15,12 9,17.5" ${common}/>`;
    case "chevron-down":
      return `<polyline points="6.5,9.5 12,15 17.5,9.5" ${common}/>`;
    case "mountain":
      return `<polyline points="3.5,18 9.2,7 13.2,13.5 16.2,9.8 20.5,18" ${common}/>`;
    case "qrcode":
      return (
        `<rect x="4.5" y="4.5" width="5.8" height="5.8" rx="1" ${common}/>` +
        `<rect x="13.7" y="4.5" width="5.8" height="5.8" rx="1" ${common}/>` +
        `<rect x="4.5" y="13.7" width="5.8" height="5.8" rx="1" ${common}/>` +
        `<rect x="13.8" y="13.8" width="2.4" height="2.4" rx="0.4" fill="${c}"/>` +
        `<rect x="17.2" y="17.2" width="2.4" height="2.4" rx="0.4" fill="${c}"/>`
      );
    case "alert":
      return (
        `<polygon points="12,4 20.5,19 3.5,19" ${common}/>` +
        `<line x1="12" y1="9.5" x2="12" y2="14" ${common}/>` +
        `<circle cx="12" cy="16.8" r="1" fill="${c}"/>`
      );
    case "search":
      return (
        `<circle cx="10.5" cy="10.5" r="5.8" ${common}/>` +
        `<line x1="14.8" y1="14.8" x2="19.8" y2="19.8" ${common}/>`
      );
    case "plus":
      return (
        `<line x1="12" y1="5" x2="12" y2="19" ${common}/>` +
        `<line x1="5" y1="12" x2="19" y2="12" ${common}/>`
      );
    case "camera":
      return (
        `<rect x="3.5" y="7" width="17" height="11.5" rx="2.2" ${common}/>` +
        `<path d="M8 7L9.5 4.5H14.5L16 7" ${common}/>` +
        `<circle cx="12" cy="12.8" r="3" ${common}/>`
      );
    case "file":
      return (
        `<path d="M6.5 3.5H14L18.5 8V19.5A1.5 1.5 0 0 1 17 21H7A1.5 1.5 0 0 1 5.5 19.5V5A1.5 1.5 0 0 1 6.5 3.5Z" ${common}/>` +
        `<polyline points="14,3.5 14,8 18.5,8" ${common}/>`
      );
    case "moon":
      return `<path d="M18.5 14.5A7 7 0 0 1 9.5 5.5A7 7 0 1 0 18.5 14.5Z" ${common}/>`;
    case "sun":
      return (
        `<circle cx="12" cy="12" r="4" ${common}/>` +
        `<line x1="12" y1="3" x2="12" y2="5.2" ${common}/>` +
        `<line x1="12" y1="18.8" x2="12" y2="21" ${common}/>` +
        `<line x1="3" y1="12" x2="5.2" y2="12" ${common}/>` +
        `<line x1="18.8" y1="12" x2="21" y2="12" ${common}/>` +
        `<line x1="5.6" y1="5.6" x2="7.2" y2="7.2" ${common}/>` +
        `<line x1="16.8" y1="16.8" x2="18.4" y2="18.4" ${common}/>`
      );
    case "flame":
      return `<path d="M12.5 3.5C15.5 6.8 17.8 9.8 17.8 13.5A5.8 5.8 0 1 1 6.2 13.5C6.2 10.6 7.8 8.4 9.2 7.2C9.4 9.5 10.8 10.6 11.4 10.2C11.8 8.2 11.6 5.6 12.5 3.5Z" ${common}/>`;
    case "compass":
      return (
        `<circle cx="12" cy="12" r="8.5" ${common}/>` +
        `<polygon points="15.5,8.5 13.2,13.2 8.5,15.5 10.8,10.8" ${common}/>`
      );
    case "heart":
      return `<path d="M12 19.5C5.2 14.8 4.2 9.5 6.8 6.8A4.2 4.2 0 0 1 12 7.5A4.2 4.2 0 0 1 17.2 6.8C19.8 9.5 18.8 14.8 12 19.5Z" ${common}/>`;
    case "eye":
      return (
        `<path d="M3 12C5.5 7.5 8.8 5.8 12 5.8C15.2 5.8 18.5 7.5 21 12C18.5 16.5 15.2 18.2 12 18.2C8.8 18.2 5.5 16.5 3 12Z" ${common}/>` +
        `<circle cx="12" cy="12" r="2.6" fill="${c}"/>`
      );
    case "lock":
      return (
        `<rect x="5.5" y="10.5" width="13" height="9.5" rx="2.2" ${common}/>` +
        `<path d="M8.5 10.5V7.8A3.5 3.5 0 0 1 15.5 7.8V10.5" ${common}/>` +
        `<circle cx="12" cy="15" r="1.2" fill="${c}"/>`
      );
    default:
      return `<circle cx="12" cy="12" r="7" ${common}/>`;
  }
}

const iconUri = computed(() => {
  const c = resolvedColor.value;
  const shapes = buildShapes(props.name, c, props.strokeWidth);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">${shapes}</svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
});
</script>

<style scoped>
.rgm-vec-icon {
  display: inline-block;
  flex-shrink: 0;
  vertical-align: middle;
}
</style>
