'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { getSocket } from '@/lib/socket';
import QuestionCard from '@/components/QuestionCard';
import Timer from '@/components/Timer';
import ScoreBoard from '@/components/ScoreBoard';
import DoubleDown from '@/components/DoubleDown';

interface PlayerResult {
  name: string;
  isCorrect: boolean;
  pointsEarned: number;
  totalScore: number;
  streak: number;
  doubleDown: boolean;
  answerTime: number | null;
  answered: boolean;
}

interface QuestionData {
  questionNumber: number;
  totalQuestions: number;
  questionText: string;
  answers: string[];
  difficulty: number;
  category: string;
  timeMs: number;
}

interface QuestionResult {
  correctIndex: number;
  correctAnswer: string;
  playerResults: PlayerResult[];
  questionNumber: number;
  totalQuestions: number;
}

interface GameOverData {
  results: {
    name: string;
    score: number;
    correctCount: number;
    maxStreak: number;
    isHost: boolean;
  }[];
  totalQuestions: number;
}

type Phase = 'waiting' | 'double-down' | 'question' | 'result' | 'game-over';

export default function PlayPage() {
  const params = useParams();
  const router = useRouter();
  const roomCode = (params.code as string).toUpperCase();
  const playerName = typeof window !== 'undefined' ? localStorage.getItem('kpop-quiz-name') || '' : '';

  const [phase, setPhase] = useState<Phase>('waiting');
  const [question, setQuestion] = useState<QuestionData | null>(null);
  const [selectedAnswer, setSelectedAnswer] = useState<number | null>(null);
  const [result, setResult] = useState<QuestionResult | null>(null);
  const [gameOver, setGameOver] = useState<GameOverData | null>(null);
  const [doubleDown, setDoubleDown] = useState(false);
  const [timerMs, setTimerMs] = useState(0);
  const [timerTotal, setTimerTotal] = useState(0);
  const [myResult, setMyResult] = useState<PlayerResult | null>(null);
  const [questionInfo, setQuestionInfo] = useState<{ number: number; total: number; difficulty: number; category: string } | null>(null);

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timerStartRef = useRef<number>(0);

  const startClientTimer = useCallback((totalMs: number) => {
    if (timerRef.current) clearInterval(timerRef.current);
    setTimerTotal(totalMs);
    setTimerMs(totalMs);
    timerStartRef.current = Date.now();

    timerRef.current = setInterval(() => {
      const elapsed = Date.now() - timerStartRef.current;
      const remaining = Math.max(0, totalMs - elapsed);
      setTimerMs(remaining);
      if (remaining <= 0 && timerRef.current) {
        clearInterval(timerRef.current);
      }
    }, 50);
  }, []);

  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => {
    const socket = getSocket();

    socket.on('double-down-phase', (data: { questionNumber: number; totalQuestions: number; difficulty: number; category: string; timeMs: number }) => {
      setPhase('double-down');
      setDoubleDown(false);
      setSelectedAnswer(null);
      setResult(null);
      setMyResult(null);
      setQuestionInfo({
        number: data.questionNumber,
        total: data.totalQuestions,
        difficulty: data.difficulty,
        category: data.category,
      });
      startClientTimer(data.timeMs);
    });

    socket.on('next-question', (data: QuestionData) => {
      setPhase('question');
      setQuestion(data);
      setSelectedAnswer(null);
      startClientTimer(data.timeMs);
    });

    socket.on('question-result', (data: QuestionResult) => {
      stopTimer();
      setPhase('result');
      setResult(data);
      const me = data.playerResults.find((p) => p.name === playerName);
      if (me) setMyResult(me);
    });

    socket.on('game-over', (data: GameOverData) => {
      stopTimer();
      setPhase('game-over');
      setGameOver(data);
    });

    return () => {
      socket.off('double-down-phase');
      socket.off('next-question');
      socket.off('question-result');
      socket.off('game-over');
      stopTimer();
    };
  }, [playerName, startClientTimer, stopTimer]);

  const handleDoubleDown = useCallback(() => {
    const socket = getSocket();
    socket.emit('double-down', { roomCode });
    setDoubleDown(true);
  }, [roomCode]);

  const handleAnswer = useCallback((index: number) => {
    if (selectedAnswer !== null) return;
    setSelectedAnswer(index);
    const socket = getSocket();
    socket.emit('submit-answer', { roomCode, answerIndex: index }, () => {});
  }, [roomCode, selectedAnswer]);

  const difficultyLabel = (d: number) => ['', '⭐', '⭐⭐', '⭐⭐⭐', '⭐⭐⭐⭐', '⭐⭐⭐⭐⭐'][d] || '';
  const difficultyColor = (d: number) => ['', 'text-green-400', 'text-blue-400', 'text-yellow-400', 'text-orange-400', 'text-red-400'][d] || '';
  const categoryIcon = (c: string) => {
    const icons: Record<string, string> = { debut: '🎬', member: '👤', song: '🎵', group_fact: '📋', award: '🏆' };
    return icons[c] || '❓';
  };

  // ─── Waiting Phase ───
  if (phase === 'waiting') {
    return (
      <main className="flex-1 flex flex-col items-center justify-center px-6">
        <div className="text-4xl mb-4 animate-pulse-glow">🎤</div>
        <h2 className="text-xl font-bold text-gray-300">Get Ready!</h2>
        <p className="text-gray-500 text-sm mt-2">The game is about to begin...</p>
      </main>
    );
  }

  // ─── Game Over ───
  if (phase === 'game-over' && gameOver) {
    const myRank = gameOver.results.findIndex((r) => r.name === playerName) + 1;
    return (
      <main className="flex-1 flex flex-col items-center px-6 py-8 safe-top safe-bottom">
        <div className="text-center mb-6 animate-slide-down">
          <div className="text-5xl mb-3">
            {myRank === 1 ? '👑' : myRank === 2 ? '🥈' : myRank === 3 ? '🥉' : '🎤'}
          </div>
          <h1 className="text-3xl font-black text-gradient">Game Over!</h1>
        </div>

        <div className="w-full max-w-sm space-y-3 mb-8">
          {gameOver.results.map((r, i) => (
            <div
              key={r.name}
              className={`glass rounded-xl p-4 flex items-center gap-4 animate-slide-up
                ${r.name === playerName ? 'border-kpop-purple/30 border' : ''}`}
              style={{ animationDelay: `${i * 0.1}s` }}
            >
              <div className={`w-10 h-10 rounded-full flex items-center justify-center font-black text-lg
                ${i === 0 ? 'bg-yellow-500/20 text-yellow-400' : 
                  i === 1 ? 'bg-gray-400/20 text-gray-300' : 
                  i === 2 ? 'bg-orange-500/20 text-orange-400' : 
                  'bg-white/5 text-gray-500'}`}>
                {i + 1}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-bold text-white truncate">
                  {r.name} {r.name === playerName ? '(you)' : ''} {r.isHost ? '👑' : ''}
                </p>
                <p className="text-xs text-gray-400">
                  {r.correctCount}/{gameOver.totalQuestions} correct · Best streak: {r.maxStreak}
                </p>
              </div>
              <div className="text-right">
                <p className="font-black text-lg text-gradient">{r.score.toLocaleString()}</p>
              </div>
            </div>
          ))}
        </div>

        <button
          onClick={() => router.push('/')}
          className="w-full max-w-sm py-4 rounded-xl font-bold text-base text-white
                     bg-gradient-to-r from-kpop-pink to-kpop-purple
                     glow-pink btn-press transition-all"
        >
          🏠 Back to Home
        </button>
      </main>
    );
  }

  // ─── Double Down Phase ───
  if (phase === 'double-down' && questionInfo) {
    return (
      <main className="flex-1 flex flex-col items-center justify-center px-6 safe-top safe-bottom">
        {/* Progress */}
        <div className="w-full max-w-sm mb-4">
          <div className="flex justify-between items-center text-xs text-gray-400 mb-1">
            <span>Question {questionInfo.number}/{questionInfo.total}</span>
            <span className={difficultyColor(questionInfo.difficulty)}>
              {difficultyLabel(questionInfo.difficulty)}
            </span>
          </div>
          <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-kpop-pink to-kpop-purple rounded-full transition-all duration-500"
              style={{ width: `${(questionInfo.number / questionInfo.total) * 100}%` }}
            />
          </div>
        </div>

        {/* Timer */}
        <Timer timeMs={timerMs} totalMs={timerTotal} />

        {/* Double Down Card */}
        <DoubleDown
          onDoubleDown={handleDoubleDown}
          isActive={doubleDown}
          category={questionInfo.category}
          difficulty={questionInfo.difficulty}
        />
      </main>
    );
  }

  // ─── Question Phase ───
  if ((phase === 'question' || phase === 'result') && question) {
    return (
      <main className="flex-1 flex flex-col px-6 py-4 safe-top safe-bottom">
        {/* Progress */}
        <div className="w-full max-w-sm mx-auto mb-3">
          <div className="flex justify-between items-center text-xs text-gray-400 mb-1">
            <span className="flex items-center gap-1.5">
              {categoryIcon(question.category)} Q{question.questionNumber}/{question.totalQuestions}
            </span>
            <span className="flex items-center gap-1.5">
              {doubleDown && <span className="text-yellow-400 font-bold text-[10px] bg-yellow-400/10 px-1.5 py-0.5 rounded">2×</span>}
              <span className={difficultyColor(question.difficulty)}>
                {difficultyLabel(question.difficulty)}
              </span>
            </span>
          </div>
          <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-kpop-pink to-kpop-purple rounded-full transition-all duration-500"
              style={{ width: `${(question.questionNumber / question.totalQuestions) * 100}%` }}
            />
          </div>
        </div>

        {/* Timer */}
        {phase === 'question' && (
          <div className="w-full max-w-sm mx-auto mb-4">
            <Timer timeMs={timerMs} totalMs={timerTotal} />
          </div>
        )}

        {/* Question */}
        <QuestionCard
          questionText={question.questionText}
          answers={question.answers}
          selectedAnswer={selectedAnswer}
          correctIndex={result?.correctIndex ?? null}
          phase={phase}
          onAnswer={handleAnswer}
        />

        {/* Result feedback */}
        {phase === 'result' && myResult && (
          <div className="w-full max-w-sm mx-auto mt-4 animate-score-pop">
            <div className={`glass rounded-xl p-4 text-center
              ${myResult.isCorrect ? 'border border-green-500/30' : 'border border-red-500/30'}`}>
              <div className="text-2xl mb-1">
                {myResult.isCorrect ? '✅' : '❌'}
              </div>
              <p className={`font-bold text-lg ${myResult.isCorrect ? 'text-green-400' : 'text-red-400'}`}>
                {myResult.isCorrect ? 'Correct!' : 'Wrong!'}
              </p>
              <p className={`text-2xl font-black mt-1 ${myResult.pointsEarned >= 0 ? 'text-gradient' : 'text-red-400'}`}>
                {myResult.pointsEarned > 0 ? '+' : ''}{myResult.pointsEarned}
              </p>
              {myResult.streak >= 3 && (
                <p className="text-xs text-yellow-400 mt-1 font-semibold">🔥 {myResult.streak} streak! (1.5× bonus)</p>
              )}
              {myResult.doubleDown && (
                <p className="text-xs text-yellow-400 mt-1 font-semibold">
                  {myResult.isCorrect ? '💰 Double Down pays off!' : '💸 Double Down backfired!'}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Score board (during results) */}
        {phase === 'result' && result && (
          <div className="w-full max-w-sm mx-auto mt-3">
            <ScoreBoard playerResults={result.playerResults} currentPlayer={playerName} />
          </div>
        )}
      </main>
    );
  }

  // Fallback
  return (
    <main className="flex-1 flex flex-col items-center justify-center px-6">
      <div className="text-4xl mb-4 animate-pulse-glow">🎤</div>
      <p className="text-gray-400">Loading...</p>
    </main>
  );
}
