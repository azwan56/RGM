import { defineConfig } from "vite";
import uni from "@dcloudio/vite-plugin-uni";
import { execFileSync } from "node:child_process";
import path from "node:path";

function rgmMpWeixinSubpackageOptimizer() {
  let outDir = "";
  return {
    name: "rgm-mp-weixin-subpackage-optimizer",
    apply: "build" as const,
    configResolved(resolved: any) {
      outDir = resolved?.build?.outDir || "";
    },
    closeBundle() {
      if (!outDir || !outDir.includes("mp-weixin")) return;
      try {
        const scriptPath = path.resolve(__dirname, "scripts/optimize-wxss.cjs");
        execFileSync(process.execPath, [scriptPath, outDir], { stdio: "inherit" });
      } catch (e) {
        console.warn("[rgm-mp-weixin-subpackage-optimizer] warning:", e);
      }
    },
  };
}

export default defineConfig({
  plugins: [uni(), rgmMpWeixinSubpackageOptimizer()],
});
