'use client';

interface Player {
  name: string;
  isHost: boolean;
  connected: boolean;
  score: number;
}

interface PlayerListProps {
  players: Player[];
}

const avatarColors = [
  'from-pink-500 to-rose-500',
  'from-blue-500 to-indigo-500',
  'from-emerald-500 to-teal-500',
  'from-amber-500 to-orange-500',
  'from-purple-500 to-violet-500',
  'from-cyan-500 to-sky-500',
  'from-red-500 to-pink-500',
  'from-lime-500 to-green-500',
];

export default function PlayerList({ players }: PlayerListProps) {
  if (players.length === 0) {
    return (
      <div className="glass rounded-xl p-6 text-center">
        <p className="text-gray-500 text-sm">No players yet...</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {players.map((player, i) => (
        <div
          key={player.name}
          className={`glass rounded-xl px-4 py-3 flex items-center gap-3 animate-slide-up
            ${!player.connected ? 'opacity-40' : ''}`}
          style={{ animationDelay: `${i * 0.05}s` }}
        >
          {/* Avatar */}
          <div className={`w-10 h-10 rounded-full bg-gradient-to-br ${avatarColors[i % avatarColors.length]}
                          flex items-center justify-center text-white font-black text-sm`}>
            {player.name.charAt(0).toUpperCase()}
          </div>

          {/* Name */}
          <div className="flex-1 min-w-0">
            <p className="font-bold text-white text-sm truncate">
              {player.name}
            </p>
            <p className="text-xs text-gray-400">
              {player.isHost ? '👑 Host' : 'Player'}
              {!player.connected && ' · Disconnected'}
            </p>
          </div>

          {/* Ready indicator */}
          <div className={`w-3 h-3 rounded-full ${player.connected ? 'bg-green-500' : 'bg-gray-600'}`} />
        </div>
      ))}
    </div>
  );
}
