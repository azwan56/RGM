<script setup lang="ts">
import { onLaunch, onShow, onHide } from "@dcloudio/uni-app";
import { checkAndAutoLogin } from "./utils/api";

onLaunch(() => {
  console.log("RGM MiniApp Launched");
  checkAndAutoLogin();
});

onShow(() => {
  console.log("App Show");
});

onHide(() => {
  console.log("App Hide");
});
</script>

<style>
/* Global Dark Theme Aesthetic */
page {
  background-color: #0a0a0a;
  color: #ffffff;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  box-sizing: border-box;
}

view, text, button, input, image {
  box-sizing: border-box;
}

/* Scrollbar hidden */
::-webkit-scrollbar {
  display: none;
  width: 0;
  height: 0;
  color: transparent;
}
</style>
