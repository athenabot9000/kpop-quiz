'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { getSocket } from '@/lib/socket';

export default function HomePage() {
  const router = useRouter();
  const [playerName, setPlayerName] = useState('');
  const [roomCode, setRoomCode] = useState('');
  const [mode, setMode] = useState<'menu' | 'create' | 'join'>('menu');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem('kpop-quiz-name');
    if (saved) setPlayerName(saved);
  }, []);

  const saveName = (name: string) => {
    setPlayerName(name);
    localStorage.setItem('kpop-quiz-name', name);
  };

  const handleCreate = () => {
    if (!playerName.trim()) {
      setError('Enter your name first!');
      return;
    }
    setError('');
    setLoading(true);

    const socket = getSocket();
    socket.emit('create-room', { playerName: playerName.trim() }, (res: any) => {
      setLoading(false);
      if (res.success) {
        localStorage.setItem('kpop-quiz-name', playerName.trim());
        localStorage.setItem('kpop-quiz-room', res.roomCode);
        router.push(`/room/${res.roomCode}`);
      } else {
        setError(res.error || 'Failed to create room');
      }
    });
  };

  const handleJoin = () => {
    if (!playerName.trim()) {
      setError('Enter your name first!');
      return;
    }
    if (!roomCode.trim() || roomCode.trim().length !== 4) {
      setError('Enter a 4-character room code');
      return;
    }
    setError('');
    setLoading(true);

    const socket = getSocket();
    const code = roomCode.trim().toUpperCase();
    socket.emit('join-room', { roomCode: code, playerName: playerName.trim() }, (res: any) => {
      setLoading(false);
      if (res.success) {
        localStorage.setItem('kpop-quiz-name', playerName.trim());
        localStorage.setItem('kpop-quiz-room', code);
        router.push(`/room/${code}`);
      } else {
        setError(res.error || 'Failed to join room');
      }
    });
  };

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
        {/* Name Input — always shown */}
        <div className="mb-5">
          <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
            Your Name
          </label>
          <input
            type="text"
            value={playerName}
            onChange={(e) => saveName(e.target.value)}
            placeholder="Enter display name..."
            maxLength={20}
            className="w-full bg-kpop-darker border border-white/10 rounded-xl px-4 py-3.5 text-white 
                       placeholder-gray-500 text-base font-medium
                       focus:outline-none focus:border-kpop-purple/50 focus:ring-1 focus:ring-kpop-purple/30
                       transition-colors"
          />
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
          </div>
        )}

        {mode === 'create' && (
          <div className="space-y-3 animate-slide-up">
            <button
              onClick={handleCreate}
              disabled={loading}
              className="w-full py-4 rounded-xl font-bold text-base text-white
                         bg-gradient-to-r from-kpop-pink to-kpop-purple
                         glow-pink btn-press transition-all
                         disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
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
              disabled={loading}
              className="w-full py-4 rounded-xl font-bold text-base text-white
                         bg-gradient-to-r from-kpop-blue to-kpop-cyan
                         glow-purple btn-press transition-all
                         disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
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
