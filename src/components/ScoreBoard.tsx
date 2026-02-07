'use client';

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

interface ScoreBoardProps {
  playerResults: PlayerResult[];
  currentPlayer: string;
}

export default function ScoreBoard({ playerResults, currentPlayer }: ScoreBoardProps) {
  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Scores</h3>
      {playerResults.map((player, i) => (
        <div
          key={player.name}
          className={`flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all animate-slide-up
            ${player.name === currentPlayer 
              ? 'glass border border-kpop-purple/20' 
              : 'bg-white/[0.02]'}`}
          style={{ animationDelay: `${i * 0.05}s` }}
        >
          {/* Rank */}
          <span className={`text-sm font-black w-6 text-center
            ${i === 0 ? 'text-yellow-400' : i === 1 ? 'text-gray-300' : i === 2 ? 'text-orange-400' : 'text-gray-500'}`}>
            {i + 1}
          </span>

          {/* Correct/wrong indicator */}
          <span className="text-sm">
            {player.isCorrect ? '✅' : player.answered ? '❌' : '⏱️'}
          </span>

          {/* Name */}
          <span className={`flex-1 text-sm font-semibold truncate
            ${player.name === currentPlayer ? 'text-white' : 'text-gray-300'}`}>
            {player.name}
            {player.name === currentPlayer && <span className="text-gray-500 text-xs ml-1">(you)</span>}
          </span>

          {/* Streak */}
          {player.streak >= 3 && (
            <span className="text-[10px] font-bold text-yellow-400 bg-yellow-400/10 px-1.5 py-0.5 rounded">
              🔥{player.streak}
            </span>
          )}

          {/* Points change */}
          <span className={`text-xs font-bold min-w-[50px] text-right
            ${player.pointsEarned > 0 ? 'text-green-400' : player.pointsEarned < 0 ? 'text-red-400' : 'text-gray-500'}`}>
            {player.pointsEarned > 0 ? `+${player.pointsEarned}` : player.pointsEarned === 0 ? '—' : player.pointsEarned}
          </span>

          {/* Total */}
          <span className="text-sm font-black text-white min-w-[60px] text-right">
            {player.totalScore.toLocaleString()}
          </span>
        </div>
      ))}
    </div>
  );
}
