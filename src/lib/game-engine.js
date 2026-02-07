const path = require('path');
const Database = require('better-sqlite3');

const DB_PATH = path.join(__dirname, '../../data/kpop_quiz.db');

// ─── Database Queries ───

function getDb() {
  return new Database(DB_PATH, { readonly: true });
}

function loadQuestions(count = 15) {
  const db = getDb();
  try {
    const questions = db
      .prepare(
        `SELECT id, type, difficulty, category, question_text, correct_answer, metadata_json
         FROM questions WHERE type = 'text'
         ORDER BY RANDOM() LIMIT ?`
      )
      .all(count);
    return questions;
  } finally {
    db.close();
  }
}

function generateWrongAnswers(question) {
  const db = getDb();
  try {
    const meta = question.metadata_json ? JSON.parse(question.metadata_json) : {};
    const pool = meta.options_pool || '';
    const correct = question.correct_answer;
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
      // Get members from same group or similar groups
      const groupName = pool.replace('members_', '').toUpperCase();
      // First try to get from the same group
      const group = db.prepare('SELECT id FROM groups WHERE UPPER(name) LIKE ?').get(`%${groupName}%`);
      if (group) {
        candidates = db
          .prepare('SELECT stage_name FROM artists WHERE group_id = ? AND stage_name != ? ORDER BY RANDOM() LIMIT 10')
          .all(group.id, correct)
          .map((r) => r.stage_name);
      }
      // If not enough, add from same gender
      if (candidates.length < 3) {
        const gender = db.prepare('SELECT gender FROM artists WHERE stage_name = ?').get(correct);
        const g = gender ? gender.gender : 'female';
        const more = db
          .prepare('SELECT DISTINCT stage_name FROM artists WHERE gender = ? AND stage_name != ? AND stage_name NOT IN (' + candidates.map(() => '?').join(',') + ') ORDER BY RANDOM() LIMIT 10')
          .all(g, correct, ...candidates)
          .map((r) => r.stage_name);
        candidates = [...candidates, ...more];
      }
    } else if (pool === 'members_bts_real' || pool === 'korean_names_female') {
      // Real names — use a static pool
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
      // Songs from a specific group
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
      // Pad with songs from other groups if needed
      if (candidates.length < 3) {
        const more = db
          .prepare('SELECT title FROM songs WHERE title != ? AND title NOT IN (' + candidates.map(() => '?').join(',') + ') ORDER BY RANDOM() LIMIT 10')
          .all(correct, ...candidates)
          .map((r) => r.title);
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
    } else {
      // Fallback: use groups
      candidates = db
        .prepare('SELECT DISTINCT name FROM groups WHERE name != ? ORDER BY RANDOM() LIMIT 10')
        .all(correct)
        .map((r) => r.name);
    }

    return candidates.slice(0, 3);
  } finally {
    db.close();
  }
}

// ─── Room Management ───

const rooms = new Map();
const playerRooms = new Map(); // socketId → Set<roomCode>

function generateRoomCode() {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // no ambiguous chars
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
        players: [player],
        hostSocketId: socketId,
        questions: [],
        currentQuestion: 0,
        totalQuestions: 0,
        currentQuestionData: null,
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

      // Treat as new join if in lobby
      if (room.status === 'lobby') {
        return this.joinRoom(socketId, roomCode, playerName);
      }
      throw new Error('Cannot rejoin — game in progress and you were not in it');
    },

    startGame(socketId, roomCode) {
      const room = rooms.get(roomCode);
      if (!room) throw new Error('Room not found');
      if (room.hostSocketId !== socketId) throw new Error('Only the host can start the game');
      if (room.players.length < 1) throw new Error('Need at least 1 player');

      const questionCount = Math.min(15, 25); // use all available or cap at 15
      const rawQuestions = loadQuestions(questionCount);

      room.questions = rawQuestions.map((q) => {
        const wrong = generateWrongAnswers(q);
        const answers = [q.correct_answer, ...wrong.slice(0, 3)];
        // Ensure we have exactly 4 answers
        while (answers.length < 4) answers.push('—');
        // Shuffle
        const correctIndex = 0;
        const shuffled = answers
          .map((a, i) => ({ answer: a, isCorrect: i === correctIndex }))
          .sort(() => Math.random() - 0.5);

        return {
          id: q.id,
          questionText: q.question_text,
          difficulty: q.difficulty,
          category: q.category,
          answers: shuffled.map((s) => s.answer),
          correctIndex: shuffled.findIndex((s) => s.isCorrect),
          correctAnswer: q.correct_answer,
        };
      });

      room.totalQuestions = room.questions.length;
      room.currentQuestion = 0;
      room.status = 'playing';

      return { totalQuestions: room.totalQuestions };
    },

    getNextQuestion(roomCode) {
      const room = rooms.get(roomCode);
      if (!room) return null;

      if (room.currentQuestion >= room.questions.length) return null;

      room.currentQuestion++;
      room.currentQuestionData = room.questions[room.currentQuestion - 1];
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

    submitAnswer(socketId, roomCode, answerIndex) {
      const room = rooms.get(roomCode);
      if (!room || room.status !== 'playing') throw new Error('Game not active');

      const player = room.players.find((p) => p.socketId === socketId);
      if (!player) throw new Error('Player not in room');
      if (player.currentAnswer !== null) throw new Error('Already answered');

      player.currentAnswer = answerIndex;
      player.answerTime = Date.now() - room.timerStart;

      // Check if all connected players have answered
      const connectedPlayers = room.players.filter((p) => p.connected);
      const allAnswered = connectedPlayers.every((p) => p.currentAnswer !== null);

      return { received: true, allAnswered };
    },

    calculateScores(roomCode) {
      const room = rooms.get(roomCode);
      if (!room) return null;

      const q = room.currentQuestionData;
      const basePoints = [0, 100, 200, 300, 400, 500][q.difficulty] || 100;

      const playerResults = room.players.map((p) => {
        const isCorrect = p.currentAnswer === q.correctIndex;
        let pointsEarned = 0;

        if (isCorrect) {
          pointsEarned = basePoints;

          // Speed bonus: up to 50% for fast answers (0-10 seconds)
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
          // Wrong or no answer
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

      // Sort by score descending
      playerResults.sort((a, b) => b.totalScore - a.totalScore);

      return {
        correctIndex: q.correctIndex,
        correctAnswer: q.correctAnswer,
        playerResults,
        questionNumber: room.currentQuestion,
        totalQuestions: room.totalQuestions,
      };
    },

    endGame(roomCode) {
      const room = rooms.get(roomCode);
      if (!room) return null;

      room.status = 'finished';
      if (room._timer) clearTimeout(room._timer);

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

        // Clean up empty rooms
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
