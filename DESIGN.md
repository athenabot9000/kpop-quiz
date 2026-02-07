# K-Pop Quiz App — Design Document

## Overview

A mobile-friendly multiplayer quiz app where players take turns answering K-pop trivia questions. Three question types: text trivia, face recognition, and audio clip identification. Players compete for the highest score over time.

**Platform:** Mobile Safari (web app)
**Stack:** Next.js + Socket.IO + SQLite
**Hosting:** Replit initially → self-hosted later

---

## Question Types

### 1. Text Trivia (60% of questions)
- Standard multiple choice, 4 options
- Example: "Which group debuted with the song 'No More Dream'?"
- Timer: 10 seconds
- Categories: debut info, member facts, awards, song/album facts, group facts

### 2. Face Recognition (20% of questions)
- Flash an idol's photo for 5 seconds
- Player has 5 seconds to pick the correct name from 4 choices
- Images cropped to face, consistent aspect ratio (3:4 portrait)

### 3. Audio Clip (20% of questions)
- Play a 5-second audio clip
- Player has 5 seconds to pick the correct song from 4 choices
- Clip difficulty varies by section (chorus = easy, instrumental = expert)

---

## Difficulty System

### Scoring Formula

Each artist/group gets a difficulty score from two signals:

```
popularity_score = log10(spotify_monthly_listeners + 1)
era_penalty = (current_year - debut_year) * 0.15
difficulty_raw = (max_popularity - popularity_score) + era_penalty
```

Bucketed into 5 tiers:

| Tier | Points | Multiplier | Examples |
|------|--------|------------|---------|
| 1 - Easy | 100 | 1x | BTS, BLACKPINK, TWICE, Stray Kids, NewJeans |
| 2 - Medium | 200 | 2x | IVE, (G)I-DLE, ENHYPEN, TXT, ITZY |
| 3 - Hard | 300 | 3x | Dreamcatcher, ONEUS, Kep1er, VIVIZ |
| 4 - Very Hard | 400 | 4x | KARA, T-ara, 2PM, After School, SHINee |
| 5 - Expert | 500 | 5x | H.O.T, S.E.S, g.o.d, Shinhwa, Sechskies |

### Audio Clip Difficulty (additional layer)

| Section Type | Difficulty Modifier |
|-------------|-------------------|
| Chorus / hook | +0 (easiest — most recognizable) |
| Verse / pre-chorus | +1 |
| Bridge / outro | +2 |
| Instrumental / intro | +3 (hardest — no vocal cues) |

Audio clip difficulty = artist difficulty + section modifier (capped at 5).

---

## Game Mechanics

### Turn Structure
1. Player's turn begins
2. **Optional: Double Down** — commit before seeing the question. If correct, earn 2x points. If wrong, lose the base points.
3. **Optional: Pick difficulty** — choose a tier for more points (or get one assigned randomly within their comfort range)
4. Question appears with timer
5. Answer or time expires → score updates
6. Next player's turn

### Scoring
- Base points per difficulty tier (100/200/300/400/500)
- Double down: 2x if correct, -1x if wrong
- Streak bonus: 3+ correct in a row → 1.5x multiplier
- Perfect round bonus: all correct in a round → bonus points

### Multiplayer
- Room codes (like Kahoot/Jackbox) for session join
- 2-8 players per room
- Rounds: configurable (10/20/30 questions per round)
- Leaderboard: running score across multiple games
- Persistent player profiles with lifetime stats

---

## Content Database Schema

```sql
-- ============================================
-- REFERENCE DATA
-- ============================================

CREATE TABLE groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    korean_name TEXT,
    company TEXT,
    debut_year INTEGER,
    disband_year INTEGER,         -- NULL if active
    generation INTEGER,           -- 1-5
    gender TEXT NOT NULL,          -- 'male', 'female', 'coed'
    spotify_listeners INTEGER,    -- monthly listeners (for difficulty)
    difficulty INTEGER NOT NULL,  -- 1-5 computed
    active INTEGER DEFAULT 1,
    UNIQUE(name)
);

CREATE TABLE artists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage_name TEXT NOT NULL,
    real_name TEXT,
    korean_name TEXT,
    group_id INTEGER REFERENCES groups(id),
    birth_date TEXT,
    position TEXT,                -- 'vocal', 'rap', 'dance', 'visual', 'leader'
    nationality TEXT,
    gender TEXT NOT NULL,
    is_soloist INTEGER DEFAULT 0,
    difficulty INTEGER NOT NULL,  -- inherited from group + solo popularity
    UNIQUE(stage_name, group_id)
);

CREATE TABLE songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    korean_title TEXT,
    group_id INTEGER REFERENCES groups(id),
    artist_id INTEGER REFERENCES artists(id),  -- for solo songs
    album TEXT,
    year INTEGER,
    is_title_track INTEGER DEFAULT 0,
    youtube_id TEXT,
    spotify_id TEXT,
    difficulty INTEGER NOT NULL,
    UNIQUE(title, group_id)
);

-- ============================================
-- MEDIA ASSETS
-- ============================================

CREATE TABLE face_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_id INTEGER NOT NULL REFERENCES artists(id),
    image BLOB NOT NULL,
    width INTEGER,
    height INTEGER,
    format TEXT DEFAULT 'jpeg',   -- 'jpeg' or 'png'
    source_url TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE audio_clips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id INTEGER NOT NULL REFERENCES songs(id),
    clip BLOB NOT NULL,
    format TEXT DEFAULT 'mp3',
    start_sec REAL,               -- position in original song
    duration_sec REAL DEFAULT 5.0,
    section_type TEXT,            -- 'chorus', 'verse', 'bridge', 'instrumental', 'intro', 'outro'
    section_difficulty INTEGER,   -- 0-3 modifier based on section type
    created_at TEXT DEFAULT (datetime('now'))
);

-- ============================================
-- QUESTIONS
-- ============================================

CREATE TABLE questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,            -- 'text', 'face', 'audio'
    difficulty INTEGER NOT NULL,  -- 1-5 final difficulty
    category TEXT,                -- 'debut', 'member', 'song', 'award', 'group_fact'

    -- Text question fields
    question_text TEXT,           -- "Which group debuted in 2016 with 'Whistle'?"

    -- Media references (NULL for text questions)
    face_image_id INTEGER REFERENCES face_images(id),
    audio_clip_id INTEGER REFERENCES audio_clips(id),

    -- Answer
    correct_answer TEXT NOT NULL,

    -- Wrong answers generated dynamically at game time
    -- based on same-gender, same-generation, similar-difficulty artists/songs
    -- No need to store them — more replayable this way

    times_shown INTEGER DEFAULT 0,
    times_correct INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

-- ============================================
-- INDEXES
-- ============================================

CREATE INDEX idx_artists_group ON artists(group_id);
CREATE INDEX idx_artists_difficulty ON artists(difficulty);
CREATE INDEX idx_songs_group ON songs(group_id);
CREATE INDEX idx_songs_difficulty ON songs(difficulty);
CREATE INDEX idx_questions_type ON questions(type);
CREATE INDEX idx_questions_difficulty ON questions(difficulty);
CREATE INDEX idx_face_images_artist ON face_images(artist_id);
CREATE INDEX idx_audio_clips_song ON audio_clips(song_id);
```

---

## Content Pipeline

### Phase 1: Artist & Song Roster

**Source:** kprofiles.com, kpop.fandom.com, Wikipedia K-pop lists

Script: `scripts/kpop/scrape_roster.py`
1. Scrape group listings (name, debut year, company, members, status)
2. For each group, scrape member list (stage name, real name, position, birth date)
3. Scrape discography (title tracks + popular B-sides)
4. Pull Spotify monthly listeners via Spotify Web API for popularity scoring
5. Compute difficulty ratings
6. Write to SQLite

**Output:** ~400-500 groups, ~3,000-4,000 artists, ~5,000+ songs

### Phase 2: Face Images

Script: `scripts/kpop/download_faces.py`
1. For each artist, search for promotional/profile photos
2. Download candidate images
3. Run face detection (OpenCV or dlib) to locate face
4. Crop to 3:4 portrait ratio, centered on face
5. Resize to 750x1000 (iPhone-optimized)
6. Convert to JPEG (quality 85, ~50-150KB each)
7. Store as BLOB in face_images table

**Target:** 1-3 images per artist for top 500 artists = ~800-1,500 images
**Estimated size:** ~150MB

### Phase 3: Audio Clips

Script: `scripts/kpop/extract_audio_clips.py`

**Dependencies:** yt-dlp, ffmpeg, demucs, librosa

Per song:
1. Download audio via yt-dlp (from YouTube)
2. Run demucs vocal separation → vocals track + instrumental track
3. Run librosa structural analysis:
   - Self-similarity matrix → find repeating sections (chorus)
   - Energy envelope → find peaks (chorus) and valleys (bridge/instrumental)
   - Vocal energy from demucs output → find instrumental sections
4. Classify sections: chorus, verse, bridge, instrumental, intro, outro
5. Extract 5-second clips from each usable section
6. Encode as MP3 128kbps (~80KB per clip)
7. Store as BLOB with section_type and section_difficulty

**Target:** 2-4 clips per song for top 300 songs = ~600-1,200 clips
**Processing time:** ~30 sec/song (demucs) = ~3-4 hours for 300 songs
**Estimated size:** ~80MB

### Phase 4: Text Question Generation

Script: `scripts/kpop/generate_questions.py`

**Approach:** LLM-generated from structured metadata

Question templates by category:
- **Debut:** "Which group debuted in {year} with '{song}'?"
- **Member:** "Who is the {position} of {group}?"
- **Song:** "Which group released the song '{title}'?"
- **Award:** "Which group won MAMA Artist of the Year in {year}?"
- **Group fact:** "How many members does {group} have?"
- **Solo:** "Which {group} member released the solo song '{title}'?"

1. Feed artist/song metadata to LLM in batches
2. Generate 4-6 questions per group (top groups), 2-3 per smaller groups
3. Difficulty auto-assigned from the group's difficulty rating
4. Validate: no duplicate questions, correct answers verified against data
5. Store in questions table

**Target:** ~2,000 text questions
**Cost:** Minimal — Groq or Sonnet for generation

### Phase 5: Wrong Answer Generation (Runtime)

Wrong answers are NOT stored — generated dynamically at game time for replayability.

Algorithm:
```
For a face question about Artist X (girl group, 4th gen, difficulty 3):
  → Pick 3 wrong answers from: same gender, ±1 generation, ±1 difficulty
  → Ensure no duplicate group (don't show two TWICE members as choices)
  → Shuffle order

For an audio question about Song Y (boy group, 3rd gen):
  → Pick 3 wrong songs from: same gender group, ±1 generation, ±1 difficulty
  → Prefer same-year or similar-style songs for harder choices
```

This means the same question has different wrong answers every time = infinite replayability.

---

## App Architecture

### Frontend (Next.js)
```
/                     → Landing page (create/join room)
/room/[code]          → Game lobby (waiting for players)
/room/[code]/play     → Active game (questions, timer, scoring)
/room/[code]/results  → Round results & leaderboard
/profile              → Player stats & history
```

### Backend
- **Next.js API routes** for REST endpoints
- **Socket.IO** for real-time game state
  - Room creation/joining
  - Turn management
  - Timer sync (server-authoritative)
  - Score updates
  - Player presence

### Key Mobile Safari Considerations
- **Audio:** Use Howler.js — handles Safari's autoplay restrictions (requires user gesture to unlock audio context)
- **No PWA install prompt** on Safari — but can use "Add to Home Screen" with proper manifest
- **Viewport:** Lock to portrait, use `viewport-fit=cover` for notch handling
- **Touch:** All interactions must be touch-friendly (large tap targets, no hover states)

---

## Content Size Estimates

| Content | Count | Avg Size | Total |
|---------|-------|----------|-------|
| Groups | 500 | metadata | ~1MB |
| Artists | 3,500 | metadata | ~2MB |
| Songs | 5,000 | metadata | ~3MB |
| Face images | 1,000 | 120KB | ~120MB |
| Audio clips | 800 | 80KB | ~64MB |
| Text questions | 2,000 | metadata | ~1MB |
| **Total** | | | **~190MB** |

Fits comfortably in a single SQLite file. For the web app, media would be served from the server (not shipped to the client all at once).

---

## Build Order

### Phase 1: Content Database (build locally)
1. Scrape roster → populate groups, artists, songs tables
2. Compute difficulty ratings from Spotify data
3. Download + crop face images
4. Download + analyze + clip audio
5. Generate text questions
6. Validate & QA the database

### Phase 2: App MVP
1. Project scaffold (Next.js + Socket.IO)
2. Single-player mode (no multiplayer yet — just quiz flow)
3. All three question types working
4. Timer + scoring
5. Mobile Safari optimization

### Phase 3: Multiplayer
1. Room creation + join codes
2. Turn-based flow
3. Double down mechanic
4. Difficulty selection
5. Leaderboard + persistent scores

### Phase 4: Polish
1. Animations (card flip for face reveal, waveform for audio)
2. Sound effects
3. Player avatars
4. Stats & history
5. Deploy to Replit

---

## Decisions (Feb 6)

1. **Popularity data:** No Spotify API. Use YouTube view counts (yt-dlp metadata), MelOn chart history, and Wikipedia chart positions as proxies.
2. **Auth:** Username/password. Magic link via SMS or email if easy to add (passwordless login). Persistent cookie — stay logged in indefinitely.
3. **QA:** No review UI. Build the pipeline, spot-check, adjust iteratively.
4. **Priority:** 3rd gen onwards (2012+) first. TWICE, BLACKPINK, BTS, EXO, Red Velvet, GOT7, SEVENTEEN, MAMAMOO → 4th gen → 5th gen. 1st/2nd gen in later waves.
5. **Content licensing:** Fair use for personal/friend quiz app. Reassess if it goes public.
