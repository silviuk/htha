// Node on Windows resolves an explicit directory through index.js.
// Keep the brief's `node --test tests/` command reproducible without dependencies.
require('./schedule-card.test.cjs');
require('./schedule-editor.test.cjs');
