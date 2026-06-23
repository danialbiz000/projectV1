// Patch script — run once with: node patch.js
const fs = require('fs');
const path = require('path');

let totalFixed = 0;

function replace(content, from, to, label) {
  if (content.includes(from)) {
    const result = content.split(from).join(to);
    console.log(`  [OK] ${label}`);
    totalFixed++;
    return result;
  }
  console.log(`  [--] Already applied or not found: ${label}`);
  return content;
}

console.log('\n=== Portfolio Nexus patch ===\n');

// ── server.js ──────────────────────────────────────────────────────────────
let srv = fs.readFileSync(path.join(__dirname, 'server.js'), 'utf8');

// Fix A: remove feed=iex from daily bars (AT cycle)
srv = replace(srv,
  "timeframe: '1Day', limit: '60', feed: 'iex'",
  "timeframe: '1Day', limit: '60'",
  "Remove feed=iex from daily bars"
);

// Fix B: watchlistSize default 10 → 30
srv = replace(srv,
  "watchlistSize: 10,",
  "watchlistSize: 30,",
  "Default watchlistSize 10→30"
);

// Fix C: aiSelectWatchlist cap 30 → 50 (variant 1)
srv = replace(srv,
  "Math.max(5, Math.min(30, AT.watchlistSize || 10))",
  "Math.max(5, Math.min(50, AT.watchlistSize || 30))",
  "Raise aiSelectWatchlist cap to 50"
);
// Fix C variant 2 (already has || 30 but wrong cap)
srv = replace(srv,
  "Math.max(5, Math.min(30, AT.watchlistSize || 30))",
  "Math.max(5, Math.min(50, AT.watchlistSize || 30))",
  "Raise aiSelectWatchlist cap to 50 (v2)"
);

// Fix D: config endpoint — add watchlistSize + aiManagedWatchlist saving
// Try multiple variants of the surrounding text
const configPatterns = [
  `if (resetHalt) { AT.halted = false; AT.haltReason = ''; AT.sessionStartEquity = null; }\n\n  atSchedule();\n  res.json(atPublicState());\n});`,
  `if (resetHalt) { AT.halted = false; AT.haltReason = ''; AT.sessionStartEquity = null; }\r\n\r\n  atSchedule();\r\n  res.json(atPublicState());\r\n});`,
];
const configReplacement = `if (resetHalt) { AT.halted = false; AT.haltReason = ''; AT.sessionStartEquity = null; }

  const { aiManagedWatchlist, watchlistSize } = req.body;
  if (typeof aiManagedWatchlist === 'boolean') AT.aiManagedWatchlist = aiManagedWatchlist;
  if (watchlistSize != null && Number.isFinite(+watchlistSize)) AT.watchlistSize = Math.max(3, Math.min(50, +watchlistSize));

  saveAtState();
  atSchedule();
  res.json(atPublicState());
});`;

// Check if already patched
if (srv.includes("const { aiManagedWatchlist, watchlistSize } = req.body;")) {
  console.log("  [--] Already applied or not found: Config endpoint watchlistSize save");
} else {
  let patched = false;
  for (const pat of configPatterns) {
    if (srv.includes(pat)) {
      srv = srv.split(pat).join(configReplacement);
      console.log("  [OK] Config endpoint watchlistSize save");
      totalFixed++;
      patched = true;
      break;
    }
  }
  if (!patched) {
    // Print surrounding context to help debug
    const idx = srv.indexOf('atSchedule();\n  res.json(atPublicState());');
    console.log("  [!!] Config endpoint fix FAILED — printing context for debug:");
    if (idx > -1) console.log(JSON.stringify(srv.slice(Math.max(0, idx-200), idx+100)));
    else console.log("  [!!] Could not find atSchedule() near config endpoint");
  }
}

fs.writeFileSync(path.join(__dirname, 'server.js'), srv, 'utf8');
console.log("  => server.js saved\n");

// ── public/index.html ──────────────────────────────────────────────────────
let html = fs.readFileSync(path.join(__dirname, 'public', 'index.html'), 'utf8');

html = replace(html, 'value="10" min="3" max="20"', 'value="30" min="3" max="50"', 'Input max 20→50, default 10→30');
html = replace(html, 'value="10" min="3" max="20" step="1"', 'value="30" min="3" max="50" step="1"', 'Input max 20→50 (v2)');
html = replace(html, '(3–20)', '(3–50)', 'Label 3–20 → 3–50');
html = replace(html, '(3-20)', '(3-50)', 'Label 3-20 → 3-50 (v2)');
html = replace(html, 'data.watchlistSize || 10', 'data.watchlistSize || 30', 'UI default watchlistSize 10→30');

fs.writeFileSync(path.join(__dirname, 'public', 'index.html'), html, 'utf8');
console.log("  => public/index.html saved\n");

console.log(`=== Done: ${totalFixed} fix(es) applied ===`);
console.log('Restart the server: node server.js\n');
