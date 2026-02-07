'use client';

interface DoubleDownProps {
  onDoubleDown: () => void;
  isActive: boolean;
  category: string;
  difficulty: number;
}

const categoryLabels: Record<string, string> = {
  debut: '🎬 Debut',
  member: '👤 Member',
  song: '🎵 Song',
  group_fact: '📋 Group Fact',
  award: '🏆 Award',
};

const difficultyLabels = ['', 'Easy', 'Medium', 'Hard', 'Very Hard', 'Expert'];
const difficultyColors = ['', 'text-green-400', 'text-blue-400', 'text-yellow-400', 'text-orange-400', 'text-red-400'];

export default function DoubleDown({ onDoubleDown, isActive, category, difficulty }: DoubleDownProps) {
  return (
    <div className="w-full max-w-sm animate-pop">
      <div className="glass rounded-2xl p-6 text-center">
        <h2 className="text-xl font-black text-white mb-4">Double Down?</h2>

        {/* Hints about the upcoming question */}
        <div className="flex justify-center gap-4 mb-5">
          <div className="bg-white/5 rounded-xl px-4 py-2.5">
            <p className="text-xs text-gray-400 mb-0.5">Category</p>
            <p className="text-sm font-bold text-white">
              {categoryLabels[category] || category}
            </p>
          </div>
          <div className="bg-white/5 rounded-xl px-4 py-2.5">
            <p className="text-xs text-gray-400 mb-0.5">Difficulty</p>
            <p className={`text-sm font-bold ${difficultyColors[difficulty]}`}>
              {difficultyLabels[difficulty]}
            </p>
          </div>
        </div>

        <p className="text-sm text-gray-400 mb-5 leading-relaxed">
          Commit before seeing the question.<br />
          <span className="text-green-400 font-semibold">Correct = 2× points</span> · <span className="text-red-400 font-semibold">Wrong = lose points</span>
        </p>

        {!isActive ? (
          <button
            onClick={onDoubleDown}
            className="w-full py-4 rounded-xl font-bold text-base text-white
                       bg-gradient-to-r from-yellow-500 to-amber-600
                       btn-press transition-all
                       shadow-lg shadow-yellow-500/20"
          >
            💰 Double Down!
          </button>
        ) : (
          <div className="py-4 rounded-xl font-bold text-base text-yellow-400
                          bg-yellow-500/10 border border-yellow-500/30">
            💰 Doubled Down! Good luck...
          </div>
        )}

        <p className="text-xs text-gray-600 mt-3">
          Or just wait — question will appear automatically
        </p>
      </div>
    </div>
  );
}
