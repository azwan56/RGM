import { createSSRApp } from "vue";
import App from "./App.vue";
import { telemetryPageMixin } from "./utils/telemetry";

export function createApp() {
  const app = createSSRApp(App);
  app.mixin(telemetryPageMixin);
  return {
    app,
  };
}
