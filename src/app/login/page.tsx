'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import Link from 'next/link';

export default function LoginPage() {
  const router = useRouter();
  const { user, loading, login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && user) {
      router.replace('/');
    }
  }, [user, loading, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError('Please fill in all fields');
      return;
    }
    setError('');
    setSubmitting(true);

    const result = await login(username.trim(), password);
    setSubmitting(false);

    if (result.success) {
      router.replace('/');
    } else {
      setError(result.error || 'Login failed');
    }
  };

  if (loading) {
    return (
      <main className="flex-1 flex flex-col items-center justify-center px-6">
        <div className="text-4xl mb-4 animate-pulse-glow">🎤</div>
        <p className="text-gray-400">Loading...</p>
      </main>
    );
  }

  return (
    <main className="flex-1 flex flex-col items-center justify-center px-6 py-8 safe-top safe-bottom">
      {/* Logo */}
      <div className="text-center mb-10 animate-slide-down">
        <div className="text-5xl mb-3">🎤</div>
        <h1 className="text-4xl font-black text-gradient tracking-tight">
          K-Pop Quiz
        </h1>
        <p className="text-gray-400 mt-2 text-sm font-medium">
          Sign in to play
        </p>
      </div>

      {/* Login Card */}
      <div className="glass rounded-2xl p-6 w-full max-w-sm animate-slide-up">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter username..."
              maxLength={20}
              autoComplete="username"
              className="w-full bg-kpop-darker border border-white/10 rounded-xl px-4 py-3.5 text-white 
                         placeholder-gray-500 text-base font-medium
                         focus:outline-none focus:border-kpop-purple/50 focus:ring-1 focus:ring-kpop-purple/30
                         transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter password..."
              autoComplete="current-password"
              className="w-full bg-kpop-darker border border-white/10 rounded-xl px-4 py-3.5 text-white 
                         placeholder-gray-500 text-base font-medium
                         focus:outline-none focus:border-kpop-purple/50 focus:ring-1 focus:ring-kpop-purple/30
                         transition-colors"
            />
          </div>

          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm text-center font-medium animate-shake">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-4 rounded-xl font-bold text-base text-white
                       bg-gradient-to-r from-kpop-pink to-kpop-purple
                       glow-pink btn-press transition-all
                       disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Signing in...
              </span>
            ) : (
              '✨ Sign In'
            )}
          </button>
        </form>

        <div className="mt-5 text-center">
          <p className="text-gray-500 text-sm">
            Don&apos;t have an account?{' '}
            <Link href="/register" className="text-kpop-purple font-semibold hover:text-kpop-pink transition-colors">
              Sign Up
            </Link>
          </p>
        </div>
      </div>

      {/* Footer */}
      <div className="mt-8 text-center text-xs text-gray-600">
        <p>Real-time multiplayer K-Pop trivia</p>
      </div>
    </main>
  );
}
