const path = require('path');
const Database = require('better-sqlite3');

// Content DB: questions, songs, groups, artists, audio_clips, face_images
// Deployed via git — safe to overwrite on every push
const CONTENT_DB_PATH = path.join(__dirname, '../../data/kpop_quiz.db');

// User DB: users, user_stats, game_history, game_sessions, game_players, game_answers
// Lives outside git — never overwritten by deploys
const USER_DB_PATH = path.join(__dirname, '../../data/users.db');

/** Get a read-only handle to the content DB (questions, songs, etc.) */
function getDb() {
  return new Database(CONTENT_DB_PATH, { readonly: true });
}

/** Get a writable handle to the content DB (rarely needed at runtime) */
function getContentWriteDb() {
  return new Database(CONTENT_DB_PATH);
}

/** Get a read-only handle to the user DB */
function getUserDb() {
  return new Database(USER_DB_PATH, { readonly: true });
}

/** Get a writable handle to the user DB */
function getUserWriteDb() {
  return new Database(USER_DB_PATH);
}

/**
 * Run migrations — creates user tables in users.db if they don't exist.
 * Also migrates existing user data from content DB if found.
 * Skipped when PostgreSQL is available (user data lives there instead).
 */
function runMigrations() {
  // Skip SQLite user migrations if Postgres is handling user data
  try {
    const { isPostgres } = require('./db-postgres');
    if (isPostgres()) {
      console.log('[DB] Skipping SQLite user migrations (using PostgreSQL)');
      return;
    }
  } catch (e) {
    // db-postgres not available, continue with SQLite
  }

  const userDb = getUserWriteDb();
  try {
    userDb.exec(`
      CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        display_name TEXT,
        avatar_url TEXT,
        games_played INTEGER DEFAULT 0,
        total_score INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')),
        last_login TEXT
      );
    `);
    userDb.exec(`CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);`);

    userDb.exec(`
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
    userDb.exec(`CREATE INDEX IF NOT EXISTS idx_user_stats_points ON user_stats(total_points DESC);`);
    userDb.exec(`CREATE INDEX IF NOT EXISTS idx_user_stats_wins ON user_stats(wins DESC);`);

    userDb.exec(`
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
    userDb.exec(`CREATE INDEX IF NOT EXISTS idx_game_history_user ON game_history(user_id);`);

    userDb.exec(`
      CREATE TABLE IF NOT EXISTS game_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_code TEXT NOT NULL UNIQUE,
        host_user_id INTEGER REFERENCES users(id),
        status TEXT DEFAULT 'lobby',
        round_count INTEGER DEFAULT 20,
        current_round INTEGER DEFAULT 0,
        min_difficulty INTEGER DEFAULT 1,
        max_difficulty INTEGER DEFAULT 5,
        created_at TEXT DEFAULT (datetime('now')),
        finished_at TEXT
      );
    `);
    userDb.exec(`CREATE INDEX IF NOT EXISTS idx_game_sessions_code ON game_sessions(room_code);`);

    userDb.exec(`
      CREATE TABLE IF NOT EXISTS game_players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER REFERENCES game_sessions(id),
        user_id INTEGER REFERENCES users(id),
        score INTEGER DEFAULT 0,
        correct_count INTEGER DEFAULT 0,
        streak INTEGER DEFAULT 0,
        max_streak INTEGER DEFAULT 0,
        joined_at TEXT DEFAULT (datetime('now'))
      );
    `);

    userDb.exec(`
      CREATE TABLE IF NOT EXISTS game_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER REFERENCES game_sessions(id),
        player_id INTEGER REFERENCES game_players(id),
        question_id INTEGER,
        round_number INTEGER,
        answer_given TEXT,
        is_correct INTEGER,
        points_earned INTEGER,
        doubled_down INTEGER DEFAULT 0,
        time_taken_ms INTEGER,
        answered_at TEXT DEFAULT (datetime('now'))
      );
    `);

    // ─── One-time migration: copy users from content DB if they exist there ───
    const userCount = userDb.prepare('SELECT COUNT(*) as c FROM users').get().c;
    if (userCount === 0) {
      try {
        const contentDb = new Database(CONTENT_DB_PATH, { readonly: true });
        const oldUsers = contentDb.prepare('SELECT * FROM users').all();
        if (oldUsers.length > 0) {
          console.log(`[DB] Migrating ${oldUsers.length} users from content DB to users.db...`);
          const insert = userDb.prepare(
            'INSERT OR IGNORE INTO users (id, username, password_hash, email, phone, display_name, avatar_url, games_played, total_score, created_at, last_login) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
          );
          for (const u of oldUsers) {
            insert.run(u.id, u.username, u.password_hash, u.email, u.phone, u.display_name, u.avatar_url, u.games_played, u.total_score, u.created_at, u.last_login);
          }

          // Migrate user_stats
          const oldStats = contentDb.prepare('SELECT * FROM user_stats').all();
          const insertStats = userDb.prepare(
            'INSERT OR IGNORE INTO user_stats (user_id, games_played, total_points, wins, best_streak, best_score, correct_answers, total_answers, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
          );
          for (const s of oldStats) {
            insertStats.run(s.user_id, s.games_played, s.total_points, s.wins, s.best_streak, s.best_score, s.correct_answers, s.total_answers, s.created_at, s.updated_at);
          }

          // Migrate game_history
          const oldHistory = contentDb.prepare('SELECT * FROM game_history').all();
          const insertHistory = userDb.prepare(
            'INSERT OR IGNORE INTO game_history (id, user_id, room_code, score, correct_answers, total_questions, won, streak_best, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)'
          );
          for (const h of oldHistory) {
            insertHistory.run(h.id, h.user_id, h.room_code, h.score, h.correct_answers, h.total_questions, h.won, h.streak_best, h.created_at);
          }

          console.log(`[DB] Migrated ${oldUsers.length} users, ${oldStats.length} stats, ${oldHistory.length} history records`);
        }
        contentDb.close();
      } catch (err) {
        // Content DB might not have user tables — that's fine
        console.log(`[DB] No users to migrate from content DB (${err.message})`);
      }
    }

    console.log('[DB] Migrations complete (users.db)');
  } finally {
    userDb.close();
  }
}

module.exports = { getDb, getContentWriteDb, getUserDb, getUserWriteDb, runMigrations, CONTENT_DB_PATH, USER_DB_PATH };
