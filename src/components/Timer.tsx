'use client';

interface TimerProps {
  timeMs: number;
  totalMs: number;
}

export default function Timer({ timeMs, totalMs }: TimerProps) {
  const fraction = totalMs > 0 ? timeMs / totalMs : 0;
  const seconds = Math.ceil(timeMs / 1000);
  const isUrgent = timeMs < 3000 && timeMs > 0;

  // Color transitions: green → yellow → red
  let barColor = 'from-green-400 to-emerald-500';
  if (fraction < 0.3) {
    barColor = 'from-red-500 to-rose-600';
  } else if (fraction < 0.6) {
    barColor = 'from-yellow-400 to-amber-500';
  }

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-1.5">
        <div className={`text-2xl font-black tabular-nums transition-colors duration-300
          ${isUrgent ? 'text-red-400 animate-pulse-glow' : 'text-white'}`}>
          {seconds}
        </div>
        <div className="text-xs text-gray-500 font-medium">
          {totalMs === 3000 ? 'Double Down' : 'Answer'}
        </div>
      </div>
      <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
        <div
          className={`h-full bg-gradient-to-r ${barColor} rounded-full transition-none`}
          style={{ width: `${fraction * 100}%` }}
        />
      </div>
    </div>
  );
}
