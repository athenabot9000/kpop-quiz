const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { getUserWriteDb, getUserDb } = require('./db');
const { isPostgres, getPool } = require('./db-postgres');

const JWT_SECRET = process.env.JWT_SECRET || 'kpop-quiz-secret-key-change-in-production-2024';
const JWT_EXPIRES = '7d';
const SALT_ROUNDS = 10;

/**
 * Register a new user
 */
async function registerUser(username, password, displayName) {
  // Validate
  if (!username || username.length < 3 || username.length > 20) {
    throw new Error('Username must be 3-20 characters');
  }
  if (!password || password.length < 4) {
    throw new Error('Password must be at least 4 characters');
  }
  if (!displayName || displayName.length < 1 || displayName.length > 20) {
    throw new Error('Display name must be 1-20 characters');
  }

  if (isPostgres()) {
    const pool = getPool();

    // Check if username exists
    const existing = await pool.query(
      'SELECT id FROM users WHERE LOWER(username) = LOWER($1)', [username]
    );
    if (existing.rows.length > 0) {
      throw new Error('Username already taken');
    }

    // Hash password and insert
    const passwordHash = bcrypt.hashSync(password, SALT_ROUNDS);
    const result = await pool.query(
      'INSERT INTO users (username, password_hash, display_name) VALUES ($1, $2, $3) RETURNING id',
      [username.toLowerCase(), passwordHash, displayName]
    );
    const userId = result.rows[0].id;

    // Create initial stats record
    await pool.query('INSERT INTO user_stats (user_id) VALUES ($1)', [userId]);

    return { id: userId, username: username.toLowerCase(), displayName };
  } else {
    // SQLite fallback
    const db = getUserWriteDb();
    try {
      const existing = db.prepare('SELECT id FROM users WHERE LOWER(username) = LOWER(?)').get(username);
      if (existing) {
        throw new Error('Username already taken');
      }

      const passwordHash = bcrypt.hashSync(password, SALT_ROUNDS);
      const result = db.prepare(
        'INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)'
      ).run(username.toLowerCase(), passwordHash, displayName);

      const userId = result.lastInsertRowid;
      db.prepare('INSERT INTO user_stats (user_id) VALUES (?)').run(userId);

      return { id: userId, username: username.toLowerCase(), displayName };
    } finally {
      db.close();
    }
  }
}

/**
 * Login a user, returns user data + JWT token
 */
async function loginUser(username, password) {
  if (isPostgres()) {
    const pool = getPool();

    const result = await pool.query(
      'SELECT id, username, password_hash, display_name FROM users WHERE LOWER(username) = LOWER($1)',
      [username]
    );
    if (result.rows.length === 0) {
      throw new Error('Invalid username or password');
    }

    const user = result.rows[0];
    const valid = bcrypt.compareSync(password, user.password_hash);
    if (!valid) {
      throw new Error('Invalid username or password');
    }

    // Update last_login
    await pool.query('UPDATE users SET last_login = NOW() WHERE id = $1', [user.id]);

    const token = jwt.sign(
      { userId: user.id, username: user.username, displayName: user.display_name },
      JWT_SECRET,
      { expiresIn: JWT_EXPIRES }
    );

    return {
      token,
      user: {
        id: user.id,
        username: user.username,
        displayName: user.display_name,
      },
    };
  } else {
    // SQLite fallback
    const db = getUserDb();
    try {
      const user = db.prepare(
        'SELECT id, username, password_hash, display_name FROM users WHERE LOWER(username) = LOWER(?)'
      ).get(username);

      if (!user) {
        throw new Error('Invalid username or password');
      }

      const valid = bcrypt.compareSync(password, user.password_hash);
      if (!valid) {
        throw new Error('Invalid username or password');
      }

      // Update last_login
      const writeDb = getUserWriteDb();
      try {
        writeDb.prepare("UPDATE users SET last_login = datetime('now') WHERE id = ?").run(user.id);
      } finally {
        writeDb.close();
      }

      const token = jwt.sign(
        { userId: user.id, username: user.username, displayName: user.display_name },
        JWT_SECRET,
        { expiresIn: JWT_EXPIRES }
      );

      return {
        token,
        user: {
          id: user.id,
          username: user.username,
          displayName: user.display_name,
        },
      };
    } finally {
      db.close();
    }
  }
}

/**
 * Verify JWT token, returns user payload or null
 */
function verifyToken(token) {
  try {
    return jwt.verify(token, JWT_SECRET);
  } catch {
    return null;
  }
}

/**
 * Get user by ID
 */
async function getUserById(userId) {
  if (isPostgres()) {
    const pool = getPool();
    const result = await pool.query(
      'SELECT id, username, display_name, created_at, last_login FROM users WHERE id = $1',
      [userId]
    );
    return result.rows.length > 0 ? result.rows[0] : null;
  } else {
    const db = getUserDb();
    try {
      const user = db.prepare(
        'SELECT id, username, display_name, created_at, last_login FROM users WHERE id = ?'
      ).get(userId);
      return user || null;
    } finally {
      db.close();
    }
  }
}

/**
 * Get user stats
 */
async function getUserStats(userId) {
  if (isPostgres()) {
    const pool = getPool();
    const result = await pool.query('SELECT * FROM user_stats WHERE user_id = $1', [userId]);
    return result.rows.length > 0 ? result.rows[0] : null;
  } else {
    const db = getUserDb();
    try {
      const stats = db.prepare('SELECT * FROM user_stats WHERE user_id = ?').get(userId);
      return stats || null;
    } finally {
      db.close();
    }
  }
}

/**
 * Get user game history
 */
async function getGameHistory(userId, limit = 20) {
  if (isPostgres()) {
    const pool = getPool();
    const result = await pool.query(
      'SELECT * FROM game_history WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2',
      [userId, limit]
    );
    return result.rows;
  } else {
    const db = getUserDb();
    try {
      return db.prepare(
        'SELECT * FROM game_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?'
      ).all(userId, limit);
    } finally {
      db.close();
    }
  }
}

/**
 * Record game results for a user
 */
async function recordGameResult(userId, roomCode, score, correctAnswers, totalQuestions, won, streakBest) {
  if (isPostgres()) {
    const pool = getPool();

    // Insert game history
    await pool.query(
      `INSERT INTO game_history (user_id, room_code, score, correct_answers, total_questions, won, streak_best)
       VALUES ($1, $2, $3, $4, $5, $6, $7)`,
      [userId, roomCode, score, correctAnswers, totalQuestions, won ? true : false, streakBest]
    );

    // Update user_stats
    const stats = await pool.query('SELECT * FROM user_stats WHERE user_id = $1', [userId]);
    if (stats.rows.length > 0) {
      await pool.query(
        `UPDATE user_stats SET
          games_played = games_played + 1,
          total_points = total_points + $1,
          wins = wins + $2,
          best_streak = GREATEST(best_streak, $3),
          best_score = GREATEST(best_score, $4),
          correct_answers = correct_answers + $5,
          total_answers = total_answers + $6,
          updated_at = NOW()
        WHERE user_id = $7`,
        [score, won ? 1 : 0, streakBest, score, correctAnswers, totalQuestions, userId]
      );
    } else {
      await pool.query(
        `INSERT INTO user_stats (user_id, games_played, total_points, wins, best_streak, best_score, correct_answers, total_answers)
         VALUES ($1, 1, $2, $3, $4, $5, $6, $7)`,
        [userId, score, won ? 1 : 0, streakBest, score, correctAnswers, totalQuestions]
      );
    }

    console.log(`[Stats] Recorded game for user ${userId}: score=${score}, correct=${correctAnswers}/${totalQuestions}, won=${won}`);
  } else {
    // SQLite fallback
    const db = getUserWriteDb();
    try {
      db.prepare(`
        INSERT INTO game_history (user_id, room_code, score, correct_answers, total_questions, won, streak_best)
        VALUES (?, ?, ?, ?, ?, ?, ?)
      `).run(userId, roomCode, score, correctAnswers, totalQuestions, won ? 1 : 0, streakBest);

      const stats = db.prepare('SELECT * FROM user_stats WHERE user_id = ?').get(userId);
      if (stats) {
        db.prepare(`
          UPDATE user_stats SET
            games_played = games_played + 1,
            total_points = total_points + ?,
            wins = wins + ?,
            best_streak = MAX(best_streak, ?),
            best_score = MAX(best_score, ?),
            correct_answers = correct_answers + ?,
            total_answers = total_answers + ?,
            updated_at = datetime('now')
          WHERE user_id = ?
        `).run(score, won ? 1 : 0, streakBest, score, correctAnswers, totalQuestions, userId);
      } else {
        db.prepare(`
          INSERT INTO user_stats (user_id, games_played, total_points, wins, best_streak, best_score, correct_answers, total_answers)
          VALUES (?, 1, ?, ?, ?, ?, ?, ?)
        `).run(userId, score, won ? 1 : 0, streakBest, score, correctAnswers, totalQuestions);
      }

      console.log(`[Stats] Recorded game for user ${userId}: score=${score}, correct=${correctAnswers}/${totalQuestions}, won=${won}`);
    } finally {
      db.close();
    }
  }
}

/**
 * Get leaderboard
 */
async function getLeaderboard(sortBy = 'total_points', limit = 50) {
  const validSorts = ['total_points', 'wins', 'games_played', 'best_score', 'best_streak'];
  const sort = validSorts.includes(sortBy) ? sortBy : 'total_points';

  if (isPostgres()) {
    const pool = getPool();
    // Note: sort column is validated above against a whitelist, safe to interpolate
    const result = await pool.query(
      `SELECT u.id, u.username, u.display_name, s.*
       FROM user_stats s
       JOIN users u ON u.id = s.user_id
       WHERE s.games_played > 0
       ORDER BY s.${sort} DESC
       LIMIT $1`,
      [limit]
    );
    return result.rows;
  } else {
    const db = getUserDb();
    try {
      return db.prepare(`
        SELECT u.id, u.username, u.display_name, s.*
        FROM user_stats s
        JOIN users u ON u.id = s.user_id
        WHERE s.games_played > 0
        ORDER BY s.${sort} DESC
        LIMIT ?
      `).all(limit);
    } finally {
      db.close();
    }
  }
}

module.exports = {
  registerUser,
  loginUser,
  verifyToken,
  getUserById,
  getUserStats,
  getGameHistory,
  recordGameResult,
  getLeaderboard,
  JWT_SECRET,
};
