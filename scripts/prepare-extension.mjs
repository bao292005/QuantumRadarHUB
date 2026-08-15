import { mkdir, readFile, readdir, rename, writeFile } from "node:fs/promises";
import path from "node:path";

const outputRoot = path.resolve("out");
const inlineRoot = path.join(outputRoot, "_next", "static", "extension-inline");
const textExtensions = new Set([".css", ".html", ".js", ".json", ".txt"]);

async function walk(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const paths = [];
  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    paths.push(entryPath);
    if (entry.isDirectory()) paths.push(...await walk(entryPath));
  }
  return paths;
}

async function externalizeInlineScripts() {
  await mkdir(inlineRoot, { recursive: true });
  const htmlFiles = (await walk(outputRoot)).filter((file) => path.extname(file) === ".html");
  for (const htmlFile of htmlFiles) {
    let index = 0;
    let html = await readFile(htmlFile, "utf8");
    const slug = path.relative(outputRoot, htmlFile).replaceAll(path.sep, "-").replace(/[^a-zA-Z0-9.-]/g, "-");
    const replacements = [];
    html.replace(/<script([^>]*)>([\s\S]*?)<\/script>/g, (tag, attributes, source) => {
      if (/\bsrc\s*=/.test(attributes) || !source.trim()) return tag;
      const fileName = `${slug}-${index++}.js`;
      replacements.push({ tag, attributes, source, fileName });
      return tag;
    });
    for (const item of replacements) {
      await writeFile(path.join(inlineRoot, item.fileName), `${item.source}\n`, "utf8");
      html = html.replace(item.tag, `<script${item.attributes} src="/_next/static/extension-inline/${item.fileName}"></script>`);
    }
    await writeFile(htmlFile, html, "utf8");
  }
}

async function sanitizeReservedNames() {
  const allPaths = await walk(outputRoot);
  const reserved = allPaths
    .filter((entryPath) => path.basename(entryPath).startsWith("_"))
    .sort((a, b) => b.split(path.sep).length - a.split(path.sep).length);
  const nameMap = new Map();
  for (const oldPath of reserved) {
    const oldName = path.basename(oldPath);
    const newName = oldName === "_next" ? "next-assets" : `next-${oldName.replace(/^_+/, "")}`;
    await rename(oldPath, path.join(path.dirname(oldPath), newName));
    nameMap.set(oldName, newName);
  }
  const textFiles = (await walk(outputRoot)).filter((file) => textExtensions.has(path.extname(file)));
  for (const file of textFiles) {
    let content = await readFile(file, "utf8");
    for (const [oldName, newName] of nameMap) {
      if (oldName === "_next") {
        content = content.replaceAll("/_next/", "/next-assets/");
      } else if (path.extname(oldName)) {
        content = content.replaceAll(oldName, newName);
      } else {
        content = content.replaceAll(`/${oldName}/`, `/${newName}/`);
      }
    }
    await writeFile(file, content, "utf8");
  }
  const invalid = (await walk(outputRoot)).filter((entryPath) => path.basename(entryPath).startsWith("_"));
  if (invalid.length) throw new Error(`Chrome-reserved paths remain:\n${invalid.join("\n")}`);
}

await externalizeInlineScripts();
await sanitizeReservedNames();
console.log("Prepared Chrome MV3 output: removed reserved names and externalized inline scripts.");
