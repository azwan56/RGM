<script setup lang="ts">
import { onLaunch, onShow, onHide } from "@dcloudio/uni-app";
import { checkAndAutoLogin } from "./utils/api";

function applyTabBarStyle() {
  try {
    uni.setTabBarStyle({
      color: "#d4d4d8",
      selectedColor: "#fc4c02",
      backgroundColor: "#121214",
      borderStyle: "black"
    });
  } catch (e) {
    // Ignore if running in non-tabBar context
  }
}

onLaunch(() => {
  console.log("RGM MiniApp Launched");
  applyTabBarStyle();
  checkAndAutoLogin();
});

onShow(() => {
  console.log("App Show");
  applyTabBarStyle();
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
