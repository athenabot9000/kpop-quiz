const { createServer } = require('http');
const { parse } = require('url');
const next = require('next');
const { Server } = require('socket.io');
const { createGameEngine } = require('./src/lib/game-engine');
const { runMigrations } = require('./src/lib/db');
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
    socket.on('create-room', ({ playerName }, callback) => {
      try {
        const result = engine.createRoom(socket.id, playerName);
        socket.join(result.roomCode);

        // Associate userId with this player in the room
        const userInfo = socketUsers.get(socket.id);
        if (userInfo) {
          engine.setPlayerUserId(result.roomCode, socket.id, userInfo.userId);
        }

        console.log(`[Room] Created ${result.roomCode} by ${playerName}`);
        callback({ success: true, ...result });
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
        console.log(`[Room] ${playerName} joined ${roomCode.toUpperCase()}`);
        callback({ success: true, ...result });
      } catch (err) {
        callback({ success: false, error: err.message });
      }
    });

    // ─── Start Game ───
    socket.on('start-game', ({ roomCode }, callback) => {
      try {
        const result = engine.startGame(socket.id, roomCode);
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

    // ─── Submit Answer ───
    socket.on('submit-answer', ({ roomCode, answerIndex }, callback) => {
      try {
        const result = engine.submitAnswer(socket.id, roomCode, answerIndex);
        callback({ success: true, received: true });
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

        io.to(roomCode).emit('player-joined', {
          players: result.players,
          playerName,
        });
        callback({ success: true, ...result });
      } catch (err) {
        callback({ success: false, error: err.message });
      }
    });
  });

  // ─── Server-authoritative question flow ───
  function sendNextQuestion(roomCode) {
    const room = engine.getRoom(roomCode);
    if (!room || room.status !== 'playing') return;

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

    // Send double-down phase (5 seconds)
    io.to(roomCode).emit('double-down-phase', {
      questionNumber: room.currentQuestion,
      totalQuestions: room.totalQuestions,
      difficulty: question.difficulty,
      category: question.category,
      timeMs: 5000,
    });

    setTimeout(() => {
      // Send the actual question
      io.to(roomCode).emit('next-question', {
        questionNumber: room.currentQuestion,
        totalQuestions: room.totalQuestions,
        questionText: question.questionText,
        answers: question.answers,
        difficulty: question.difficulty,
        category: question.category,
        timeMs: 10000,
      });

      // Start server timer
      engine.startTimer(roomCode);

      // After 10 seconds, reveal answer
      room._timer = setTimeout(() => {
        revealAnswer(roomCode);
      }, 10000);
    }, 5000);
  }

  function revealAnswer(roomCode) {
    const room = engine.getRoom(roomCode);
    if (!room || room.status !== 'playing') return;

    const result = engine.calculateScores(roomCode);
    io.to(roomCode).emit('question-result', result);
    console.log(`[Game] Q${room.currentQuestion} result in ${roomCode}`);

    // Wait 4 seconds showing results, then next question
    setTimeout(() => {
      sendNextQuestion(roomCode);
    }, 4000);
  }

  httpServer.listen(port, () => {
    console.log(`\n  🎤 K-Pop Quiz ready at http://${hostname}:${port}\n`);
  });
});
