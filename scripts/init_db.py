#!/usr/bin/env python3
"""Initialize the K-pop quiz SQLite database."""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'kpop_quiz.db')

SCHEMA = """
-- ============================================
-- REFERENCE DATA
-- ============================================

CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    korean_name TEXT,
    company TEXT,
    debut_year INTEGER,
    disband_year INTEGER,
    generation INTEGER,
    gender TEXT NOT NULL,  -- 'male', 'female', 'coed'
    member_count INTEGER,
    youtube_views INTEGER,  -- total MV views (popularity proxy)
    difficulty INTEGER,
    active INTEGER DEFAULT 1,
    profile_url TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(name)
);

CREATE TABLE IF NOT EXISTS artists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage_name TEXT NOT NULL,
    real_name TEXT,
    korean_name TEXT,
    group_id INTEGER REFERENCES groups(id),
    birth_date TEXT,
    position TEXT,
    nationality TEXT,
    gender TEXT NOT NULL,
    is_soloist INTEGER DEFAULT 0,
    difficulty INTEGER,
    profile_url TEXT,
    image_url TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(stage_name, group_id)
);

CREATE TABLE IF NOT EXISTS songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    korean_title TEXT,
    group_id INTEGER REFERENCES groups(id),
    artist_id INTEGER REFERENCES artists(id),
    album TEXT,
    year INTEGER,
    is_title_track INTEGER DEFAULT 0,
    youtube_id TEXT,
    youtube_views INTEGER,
    difficulty INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(title, group_id)
);

-- ============================================
-- MEDIA ASSETS
-- ============================================

CREATE TABLE IF NOT EXISTS face_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_id INTEGER NOT NULL REFERENCES artists(id),
    image BLOB NOT NULL,
    width INTEGER,
    height INTEGER,
    format TEXT DEFAULT 'jpeg',
    source_url TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audio_clips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id INTEGER NOT NULL REFERENCES songs(id),
    clip BLOB NOT NULL,
    format TEXT DEFAULT 'mp3',
    start_sec REAL,
    duration_sec REAL DEFAULT 5.0,
    section_type TEXT,
    section_difficulty INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);

-- ============================================
-- QUESTIONS
-- ============================================

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,  -- 'text', 'face', 'audio'
    difficulty INTEGER NOT NULL,
    category TEXT,
    question_text TEXT,
    face_image_id INTEGER REFERENCES face_images(id),
    audio_clip_id INTEGER REFERENCES audio_clips(id),
    correct_answer TEXT NOT NULL,
    metadata_json TEXT,  -- extra context for wrong answer generation
    times_shown INTEGER DEFAULT 0,
    times_correct INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

-- ============================================
-- GAME / AUTH
-- ============================================

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    display_name TEXT,
    avatar_url TEXT,
    games_played INTEGER DEFAULT 0,
    total_score INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    last_login TEXT
);

CREATE TABLE IF NOT EXISTS game_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_code TEXT NOT NULL UNIQUE,
    host_user_id INTEGER REFERENCES users(id),
    status TEXT DEFAULT 'lobby',  -- 'lobby', 'playing', 'finished'
    round_count INTEGER DEFAULT 20,
    current_round INTEGER DEFAULT 0,
    min_difficulty INTEGER DEFAULT 1,
    max_difficulty INTEGER DEFAULT 5,
    created_at TEXT DEFAULT (datetime('now')),
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS game_players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES game_sessions(id),
    user_id INTEGER REFERENCES users(id),
    score INTEGER DEFAULT 0,
    correct_count INTEGER DEFAULT 0,
    streak INTEGER DEFAULT 0,
    max_streak INTEGER DEFAULT 0,
    joined_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS game_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES game_sessions(id),
    player_id INTEGER REFERENCES game_players(id),
    question_id INTEGER REFERENCES questions(id),
    round_number INTEGER,
    answer_given TEXT,
    is_correct INTEGER,
    points_earned INTEGER,
    doubled_down INTEGER DEFAULT 0,
    time_taken_ms INTEGER,
    answered_at TEXT DEFAULT (datetime('now'))
);

-- ============================================
-- INDEXES
-- ============================================

CREATE INDEX IF NOT EXISTS idx_artists_group ON artists(group_id);
CREATE INDEX IF NOT EXISTS idx_artists_difficulty ON artists(difficulty);
CREATE INDEX IF NOT EXISTS idx_songs_group ON songs(group_id);
CREATE INDEX IF NOT EXISTS idx_songs_difficulty ON songs(difficulty);
CREATE INDEX IF NOT EXISTS idx_questions_type ON questions(type);
CREATE INDEX IF NOT EXISTS idx_questions_difficulty ON questions(difficulty);
CREATE INDEX IF NOT EXISTS idx_face_images_artist ON face_images(artist_id);
CREATE INDEX IF NOT EXISTS idx_audio_clips_song ON audio_clips(song_id);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_game_sessions_code ON game_sessions(room_code);
"""

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    
    # Verify
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Database initialized at {os.path.abspath(DB_PATH)}")
    print(f"Tables: {', '.join(tables)}")
    conn.close()

if __name__ == '__main__':
    init_db()
