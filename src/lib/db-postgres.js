/**
 * PostgreSQL connection pool and migrations for user data.
 * Falls back to SQLite when DATABASE_URL is not set (local dev).
 */

let pool = null;
let _isPostgres = false;

function isPostgres() {
  return _isPostgres;
}

function getPool() {
  return pool;
}

/**
 * Initialize the PostgreSQL connection pool and run migrations.
 * Returns true if Postgres is available, false if falling back to SQLite.
 */
async function runPostgresMigrations() {
  const databaseUrl = process.env.DATABASE_URL;
  if (!databaseUrl) {
    console.log('[DB] No DATABASE_URL set — using SQLite for user data');
    return false;
  }

  try {
    const { Pool } = require('pg');
    pool = new Pool({
      connectionString: databaseUrl,
      ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false,
      max: 10,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 5000,
    });

    // Test connection
    const client = await pool.connect();
    console.log('[DB] PostgreSQL connected successfully');
    client.release();

    // Run migrations
    await createTables();
    _isPostgres = true;
    console.log('[DB] PostgreSQL migrations complete');
    return true;
  } catch (err) {
    console.error('[DB] PostgreSQL connection failed, falling back to SQLite:', err.message);
    pool = null;
    _isPostgres = false;
    return false;
  }
}

async function createTables() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS users (
      id SERIAL PRIMARY KEY,
      username TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      email TEXT,
      phone TEXT,
      display_name TEXT,
      avatar_url TEXT,
      games_played INTEGER DEFAULT 0,
      total_score INTEGER DEFAULT 0,
      created_at TIMESTAMP DEFAULT NOW(),
      last_login TIMESTAMP
    );
  `);
  await pool.query(`CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);`);

  await pool.query(`
    CREATE TABLE IF NOT EXISTS user_stats (
      user_id INTEGER PRIMARY KEY REFERENCES users(id),
      games_played INTEGER DEFAULT 0,
      total_points INTEGER DEFAULT 0,
      wins INTEGER DEFAULT 0,
      best_streak INTEGER DEFAULT 0,
      best_score INTEGER DEFAULT 0,
      correct_answers INTEGER DEFAULT 0,
      total_answers INTEGER DEFAULT 0,
      created_at TIMESTAMP DEFAULT NOW(),
      updated_at TIMESTAMP DEFAULT NOW()
    );
  `);
  await pool.query(`CREATE INDEX IF NOT EXISTS idx_user_stats_points ON user_stats(total_points DESC);`);
  await pool.query(`CREATE INDEX IF NOT EXISTS idx_user_stats_wins ON user_stats(wins DESC);`);

  await pool.query(`
    CREATE TABLE IF NOT EXISTS game_history (
      id SERIAL PRIMARY KEY,
      user_id INTEGER REFERENCES users(id),
      room_code TEXT,
      score INTEGER DEFAULT 0,
      correct_answers INTEGER DEFAULT 0,
      total_questions INTEGER DEFAULT 0,
      won BOOLEAN DEFAULT FALSE,
      streak_best INTEGER DEFAULT 0,
      created_at TIMESTAMP DEFAULT NOW()
    );
  `);
  await pool.query(`CREATE INDEX IF NOT EXISTS idx_game_history_user ON game_history(user_id);`);

  await pool.query(`
    CREATE TABLE IF NOT EXISTS game_sessions (
      id SERIAL PRIMARY KEY,
      room_code TEXT NOT NULL UNIQUE,
      host_user_id INTEGER REFERENCES users(id),
      status TEXT DEFAULT 'lobby',
      round_count INTEGER DEFAULT 20,
      current_round INTEGER DEFAULT 0,
      min_difficulty INTEGER DEFAULT 1,
      max_difficulty INTEGER DEFAULT 5,
      created_at TIMESTAMP DEFAULT NOW(),
      finished_at TIMESTAMP
    );
  `);
  await pool.query(`CREATE INDEX IF NOT EXISTS idx_game_sessions_code ON game_sessions(room_code);`);

  await pool.query(`
    CREATE TABLE IF NOT EXISTS game_players (
      id SERIAL PRIMARY KEY,
      session_id INTEGER REFERENCES game_sessions(id),
      user_id INTEGER REFERENCES users(id),
      score INTEGER DEFAULT 0,
      correct_count INTEGER DEFAULT 0,
      streak INTEGER DEFAULT 0,
      max_streak INTEGER DEFAULT 0,
      joined_at TIMESTAMP DEFAULT NOW()
    );
  `);

  await pool.query(`
    CREATE TABLE IF NOT EXISTS game_answers (
      id SERIAL PRIMARY KEY,
      session_id INTEGER REFERENCES game_sessions(id),
      player_id INTEGER REFERENCES game_players(id),
      question_id INTEGER,
      round_number INTEGER,
      answer_given TEXT,
      is_correct BOOLEAN,
      points_earned INTEGER,
      doubled_down BOOLEAN DEFAULT FALSE,
      time_taken_ms INTEGER,
      answered_at TIMESTAMP DEFAULT NOW()
    );
  `);
}

module.exports = { isPostgres, getPool, runPostgresMigrations };
