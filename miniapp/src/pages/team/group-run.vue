<template>
  <view style="min-height: 100vh; background-color: var(--rgm-bg, #0b0b0e);" />
</template>

<script setup lang="ts">
import { onLoad } from "@dcloudio/uni-app";

onLoad((options?: Record<string, any>) => {
  const qs = options
    ? Object.entries(options)
        .filter(([, v]) => v !== undefined && v !== null)
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
        .join("&")
    : "";
  uni.redirectTo({
    url: `/pages/group-run/group-run${qs ? "?" + qs : ""}`,
    fail: () => uni.switchTab({ url: "/pages/team/team" }),
  });
});
</script>
