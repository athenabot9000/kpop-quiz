'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import Link from 'next/link';

interface Stats {
  games_played: number;
  total_points: number;
  wins: number;
  best_streak: number;
  best_score: number;
  correct_answers: number;
  total_answers: number;
}

interface GameHistoryEntry {
  id: number;
  room_code: string;
  score: number;
  correct_answers: number;
  total_questions: number;
  won: number;
  streak_best: number;
  created_at: string;
}

export default function ProfilePage() {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [stats, setStats] = useState<Stats | null>(null);
  const [history, setHistory] = useState<GameHistoryEntry[]>([]);
  const [dataLoading, setDataLoading] = useState(true);

  useEffect(() => {
    if (!loading && !user) {
      router.replace('/login');
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      fetch(`/api/stats/${user.id}`)
        .then((res) => res.json())
        .then((data) => {
          if (data.success) {
            setStats(data.stats);
            setHistory(data.history || []);
          }
        })
        .catch(() => {})
        .finally(() => setDataLoading(false));
    }
  }, [user]);

  const handleLogout = async () => {
    await logout();
    router.replace('/login');
  };

  if (loading || !user) {
    return (
      <main className="flex-1 flex flex-col items-center justify-center px-6">
        <div className="text-4xl mb-4 animate-pulse-glow">🎤</div>
        <p className="text-gray-400">Loading...</p>
      </main>
    );
  }

  const accuracy = stats && stats.total_answers > 0
    ? Math.round((stats.correct_answers / stats.total_answers) * 100)
    : 0;

  const winRate = stats && stats.games_played > 0
    ? Math.round((stats.wins / stats.games_played) * 100)
    : 0;

  return (
    <main className="flex-1 flex flex-col items-center px-6 py-8 safe-top safe-bottom">
      {/* Header */}
      <div className="text-center mb-6 animate-slide-down">
        <div className="text-4xl mb-2">👤</div>
        <h1 className="text-3xl font-black text-gradient">{user.displayName}</h1>
        <p className="text-gray-500 text-sm mt-1">@{user.username}</p>
      </div>

      {/* Stats Grid */}
      {stats && !dataLoading && (
        <div className="w-full max-w-sm mb-6 animate-slide-up">
          <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3 px-1">
            All-Time Stats
          </h2>
          <div className="grid grid-cols-2 gap-3">
            <StatCard label="Games Played" value={stats.games_played.toString()} icon="🎮" />
            <StatCard label="Total Points" value={stats.total_points.toLocaleString()} icon="⭐" />
            <StatCard label="Wins" value={stats.wins.toString()} icon="🏆" />
            <StatCard label="Win Rate" value={`${winRate}%`} icon="📊" />
            <StatCard label="Best Score" value={stats.best_score.toLocaleString()} icon="🔥" />
            <StatCard label="Best Streak" value={stats.best_streak.toString()} icon="⚡" />
            <StatCard label="Accuracy" value={`${accuracy}%`} icon="🎯" />
            <StatCard
              label="Correct / Total"
              value={`${stats.correct_answers}/${stats.total_answers}`}
              icon="✅"
            />
          </div>
        </div>
      )}

      {dataLoading && (
        <div className="w-full max-w-sm mb-6 text-center py-8">
          <div className="w-6 h-6 border-2 border-white/30 border-t-kpop-purple rounded-full animate-spin mx-auto mb-3" />
          <p className="text-gray-500 text-sm">Loading stats...</p>
        </div>
      )}

      {/* Game History */}
      {history.length > 0 && (
        <div className="w-full max-w-sm mb-6 animate-slide-up" style={{ animationDelay: '0.1s' }}>
          <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3 px-1">
            Recent Games
          </h2>
          <div className="space-y-2">
            {history.map((game) => (
              <div key={game.id} className="glass rounded-xl p-3.5 flex items-center gap-3">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm
                  ${game.won ? 'bg-yellow-500/20 text-yellow-400' : 'bg-white/5 text-gray-500'}`}>
                  {game.won ? '👑' : '🎤'}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-white text-sm">Room {game.room_code}</span>
                    {game.won ? (
                      <span className="text-[10px] bg-yellow-500/20 text-yellow-400 px-1.5 py-0.5 rounded font-semibold">
                        WIN
                      </span>
                    ) : null}
                  </div>
                  <p className="text-xs text-gray-500">
                    {game.correct_answers}/{game.total_questions} correct · Streak: {game.streak_best}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-black text-sm text-gradient">{game.score.toLocaleString()}</p>
                  <p className="text-[10px] text-gray-600">
                    {new Date(game.created_at + 'Z').toLocaleDateString()}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {!dataLoading && history.length === 0 && stats && stats.games_played === 0 && (
        <div className="glass rounded-xl p-6 text-center w-full max-w-sm mb-6 animate-slide-up">
          <p className="text-gray-400 text-sm">No games played yet!</p>
          <p className="text-gray-600 text-xs mt-1">Create or join a game to get started</p>
        </div>
      )}

      {/* Action Buttons */}
      <div className="w-full max-w-sm space-y-3 animate-slide-up" style={{ animationDelay: '0.2s' }}>
        <Link
          href="/"
          className="block w-full py-4 rounded-xl font-bold text-base text-white text-center
                     bg-gradient-to-r from-kpop-pink to-kpop-purple
                     glow-pink btn-press transition-all"
        >
          🎵 Play Game
        </Link>
        <Link
          href="/leaderboard"
          className="block w-full py-4 rounded-xl font-bold text-base text-white text-center
                     bg-kpop-card border border-white/10
                     btn-press transition-all active:bg-kpop-card-hover"
        >
          🏆 Leaderboard
        </Link>
        <button
          onClick={handleLogout}
          className="w-full py-3 text-gray-500 text-sm font-medium hover:text-gray-300 transition-colors"
        >
          Sign Out
        </button>
      </div>
    </main>
  );
}

function StatCard({ label, value, icon }: { label: string; value: string; icon: string }) {
  return (
    <div className="glass rounded-xl p-3.5 text-center">
      <div className="text-lg mb-1">{icon}</div>
      <p className="text-lg font-black text-white">{value}</p>
      <p className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold mt-0.5">{label}</p>
    </div>
  );
}
