'use client';

import AnswerButton from './AnswerButton';

interface QuestionCardProps {
  questionText: string;
  answers: string[];
  selectedAnswer: number | null;
  correctIndex: number | null;
  phase: 'question' | 'result';
  onAnswer: (index: number) => void;
}

const answerColors = [
  { bg: 'from-pink-600 to-rose-600', border: 'border-pink-500/30', glow: 'shadow-pink-500/20' },
  { bg: 'from-blue-600 to-indigo-600', border: 'border-blue-500/30', glow: 'shadow-blue-500/20' },
  { bg: 'from-amber-600 to-orange-600', border: 'border-amber-500/30', glow: 'shadow-amber-500/20' },
  { bg: 'from-emerald-600 to-teal-600', border: 'border-emerald-500/30', glow: 'shadow-emerald-500/20' },
];

export default function QuestionCard({
  questionText,
  answers,
  selectedAnswer,
  correctIndex,
  phase,
  onAnswer,
}: QuestionCardProps) {
  return (
    <div className="w-full max-w-sm mx-auto flex-1 flex flex-col">
      {/* Question Text */}
      <div className="glass rounded-2xl p-5 mb-4 animate-slide-down">
        <p className="text-lg font-bold text-white text-center leading-relaxed">
          {questionText}
        </p>
      </div>

      {/* Answer Grid */}
      <div className="space-y-3 flex-1 flex flex-col justify-center">
        {answers.map((answer, index) => {
          let state: 'default' | 'selected' | 'correct' | 'wrong' | 'disabled' = 'default';

          if (phase === 'result') {
            if (index === correctIndex) {
              state = 'correct';
            } else if (index === selectedAnswer && index !== correctIndex) {
              state = 'wrong';
            } else {
              state = 'disabled';
            }
          } else if (selectedAnswer !== null) {
            state = index === selectedAnswer ? 'selected' : 'disabled';
          }

          return (
            <AnswerButton
              key={index}
              answer={answer}
              index={index}
              state={state}
              color={answerColors[index]}
              onSelect={() => onAnswer(index)}
              delay={index * 0.05}
            />
          );
        })}
      </div>
    </div>
  );
}
