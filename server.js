const { createServer } = require('http');
const { parse } = require('url');
const next = require('next');
const { Server } = require('socket.io');
const { createGameEngine } = require('./src/lib/game-engine');
const { runMigrations } = require('./src/lib/db');
const Database = require('better-sqlite3');
const dbPath = require('path').join(__dirname, 'data/kpop_quiz.db');
const {
  registerUser,
  loginUser,
  verifyToken,
  getUserById,
  getUserStats,
  getGameHistory,
  recordGameResult,
  getLeaderboard,
} = require('./src/lib/auth');

const dev = process.env.NODE_ENV !== 'production';
const hostname = 'localhost';
const port = parseInt(process.env.PORT || '3000', 10);

// Run database migrations on startup
runMigrations();

const app = next({ dev, hostname, port });
const handle = app.getRequestHandler();

// ─── JSON body parser helper ───
function parseJsonBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', (chunk) => (body += chunk));
    req.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch {
        reject(new Error('Invalid JSON'));
      }
    });
    req.on('error', reject);
  });
}

// ─── Cookie parser helper ───
function parseCookies(req) {
  const cookies = {};
  const header = req.headers.cookie;
  if (!header) return cookies;
  header.split(';').forEach((c) => {
    const [key, ...v] = c.split('=');
    cookies[key.trim()] = decodeURIComponent(v.join('='));
  });
  return cookies;
}

// ─── Get user from request (JWT in cookie) ───
function getUserFromRequest(req) {
  const cookies = parseCookies(req);
  const token = cookies['kpop-auth'];
  if (!token) return null;
  return verifyToken(token);
}

// ─── Set auth cookie ───
function setAuthCookie(res, token) {
  const maxAge = 7 * 24 * 60 * 60; // 7 days
  res.setHeader('Set-Cookie', `kpop-auth=${token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAge}`);
}

// ─── Clear auth cookie ───
function clearAuthCookie(res) {
  res.setHeader('Set-Cookie', 'kpop-auth=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0');
}

// ─── JSON response helper ───
function jsonResponse(res, statusCode, data) {
  res.writeHead(statusCode, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data));
}

app.prepare().then(() => {
  const httpServer = createServer(async (req, res) => {
    const parsedUrl = parse(req.url, true);
    const { pathname } = parsedUrl;

    // ─── API Routes ───
    try {
      // POST /api/auth/register
      if (pathname === '/api/auth/register' && req.method === 'POST') {
        const body = await parseJsonBody(req);
        const { username, password, displayName } = body;
        try {
          const user = registerUser(username, password, displayName);
          const { token, user: userData } = loginUser(username, password);
          setAuthCookie(res, token);
          return jsonResponse(res, 200, { success: true, user: userData });
        } catch (err) {
          return jsonResponse(res, 400, { success: false, error: err.message });
        }
      }

      // POST /api/auth/login
      if (pathname === '/api/auth/login' && req.method === 'POST') {
        const body = await parseJsonBody(req);
        const { username, password } = body;
        try {
          const { token, user } = loginUser(username, password);
          setAuthCookie(res, token);
          return jsonResponse(res, 200, { success: true, user });
        } catch (err) {
          return jsonResponse(res, 401, { success: false, error: err.message });
        }
      }

      // POST /api/auth/logout
      if (pathname === '/api/auth/logout' && req.method === 'POST') {
        clearAuthCookie(res);
        return jsonResponse(res, 200, { success: true });
      }

      // GET /api/auth/me
      if (pathname === '/api/auth/me' && req.method === 'GET') {
        const payload = getUserFromRequest(req);
        if (!payload) {
          return jsonResponse(res, 401, { success: false, error: 'Not authenticated' });
        }
        const user = getUserById(payload.userId);
        if (!user) {
          clearAuthCookie(res);
          return jsonResponse(res, 401, { success: false, error: 'User not found' });
        }
        return jsonResponse(res, 200, {
          success: true,
          user: {
            id: user.id,
            username: user.username,
            displayName: user.display_name,
            createdAt: user.created_at,
          },
        });
      }

      // GET /api/stats/:userId
      if (pathname.startsWith('/api/stats/') && req.method === 'GET') {
        const userId = parseInt(pathname.split('/')[3]);
        if (isNaN(userId)) {
          return jsonResponse(res, 400, { success: false, error: 'Invalid user ID' });
        }
        const stats = getUserStats(userId);
        const history = getGameHistory(userId);
        const user = getUserById(userId);
        if (!user) {
          return jsonResponse(res, 404, { success: false, error: 'User not found' });
        }
        return jsonResponse(res, 200, {
          success: true,
          user: { id: user.id, username: user.username, displayName: user.display_name, createdAt: user.created_at },
          stats: stats || { games_played: 0, total_points: 0, wins: 0, best_streak: 0, best_score: 0, correct_answers: 0, total_answers: 0 },
          history,
        });
      }

      // GET /api/media/face/:id — serve face images from DB
      if (pathname.startsWith('/api/media/face/') && req.method === 'GET') {
        const id = parseInt(pathname.split('/')[4]);
        if (isNaN(id)) {
          res.writeHead(400);
          return res.end('Invalid ID');
        }
        const db = new Database(dbPath, { readonly: true });
        try {
          const row = db.prepare('SELECT image, format FROM face_images WHERE id = ?').get(id);
          if (!row) {
            res.writeHead(404);
            return res.end('Not found');
          }
          const mime = row.format === 'png' ? 'image/png' : row.format === 'webp' ? 'image/webp' : 'image/jpeg';
          res.writeHead(200, {
            'Content-Type': mime,
            'Cache-Control': 'public, max-age=86400',
          });
          return res.end(row.image);
        } finally {
          db.close();
        }
      }

      // GET /api/media/audio/:id — serve audio clips from DB
      if (pathname.startsWith('/api/media/audio/') && req.method === 'GET') {
        const id = parseInt(pathname.split('/')[4]);
        if (isNaN(id)) {
          res.writeHead(400);
          return res.end('Invalid ID');
        }
        const db = new Database(dbPath, { readonly: true });
        try {
          const row = db.prepare('SELECT clip, format FROM audio_clips WHERE id = ?').get(id);
          if (!row) {
            res.writeHead(404);
            return res.end('Not found');
          }
          const mime = row.format === 'ogg' ? 'audio/ogg' : 'audio/mpeg';
          res.writeHead(200, {
            'Content-Type': mime,
            'Cache-Control': 'public, max-age=86400',
          });
          return res.end(row.clip);
        } finally {
          db.close();
        }
      }

      // GET /api/leaderboard
      if (pathname === '/api/leaderboard' && req.method === 'GET') {
        const sortBy = parsedUrl.query.sort || 'total_points';
        const data = getLeaderboard(sortBy);
        return jsonResponse(res, 200, { success: true, leaderboard: data });
      }
    } catch (err) {
      console.error('[API Error]', err);
      return jsonResponse(res, 500, { success: false, error: 'Internal server error' });
    }

    // ─── Next.js handler ───
    handle(req, res, parsedUrl);
  });

  const io = new Server(httpServer, {
    cors: { origin: '*', methods: ['GET', 'POST'] },
    pingTimeout: 60000,
    pingInterval: 25000,
  });

  const engine = createGameEngine();

  // Track userId per socket for stats recording
  const socketUsers = new Map(); // socketId → { userId, displayName }

  io.on('connection', (socket) => {
    console.log(`[Socket] Connected: ${socket.id}`);

    // ─── Auth: set user identity for this socket ───
    socket.on('set-user', ({ userId, displayName }, callback) => {
      socketUsers.set(socket.id, { userId, displayName });
      if (callback) callback({ success: true });
    });

    // ─── Create Room ───
    socket.on('create-room', ({ playerName, mode }, callback) => {
      try {
        const result = engine.createRoom(socket.id, playerName);
        socket.join(result.roomCode);

        // Store the game mode on the room
        const gameMode = mode === 'quick' ? 'quick' : 'all';
        engine.setRoomMode(result.roomCode, gameMode);

        // Associate userId with this player in the room
        const userInfo = socketUsers.get(socket.id);
        if (userInfo) {
          engine.setPlayerUserId(result.roomCode, socket.id, userInfo.userId);
        }

        console.log(`[Room] Created ${result.roomCode} by ${playerName} (mode: ${gameMode})`);
        callback({ success: true, ...result, mode: gameMode });
      } catch (err) {
        callback({ success: false, error: err.message });
      }
    });

    // ─── Join Room ───
    socket.on('join-room', ({ roomCode, playerName }, callback) => {
      try {
        const result = engine.joinRoom(socket.id, roomCode.toUpperCase(), playerName);
        socket.join(roomCode.toUpperCase());

        // Associate userId
        const userInfo = socketUsers.get(socket.id);
        if (userInfo) {
          engine.setPlayerUserId(roomCode.toUpperCase(), socket.id, userInfo.userId);
        }

        io.to(roomCode.toUpperCase()).emit('player-joined', {
          players: result.players,
          playerName,
        });
        const joinMode = engine.getRoomMode(roomCode.toUpperCase());
        console.log(`[Room] ${playerName} joined ${roomCode.toUpperCase()}`);
        callback({ success: true, ...result, mode: joinMode });
      } catch (err) {
        callback({ success: false, error: err.message });
      }
    });

    // ─── Start Game ───
    socket.on('start-game', ({ roomCode, mode }, callback) => {
      try {
        // Use room's pre-set mode (from create), fallback to client mode for backwards compat
        const roomMode = engine.getRoomMode(roomCode);
        const gameMode = mode ? (mode === 'quick' ? 'quick' : 'all') : roomMode;
        const result = engine.startGame(socket.id, roomCode, gameMode);
        io.to(roomCode).emit('game-started', {
          totalQuestions: result.totalQuestions,
        });
        console.log(`[Game] Started in ${roomCode} with ${result.totalQuestions} questions`);

        // Send first question after a brief delay
        setTimeout(() => {
          sendNextQuestion(roomCode);
        }, 1500);

        callback({ success: true });
      } catch (err) {
        callback({ success: false, error: err.message });
      }
    });

    // ─── Double Down ───
    socket.on('double-down', ({ roomCode }) => {
      try {
        engine.setDoubleDown(socket.id, roomCode);
      } catch (err) {
        console.error(`[DoubleDown] Error: ${err.message}`);
      }
    });

    // ─── Cancel Double Down ───
    socket.on('cancel-double-down', ({ roomCode }) => {
      try {
        engine.cancelDoubleDown(socket.id, roomCode);
      } catch (err) {
        console.error(`[CancelDoubleDown] Error: ${err.message}`);
      }
    });

    // ─── Level Up (player opts into harder questions) ───
    socket.on('level-up', ({ roomCode }, callback) => {
      try {
        const newDifficulty = engine.levelUp(roomCode);
        if (newDifficulty !== null) {
          io.to(roomCode).emit('difficulty-changed', { difficulty: newDifficulty });
        }
        if (callback) callback({ success: true, difficulty: newDifficulty });
      } catch (err) {
        if (callback) callback({ success: false, error: err.message });
      }
    });

    // ─── Submit Answer ───
    socket.on('submit-answer', ({ roomCode, answerIndex }, callback) => {
      try {
        const result = engine.submitAnswer(socket.id, roomCode, answerIndex);
        callback({ success: true, received: true });

        // If all players have answered, reveal immediately
        if (result.allAnswered) {
          const room = engine.getRoom(roomCode);
          if (room && room._timer) {
            clearTimeout(room._timer);
            room._timer = null;
          }
          revealAnswer(roomCode);
        }
      } catch (err) {
        callback({ success: false, error: err.message });
      }
    });

    // ─── Disconnect ───
    socket.on('disconnect', () => {
      console.log(`[Socket] Disconnected: ${socket.id}`);
      socketUsers.delete(socket.id);
      const rooms = engine.handleDisconnect(socket.id);
      rooms.forEach((roomCode) => {
        const room = engine.getRoom(roomCode);
        if (room) {
          io.to(roomCode).emit('player-left', {
            players: room.players.filter((p) => p.connected),
          });
        }
      });
    });

    // ─── Reconnect support ───
    socket.on('rejoin-room', ({ roomCode, playerName }, callback) => {
      try {
        const result = engine.rejoinRoom(socket.id, roomCode, playerName);
        socket.join(roomCode);

        // Re-associate userId
        const userInfo = socketUsers.get(socket.id);
        if (userInfo) {
          engine.setPlayerUserId(roomCode, socket.id, userInfo.userId);
        }

        const rejoinMode = engine.getRoomMode(roomCode);
        io.to(roomCode).emit('player-joined', {
          players: result.players,
          playerName,
        });
        callback({ success: true, ...result, mode: rejoinMode });
      } catch (err) {
        callback({ success: false, error: err.message });
      }
    });
  });

  // ─── Server-authoritative question flow ───
  // Clear ALL pending timers for a room to prevent overlapping questions
  function clearRoomTimers(room) {
    if (room._timer) { clearTimeout(room._timer); room._timer = null; }
    if (room._ddTimer) { clearTimeout(room._ddTimer); room._ddTimer = null; }
    if (room._resultTimer) { clearTimeout(room._resultTimer); room._resultTimer = null; }
  }

  function sendNextQuestion(roomCode) {
    const room = engine.getRoom(roomCode);
    if (!room || room.status !== 'playing') return;

    // Clear any stale timers first
    clearRoomTimers(room);

    const question = engine.getNextQuestion(roomCode);
    if (!question) {
      // Game over
      const results = engine.endGame(roomCode);
      io.to(roomCode).emit('game-over', results);
      console.log(`[Game] Over in ${roomCode}`);

      // Record stats for all players
      if (results && results.results) {
        const winner = results.results[0]; // sorted by score desc
        results.results.forEach((r) => {
          if (r.userId) {
            try {
              recordGameResult(
                r.userId,
                roomCode,
                r.score,
                r.correctCount,
                results.totalQuestions,
                r.name === winner.name && results.results.length > 1,
                r.maxStreak
              );
            } catch (err) {
              console.error(`[Stats] Failed to record for user ${r.userId}:`, err.message);
            }
          }
        });
      }
      return;
    }

    // Reset double-downs for new question
    engine.resetRound(roomCode);

    // Track which question this timer sequence is for (prevents stale timer callbacks)
    const questionNum = room.currentQuestion;

    function sendQuestionNow() {
      // Guard: make sure we're still on the same question
      if (!room || room.status !== 'playing' || room.currentQuestion !== questionNum) return;
      room._ddTimer = null;

      // Send the actual question (with type and media for face/audio)
      io.to(roomCode).emit('next-question', {
        questionNumber: room.currentQuestion,
        totalQuestions: room.totalQuestions,
        questionText: question.questionText,
        answers: question.answers,
        difficulty: question.difficulty,
        category: question.category,
        type: question.type || 'text',
        mediaUrl: question.mediaUrl || null,
        timeMs: 10000,
      });

      // Start server timer
      engine.startTimer(roomCode);

      // After 10 seconds, reveal answer
      room._timer = setTimeout(() => {
        if (!room || room.status !== 'playing' || room.currentQuestion !== questionNum) return;
        revealAnswer(roomCode);
      }, 10000);
    }

    // Skip double-down on the first question — jump straight in
    if (room.currentQuestion === 1) {
      sendQuestionNow();
    } else {
      // Send double-down phase (5 seconds)
      io.to(roomCode).emit('double-down-phase', {
        questionNumber: room.currentQuestion,
        totalQuestions: room.totalQuestions,
        difficulty: question.difficulty,
        category: question.category,
        timeMs: 5000,
      });

      room._ddTimer = setTimeout(sendQuestionNow, 5000);
    }
  }

  function revealAnswer(roomCode) {
    const room = engine.getRoom(roomCode);
    if (!room || room.status !== 'playing') return;

    // Clear the answer timer
    if (room._timer) { clearTimeout(room._timer); room._timer = null; }

    const result = engine.calculateScores(roomCode);
    io.to(roomCode).emit('question-result', result);
    console.log(`[Game] Q${room.currentQuestion} result in ${roomCode}`);

    // Wait 4 seconds showing results, then next question
    room._resultTimer = setTimeout(() => {
      room._resultTimer = null;
      sendNextQuestion(roomCode);
    }, 4000);
  }

  httpServer.listen(port, () => {
    console.log(`\n  🎤 K-Pop Quiz ready at http://${hostname}:${port}\n`);
  });
});
