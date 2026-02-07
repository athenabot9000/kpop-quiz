'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth-context';
import Link from 'next/link';

interface LeaderboardEntry {
  id: number;
  username: string;
  display_name: string;
  games_played: number;
  total_points: number;
  wins: number;
  best_streak: number;
  best_score: number;
  correct_answers: number;
  total_answers: number;
}

type SortKey = 'total_points' | 'wins' | 'best_score' | 'games_played' | 'best_streak';

const SORT_OPTIONS: { key: SortKey; label: string; icon: string }[] = [
  { key: 'total_points', label: 'Points', icon: '⭐' },
  { key: 'wins', label: 'Wins', icon: '🏆' },
  { key: 'best_score', label: 'Best Score', icon: '🔥' },
  { key: 'games_played', label: 'Games', icon: '🎮' },
  { key: 'best_streak', label: 'Streak', icon: '⚡' },
];

export default function LeaderboardPage() {
  const { user } = useAuth();
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<SortKey>('total_points');

  useEffect(() => {
    setLoading(true);
    fetch(`/api/leaderboard?sort=${sortBy}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          setEntries(data.leaderboard);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [sortBy]);

  const getDisplayValue = (entry: LeaderboardEntry): string => {
    switch (sortBy) {
      case 'total_points': return entry.total_points.toLocaleString();
      case 'wins': return entry.wins.toString();
      case 'best_score': return entry.best_score.toLocaleString();
      case 'games_played': return entry.games_played.toString();
      case 'best_streak': return entry.best_streak.toString();
      default: return entry.total_points.toLocaleString();
    }
  };

  const rankEmoji = (i: number) => {
    if (i === 0) return '👑';
    if (i === 1) return '🥈';
    if (i === 2) return '🥉';
    return `${i + 1}`;
  };

  const rankBg = (i: number) => {
    if (i === 0) return 'bg-yellow-500/20 text-yellow-400';
    if (i === 1) return 'bg-gray-400/20 text-gray-300';
    if (i === 2) return 'bg-orange-500/20 text-orange-400';
    return 'bg-white/5 text-gray-500';
  };

  return (
    <main className="flex-1 flex flex-col items-center px-6 py-8 safe-top safe-bottom">
      {/* Header */}
      <div className="text-center mb-6 animate-slide-down">
        <div className="text-4xl mb-2">🏆</div>
        <h1 className="text-3xl font-black text-gradient">Leaderboard</h1>
        <p className="text-gray-500 text-sm mt-1">Top K-Pop quiz masters</p>
      </div>

      {/* Sort Tabs */}
      <div className="w-full max-w-sm mb-5 overflow-x-auto animate-slide-up">
        <div className="flex gap-2 min-w-max">
          {SORT_OPTIONS.map((opt) => (
            <button
              key={opt.key}
              onClick={() => setSortBy(opt.key)}
              className={`px-3 py-2 rounded-lg text-xs font-semibold transition-all whitespace-nowrap
                ${sortBy === opt.key
                  ? 'bg-gradient-to-r from-kpop-pink/20 to-kpop-purple/20 text-white border border-kpop-purple/30'
                  : 'bg-kpop-card text-gray-400 border border-white/5 hover:text-gray-300'
                }`}
            >
              {opt.icon} {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Leaderboard List */}
      {loading ? (
        <div className="py-8 text-center">
          <div className="w-6 h-6 border-2 border-white/30 border-t-kpop-purple rounded-full animate-spin mx-auto mb-3" />
          <p className="text-gray-500 text-sm">Loading...</p>
        </div>
      ) : entries.length === 0 ? (
        <div className="glass rounded-xl p-6 text-center w-full max-w-sm animate-slide-up">
          <p className="text-gray-400 text-sm">No players yet!</p>
          <p className="text-gray-600 text-xs mt-1">Be the first to play a game</p>
        </div>
      ) : (
        <div className="w-full max-w-sm space-y-2 mb-6">
          {entries.map((entry, i) => (
            <div
              key={entry.id}
              className={`glass rounded-xl p-3.5 flex items-center gap-3 animate-slide-up
                ${user && entry.id === user.id ? 'border border-kpop-purple/30' : ''}`}
              style={{ animationDelay: `${Math.min(i * 0.05, 0.5)}s` }}
            >
              <div className={`w-9 h-9 rounded-full flex items-center justify-center font-black text-sm ${rankBg(i)}`}>
                {rankEmoji(i)}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-bold text-white text-sm truncate">
                  {entry.display_name}
                  {user && entry.id === user.id ? ' (you)' : ''}
                </p>
                <p className="text-[10px] text-gray-500">
                  {entry.games_played} games · {entry.wins} wins ·{' '}
                  {entry.total_answers > 0
                    ? Math.round((entry.correct_answers / entry.total_answers) * 100)
                    : 0}% accuracy
                </p>
              </div>
              <div className="text-right">
                <p className="font-black text-sm text-gradient">{getDisplayValue(entry)}</p>
                <p className="text-[10px] text-gray-600 uppercase">
                  {SORT_OPTIONS.find((o) => o.key === sortBy)?.label}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Navigation */}
      <div className="w-full max-w-sm space-y-3 animate-slide-up" style={{ animationDelay: '0.2s' }}>
        <Link
          href="/"
          className="block w-full py-4 rounded-xl font-bold text-base text-white text-center
                     bg-gradient-to-r from-kpop-pink to-kpop-purple
                     glow-pink btn-press transition-all"
        >
          🎵 Play Game
        </Link>
        {user && (
          <Link
            href="/profile"
            className="block w-full py-4 rounded-xl font-bold text-base text-white text-center
                       bg-kpop-card border border-white/10
                       btn-press transition-all active:bg-kpop-card-hover"
          >
            👤 My Profile
          </Link>
        )}
      </div>
    </main>
  );
}
