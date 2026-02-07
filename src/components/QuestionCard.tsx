'use client';

import { useEffect, useRef, useState } from 'react';
import AnswerButton from './AnswerButton';

interface QuestionCardProps {
  questionText: string;
  answers: string[];
  selectedAnswer: number | null;
  correctIndex: number | null;
  phase: 'question' | 'result';
  onAnswer: (index: number) => void;
  type?: 'text' | 'face' | 'audio';
  mediaUrl?: string | null;
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
  type = 'text',
  mediaUrl = null,
}: QuestionCardProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [audioPlaying, setAudioPlaying] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);

  // Auto-play audio when question appears
  useEffect(() => {
    if (type === 'audio' && mediaUrl && phase === 'question') {
      const audio = new Audio(mediaUrl);
      audioRef.current = audio;
      audio.play().then(() => setAudioPlaying(true)).catch(() => {});
      audio.onended = () => setAudioPlaying(false);
      return () => {
        audio.pause();
        audio.src = '';
      };
    }
  }, [type, mediaUrl, phase]);

  const handleReplay = () => {
    if (audioRef.current) {
      audioRef.current.currentTime = 0;
      audioRef.current.play().then(() => setAudioPlaying(true)).catch(() => {});
    }
  };

  return (
    <div className="w-full max-w-sm mx-auto flex-1 flex flex-col">
      {/* Question Text + Media */}
      <div className="glass rounded-2xl p-5 mb-4 animate-slide-down">
        {/* Face/Photo question — show image */}
        {type === 'face' && mediaUrl && (
          <div className="flex justify-center mb-3">
            <div className="relative w-40 h-40 rounded-xl overflow-hidden bg-white/5">
              {!imageLoaded && (
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-3xl animate-pulse">📷</div>
                </div>
              )}
              <img
                src={mediaUrl}
                alt="Who is this idol?"
                className={`w-full h-full object-cover transition-opacity duration-300 ${imageLoaded ? 'opacity-100' : 'opacity-0'}`}
                onLoad={() => setImageLoaded(true)}
                onError={() => setImageLoaded(true)}
              />
            </div>
          </div>
        )}

        {/* Audio question — show play button */}
        {type === 'audio' && (
          <div className="flex justify-center mb-3">
            <button
              onClick={handleReplay}
              className={`w-20 h-20 rounded-full flex items-center justify-center transition-all
                ${audioPlaying 
                  ? 'bg-gradient-to-r from-kpop-pink to-kpop-purple animate-pulse-glow' 
                  : 'bg-white/10 hover:bg-white/20'}`}
            >
              <span className="text-3xl">{audioPlaying ? '🎵' : '▶️'}</span>
            </button>
          </div>
        )}

        <p className="text-lg font-bold text-white text-center leading-relaxed">
          {questionText}
        </p>

        {/* Type badge */}
        {type !== 'text' && (
          <div className="flex justify-center mt-2">
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              type === 'face' ? 'bg-purple-500/20 text-purple-300' :
              type === 'audio' ? 'bg-cyan-500/20 text-cyan-300' : ''
            }`}>
              {type === 'face' ? '📸 Photo Question' : '🎧 Audio Question'}
            </span>
          </div>
        )}
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
