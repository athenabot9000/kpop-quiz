const path = require('path');
const Database = require('better-sqlite3');

const DB_PATH = path.join(__dirname, '../../data/kpop_quiz.db');

// ─── Database Queries ───

function getDb() {
  return new Database(DB_PATH, { readonly: true });
}

// Quick Quiz group config: name variants for text matching + DB group IDs
const QUICK_QUIZ_GROUPS = {
  names: ['ENHYPEN', 'TWICE', 'BABYMONSTER', 'Baby Monster', 'BLACKPINK', 'KATSEYE', 'Katseye'],
  ids: [59, 208, 275], // ENHYPEN=59, BLACKPINK=208, TWICE=275 (BABYMONSTER + KATSEYE added dynamically)
};

// Resolve quick quiz group IDs at startup (includes any newly added groups)
function getQuickQuizGroupIds() {
  const db = getDb();
  try {
    const rows = db.prepare(
      `SELECT id FROM groups WHERE UPPER(name) IN (${QUICK_QUIZ_GROUPS.names.map(() => '?').join(',')})`,
    ).all(...QUICK_QUIZ_GROUPS.names.map(n => n.toUpperCase()));
    return rows.map(r => r.id);
  } finally {
    db.close();
  }
}

/**
 * Load questions bucketed by difficulty.
 * Returns an object: { 1: [...], 2: [...], 3: [...], 4: [...], 5: [...] }
 * Includes text, face, and audio question types.
 * Excludes questions with em-dash correct answers (bad data).
 * @param {string} mode - 'all' for Energy Exam, 'quick' for Quick Quiz (5 groups only)
 */
function loadQuestionPool(mode = 'all') {
  const db = getDb();
  try {
    const rows = db
      .prepare(
        `SELECT id, type, difficulty, category, question_text, correct_answer, metadata_json,
                face_image_id, audio_clip_id
         FROM questions
         WHERE correct_answer != '—'
           AND correct_answer != '-'
           AND correct_answer != ''
           AND LENGTH(TRIM(correct_answer)) > 0
         ORDER BY RANDOM()`
      )
      .all();

    // If quick quiz, filter to only questions about the 5 groups
    let filtered = rows;
    if (mode === 'quick') {
      const groupIds = getQuickQuizGroupIds();
      const namePatterns = QUICK_QUIZ_GROUPS.names.map(n => n.toUpperCase());

      filtered = rows.filter(row => {
        // Check metadata group_id or correct_group_id
        if (row.metadata_json) {
          try {
            const meta = JSON.parse(row.metadata_json);
            if (meta.group_id && groupIds.includes(meta.group_id)) return true;
            if (meta.correct_group_id && groupIds.includes(meta.correct_group_id)) return true;
          } catch {}
        }
        // Check question text and answer for group name mentions
        const qt = (row.question_text || '').toUpperCase();
        const ca = (row.correct_answer || '').toUpperCase();
        return namePatterns.some(name => qt.includes(name) || ca === name);
      });
    }

    const pool = { 1: [], 2: [], 3: [], 4: [], 5: [] };
    for (const row of filtered) {
      const d = row.difficulty;
      if (d >= 1 && d <= 5 && pool[d]) {
        pool[d].push(row);
      }
    }
    return pool;
  } finally {
    db.close();
  }
}

function generateWrongAnswers(question) {
  const db = getDb();
  try {
    const meta = question.metadata_json ? JSON.parse(question.metadata_json) : {};
    const correct = question.correct_answer;

    // ─── FIRST: check if wrong_answers are embedded in metadata ───
    if (meta.wrong_answers && Array.isArray(meta.wrong_answers) && meta.wrong_answers.length >= 3) {
      // Filter out any invalid answers (dashes, empty, duplicates of correct)
      const valid = meta.wrong_answers.filter(
        (a) => a && a !== '—' && a !== '-' && a.trim().length > 0 && a !== correct
      );
      if (valid.length >= 3) {
        // Shuffle and return 3
        return valid.sort(() => Math.random() - 0.5).slice(0, 3);
      }
    }

    // ─── SECOND: use options_pool logic ───
    const pool = meta.options_pool || '';
    let candidates = [];

    if (pool.startsWith('groups_female')) {
      candidates = db
        .prepare('SELECT DISTINCT name FROM groups WHERE gender = ? AND name != ? ORDER BY RANDOM() LIMIT 10')
        .all('female', correct)
        .map((r) => r.name);
    } else if (pool.startsWith('groups_male')) {
      candidates = db
        .prepare('SELECT DISTINCT name FROM groups WHERE gender = ? AND name != ? ORDER BY RANDOM() LIMIT 10')
        .all('male', correct)
        .map((r) => r.name);
    } else if (pool.startsWith('members_')) {
      const groupName = pool.replace('members_', '').toUpperCase();
      const group = db.prepare('SELECT id FROM groups WHERE UPPER(name) LIKE ?').get(`%${groupName}%`);
      if (group) {
        candidates = db
          .prepare('SELECT stage_name FROM artists WHERE group_id = ? AND stage_name != ? ORDER BY RANDOM() LIMIT 10')
          .all(group.id, correct)
          .map((r) => r.stage_name);
      }
      if (candidates.length < 3) {
        const gender = db.prepare('SELECT gender FROM artists WHERE stage_name = ?').get(correct);
        const g = gender ? gender.gender : 'female';
        const placeholders = candidates.map(() => '?').join(',');
        const query = placeholders
          ? `SELECT DISTINCT stage_name FROM artists WHERE gender = ? AND stage_name != ? AND stage_name NOT IN (${placeholders}) ORDER BY RANDOM() LIMIT 10`
          : `SELECT DISTINCT stage_name FROM artists WHERE gender = ? AND stage_name != ? ORDER BY RANDOM() LIMIT 10`;
        const params = placeholders ? [g, correct, ...candidates] : [g, correct];
        const more = db.prepare(query).all(...params).map((r) => r.stage_name);
        candidates = [...candidates, ...more];
      }
    } else if (pool === 'members_bts_real' || pool === 'korean_names_female') {
      const realNames = [
        'Kim Nam-joon', 'Kim Seok-jin', 'Min Yoon-gi', 'Jung Ho-seok',
        'Park Ji-min', 'Kim Tae-hyung', 'Jeon Jung-kook',
        'Park Chae-young', 'Kim Ji-soo', 'Lalisa Manobal', 'Kim Jennie',
        'Im Na-yeon', 'Yoo Jeong-yeon', 'Hirai Momo', 'Minatozaki Sana',
        'Myoui Mina', 'Kim Da-hyun', 'Son Chae-young', 'Chou Tzu-yu',
        'Yoo Ji-min', 'Kim Min-jeong', 'Uchinaga Aeri', 'Ning Yi-zhuo',
      ];
      candidates = realNames.filter((n) => n !== correct).sort(() => Math.random() - 0.5);
    } else if (pool === 'numbers_small') {
      const nums = ['3', '4', '5', '6', '7', '8', '9'];
      candidates = nums.filter((n) => n !== correct).sort(() => Math.random() - 0.5);
    } else if (pool === 'numbers_medium') {
      const nums = ['7', '9', '11', '12', '13', '14', '15', '17'];
      candidates = nums.filter((n) => n !== correct).sort(() => Math.random() - 0.5);
    } else if (pool.startsWith('years_')) {
      const baseYear = parseInt(pool.replace('years_', ''));
      const years = [];
      for (let y = baseYear - 3; y <= baseYear + 3; y++) {
        if (y.toString() !== correct) years.push(y.toString());
      }
      candidates = years.sort(() => Math.random() - 0.5);
    } else if (pool === 'companies') {
      const companies = [
        'SM Entertainment', 'YG Entertainment', 'JYP Entertainment',
        'HYBE', 'Big Hit Entertainment', 'BIGHIT MUSIC',
        'Starship Entertainment', 'CUBE Entertainment',
        'Pledis Entertainment', 'RBW', 'SOURCE MUSIC', 'ADOR',
        'KQ Entertainment', 'BELIFT LAB',
      ];
      candidates = companies.filter((c) => c !== correct).sort(() => Math.random() - 0.5);
    } else if (pool.startsWith('songs_')) {
      const groupKey = pool.replace('songs_', '');
      const groupMap = {
        'aespa': 'aespa', 'bp': 'BLACKPINK', 'blackpink': 'BLACKPINK',
        'skz': 'Stray Kids', 'gidle': '(G)I-DLE', 'twice': 'TWICE',
        'bts': 'BTS', 'newjeans': 'NewJeans',
      };
      const groupName = groupMap[groupKey] || groupKey;
      const group = db.prepare('SELECT id FROM groups WHERE name = ?').get(groupName);
      if (group) {
        candidates = db
          .prepare('SELECT title FROM songs WHERE group_id = ? AND title != ? ORDER BY RANDOM() LIMIT 10')
          .all(group.id, correct)
          .map((r) => r.title);
      }
      if (candidates.length < 3) {
        const placeholders = candidates.map(() => '?').join(',');
        const query = placeholders
          ? `SELECT title FROM songs WHERE title != ? AND title NOT IN (${placeholders}) ORDER BY RANDOM() LIMIT 10`
          : `SELECT title FROM songs WHERE title != ? ORDER BY RANDOM() LIMIT 10`;
        const params = placeholders ? [correct, ...candidates] : [correct];
        const more = db.prepare(query).all(...params).map((r) => r.title);
        candidates = [...candidates, ...more];
      }
    } else if (pool === 'positions') {
      const positions = [
        'Leader, Main Vocalist', 'Main Rapper, Lead Dancer',
        'Main Dancer, Lead Vocalist', 'Lead Rapper, Sub Vocalist',
        'Main Vocalist, Visual', 'Leader, Main Rapper',
        'Main Dancer, Sub Vocalist', 'Lead Vocalist, Visual',
        'Leader, Main Dancer, Lead Vocalist',
      ];
      candidates = positions.filter((p) => p !== correct).sort(() => Math.random() - 0.5);
    } else if (pool === 'member_pairs_skz') {
      const pairs = [
        'Han and Seungmin', 'Hyunjin and Lee Know', 'Changbin and I.N',
        'Bang Chan and Lee Know', 'Han and Felix',
        'Hyunjin and Changbin', 'Seungmin and I.N',
      ];
      candidates = pairs.filter((p) => p !== correct).sort(() => Math.random() - 0.5);
    } else if (pool === 'albums') {
      // Album questions — use wrong_answers from metadata if available
      if (meta.wrong_answers && meta.wrong_answers.length > 0) {
        candidates = meta.wrong_answers
          .filter((a) => a && a !== '—' && a !== '-' && a.trim().length > 0 && a !== correct)
          .sort(() => Math.random() - 0.5);
      }
    } else {
      // Fallback: use groups
      candidates = db
        .prepare('SELECT DISTINCT name FROM groups WHERE name != ? ORDER BY RANDOM() LIMIT 10')
        .all(correct)
        .map((r) => r.name);
    }

    // ─── FINAL: type-match validation ───
    // If correct answer looks like a year/number, ensure wrong answers are also numbers
    const correctIsYear = /^\d{4}$/.test(correct);
    const correctIsNumber = /^\d+$/.test(correct);

    if (correctIsYear) {
      // Filter to only year-like candidates
      const yearCandidates = candidates.filter((c) => /^\d{4}$/.test(c));
      if (yearCandidates.length >= 3) {
        return yearCandidates.slice(0, 3);
      }
      // Generate plausible years around the correct year
      const baseYear = parseInt(correct);
      const fallbackYears = [];
      for (let y = baseYear - 4; y <= baseYear + 4; y++) {
        if (y.toString() !== correct) fallbackYears.push(y.toString());
      }
      return fallbackYears.sort(() => Math.random() - 0.5).slice(0, 3);
    }

    if (correctIsNumber && !correctIsYear) {
      const numCandidates = candidates.filter((c) => /^\d+$/.test(c));
      if (numCandidates.length >= 3) {
        return numCandidates.slice(0, 3);
      }
      // Generate nearby numbers
      const base = parseInt(correct);
      const fallbackNums = [];
      for (let n = Math.max(1, base - 4); n <= base + 4; n++) {
        if (n.toString() !== correct) fallbackNums.push(n.toString());
      }
      return fallbackNums.sort(() => Math.random() - 0.5).slice(0, 3);
    }

    // Filter out any dash/empty answers from candidates
    const cleanCandidates = candidates.filter(
      (c) => c && c !== '—' && c !== '-' && c.trim().length > 0 && c !== correct
    );

    return cleanCandidates.slice(0, 3);
  } finally {
    db.close();
  }
}

// ─── Room Management ───

const rooms = new Map();
const playerRooms = new Map(); // socketId → Set<roomCode>

function generateRoomCode() {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  let code = '';
  for (let i = 0; i < 4; i++) {
    code += chars[Math.floor(Math.random() * chars.length)];
  }
  return code;
}

function createGameEngine() {
  return {
    setPlayerUserId(roomCode, socketId, userId) {
      const room = rooms.get(roomCode);
      if (!room) return;
      const player = room.players.find((p) => p.socketId === socketId);
      if (player) {
        player.userId = userId;
      }
    },

    setRoomMode(roomCode, mode) {
      const room = rooms.get(roomCode);
      if (!room) return;
      room.mode = mode === 'quick' ? 'quick' : 'all';
    },

    getRoomMode(roomCode) {
      const room = rooms.get(roomCode);
      return room ? room.mode || 'quick' : 'quick';
    },

    createRoom(socketId, playerName) {
      let roomCode;
      do {
        roomCode = generateRoomCode();
      } while (rooms.has(roomCode));

      const player = {
        socketId,
        name: playerName,
        userId: null,
        score: 0,
        streak: 0,
        maxStreak: 0,
        correctCount: 0,
        isHost: true,
        connected: true,
        doubleDown: false,
        currentAnswer: null,
        answerTime: null,
      };

      rooms.set(roomCode, {
        code: roomCode,
        status: 'lobby',
        mode: 'quick', // default, overridden by setRoomMode
        players: [player],
        hostSocketId: socketId,
        questions: [],
        currentQuestion: 0,
        totalQuestions: 0,
        currentQuestionData: null,
        currentDifficulty: 1, // Start easy!
        questionPool: null,
        timerStart: null,
        _timer: null,
      });

      if (!playerRooms.has(socketId)) playerRooms.set(socketId, new Set());
      playerRooms.get(socketId).add(roomCode);

      return { roomCode, player, players: [player] };
    },

    joinRoom(socketId, roomCode, playerName) {
      const room = rooms.get(roomCode);
      if (!room) throw new Error('Room not found');
      if (room.status !== 'lobby') throw new Error('Game already in progress');
      if (room.players.length >= 8) throw new Error('Room is full');
      if (room.players.some((p) => p.name === playerName))
        throw new Error('Name already taken in this room');

      const player = {
        socketId,
        name: playerName,
        userId: null,
        score: 0,
        streak: 0,
        maxStreak: 0,
        correctCount: 0,
        isHost: false,
        connected: true,
        doubleDown: false,
        currentAnswer: null,
        answerTime: null,
      };

      room.players.push(player);
      if (!playerRooms.has(socketId)) playerRooms.set(socketId, new Set());
      playerRooms.get(socketId).add(roomCode);

      return { player, players: room.players, isHost: false };
    },

    rejoinRoom(socketId, roomCode, playerName) {
      const room = rooms.get(roomCode);
      if (!room) throw new Error('Room not found');

      const existing = room.players.find((p) => p.name === playerName);
      if (existing) {
        existing.socketId = socketId;
        existing.connected = true;
        if (!playerRooms.has(socketId)) playerRooms.set(socketId, new Set());
        playerRooms.get(socketId).add(roomCode);
        return { player: existing, players: room.players, isHost: existing.isHost, status: room.status };
      }

      if (room.status === 'lobby') {
        return this.joinRoom(socketId, roomCode, playerName);
      }
      throw new Error('Cannot rejoin — game in progress and you were not in it');
    },

    startGame(socketId, roomCode, mode = 'all') {
      const room = rooms.get(roomCode);
      if (!room) throw new Error('Room not found');
      if (room.hostSocketId !== socketId) throw new Error('Only the host can start the game');
      if (room.players.length < 1) throw new Error('Need at least 1 player');

      // Load question pool based on game mode
      room.gameMode = mode;
      room.questionPool = loadQuestionPool(mode);
      room.currentDifficulty = 1; // Always start at easiest
      room.totalQuestions = mode === 'quick' ? 10 : 15;
      room.currentQuestion = 0;
      room.questions = []; // Will be built dynamically
      room.status = 'playing';

      console.log(`[Game] Starting with adaptive difficulty. Pool sizes: ${
        Object.entries(room.questionPool).map(([d, qs]) => `D${d}:${qs.length}`).join(', ')
      }`);

      return { totalQuestions: room.totalQuestions };
    },

    /**
     * Pick the next question based on current adaptive difficulty.
     * Falls back to adjacent difficulties if current bucket is empty.
     */
    getNextQuestion(roomCode) {
      const room = rooms.get(roomCode);
      if (!room) return null;
      if (room.currentQuestion >= room.totalQuestions) return null;

      room.currentQuestion++;

      // Pick from current difficulty, fall back to neighbors
      const pool = room.questionPool;
      const diff = room.currentDifficulty;
      let q = null;

      // Try current difficulty first, then expand outward
      const tryOrder = [diff];
      for (let offset = 1; offset <= 4; offset++) {
        if (diff + offset <= 5) tryOrder.push(diff + offset);
        if (diff - offset >= 1) tryOrder.push(diff - offset);
      }

      for (const d of tryOrder) {
        if (pool[d] && pool[d].length > 0) {
          q = pool[d].shift(); // Take one question from this difficulty bucket
          break;
        }
      }

      if (!q) return null; // Truly exhausted (shouldn't happen with 8k+ questions)

      // Generate wrong answers and build the question
      const wrong = generateWrongAnswers(q);
      const answers = [q.correct_answer, ...wrong.slice(0, 3)];
      while (answers.length < 4) {
        // Pad with plausible filler if needed (shouldn't happen after fixes)
        answers.push('Unknown');
      }

      const shuffled = answers
        .map((a, i) => ({ answer: a, isCorrect: i === 0 }))
        .sort(() => Math.random() - 0.5);

      // Build media URL for face/audio questions
      let mediaUrl = null;
      let questionType = q.type || 'text';
      const meta = q.metadata_json ? JSON.parse(q.metadata_json) : {};

      if (q.type === 'face') {
        // Use the photo_path from metadata (static file served from /images/members/)
        if (meta.photo_path) {
          mediaUrl = meta.photo_path;
        } else if (q.face_image_id) {
          mediaUrl = `/api/media/face/${q.face_image_id}`;
        }
      } else if (q.type === 'audio') {
        if (q.audio_clip_id) {
          mediaUrl = `/api/media/audio/${q.audio_clip_id}`;
        }
      }

      room.currentQuestionData = {
        id: q.id,
        questionText: q.question_text,
        difficulty: q.difficulty,
        category: q.category,
        type: questionType,
        mediaUrl: mediaUrl,
        answers: shuffled.map((s) => s.answer),
        correctIndex: shuffled.findIndex((s) => s.isCorrect),
        correctAnswer: q.correct_answer,
      };

      return room.currentQuestionData;
    },

    resetRound(roomCode) {
      const room = rooms.get(roomCode);
      if (!room) return;
      room.players.forEach((p) => {
        p.doubleDown = false;
        p.currentAnswer = null;
        p.answerTime = null;
      });
    },

    startTimer(roomCode) {
      const room = rooms.get(roomCode);
      if (!room) return;
      room.timerStart = Date.now();
    },

    setDoubleDown(socketId, roomCode) {
      const room = rooms.get(roomCode);
      if (!room) return;
      const player = room.players.find((p) => p.socketId === socketId);
      if (player) {
        player.doubleDown = true;
      }
    },

    levelUp(roomCode) {
      const room = rooms.get(roomCode);
      if (!room) return null;
      if (room.currentDifficulty < 5) {
        room.currentDifficulty++;
        console.log(`[Difficulty] ↑ Player chose to level up to ${room.currentDifficulty}`);
      }
      return room.currentDifficulty;
    },

    getDifficulty(roomCode) {
      const room = rooms.get(roomCode);
      return room ? room.currentDifficulty : 1;
    },

    cancelDoubleDown(socketId, roomCode) {
      const room = rooms.get(roomCode);
      if (!room) return;
      const player = room.players.find((p) => p.socketId === socketId);
      if (player) {
        player.doubleDown = false;
      }
    },

    submitAnswer(socketId, roomCode, answerIndex) {
      const room = rooms.get(roomCode);
      if (!room || room.status !== 'playing') throw new Error('Game not active');

      const player = room.players.find((p) => p.socketId === socketId);
      if (!player) throw new Error('Player not in room');
      if (player.currentAnswer !== null) throw new Error('Already answered');

      player.currentAnswer = answerIndex;
      player.answerTime = Date.now() - room.timerStart;

      const connectedPlayers = room.players.filter((p) => p.connected);
      const allAnswered = connectedPlayers.every((p) => p.currentAnswer !== null);

      return { received: true, allAnswered };
    },

    calculateScores(roomCode) {
      const room = rooms.get(roomCode);
      if (!room) return null;

      const q = room.currentQuestionData;
      const basePoints = [0, 100, 200, 300, 400, 500][q.difficulty] || 100;

      // Track how many players got it right for difficulty adjustment
      let correctCount = 0;
      let totalAnswered = 0;

      const playerResults = room.players.map((p) => {
        const isCorrect = p.currentAnswer === q.correctIndex;
        let pointsEarned = 0;

        if (p.currentAnswer !== null) totalAnswered++;

        if (isCorrect) {
          correctCount++;
          pointsEarned = basePoints;

          // Speed bonus: up to 50% for fast answers
          if (p.answerTime !== null) {
            const speedFraction = Math.max(0, 1 - p.answerTime / 10000);
            const speedBonus = Math.round(basePoints * 0.5 * speedFraction);
            pointsEarned += speedBonus;
          }

          // Streak bonus
          p.streak++;
          if (p.streak > p.maxStreak) p.maxStreak = p.streak;
          if (p.streak >= 3) {
            pointsEarned = Math.round(pointsEarned * 1.5);
          }

          // Double down
          if (p.doubleDown) {
            pointsEarned *= 2;
          }

          p.correctCount++;
        } else {
          p.streak = 0;
          if (p.doubleDown) {
            pointsEarned = -basePoints;
          }
        }

        p.score += pointsEarned;
        if (p.score < 0) p.score = 0;

        return {
          name: p.name,
          isCorrect,
          pointsEarned,
          totalScore: p.score,
          streak: p.streak,
          doubleDown: p.doubleDown,
          answerTime: p.answerTime,
          answered: p.currentAnswer !== null,
        };
      });

      // ─── Difficulty stays at current level unless player opts in ───
      // Difficulty is now player-controlled via 'level-up' socket event.
      // We only auto-drop if the player gets it wrong to keep it fun.
      if (totalAnswered > 0) {
        const correctRatio = correctCount / totalAnswered;
        if (correctRatio < 0.5 && room.currentDifficulty > 1) {
          room.currentDifficulty--;
          console.log(`[Difficulty] ↓ Dropped to ${room.currentDifficulty} (${Math.round(correctRatio*100)}% correct)`);
        }
      }

      playerResults.sort((a, b) => b.totalScore - a.totalScore);

      return {
        correctIndex: q.correctIndex,
        correctAnswer: q.correctAnswer,
        playerResults,
        questionNumber: room.currentQuestion,
        totalQuestions: room.totalQuestions,
        difficulty: q.difficulty,
        currentDifficulty: room.currentDifficulty,
      };
    },

    endGame(roomCode) {
      const room = rooms.get(roomCode);
      if (!room) return null;

      room.status = 'finished';
      if (room._timer) clearTimeout(room._timer);
      if (room._ddTimer) clearTimeout(room._ddTimer);
      if (room._resultTimer) clearTimeout(room._resultTimer);

      const finalResults = room.players
        .map((p) => ({
          name: p.name,
          score: p.score,
          correctCount: p.correctCount,
          maxStreak: p.maxStreak,
          isHost: p.isHost,
          userId: p.userId || null,
        }))
        .sort((a, b) => b.score - a.score);

      return {
        results: finalResults,
        totalQuestions: room.totalQuestions,
      };
    },

    getRoom(roomCode) {
      return rooms.get(roomCode);
    },

    handleDisconnect(socketId) {
      const roomCodes = playerRooms.get(socketId);
      if (!roomCodes) return [];

      const affected = [];
      roomCodes.forEach((roomCode) => {
        const room = rooms.get(roomCode);
        if (!room) return;
        const player = room.players.find((p) => p.socketId === socketId);
        if (player) {
          player.connected = false;
          affected.push(roomCode);
        }

        const connectedPlayers = room.players.filter((p) => p.connected);
        if (connectedPlayers.length === 0) {
          if (room._timer) clearTimeout(room._timer);
          rooms.delete(roomCode);
          console.log(`[Room] Deleted empty room ${roomCode}`);
        }
      });

      playerRooms.delete(socketId);
      return affected;
    },
  };
}

module.exports = { createGameEngine };
