#!/usr/bin/env python3
"""
Comprehensive audit and fix script for K-Pop Quiz question database.
Fixes:
1. song_album questions with bad correct answers (em-dash, numbers, KOR/JPN, Released:, etc.)
2. song_not questions with nonsensical real_songs or NOT-answers (dates, awards, albums)
3. group_song questions with non-song answers (tours, concerts, dates, albums, KOR, awards)
4. song_group questions where answer is leaked in question text
5. song_group questions about non-songs (tours, concerts, DVDs, dates, awards)
6. song_year questions about non-songs or with answer leaked
7. Wrong answers containing invalid data (KOR, numbers, dates, etc.)
8. Adds BTS to Quick Quiz groups
"""

import sqlite3
import json
import re
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'kpop_quiz.db')

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def is_bad_album_answer(answer):
    """Check if a song_album correct_answer is nonsensical"""
    if not answer or answer.strip() in ('—', '-', ''):
        return True
    # Pure numbers (like "7", "88", etc.) - not real album names
    if re.match(r'^\d+$', answer.strip()):
        return True
    # KOR/JPN sales data
    if re.match(r'^(KOR|JPN)', answer.strip()):
        return True
    # Wikipedia metadata
    if answer.startswith('Released:'):
        return True
    if answer.startswith('Original song'):
        return True
    # USSales
    if 'USSales' in answer:
        return True
    return False

def is_bad_wrong_answer(answer):
    """Check if a wrong_answer option is nonsensical"""
    if not answer or answer.strip() in ('—', '-', '', '—N/a'):
        return True
    # Pure numbers
    if re.match(r'^\d+$', answer.strip()):
        return True
    # KOR/JPN sales data
    if re.match(r'^(KOR|JPN)', answer.strip()):
        return True
    # Wikipedia metadata
    if answer.startswith('Released:'):
        return True
    if answer.startswith('Original song'):
        return True
    if 'USSales' in answer:
        return True
    return False

def is_non_song(text):
    """Check if text is not actually a song title (it's a tour, concert, album, date, award, etc.)"""
    patterns = [
        r'Tour', r'Concert', r'DVD', r'Blu-ray', r'Super Show', r'Fantasia',
        r'Fan ?meeting', r'Fan ?meet', r'Award', r'Showcase', r'KCON',
        r'Live in', r'World Tour', r'in Seoul', r'in Japan', r'in Korea',
        r'Compilation', r'First Japan Tour', r'in Las Vegas',
        r'^\d{4}$',  # just a year
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d',
        r'Released:',
    ]
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False

def is_date_string(text):
    """Check if text looks like a date (e.g., 'August 17, 2024', 'July 6, 2024')"""
    return bool(re.match(
        r'^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d',
        text, re.IGNORECASE
    ))

def audit_and_fix():
    conn = connect()
    cur = conn.cursor()
    
    deleted_ids = []
    updated = 0
    
    # ─────────────────────────────────────────────
    # 1. Delete song_album questions with bad correct answers
    # ─────────────────────────────────────────────
    rows = cur.execute("SELECT id, correct_answer FROM questions WHERE category='song_album'").fetchall()
    bad_album_ids = []
    for r in rows:
        if is_bad_album_answer(r['correct_answer']):
            bad_album_ids.append(r['id'])
    
    if bad_album_ids:
        placeholders = ','.join('?' * len(bad_album_ids))
        cur.execute(f"DELETE FROM questions WHERE id IN ({placeholders})", bad_album_ids)
        deleted_ids.extend(bad_album_ids)
        print(f"[song_album] Deleted {len(bad_album_ids)} questions with bad correct answers")
    
    # Clean wrong_answers in remaining song_album questions
    rows = cur.execute("SELECT id, metadata_json FROM questions WHERE category='song_album'").fetchall()
    for r in rows:
        if not r['metadata_json']:
            continue
        try:
            meta = json.loads(r['metadata_json'])
        except:
            continue
        if 'wrong_answers' not in meta:
            continue
        original = meta['wrong_answers']
        cleaned = [a for a in original if not is_bad_wrong_answer(a)]
        if len(cleaned) < len(original):
            meta['wrong_answers'] = cleaned
            cur.execute("UPDATE questions SET metadata_json=? WHERE id=?", 
                       (json.dumps(meta, ensure_ascii=False), r['id']))
            updated += 1
    print(f"[song_album] Cleaned wrong_answers in {updated} remaining questions")
    
    # ─────────────────────────────────────────────
    # 2. Delete/fix song_not questions with bad data
    # ─────────────────────────────────────────────
    rows = cur.execute("SELECT id, question_text, correct_answer, metadata_json FROM questions WHERE category='song_not'").fetchall()
    bad_not_ids = []
    for r in rows:
        is_bad = False
        # Bad NOT-answer (the correct answer that's supposed to be from another group)
        if is_non_song(r['correct_answer']) or is_date_string(r['correct_answer']):
            is_bad = True
        
        # Bad real_songs (the wrong answers that should be actual songs)
        if r['metadata_json']:
            try:
                meta = json.loads(r['metadata_json'])
                real_songs = meta.get('real_songs', []) or meta.get('wrong_answers', [])
                bad_songs = [s for s in real_songs if is_non_song(s) or is_date_string(s)]
                if len(bad_songs) > 0:
                    is_bad = True
            except:
                pass
        
        if is_bad:
            bad_not_ids.append(r['id'])
    
    if bad_not_ids:
        placeholders = ','.join('?' * len(bad_not_ids))
        cur.execute(f"DELETE FROM questions WHERE id IN ({placeholders})", bad_not_ids)
        deleted_ids.extend(bad_not_ids)
        print(f"[song_not] Deleted {len(bad_not_ids)} questions with bad data")
    
    # ─────────────────────────────────────────────
    # 3. Delete group_song questions with bad answers
    # ─────────────────────────────────────────────
    rows = cur.execute("SELECT id, question_text, correct_answer FROM questions WHERE category='group_song'").fetchall()
    bad_gs_ids = []
    for r in rows:
        answer = r['correct_answer']
        # Non-songs as answers
        if is_non_song(answer) or is_date_string(answer):
            bad_gs_ids.append(r['id'])
        # KOR/JPN as answer
        elif answer.strip() in ('KOR', 'JPN'):
            bad_gs_ids.append(r['id'])
        # Album names as songs (contains "Chapter", "EP.", etc.)
        elif re.search(r'(Chapter|EP\.|Album)', answer) and ':' in answer:
            bad_gs_ids.append(r['id'])
        # "&" by itself
        elif answer.strip() == '&':
            bad_gs_ids.append(r['id'])
    
    if bad_gs_ids:
        placeholders = ','.join('?' * len(bad_gs_ids))
        cur.execute(f"DELETE FROM questions WHERE id IN ({placeholders})", bad_gs_ids)
        deleted_ids.extend(bad_gs_ids)
        print(f"[group_song] Deleted {len(bad_gs_ids)} questions with bad answers")
    
    # Clean wrong_answers in remaining group_song questions (remove KOR, etc.)
    cnt = 0
    rows = cur.execute("SELECT id, metadata_json FROM questions WHERE category='group_song'").fetchall()
    for r in rows:
        if not r['metadata_json']:
            continue
        try:
            meta = json.loads(r['metadata_json'])
        except:
            continue
        if 'wrong_answers' not in meta:
            continue
        original = meta['wrong_answers']
        cleaned = [a for a in original if a.strip() not in ('KOR', 'JPN', '—', '-', '') 
                   and not re.match(r'^\d+$', a.strip())
                   and not is_non_song(a)
                   and not is_date_string(a)]
        if len(cleaned) < len(original):
            meta['wrong_answers'] = cleaned
            cur.execute("UPDATE questions SET metadata_json=? WHERE id=?",
                       (json.dumps(meta, ensure_ascii=False), r['id']))
            cnt += 1
    print(f"[group_song] Cleaned wrong_answers in {cnt} remaining questions")
    
    # ─────────────────────────────────────────────
    # 4. Delete song_group questions about non-songs 
    # ─────────────────────────────────────────────
    rows = cur.execute("SELECT id, question_text, correct_answer FROM questions WHERE category='song_group'").fetchall()
    bad_sg_ids = []
    for r in rows:
        qt = r['question_text'] or ''
        ca = r['correct_answer'] or ''
        
        # Extract the "song" title from the question text
        match = re.search(r'"([^"]+)"', qt)
        if match:
            song_title = match.group(1)
            if is_non_song(song_title) or is_date_string(song_title):
                bad_sg_ids.append(r['id'])
                continue
        
        # Answer leaked in question text (group name appears in song title or question)
        if len(ca) > 2 and ca.upper() in qt.upper():
            # But allow cases where the group name is just part of a longer word
            # Check if it's a standalone match
            pattern = re.compile(r'\b' + re.escape(ca) + r'\b', re.IGNORECASE)
            if pattern.search(qt):
                bad_sg_ids.append(r['id'])
                continue
    
    if bad_sg_ids:
        placeholders = ','.join('?' * len(bad_sg_ids))
        cur.execute(f"DELETE FROM questions WHERE id IN ({placeholders})", bad_sg_ids)
        deleted_ids.extend(bad_sg_ids)
        print(f"[song_group] Deleted {len(bad_sg_ids)} questions (non-songs + answer leaks)")
    
    # ─────────────────────────────────────────────
    # 5. Delete song_year questions about non-songs or with leaked answers
    # ─────────────────────────────────────────────
    rows = cur.execute("SELECT id, question_text, correct_answer FROM questions WHERE category='song_year'").fetchall()
    bad_sy_ids = []
    for r in rows:
        qt = r['question_text'] or ''
        ca = r['correct_answer'] or ''
        
        # Extract the "song" title
        match = re.search(r'"([^"]+)"', qt)
        if match:
            song_title = match.group(1)
            if is_non_song(song_title) or is_date_string(song_title):
                bad_sy_ids.append(r['id'])
                continue
        
        # Year appears in song title (leaked answer)
        if ca and ca in qt:
            # Check if the year appears in what looks like a date in the "song" title
            if match:
                song_title = match.group(1)
                if ca in song_title:
                    bad_sy_ids.append(r['id'])
                    continue
    
    if bad_sy_ids:
        placeholders = ','.join('?' * len(bad_sy_ids))
        cur.execute(f"DELETE FROM questions WHERE id IN ({placeholders})", bad_sy_ids)
        deleted_ids.extend(bad_sy_ids)
        print(f"[song_year] Deleted {len(bad_sy_ids)} questions (non-songs + answer leaks)")
    
    # ─────────────────────────────────────────────
    # 6. Clean wrong_answers containing "KOR" in song_group and song_year
    # ─────────────────────────────────────────────
    cnt = 0
    for cat in ('song_group', 'song_year'):
        rows = cur.execute(f"SELECT id, metadata_json FROM questions WHERE category=?", (cat,)).fetchall()
        for r in rows:
            if not r['metadata_json']:
                continue
            try:
                meta = json.loads(r['metadata_json'])
            except:
                continue
            if 'wrong_answers' not in meta:
                continue
            original = meta['wrong_answers']
            cleaned = [a for a in original if a and a.strip() not in ('KOR', 'JPN', '—', '-', '')
                       and not re.match(r'^\d+$', a.strip())
                       and not a.startswith('Released:')]
            if len(cleaned) < len(original):
                meta['wrong_answers'] = cleaned
                cur.execute("UPDATE questions SET metadata_json=? WHERE id=?",
                           (json.dumps(meta, ensure_ascii=False), r['id']))
                cnt += 1
    print(f"[song_group/song_year] Cleaned wrong_answers in {cnt} questions")
    
    conn.commit()
    
    # ─────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────
    print(f"\n=== TOTAL: Deleted {len(deleted_ids)} bad questions ===")
    
    # Post-fix counts
    rows = cur.execute("SELECT category, COUNT(*) as cnt FROM questions GROUP BY category ORDER BY category").fetchall()
    print("\nPost-fix question counts:")
    total = 0
    for r in rows:
        print(f"  {r['category']}: {r['cnt']}")
        total += r['cnt']
    print(f"  TOTAL: {total}")
    
    conn.close()

def add_bts_questions():
    """Add BTS as a Quick Quiz group with proper questions"""
    conn = connect()
    cur = conn.cursor()
    
    # Check if BTS group exists
    bts = cur.execute("SELECT id FROM groups WHERE name LIKE '%BTS%'").fetchone()
    if not bts:
        print("[BTS] BTS group not found in database!")
        conn.close()
        return
    
    bts_id = bts['id']
    print(f"[BTS] Found BTS group_id={bts_id}")
    
    # Check existing BTS questions
    existing = cur.execute("""
        SELECT COUNT(*) as cnt FROM questions WHERE 
        question_text LIKE '%BTS%' OR correct_answer LIKE '%BTS%'
    """).fetchone()['cnt']
    print(f"[BTS] Already {existing} questions mentioning BTS")
    
    # Check BTS songs in the songs table
    bts_songs = cur.execute("""
        SELECT s.id, s.title, s.album, s.year FROM songs s 
        WHERE s.group_id=? ORDER BY s.year, s.title
    """, (bts_id,)).fetchall()
    print(f"[BTS] {len(bts_songs)} songs in songs table")
    
    # Check BTS members in the artists table
    bts_members = cur.execute("""
        SELECT id, stage_name, real_name FROM artists WHERE group_id=?
    """, (bts_id,)).fetchall()
    print(f"[BTS] {len(bts_members)} members in artists table")
    for m in bts_members:
        print(f"  - {m['stage_name']} ({m['real_name']})")
    
    # Get BTS group details
    bts_group = cur.execute("SELECT * FROM groups WHERE id=?", (bts_id,)).fetchone()
    
    # We won't add duplicate questions — check what we already have
    # The existing data has audio, text/group_song, text/song_not questions for BTS
    # Let's add some text questions specifically tagged for quick quiz
    
    # Key BTS songs for questions (only well-known title tracks)
    key_songs = [
        ("Dynamite", 2020, "BE"),
        ("Butter", 2021, "Butter"),
        ("Boy with Luv", 2019, "Map of the Soul: Persona"),
        ("IDOL", 2018, "Love Yourself: Answer"),
        ("DNA", 2017, "Love Yourself: Her"),
        ("Spring Day", 2017, "You Never Walk Alone"),
        ("Blood Sweat & Tears", 2016, "Wings"),
        ("Fire", 2016, "The Most Beautiful Moment in Life: Young Forever"),
        ("Permission to Dance", 2021, "Butter"),
        ("Fake Love", 2018, "Love Yourself: Tear"),
        ("MIC Drop", 2017, "Love Yourself: Her"),
        ("ON", 2020, "Map of the Soul: 7"),
        ("Black Swan", 2020, "Map of the Soul: 7"),
        ("Life Goes On", 2020, "BE"),
        ("No More Dream", 2013, "2 Cool 4 Skool"),
        ("Boy In Luv", 2014, "Skool Luv Affair"),
        ("I Need U", 2015, "The Most Beautiful Moment in Life, Part 1"),
        ("Dope", 2015, "The Most Beautiful Moment in Life, Part 1"),
        ("Run", 2015, "The Most Beautiful Moment in Life, Part 2"),
        ("Save Me", 2016, "The Most Beautiful Moment in Life: Young Forever"),
        ("Not Today", 2017, "You Never Walk Alone"),
        ("Go Go", 2017, "Love Yourself: Her"),
        ("Euphoria", 2018, "Love Yourself: Answer"),
        ("Epiphany", 2018, "Love Yourself: Answer"),
        ("Singularity", 2018, "Love Yourself: Tear"),
        ("My Universe", 2021, "My Universe"),
        ("Danger", 2014, "Dark & Wild"),
        ("War of Hormone", 2014, "Dark & Wild"),
        ("Just One Day", 2014, "Skool Luv Affair"),
        ("Mic Drop (Steve Aoki Remix)", 2017, "Love Yourself: Her"),
    ]
    
    # BTS members for member questions
    members = {
        "RM": "Kim Nam-joon",
        "Jin": "Kim Seok-jin",
        "Suga": "Min Yoon-gi",
        "J-Hope": "Jung Ho-seok",
        "Jimin": "Park Ji-min",
        "V": "Kim Tae-hyung",
        "Jungkook": "Jeon Jung-kook"
    }
    
    # Other groups for wrong answers
    other_groups = ["SEVENTEEN", "EXO", "Stray Kids", "ATEEZ", "NCT", "MONSTA X", "GOT7", "ENHYPEN", "TXT", "BLACKPINK", "TWICE", "aespa", "Red Velvet"]
    
    # Other group songs for wrong answers  
    other_songs = {
        "SEVENTEEN": ["Don't Wanna Cry", "HOT", "Super", "Very Nice"],
        "EXO": ["Love Shot", "Ko Ko Bop", "Growl", "Monster"],
        "Stray Kids": ["God's Menu", "Back Door", "Thunderous", "MANIAC"],
        "ATEEZ": ["Guerrilla", "Say My Name", "Wonderland", "Hala Hala"],
        "TWICE": ["Feel Special", "TT", "Fancy", "Like Ooh-Ahh"],
        "BLACKPINK": ["DDU-DU DDU-DU", "Kill This Love", "How You Like That", "Pink Venom"],
        "ENHYPEN": ["Drunk-Dazed", "Given-Taken", "Bite Me", "XO (Only If You Say Yes)"],
        "TXT": ["0x1=Lovesong", "Sugar Rush Ride", "Crown", "Blue Hour"],
    }
    
    # BTS albums for wrong answers in album questions
    bts_albums = [
        "2 Cool 4 Skool", "O!RUL8,2?", "Skool Luv Affair", "Dark & Wild",
        "The Most Beautiful Moment in Life, Part 1", "The Most Beautiful Moment in Life, Part 2",
        "The Most Beautiful Moment in Life: Young Forever", "Wings", "You Never Walk Alone",
        "Love Yourself: Her", "Love Yourself: Tear", "Love Yourself: Answer",
        "Map of the Soul: Persona", "Map of the Soul: 7", "BE", "Proof"
    ]
    
    new_questions = []
    
    # Add song_album questions for BTS
    for title, year, album in key_songs[:15]:
        wrong = [a for a in bts_albums if a != album][:15]
        if len(wrong) >= 3:
            meta = {
                "correct_album": album,
                "options_pool": "albums",
                "wrong_answers": wrong
            }
            new_questions.append((
                'text', 3, 'song_album',
                f'Which album features the song "{title}" by BTS?',
                album,
                json.dumps(meta, ensure_ascii=False)
            ))
    
    # Add group_song questions (which song is by BTS?)
    import random
    for title, year, album in key_songs[:10]:
        # Pick wrong answers from other groups' songs
        wrong = []
        groups_used = random.sample(list(other_songs.keys()), min(6, len(other_songs)))
        for g in groups_used:
            wrong.append(random.choice(other_songs[g]))
        wrong = wrong[:15]
        
        meta = {
            "correct_group_id": bts_id,
            "options_pool": "songs_mixed",
            "wrong_answers": wrong
        }
        new_questions.append((
            'text', 1, 'group_song',
            f'Which of these songs is by BTS?',
            title,
            json.dumps(meta, ensure_ascii=False)
        ))
    
    # Add song_group questions (which group released this BTS song?)
    for title, year, album in key_songs[:15]:
        wrong = random.sample(other_groups, min(15, len(other_groups)))
        meta = {
            "correct_group_id": bts_id,
            "options_pool": "groups",
            "wrong_answers": wrong
        }
        new_questions.append((
            'text', 1, 'song_group',
            f'Which group released the song "{title}"?',
            'BTS (Bangtan Boys)',
            json.dumps(meta, ensure_ascii=False)
        ))
    
    # Add song_year questions
    for title, year, album in key_songs[:15]:
        wrong = [str(y) for y in range(2013, 2025) if y != year]
        random.shuffle(wrong)
        meta = {
            "correct_year": year,
            "options_pool": "years",
            "wrong_answers": wrong[:15]
        }
        new_questions.append((
            'text', 2, 'song_year',
            f'What year was "{title}" by BTS released?',
            str(year),
            json.dumps(meta, ensure_ascii=False)
        ))
    
    # Add song_not questions (which is NOT a BTS song?)
    non_bts_songs = [
        ("DDU-DU DDU-DU", "BLACKPINK"),
        ("Feel Special", "TWICE"),
        ("God's Menu", "Stray Kids"),
        ("Next Level", "aespa"),
        ("Love Shot", "EXO"),
        ("Don't Wanna Cry", "SEVENTEEN"),
        ("Drunk-Dazed", "ENHYPEN"),
        ("MANIAC", "Stray Kids"),
        ("Guerrilla", "ATEEZ"),
        ("Crown", "TXT"),
    ]
    
    bts_real_songs_sets = [
        ["Dynamite", "Butter", "Spring Day"],
        ["DNA", "Fire", "Blood Sweat & Tears"],
        ["Boy with Luv", "IDOL", "Fake Love"],
        ["Permission to Dance", "ON", "MIC Drop"],
        ["I Need U", "Dope", "Run"],
    ]
    
    for i, (not_song, not_group) in enumerate(non_bts_songs[:5]):
        real_songs = bts_real_songs_sets[i]
        meta = {
            "correct_answer_is_not": True,
            "real_songs": real_songs,
            "options_pool": "songs",
            "wrong_answers": real_songs
        }
        new_questions.append((
            'text', 2, 'song_not',
            'Which of these is NOT a BTS song?',
            not_song,
            json.dumps(meta, ensure_ascii=False)
        ))
    
    # Insert all new questions
    for q in new_questions:
        cur.execute("""
            INSERT INTO questions (type, difficulty, category, question_text, correct_answer, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, q)
    
    print(f"[BTS] Added {len(new_questions)} new BTS questions")
    
    conn.commit()
    conn.close()

def update_quick_quiz_config():
    """Update the quick quiz group config to include BTS"""
    engine_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'lib', 'game-engine.js')
    
    with open(engine_path, 'r') as f:
        content = f.read()
    
    # Current: names: ['ENHYPEN', 'TWICE', 'BABYMONSTER', 'Baby Monster', 'BLACKPINK', 'KATSEYE', 'Katseye'],
    # Add BTS variants
    old_names = "names: ['ENHYPEN', 'TWICE', 'BABYMONSTER', 'Baby Monster', 'BLACKPINK', 'KATSEYE', 'Katseye'],"
    new_names = "names: ['ENHYPEN', 'TWICE', 'BABYMONSTER', 'Baby Monster', 'BLACKPINK', 'KATSEYE', 'Katseye', 'BTS', 'BTS (Bangtan Boys)'],"
    
    if old_names in content:
        content = content.replace(old_names, new_names)
        print("[Quick Quiz] Added BTS to QUICK_QUIZ_GROUPS names")
    else:
        print("[Quick Quiz] WARNING: Could not find expected names string to update")
        print("  Searching for alternative...")
        # Try to find it more flexibly
        import re
        match = re.search(r"names:\s*\[([^\]]+)\]", content)
        if match:
            print(f"  Found: names: [{match.group(1)}]")
    
    # Current: ids: [59, 208, 275], // ENHYPEN=59, BLACKPINK=208, TWICE=275 
    old_ids = "ids: [59, 208, 275], // ENHYPEN=59, BLACKPINK=208, TWICE=275 (BABYMONSTER + KATSEYE added dynamically)"
    
    # Get BTS group_id
    conn = connect()
    bts = conn.execute("SELECT id FROM groups WHERE name LIKE '%BTS%'").fetchone()
    conn.close()
    
    if bts:
        bts_id = bts['id']
        new_ids = f"ids: [59, 208, 275, {bts_id}], // ENHYPEN=59, BLACKPINK=208, TWICE=275, BTS={bts_id} (BABYMONSTER + KATSEYE added dynamically)"
        if old_ids in content:
            content = content.replace(old_ids, new_ids)
            print(f"[Quick Quiz] Added BTS (id={bts_id}) to QUICK_QUIZ_GROUPS ids")
        else:
            print("[Quick Quiz] WARNING: Could not find expected ids string to update")
    
    with open(engine_path, 'w') as f:
        f.write(content)
    
    print("[Quick Quiz] game-engine.js updated")

if __name__ == '__main__':
    print("=== K-Pop Quiz Question Audit & Fix ===\n")
    
    print("--- Phase 1: Audit & Fix Bad Questions ---")
    audit_and_fix()
    
    print("\n--- Phase 2: Add BTS Questions ---")
    add_bts_questions()
    
    print("\n--- Phase 3: Update Quick Quiz Config ---")
    update_quick_quiz_config()
    
    print("\n=== Done! ===")
