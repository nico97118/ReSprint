import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const staticDir = join(root, "src/resprint/frontend/static");
const minDir = join(staticDir, "min");
const checkOnly = process.argv.includes("--check");

const assets = [
  { input: "common.css", output: "common.min.css", kind: "css" },
  { input: "home.css", output: "home.min.css", kind: "css" },
  { input: "report.css", output: "report.min.css", kind: "css" },
  { input: "table.css", output: "table.min.css", kind: "css" },
  { input: "theme.js", output: "theme.min.js", kind: "js" },
  { input: "home.js", output: "home.min.js", kind: "js" },
  { input: "report.js", output: "report.min.js", kind: "js" },
  { input: "table.js", output: "table.min.js", kind: "js" },
  { input: "charts.js", output: "charts.min.js", kind: "js" },
];

if (!checkOnly) {
  await mkdir(minDir, { recursive: true });
}

const mismatches = [];
for (const asset of assets) {
  const inputPath = join(staticDir, asset.input);
  const outputPath = join(minDir, asset.output);
  const source = await readFile(inputPath, "utf8");
  const minified = asset.kind === "css" ? minifyCss(source) : minifyJs(source);
  const expected = `${minified}\n`;

  if (checkOnly) {
    let actual;
    try {
      actual = await readFile(outputPath, "utf8");
    } catch {
      mismatches.push(
        `${relative(root, outputPath)} is missing. Run npm run minify to regenerate it.`,
      );
      continue;
    }

    if (actual !== expected) {
      mismatches.push(
        `${relative(root, outputPath)} is stale. Run npm run minify to regenerate it.`,
      );
    }
    continue;
  }

  await writeFile(outputPath, expected, "utf8");
  console.log(`${relative(root, inputPath)} -> ${relative(root, outputPath)}`);
}

if (checkOnly && mismatches.length > 0) {
  console.error("Minified frontend assets are out of date:");
  for (const mismatch of mismatches) {
    console.error(`- ${mismatch}`);
  }
  process.exitCode = 1;
}

function minifyCss(source) {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/\s+/g, " ")
    .replace(/\s*([{}:;,>+~])\s*/g, "$1")
    .replace(/;}/g, "}")
    .trim();
}

function minifyJs(source) {
  let output = "";
  let index = 0;
  let state = "normal";
  let templateBraceDepth = 0;
  let pendingSpace = false;
  let lastEmitted = "";

  const isIdentifierChar = (char) => /[A-Za-z0-9_$]/.test(char);

  while (index < source.length) {
    const char = source[index];
    const next = source[index + 1];

    if (state === "line-comment") {
      if (char === "\n" || char === "\r") {
        state = "normal";
      }
      index += 1;
      continue;
    }

    if (state === "block-comment") {
      if (char === "*" && next === "/") {
        state = "normal";
        index += 2;
        continue;
      }
      index += 1;
      continue;
    }

    if (state === "single-quote" || state === "double-quote") {
      output += char;
      if (char === "\\") {
        output += next ?? "";
        index += 2;
        continue;
      }
      if (
        (state === "single-quote" && char === "'") ||
        (state === "double-quote" && char === '"')
      ) {
        state = "normal";
      }
      index += 1;
      continue;
    }

    if (state === "template") {
      output += char;
      if (char === "\\") {
        output += next ?? "";
        index += 2;
        continue;
      }
      if (char === "`") {
        state = "normal";
        index += 1;
        continue;
      }
      if (char === "$" && next === "{") {
        output += "{";
        state = "normal";
        templateBraceDepth = 1;
        index += 2;
        continue;
      }
      index += 1;
      continue;
    }

    if (/\s/.test(char)) {
      pendingSpace = true;
      index += 1;
      continue;
    }

    if (char === "/" && next === "/") {
      state = "line-comment";
      index += 2;
      continue;
    }

    if (char === "/" && next === "*") {
      state = "block-comment";
      index += 2;
      continue;
    }

    if (pendingSpace && isIdentifierChar(lastEmitted) && isIdentifierChar(char)) {
      output += " ";
      lastEmitted = " ";
    }
    pendingSpace = false;

    if (templateBraceDepth > 0) {
      if (char === "{") {
        templateBraceDepth += 1;
      } else if (char === "}") {
        templateBraceDepth -= 1;
        output += char;
        lastEmitted = char;
        index += 1;
        if (templateBraceDepth === 0) {
          state = "template";
        }
        continue;
      }
    }

    if (char === "'") {
      output += char;
      state = "single-quote";
      lastEmitted = char;
      index += 1;
      continue;
    }

    if (char === '"') {
      output += char;
      state = "double-quote";
      lastEmitted = char;
      index += 1;
      continue;
    }

    if (char === "`") {
      output += char;
      state = "template";
      lastEmitted = char;
      index += 1;
      continue;
    }

    output += char;
    lastEmitted = char;
    index += 1;
  }

  return output.trim();
}
