// Patch script — run once with: node patch.js
const fs = require('fs');
const path = require('path');

function patch(filePath, replacements) {
  let content = fs.readFileSync(filePath, 'utf8');
  let changed = 0;
  for (const [from, to] of replacements) {
    const before = content;
    content = content.split(from).join(to);
    if (content !== before) changed++;
    else console.warn(`  [!] Pattern not found: ${from.slice(0, 60)}...`);
  }
  fs.writeFileSync(filePath, content, 'utf8');
  console.log(`  [OK] ${filePath} — ${changed}/${replacements.length} replacements applied`);
}

console.log('\n=== Portfolio Nexus patch ===\n');

patch(path.join(__dirname, 'server.js'), [
  // Fix 1: remove feed=iex from daily bars fetch (appears twice)
  [
    "timeframe: '1Day', limit: '60', feed: 'iex'",
    "timeframe: '1Day', limit: '60'"
  ],
  // Fix 2: save watchlistSize + aiManagedWatchlist in config endpoint
  [
    `if (resetHalt) { AT.halted = false; AT.haltReason = ''; AT.sessionStartEquity = null; }

  atSchedule();
  res.json(atPublicState());`,
    `if (resetHalt) { AT.halted = false; AT.haltReason = ''; AT.sessionStartEquity = null; }

  const { aiManagedWatchlist, watchlistSize } = req.body;
  if (typeof aiManagedWatchlist === 'boolean') AT.aiManagedWatchlist = aiManagedWatchlist;
  if (watchlistSize != null && Number.isFinite(+watchlistSize)) AT.watchlistSize = Math.max(3, Math.min(50, +watchlistSize));

  saveAtState();
  atSchedule();
  res.json(atPublicState());`
  ],
  // Fix 3: raise watchlistSize cap in aiSelectWatchlist
  [
    "const n = Math.max(5, Math.min(30, AT.watchlistSize || 10));",
    "const n = Math.max(5, Math.min(50, AT.watchlistSize || 30));"
  ],
  // Fix 4: default watchlistSize to 30
  [
    "watchlistSize: 10,          // how many symbols Claude picks per cycle",
    "watchlistSize: 30,          // how many symbols Claude picks per cycle"
  ],
]);

patch(path.join(__dirname, 'public', 'index.html'), [
  // Fix 5: raise UI max and default
  [
    'value="10" min="3" max="20"',
    'value="30" min="3" max="50"'
  ],
  [
    'Quanti simboli analizzare per ciclo (3–20)',
    'Quanti simboli analizzare per ciclo (3–50)'
  ],
  [
    'data.watchlistSize || 10',
    'data.watchlistSize || 30'
  ],
]);

console.log('\nDone! Restart the server: node server.js\n');
