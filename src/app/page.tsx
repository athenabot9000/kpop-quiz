'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { getSocket } from '@/lib/socket';
import Link from 'next/link';

export default function HomePage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [roomCode, setRoomCode] = useState('');
  const [mode, setMode] = useState<'menu' | 'create' | 'join'>('menu');
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!loading && !user) {
      router.replace('/login');
    }
  }, [user, loading, router]);

  // Set user identity on socket when user is available
  useEffect(() => {
    if (user) {
      const socket = getSocket();
      socket.emit('set-user', { userId: user.id, displayName: user.displayName });
    }
  }, [user]);

  const handleCreate = () => {
    if (!user) return;
    setError('');
    setActionLoading(true);

    const socket = getSocket();
    socket.emit('create-room', { playerName: user.displayName }, (res: any) => {
      setActionLoading(false);
      if (res.success) {
        localStorage.setItem('kpop-quiz-name', user.displayName);
        localStorage.setItem('kpop-quiz-room', res.roomCode);
        router.push(`/room/${res.roomCode}`);
      } else {
        setError(res.error || 'Failed to create room');
      }
    });
  };

  const handleJoin = () => {
    if (!user) return;
    if (!roomCode.trim() || roomCode.trim().length !== 4) {
      setError('Enter a 4-character room code');
      return;
    }
    setError('');
    setActionLoading(true);

    const socket = getSocket();
    const code = roomCode.trim().toUpperCase();
    socket.emit('join-room', { roomCode: code, playerName: user.displayName }, (res: any) => {
      setActionLoading(false);
      if (res.success) {
        localStorage.setItem('kpop-quiz-name', user.displayName);
        localStorage.setItem('kpop-quiz-room', code);
        router.push(`/room/${code}`);
      } else {
        setError(res.error || 'Failed to join room');
      }
    });
  };

  if (loading || !user) {
    return (
      <main className="flex-1 flex flex-col items-center justify-center px-6">
        <div className="text-4xl mb-4 animate-pulse-glow">🎤</div>
        <p className="text-gray-400">Loading...</p>
      </main>
    );
  }

  return (
    <main className="flex-1 flex flex-col items-center justify-center px-6 py-8 safe-top safe-bottom">
      {/* Logo / Header */}
      <div className="text-center mb-10 animate-slide-down">
        <div className="text-5xl mb-3">🎤</div>
        <h1 className="text-4xl font-black text-gradient tracking-tight">
          K-Pop Quiz
        </h1>
        <p className="text-gray-400 mt-2 text-sm font-medium">
          Test your stan knowledge
        </p>
      </div>

      {/* Card */}
      <div className="glass rounded-2xl p-6 w-full max-w-sm animate-slide-up">
        {/* User Info */}
        <div className="mb-5 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Playing as</p>
            <p className="text-white font-bold text-lg">{user.displayName}</p>
          </div>
          <Link
            href="/profile"
            className="w-9 h-9 rounded-full bg-kpop-card border border-white/10 flex items-center justify-center
                       text-gray-400 hover:text-white transition-colors"
          >
            👤
          </Link>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm text-center font-medium animate-shake">
            {error}
          </div>
        )}

        {mode === 'menu' && (
          <div className="space-y-3">
            <button
              onClick={() => setMode('create')}
              className="w-full py-4 rounded-xl font-bold text-base text-white
                         bg-gradient-to-r from-kpop-pink to-kpop-purple
                         glow-pink btn-press transition-all"
            >
              🎵 Create Game
            </button>
            <button
              onClick={() => setMode('join')}
              className="w-full py-4 rounded-xl font-bold text-base text-white
                         bg-kpop-card border border-white/10
                         btn-press transition-all active:bg-kpop-card-hover"
            >
              🎶 Join Game
            </button>
            <div className="flex gap-2 pt-2">
              <Link
                href="/leaderboard"
                className="flex-1 py-3 rounded-xl font-semibold text-sm text-gray-300 text-center
                           bg-kpop-card border border-white/5
                           btn-press transition-all active:bg-kpop-card-hover"
              >
                🏆 Leaderboard
              </Link>
              <Link
                href="/profile"
                className="flex-1 py-3 rounded-xl font-semibold text-sm text-gray-300 text-center
                           bg-kpop-card border border-white/5
                           btn-press transition-all active:bg-kpop-card-hover"
              >
                📊 My Stats
              </Link>
            </div>
          </div>
        )}

        {mode === 'create' && (
          <div className="space-y-3 animate-slide-up">
            <button
              onClick={handleCreate}
              disabled={actionLoading}
              className="w-full py-4 rounded-xl font-bold text-base text-white
                         bg-gradient-to-r from-kpop-pink to-kpop-purple
                         glow-pink btn-press transition-all
                         disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {actionLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Creating...
                </span>
              ) : (
                '✨ Create Room'
              )}
            </button>
            <button
              onClick={() => { setMode('menu'); setError(''); }}
              className="w-full py-3 text-gray-400 text-sm font-medium"
            >
              ← Back
            </button>
          </div>
        )}

        {mode === 'join' && (
          <div className="space-y-3 animate-slide-up">
            <div>
              <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                Room Code
              </label>
              <input
                type="text"
                value={roomCode}
                onChange={(e) => setRoomCode(e.target.value.toUpperCase().slice(0, 4))}
                placeholder="ABCD"
                maxLength={4}
                className="w-full bg-kpop-darker border border-white/10 rounded-xl px-4 py-3.5 text-white 
                           text-center text-2xl font-black tracking-[0.3em]
                           placeholder-gray-600 uppercase
                           focus:outline-none focus:border-kpop-cyan/50 focus:ring-1 focus:ring-kpop-cyan/30
                           transition-colors"
                autoComplete="off"
              />
            </div>
            <button
              onClick={handleJoin}
              disabled={actionLoading}
              className="w-full py-4 rounded-xl font-bold text-base text-white
                         bg-gradient-to-r from-kpop-blue to-kpop-cyan
                         glow-purple btn-press transition-all
                         disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {actionLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Joining...
                </span>
              ) : (
                '🚀 Join Room'
              )}
            </button>
            <button
              onClick={() => { setMode('menu'); setError(''); }}
              className="w-full py-3 text-gray-400 text-sm font-medium"
            >
              ← Back
            </button>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="mt-8 text-center text-xs text-gray-600">
        <p>Real-time multiplayer K-Pop trivia</p>
      </div>
    </main>
  );
}
