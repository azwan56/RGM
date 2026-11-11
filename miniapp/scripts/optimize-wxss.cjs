const fs = require("fs");
const path = require("path");

function walk(dir, filterFn) {
  let results = [];
  if (!fs.existsSync(dir)) return results;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results = results.concat(walk(full, filterFn));
    } else if (!filterFn || filterFn(full)) {
      results.push(full);
    }
  }
  return results;
}

const targetDir = path.resolve(__dirname, "../dist/build/mp-weixin");
if (!fs.existsSync(targetDir)) {
  process.exit(0);
}

// 1. Relocate heavy modal components into `pages/modals/components` subpackage
//    and wire WeChat native cross-subpackage async loading (`componentPlaceholder`).
const ASYNC_MODALS = [
  "GpsTrackModal",
  "PersonalShareCardModal",
  "PersonalReportModal",
  "MapPinPickerModal",
];

const srcCompDir = path.join(targetDir, "components");
const dstCompDir = path.join(targetDir, "pages", "modals", "components");
fs.mkdirSync(dstCompDir, { recursive: true });

let relocatedBytes = 0;
const relocatedNames = new Set();

for (const compName of ASYNC_MODALS) {
  const exts = [".js", ".json", ".wxml", ".wxss"];
  const existsAll = exts.every((ext) => fs.existsSync(path.join(srcCompDir, compName + ext)));
  if (!existsAll) continue;

  for (const ext of exts) {
    const oldFile = path.join(srcCompDir, compName + ext);
    const newFile = path.join(dstCompDir, compName + ext);
    let content = fs.readFileSync(oldFile, "utf8");
    relocatedBytes += Buffer.byteLength(content);

    if (ext === ".js") {
      // Rewrite relative require("../xxx") from `components/` (depth 1) to `pages/modals/components/` (depth 3)
      content = content.replace(/require\("(\.\.\/[^"]+)"\)/g, (_m, relReq) => {
        const absTarget = path.resolve(srcCompDir, relReq);
        let newRel = path.relative(dstCompDir, absTarget).split(path.sep).join("/");
        if (!newRel.startsWith(".")) newRel = "./" + newRel;
        return `require("${newRel}")`;
      });
    }
    fs.writeFileSync(newFile, content, "utf8");
    fs.unlinkSync(oldFile);
  }
  relocatedNames.add(compName);
}

// Update all page/component .json files referencing relocated components + ensure app.json flags
for (const jsonFile of walk(targetDir, (f) => f.endsWith(".json"))) {
  let obj;
  try {
    obj = JSON.parse(fs.readFileSync(jsonFile, "utf8"));
  } catch (_) {
    continue;
  }

  const relJsonPath = path.relative(targetDir, jsonFile).split(path.sep).join("/");
  if (relJsonPath === "app.json") {
    obj.lazyCodeLoading = "requiredComponents";
    if (!obj.preloadRule) {
      obj.preloadRule = {
        "pages/index/index": {
          network: "all",
          packages: ["pages/rank", "pages/modals", "pages/activities"],
        },
        "pages/team/team": {
          network: "all",
          packages: ["pages/rank", "pages/group-run", "pages/modals"],
        },
        "pages/coach/coach": {
          network: "all",
          packages: ["pages/modals", "pages/analysis"],
        },
      };
    }
  } else if (obj && obj.usingComponents && typeof obj.usingComponents === "object") {
    const jsonDir = path.dirname(jsonFile);
    let touched = false;
    for (const [tag, compRef] of Object.entries(obj.usingComponents)) {
      if (typeof compRef !== "string") continue;
      for (const compName of relocatedNames) {
        if (compRef.endsWith(`/${compName}`) || compRef === compName) {
          const newTargetNoExt = path.join(dstCompDir, compName);
          let newRelRef = path.relative(jsonDir, newTargetNoExt).split(path.sep).join("/");
          if (!newRelRef.startsWith(".")) newRelRef = "./" + newRelRef;
          obj.usingComponents[tag] = newRelRef;
          if (!obj.componentPlaceholder) obj.componentPlaceholder = {};
          if (!obj.componentPlaceholder[tag]) {
            obj.componentPlaceholder[tag] = "view";
          }
          touched = true;
        }
      }
    }
    if (touched && jsonDir === dstCompDir && obj.componentPlaceholder) {
      // Components inside the same `pages/modals` subpackage do not need placeholder for siblings
      delete obj.componentPlaceholder;
    }
  }

  if (relJsonPath === "project.config.json") {
    fs.writeFileSync(jsonFile, JSON.stringify(obj, null, 2), "utf8");
  } else {
    fs.writeFileSync(jsonFile, JSON.stringify(obj), "utf8");
  }
}

// 2. Minify .wxss files + inject responsive font-size scaling (`--rgm-fs`)
function scaleFontSizes(str) {
  return str.replace(
    /font-size:\s*(\d+(?:\.\d+)?)(rpx|px)(\s*!important)?/g,
    (match, numStr, unit, imp) => {
      const val = parseFloat(numStr);
      const shouldScale =
        (unit === "rpx" && val >= 14 && val <= 36) ||
        (unit === "px" && val >= 9 && val <= 18);
      if (!shouldScale) return match;
      return `font-size:calc(${numStr}${unit} * var(--rgm-fs,1))${imp || ""}`;
    }
  );
}

let savedWxssBytes = 0;
let scaledFontRules = 0;
let normalizedBtnRules = 0;
for (const file of walk(targetDir, (f) => f.endsWith(".wxss"))) {
  const raw = fs.readFileSync(file, "utf8");
  const min = raw
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/\s+/g, " ")
    .replace(/\s*([{}:;,])\s*/g, "$1")
    .replace(/;}/g, "}")
    .trim();

  // Normalize fixed rpx line-height on button/flex rules to prevent iOS/Android 2-line clipping & baseline shift
  let normalized = min.replace(/([^{}]+)\{([^{}]+)\}/g, (fullRule, selector, body) => {
    const isBtnOrFlex =
      /(?:btn|cta|button)/i.test(selector) ||
      /display:(?:inline-)?flex/i.test(body);
    if (!isBtnOrFlex) return fullRule;
    const hMatch = body.match(/(?:^|;)height:(\d+(?:\.\d+)?)rpx(?=[;]|$)/);
    if (!hMatch) return fullRule;
    const hVal = parseFloat(hMatch[1]);
    if (hVal < 44) return fullRule;
    const lhRegex = new RegExp(`(^|;)line-height:${hMatch[1].replace(".", "\\.")}rpx(\\s*!important)?(?=[;]|$)`);
    if (!lhRegex.test(body)) return fullRule;
    normalizedBtnRules++;
    let newBody = body.replace(lhRegex, "$1line-height:1.25$2");
    if (!/display:(?:inline-)?flex/i.test(newBody)) {
      newBody += ";display:flex;align-items:center;justify-content:center";
    }
    return `${selector}{${newBody}}`;
  });

  let out = normalized.replace(
    /font-size:\s*(\d+(?:\.\d+)?)(rpx|px)(\s*!important)?/g,
    (match, numStr, unit, imp) => {
      const val = parseFloat(numStr);
      const shouldScale =
        (unit === "rpx" && val >= 14 && val <= 36) ||
        (unit === "px" && val >= 9 && val <= 18);
      if (!shouldScale) return match;
      scaledFontRules++;
      return `font-size:calc(${numStr}${unit} * var(--rgm-fs,1))${imp || ""}`;
    }
  );

  const relWxss = path.relative(targetDir, file).split(path.sep).join("/");
  if (
    (relWxss.startsWith("components/") || relWxss.startsWith("pages/modals/components/")) &&
    !out.includes(".font-large{")
  ) {
    out += ".font-large{--rgm-fs:1.12}.font-xlarge{--rgm-fs:1.22}";
  }

  savedWxssBytes += Buffer.byteLength(raw) - Buffer.byteLength(out);
  fs.writeFileSync(file, out, "utf8");
}

// 3. Safe .wxml minification + static inline font-size scaling
let savedWxmlBytes = 0;
for (const file of walk(targetDir, (f) => f.endsWith(".wxml"))) {
  const raw = fs.readFileSync(file, "utf8");
  const min = raw
    .replace(/<!--[\s\S]*?-->/g, "")
    // Collapse whitespace between closing/self-closing `>` and next `<` EXCEPT inside `<text>...</text>`
    .replace(/(<\/(?!text\b)[a-zA-Z0-9_-]+>|\/>)\s+(?=<)/g, "$1")
    .replace(/(<(?!text\b)[a-zA-Z0-9_-]+(?:\s+(?:"[^"]*"|'[^']*'|[^>"'])*)?>)\s+(?=<)/g, "$1")
    .replace(/\bstyle="([^"]*)"/g, (full, styleVal) => {
      if (styleVal.includes("{{")) return full;
      let nextStyle = styleVal;
      const hMatch = nextStyle.match(/height:\s*(\d+(?:\.\d+)?)rpx/);
      if (hMatch && parseFloat(hMatch[1]) >= 44) {
        const lhRe = new RegExp(`line-height:\\s*${hMatch[1].replace(".", "\\.")}rpx`);
        if (lhRe.test(nextStyle)) {
          nextStyle = nextStyle.replace(lhRe, "line-height:1.25");
          if (!/display:\s*(?:inline-)?flex/.test(nextStyle)) {
            nextStyle += ";display:flex;align-items:center;justify-content:center";
          }
        }
      }
      if (nextStyle.includes("font-size")) {
        nextStyle = scaleFontSizes(nextStyle);
      }
      return `style="${nextStyle}"`;
    })
    .trim();
  savedWxmlBytes += Buffer.byteLength(raw) - Buffer.byteLength(min);
  fs.writeFileSync(file, min, "utf8");
}

console.log(
  `[optimize-mp] Relocated ${(relocatedBytes / 1024).toFixed(1)} KB modals to subpackage | ` +
    `Scaled ${scaledFontRules} font-size rules | Normalized ${normalizedBtnRules} button rules | ` +
    `Net delta ${(savedWxssBytes / 1024).toFixed(1)} KB (.wxss) + ${(savedWxmlBytes / 1024).toFixed(1)} KB (.wxml)`
);
