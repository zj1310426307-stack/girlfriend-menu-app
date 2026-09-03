const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const dist = path.join(root, "dist");

function collectJavaScriptFiles(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) return collectJavaScriptFiles(target);
    return entry.isFile() && entry.name.endsWith(".js") ? [target] : [];
  });
}

assert.equal(fs.existsSync(path.join(dist, "app.json")), true, "dist/app.json must exist before integrity verification");

const files = collectJavaScriptFiles(dist);
const sources = new Map(files.map((file) => [file, fs.readFileSync(file, "utf8")]));
const definitions = new Set();
for (const source of sources.values()) {
  for (const match of source.matchAll(/(?:^|[,{])(\d+):function\(/g)) definitions.add(match[1]);
}

const missing = [];
for (const [file, source] of sources) {
  const moduleInitializers = source.matchAll(
    /\b\d+:function\([^,]+,[^,]+,([A-Za-z_$][\w$]*)\)\{([\s\S]*?)(?=function\s+[A-Za-z_$][\w$]*\()/g
  );
  for (const [, loaderName, initializer] of moduleInitializers) {
    const escaped = loaderName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    for (const match of initializer.matchAll(new RegExp(`\\b${escaped}\\((\\d+)\\)`, "g"))) {
      if (!definitions.has(match[1])) {
        missing.push(`${path.relative(dist, file)} -> ${match[1]}`);
      }
    }
  }
}

assert.deepEqual([...new Set(missing)], [], "compiled chunks must not reference missing numeric modules");
console.log(`weapp dist integrity: PASS (${files.length} JavaScript files, ${definitions.size} modules)`);
