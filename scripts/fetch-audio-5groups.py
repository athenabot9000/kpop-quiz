#!/usr/bin/env python3
"""
Fetch Deezer 30-second preview clips for the 5 Quick Quiz groups only.
Based on fetch-audio-previews.py but filtered to: ENHYPEN, TWICE, BLACKPINK, BABYMONSTER, KATSEYE.
"""

import sqlite3
import urllib.request
import urllib.parse
import json
import os
import sys
import time
import re

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'data', 'kpop_quiz.db')
AUDIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'public', 'audio')

DEEZER_SEARCH_URL = "https://api.deezer.com/search"

TARGET_GROUPS = ('ENHYPEN', 'TWICE', 'BLACKPINK', 'BABYMONSTER', 'KATSEYE')


def normalize_title(title):
    t = title.lower().strip()
    t = re.sub(r'\s*\(.*?\)\s*', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def search_deezer(song_title, group_name):
    queries = [
        f"{group_name} {song_title}",
        f"{song_title} {group_name}",
    ]
    
    for query in queries:
        url = f"{DEEZER_SEARCH_URL}?q={urllib.parse.quote(query)}&limit=10"
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'KpopQuizBot/1.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            print(f"  ⚠ API error: {e}", flush=True)
            time.sleep(1)
            continue
        
        if not data.get('data'):
            time.sleep(0.3)
            continue
        
        norm_title = normalize_title(song_title)
        norm_group = group_name.lower().strip()
        
        for track in data['data']:
            track_title = normalize_title(track.get('title', ''))
            artist_name = track.get('artist', {}).get('name', '').lower().strip()
            preview = track.get('preview', '')
            
            if not preview:
                continue
            
            title_match = (
                norm_title == track_title or
                norm_title in track_title or
                track_title in norm_title
            )
            
            artist_match = (
                norm_group in artist_name or
                artist_name in norm_group or
                any(word in artist_name for word in norm_group.split() if len(word) > 2)
            )
            
            if title_match and artist_match:
                return {
                    'deezer_id': track['id'],
                    'title': track['title'],
                    'artist': track['artist']['name'],
                    'album': track.get('album', {}).get('title', ''),
                    'preview_url': preview,
                    'duration': track.get('duration', 0),
                }
        
        time.sleep(0.3)
    
    return None


def download_preview(preview_url, filename):
    filepath = os.path.join(AUDIO_DIR, filename)
    
    if os.path.exists(filepath) and os.path.getsize(filepath) > 10000:
        with open(filepath, 'rb') as f:
            return f.read(), filepath
    
    try:
        req = urllib.request.Request(preview_url, headers={'User-Agent': 'KpopQuizBot/1.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            audio_data = resp.read()
        
        with open(filepath, 'wb') as f:
            f.write(audio_data)
        
        return audio_data, filepath
    except Exception as e:
        print(f"  ✗ Download failed: {e}", flush=True)
        return None, None


def create_audio_questions(db, song_id, audio_clip_id, song_title, group_name, difficulty):
    cursor = db.cursor()
    
    questions = [
        {
            'question_text': 'Which song is this?',
            'correct_answer': song_title,
            'metadata': json.dumps({
                'group_name': group_name,
                'song_id': song_id,
                'answer_type': 'song_title',
            }),
        },
        {
            'question_text': 'Which group performs this song?',
            'correct_answer': group_name,
            'metadata': json.dumps({
                'song_title': song_title,
                'song_id': song_id,
                'answer_type': 'group_name',
            }),
        },
    ]
    
    created = 0
    for q in questions:
        cursor.execute("""
            SELECT id FROM questions 
            WHERE type = 'audio' AND audio_clip_id = ? AND question_text = ?
        """, (audio_clip_id, q['question_text']))
        
        if cursor.fetchone():
            continue
        
        cursor.execute("""
            INSERT INTO questions (type, difficulty, category, question_text, 
                                   audio_clip_id, correct_answer, metadata_json)
            VALUES ('audio', ?, 'audio_recognition', ?, ?, ?, ?)
        """, (difficulty, q['question_text'], audio_clip_id, q['correct_answer'], q['metadata']))
        created += 1
    
    return created


def main():
    os.makedirs(AUDIO_DIR, exist_ok=True)
    
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    cursor = db.cursor()
    
    # Add columns if needed
    for col, typ in [('deezer_id', 'INTEGER'), ('audio_preview_url', 'TEXT'), ('audio_file', 'TEXT')]:
        try:
            cursor.execute(f"ALTER TABLE songs ADD COLUMN {col} {typ}")
        except sqlite3.OperationalError:
            pass
    db.commit()
    
    # Get songs without audio clips — ONLY for the 5 target groups
    placeholders = ','.join('?' * len(TARGET_GROUPS))
    cursor.execute(f"""
        SELECT s.id, s.title, s.korean_title, s.difficulty, g.name as group_name
        FROM songs s 
        JOIN groups g ON s.group_id = g.id
        WHERE g.name IN ({placeholders})
          AND s.id NOT IN (SELECT DISTINCT song_id FROM audio_clips)
        ORDER BY g.name, s.id
    """, TARGET_GROUPS)
    songs = cursor.fetchall()
    
    if not songs:
        print("All songs in target groups already have audio clips!")
        db.close()
        return
    
    print(f"Processing {len(songs)} songs without audio clips across {', '.join(TARGET_GROUPS)}...\n", flush=True)
    
    success = 0
    failed = 0
    questions_created = 0
    
    for song in songs:
        sid = song['id']
        title = song['title']
        group = song['group_name']
        diff = song['difficulty'] or 2
        
        print(f"[{sid}] {group} - {title}", flush=True)
        
        result = search_deezer(title, group)
        
        if not result:
            print(f"  ✗ Not found on Deezer", flush=True)
            failed += 1
            time.sleep(0.5)
            continue
        
        print(f"  → {result['artist']} - {result['title']} (Deezer #{result['deezer_id']})", flush=True)
        
        safe_name = re.sub(r'[^\w\-]', '_', f"{group}_{title}")
        filename = f"{safe_name}.mp3"
        
        audio_data, filepath = download_preview(result['preview_url'], filename)
        
        if not audio_data:
            failed += 1
            continue
        
        print(f"  ✓ Downloaded {len(audio_data)} bytes → {filename}", flush=True)
        
        cursor.execute("""
            INSERT INTO audio_clips (song_id, clip, format, start_sec, duration_sec, section_type, section_difficulty)
            VALUES (?, ?, 'mp3', 0.0, 30.0, 'preview', ?)
        """, (sid, audio_data, diff))
        clip_id = cursor.lastrowid
        
        cursor.execute("""
            UPDATE songs SET deezer_id = ?, audio_preview_url = ?, audio_file = ?
            WHERE id = ?
        """, (result['deezer_id'], result['preview_url'], filename, sid))
        
        qc = create_audio_questions(db, sid, clip_id, title, group, diff)
        questions_created += qc
        
        db.commit()
        success += 1
        time.sleep(0.5)
    
    print(f"\n{'='*50}", flush=True)
    print(f"✓ Audio clips fetched: {success}", flush=True)
    print(f"✗ Failed/not found:    {failed}", flush=True)
    print(f"📝 Questions created:  {questions_created}", flush=True)
    
    # Show per-group stats
    for gname in TARGET_GROUPS:
        cursor.execute("""
            SELECT COUNT(*) FROM audio_clips ac 
            JOIN songs s ON ac.song_id = s.id 
            JOIN groups g ON s.group_id = g.id 
            WHERE g.name = ?
        """, (gname,))
        clip_count = cursor.fetchone()[0]
        cursor.execute("""
            SELECT COUNT(*) FROM songs s JOIN groups g ON s.group_id=g.id WHERE g.name=?
        """, (gname,))
        song_count = cursor.fetchone()[0]
        print(f"  {gname}: {clip_count}/{song_count} songs have clips", flush=True)
    
    db.close()


if __name__ == '__main__':
    main()
