import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { marked } from "/Users/jmajor/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/marked/lib/marked.esm.js";
import { chromium } from "/Users/jmajor/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs";

const root = "/Users/jmajor/Downloads/remaining-giab-hiomr2-final-report";
const base = "REMAINING_GIAB_HIOMR2_FINAL_REPORT";
const markdown = fs.readFileSync(path.join(root, `${base}.md`), "utf8");
const body = marked.parse(markdown, { gfm: true });
const css = `
  @page { size: Letter; margin: 0.52in 0.52in 0.58in; }
  * { box-sizing: border-box; }
  body { font-family: Inter, Arial, sans-serif; color: #17212b; font-size: 8.8pt; line-height: 1.30; margin: 0; }
  h1 { color: #153a5b; font-size: 23pt; line-height: 1.12; margin: 0 0 12px; }
  h2 { color: #176b78; font-size: 15pt; margin: 19px 0 7px; border-bottom: 1px solid #b9d8db; padding-bottom: 3px; break-after: avoid; }
  h3 { color: #34556b; font-size: 11.5pt; margin: 14px 0 5px; break-after: avoid; }
  p { margin: 5px 0 8px; }
  ul { margin: 5px 0 9px 18px; padding: 0; }
  li { margin: 2px 0; }
  code { font-family: SFMono-Regular, Menlo, monospace; font-size: 8.2pt; color: #673c15; overflow-wrap: anywhere; }
  pre { white-space: pre-wrap; overflow-wrap: anywhere; word-break: break-word; margin: 6px 0 9px; }
  pre code { white-space: inherit; }
  table { border-collapse: collapse; width: 100%; margin: 7px 0 13px; font-size: 6.7pt; table-layout: auto; break-inside: auto; }
  thead { display: table-header-group; }
  tr { break-inside: avoid; }
  th { background: #173f5f; color: white; font-weight: 650; text-align: left; }
  th, td { border: 1px solid #c4d0d8; padding: 2.6px 3.5px; vertical-align: top; overflow-wrap: anywhere; }
  tbody tr:nth-child(even) { background: #f3f7f9; }
  a { color: #0a5f8f; text-decoration: none; overflow-wrap: anywhere; }
  strong { color: #173f5f; }
`;
const html = `<!doctype html><html><head><meta charset="utf-8"><title>Remaining-GIAB HIOMR2 final report</title><style>${css}</style></head><body>${body}</body></html>`;
const htmlPath = path.join(root, `${base}.html`);
const pdfPath = path.join(root, `${base}.pdf`);
fs.writeFileSync(htmlPath, html);
const browser = await chromium.launch({
  headless: true,
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
});
const page = await browser.newPage();
await page.goto(`file://${htmlPath}`, { waitUntil: "load" });
await page.pdf({ path: pdfPath, format: "Letter", printBackground: true, displayHeaderFooter: true, headerTemplate: "<div></div>", footerTemplate: '<div style="font-size:7px;color:#647581;width:100%;text-align:center"><span class="pageNumber"></span> / <span class="totalPages"></span></div>', margin: { top: "0.52in", right: "0.52in", bottom: "0.58in", left: "0.52in" } });
await browser.close();
console.log(`html=${htmlPath}`);
console.log(`pdf=${pdfPath}`);
