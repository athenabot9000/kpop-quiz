'use client';

interface AnswerButtonProps {
  answer: string;
  index: number;
  state: 'default' | 'selected' | 'correct' | 'wrong' | 'disabled';
  color: { bg: string; border: string; glow: string };
  onSelect: () => void;
  delay: number;
}

const labels = ['A', 'B', 'C', 'D'];

export default function AnswerButton({
  answer,
  index,
  state,
  color,
  onSelect,
  delay,
}: AnswerButtonProps) {
  const isInteractive = state === 'default';

  let containerClass = 'glass rounded-xl border transition-all duration-200 btn-press animate-slide-up ';

  switch (state) {
    case 'default':
      containerClass += `${color.border} active:scale-[0.97]`;
      break;
    case 'selected':
      containerClass += `border-kpop-purple/50 bg-kpop-purple/10 glow-purple`;
      break;
    case 'correct':
      containerClass += `border-green-500/50 bg-green-500/15 glow-green animate-pop`;
      break;
    case 'wrong':
      containerClass += `border-red-500/50 bg-red-500/15 glow-red animate-shake`;
      break;
    case 'disabled':
      containerClass += `border-white/5 opacity-40`;
      break;
  }

  return (
    <button
      onClick={isInteractive ? onSelect : undefined}
      disabled={!isInteractive}
      className={containerClass}
      style={{ animationDelay: `${delay}s` }}
    >
      <div className="flex items-center gap-3 px-4 py-4 min-h-[56px]">
        {/* Letter badge */}
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm font-black flex-shrink-0
          ${state === 'correct' ? 'bg-green-500/30 text-green-300' :
            state === 'wrong' ? 'bg-red-500/30 text-red-300' :
            state === 'selected' ? 'bg-kpop-purple/30 text-kpop-purple' :
            'bg-white/5 text-gray-400'}`}>
          {state === 'correct' ? '✓' : state === 'wrong' ? '✗' : labels[index]}
        </div>

        {/* Answer text */}
        <span className={`text-base font-semibold text-left flex-1
          ${state === 'correct' ? 'text-green-300' :
            state === 'wrong' ? 'text-red-300' :
            state === 'disabled' ? 'text-gray-500' :
            'text-white'}`}>
          {answer}
        </span>

        {/* Result indicator */}
        {state === 'correct' && (
          <span className="text-green-400 text-lg">✅</span>
        )}
        {state === 'wrong' && (
          <span className="text-red-400 text-lg">❌</span>
        )}
      </div>
    </button>
  );
}
