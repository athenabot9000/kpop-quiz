'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { getSocket } from '@/lib/socket';
import PlayerList from '@/components/PlayerList';

interface Player {
  name: string;
  isHost: boolean;
  connected: boolean;
  score: number;
}

export default function LobbyPage() {
  const params = useParams();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const roomCode = (params.code as string).toUpperCase();

  const [players, setPlayers] = useState<Player[]>([]);
  const [isHost, setIsHost] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  // Redirect if not authed
  useEffect(() => {
    if (!authLoading && !user) {
      router.replace('/login');
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    if (!user) return;

    const socket = getSocket();

    // Set user identity
    socket.emit('set-user', { userId: user.id, displayName: user.displayName });

    // Check if we need to rejoin (refresh scenario)
    if (socket.connected) {
      socket.emit('rejoin-room', { roomCode, playerName: user.displayName }, (res: any) => {
        if (res.success) {
          setPlayers(res.players);
          setIsHost(res.isHost);
          if (res.status === 'playing') {
            router.push(`/room/${roomCode}/play`);
          }
        }
      });
    }

    socket.on('player-joined', (data: { players: Player[]; playerName: string }) => {
      setPlayers(data.players);
    });

    socket.on('player-left', (data: { players: Player[] }) => {
      setPlayers(data.players);
    });

    socket.on('game-started', () => {
      router.push(`/room/${roomCode}/play`);
    });

    return () => {
      socket.off('player-joined');
      socket.off('player-left');
      socket.off('game-started');
    };
  }, [roomCode, router, user]);

  const handleStart = useCallback(() => {
    const socket = getSocket();
    socket.emit('start-game', { roomCode }, (res: any) => {
      if (!res.success) {
        setError(res.error || 'Failed to start');
      }
    });
  }, [roomCode]);

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(roomCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const el = document.createElement('textarea');
      el.value = roomCode;
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const shareCode = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: 'K-Pop Quiz',
          text: `Join my K-Pop Quiz game! Room code: ${roomCode}`,
          url: window.location.href,
        });
      } catch {}
    } else {
      copyCode();
    }
  };

  if (authLoading || !user) {
    return (
      <main className="flex-1 flex flex-col items-center justify-center px-6">
        <div className="text-4xl mb-4 animate-pulse-glow">🎤</div>
        <p className="text-gray-400">Loading...</p>
      </main>
    );
  }

  return (
    <main className="flex-1 flex flex-col items-center px-6 py-8 safe-top safe-bottom">
      {/* Header */}
      <div className="text-center mb-6 animate-slide-down">
        <div className="text-3xl mb-2">🎤</div>
        <h1 className="text-2xl font-black text-gradient">Game Lobby</h1>
      </div>

      {/* Room Code Display */}
      <div className="glass rounded-2xl p-5 w-full max-w-sm mb-6 text-center animate-slide-up">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
          Room Code
        </p>
        <div
          onClick={copyCode}
          className="text-4xl font-black tracking-[0.4em] text-gradient cursor-pointer
                     active:scale-95 transition-transform select-all pl-[0.4em]"
        >
          {roomCode}
        </div>
        <div className="flex gap-2 mt-4 justify-center">
          <button
            onClick={copyCode}
            className="px-4 py-2.5 rounded-xl text-sm font-semibold bg-kpop-card border border-white/10 
                       btn-press transition-all text-gray-300"
          >
            {copied ? '✓ Copied!' : '📋 Copy'}
          </button>
          <button
            onClick={shareCode}
            className="px-4 py-2.5 rounded-xl text-sm font-semibold bg-kpop-card border border-white/10 
                       btn-press transition-all text-gray-300"
          >
            📤 Share
          </button>
        </div>
      </div>

      {/* Players */}
      <div className="w-full max-w-sm mb-6 animate-slide-up" style={{ animationDelay: '0.1s' }}>
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3 px-1">
          Players ({players.filter(p => p.connected).length}/8)
        </h2>
        <PlayerList players={players} />
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm text-center font-medium max-w-sm w-full animate-shake">
          {error}
        </div>
      )}

      {/* Start Button (host only) */}
      {isHost && (
        <button
          onClick={handleStart}
          disabled={players.filter(p => p.connected).length < 1}
          className="w-full max-w-sm py-4 rounded-xl font-bold text-base text-white
                     bg-gradient-to-r from-kpop-pink to-kpop-purple
                     glow-pink btn-press transition-all
                     disabled:opacity-40 disabled:cursor-not-allowed
                     animate-slide-up"
          style={{ animationDelay: '0.2s' }}
        >
          🚀 Start Game
        </button>
      )}

      {!isHost && players.length > 0 && (
        <div className="text-center text-gray-400 text-sm animate-pulse-glow">
          <p>Waiting for host to start...</p>
        </div>
      )}

      {players.length === 0 && (
        <div className="text-center text-gray-500 text-sm">
          <p>Connecting to room...</p>
        </div>
      )}
    </main>
  );
}
