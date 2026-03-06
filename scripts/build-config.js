#!/usr/bin/env node
/**
 * Build script for Vercel: writes phase_3/config.js with API_BASE_URL from env.
 * Run: API_BASE_URL=https://your-api.railway.app node scripts/build-config.js
 */
const fs = require("fs");
const path = require("path");

const apiBase = (process.env.API_BASE_URL || "").trim().replace(/\/$/, "");
const configPath = path.join(__dirname, "..", "phase_3", "config.js");
const content = `/**
 * API base URL for the Phase 2 backend.
 * - Local dev: "" (uses same origin when served by FastAPI)
 * - Vercel: Injected at build from API_BASE_URL env.
 */
window.API_BASE = "${apiBase.replace(/"/g, '\\"')}";
`;

fs.writeFileSync(configPath, content, "utf8");
console.log("Wrote config.js with API_BASE =", apiBase || "(empty, same-origin)");
