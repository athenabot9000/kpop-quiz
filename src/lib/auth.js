const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { getUserWriteDb, getUserDb } = require('./db');

const JWT_SECRET = process.env.JWT_SECRET || 'kpop-quiz-secret-key-change-in-production-2024';
const JWT_EXPIRES = '7d';
const SALT_ROUNDS = 10;

/**
 * Register a new user
 */
function registerUser(username, password, displayName) {
  const db = getUserWriteDb();
  try {
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

    // Check if username exists
    const existing = db.prepare('SELECT id FROM users WHERE LOWER(username) = LOWER(?)').get(username);
    if (existing) {
      throw new Error('Username already taken');
    }

    // Hash password and insert
    const passwordHash = bcrypt.hashSync(password, SALT_ROUNDS);
    const result = db.prepare(
      'INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)'
    ).run(username.toLowerCase(), passwordHash, displayName);

    const userId = result.lastInsertRowid;

    // Create initial stats record
    db.prepare('INSERT INTO user_stats (user_id) VALUES (?)').run(userId);

    return { id: userId, username: username.toLowerCase(), displayName };
  } finally {
    db.close();
  }
}

/**
 * Login a user, returns user data + JWT token
 */
function loginUser(username, password) {
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
function getUserById(userId) {
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

/**
 * Get user stats
 */
function getUserStats(userId) {
  const db = getUserDb();
  try {
    const stats = db.prepare('SELECT * FROM user_stats WHERE user_id = ?').get(userId);
    return stats || null;
  } finally {
    db.close();
  }
}

/**
 * Get user game history
 */
function getGameHistory(userId, limit = 20) {
  const db = getUserDb();
  try {
    return db.prepare(
      'SELECT * FROM game_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?'
    ).all(userId, limit);
  } finally {
    db.close();
  }
}

/**
 * Record game results for a user
 */
function recordGameResult(userId, roomCode, score, correctAnswers, totalQuestions, won, streakBest) {
  const db = getUserWriteDb();
  try {
    // Insert game history
    db.prepare(`
      INSERT INTO game_history (user_id, room_code, score, correct_answers, total_questions, won, streak_best)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(userId, roomCode, score, correctAnswers, totalQuestions, won ? 1 : 0, streakBest);

    // Update user_stats
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
      // Create stats row if missing
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

/**
 * Get leaderboard
 */
function getLeaderboard(sortBy = 'total_points', limit = 50) {
  const db = getUserDb();
  try {
    const validSorts = ['total_points', 'wins', 'games_played', 'best_score', 'best_streak'];
    const sort = validSorts.includes(sortBy) ? sortBy : 'total_points';

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
