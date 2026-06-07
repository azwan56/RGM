const { chromium } = require('playwright');

(async () => {
  console.log("Launching browser...");
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });

  console.log("Navigating to http://localhost:3000/auth");
  await page.goto('http://localhost:3000/auth');
  
  await page.waitForTimeout(3000);
  
  console.log("Trying to login as testdocs@example.com");
  try {
    await page.fill('input[type="email"]', 'testdocs@example.com');
    await page.fill('input[type="password"]', 'password123');
    await page.click('button[type="submit"]');
    console.log("Clicked submit. Waiting 5s...");
    await page.waitForTimeout(5000);
  } catch (e) {
    console.log("Login form not found or error:", e.message);
  }

  const routes = [
    { url: 'http://localhost:3000/dashboard', file: 'rgm_dashboard.png' },
    { url: 'http://localhost:3000/dashboard/profile', file: 'rgm_profile.png' },
    { url: 'http://localhost:3000/dashboard/coach', file: 'rgm_ai_coach.png' },
    { url: 'http://localhost:3000/dashboard/analysis', file: 'rgm_analysis.png' },
    { url: 'http://localhost:3000/dashboard/team', file: 'rgm_leaderboard.png' }
  ];

  for (const route of routes) {
    console.log(`Navigating to ${route.url}`);
    await page.goto(route.url);
    await page.waitForTimeout(3000); 
    console.log(`Taking screenshot: ${route.file}`);
    await page.screenshot({ path: `../docs/images/${route.file}` });
  }

  await browser.close();
  console.log("Done taking screenshots.");
})();
