const { createServer } = require('http');
const { parse } = require('url');
const next = require('next');
const { Server } = require('socket.io');
const { createGameEngine } = require('./src/lib/game-engine');

const dev = process.env.NODE_ENV !== 'production';
const hostname = 'localhost';
const port = parseInt(process.env.PORT || '3000', 10);

const app = next({ dev, hostname, port });
const handle = app.getRequestHandler();

app.prepare().then(() => {
  const httpServer = createServer((req, res) => {
    const parsedUrl = parse(req.url, true);
    handle(req, res, parsedUrl);
  });

  const io = new Server(httpServer, {
    cors: { origin: '*', methods: ['GET', 'POST'] },
    pingTimeout: 60000,
    pingInterval: 25000,
  });

  const engine = createGameEngine();

  io.on('connection', (socket) => {
    console.log(`[Socket] Connected: ${socket.id}`);

    // ─── Create Room ───
    socket.on('create-room', ({ playerName }, callback) => {
      try {
        const result = engine.createRoom(socket.id, playerName);
        socket.join(result.roomCode);
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
      return;
    }

    // Reset double-downs for new question
    engine.resetRound(roomCode);

    // Send double-down phase (3 seconds)
    io.to(roomCode).emit('double-down-phase', {
      questionNumber: room.currentQuestion,
      totalQuestions: room.totalQuestions,
      difficulty: question.difficulty,
      category: question.category,
      timeMs: 3000,
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
    }, 3000);
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
