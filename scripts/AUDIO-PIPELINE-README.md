# Audio Clip Pipeline

## Approach: Deezer Preview API (No Auth Required)

We use Deezer's public search API to fetch 30-second MP3 preview clips for each song.

**Why Deezer over Spotify?**
- **No authentication required** — Deezer's search API is completely public
- Returns direct CDN preview URLs (30-second MP3 clips, 128kbps)
- No rate limit issues at our volume (50 req/5sec allowed)
- Spotify requires OAuth client credentials even for search

## Files

| File | Purpose |
|------|---------|
| `scripts/fetch-audio-previews.py` | Main pipeline — searches Deezer, downloads clips, creates questions |
| `app/public/audio/*.mp3` | Downloaded 30-second preview clips (~480KB each) |
| `app/data/kpop_quiz.db` | `audio_clips` table (BLOBs) + `questions` table (audio type) |

## Running

```bash
cd /home/athena/kpop-quiz
python3 -u scripts/fetch-audio-previews.py
```

**Idempotent** — skips songs that already have audio clips. Safe to re-run after adding new songs.

## Database Schema

### songs table (added columns)
- `deezer_id` — Deezer track ID
- `audio_preview_url` — Original Deezer preview URL (expires, for reference only)
- `audio_file` — Filename in `public/audio/` directory

### audio_clips table
- `song_id` — FK to songs
- `clip` — MP3 BLOB (30-second preview, ~480KB)
- `format` — 'mp3'
- `duration_sec` — 30.0
- `section_type` — 'preview'

### questions table (audio type)
For each song, 2 questions are created:
1. "Which song is this?" → correct_answer = song title
2. "Which group performs this song?" → correct_answer = group name

Both have:
- `type` = 'audio'
- `category` = 'audio_recognition'
- `audio_clip_id` → FK to audio_clips
- `metadata_json` → extra context for wrong answer generation

## Current Stats
- **27 songs** with audio clips (100% coverage)
- **27 MP3 files** on disk (~13MB total)
- **54 audio questions** (2 per song)
- **No credentials needed** — fully public API

## Serving Audio in the App

Audio files are in `public/audio/` and served statically by Next.js:
```
GET /audio/TWICE_Cheer_Up.mp3
```

The game UI can play these using a standard HTML5 `<audio>` element:
```html
<audio src="/audio/TWICE_Cheer_Up.mp3" />
```

Or fetch the clip BLOB from the `audio_clips` table via an API route.

## Adding More Songs

1. Add songs to the `songs` table (with proper `group_id`)
2. Run `python3 -u scripts/fetch-audio-previews.py`
3. It will only process songs without existing audio clips
