const path = require('path');
const Database = require('better-sqlite3');

const DB_PATH = path.join(__dirname, '../../data/kpop_quiz.db');

function getDb(readonly = false) {
  return new Database(DB_PATH, { readonly });
}

function getWriteDb() {
  return new Database(DB_PATH);
}

/**
 * Run migrations to add user_stats and game_history tables
 */
function runMigrations() {
  const db = getWriteDb();
  try {
    // Add user_stats table if it doesn't exist
    db.exec(`
      CREATE TABLE IF NOT EXISTS user_stats (
        user_id INTEGER PRIMARY KEY REFERENCES users(id),
        games_played INTEGER DEFAULT 0,
        total_points INTEGER DEFAULT 0,
        wins INTEGER DEFAULT 0,
        best_streak INTEGER DEFAULT 0,
        best_score INTEGER DEFAULT 0,
        correct_answers INTEGER DEFAULT 0,
        total_answers INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
      );
    `);

    // Add game_history table if it doesn't exist
    db.exec(`
      CREATE TABLE IF NOT EXISTS game_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id),
        room_code TEXT,
        score INTEGER DEFAULT 0,
        correct_answers INTEGER DEFAULT 0,
        total_questions INTEGER DEFAULT 0,
        won INTEGER DEFAULT 0,
        streak_best INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
      );
    `);

    db.exec(`CREATE INDEX IF NOT EXISTS idx_game_history_user ON game_history(user_id);`);
    db.exec(`CREATE INDEX IF NOT EXISTS idx_user_stats_points ON user_stats(total_points DESC);`);
    db.exec(`CREATE INDEX IF NOT EXISTS idx_user_stats_wins ON user_stats(wins DESC);`);

    console.log('[DB] Migrations complete');
  } finally {
    db.close();
  }
}

module.exports = { getDb, getWriteDb, runMigrations, DB_PATH };
