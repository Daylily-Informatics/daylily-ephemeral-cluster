#!/usr/bin/env node

import { readFileSync, writeFileSync } from "node:fs";

const [input] = process.argv.slice(2);
if (!input) {
  throw new Error("Usage: fix_portable_report_scrollbar_css.mjs <portable-report.html>");
}

const html = readFileSync(input, "utf8");
const override = `<style data-dyec-portable-scrollbar-fix>
.analytics-top-bar{width:100%!important;margin-right:0!important;margin-left:0!important}
</style>`;
if (!html.includes("</head>")) {
  throw new Error(`Portable report has no </head>: ${input}`);
}
if (html.includes("data-dyec-portable-scrollbar-fix")) {
  throw new Error(`Portable report already contains the scrollbar fix: ${input}`);
}
writeFileSync(input, html.replace("</head>", `${override}</head>`));
console.log(`Applied the headless-Chromium 100vw scrollbar containment fix to ${input}`);
