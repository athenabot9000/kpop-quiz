#!/usr/bin/env python3
"""
Generate face recognition questions from scraped member photos.
Inserts questions into the questions table with type='face'.
"""

import os
import sys
import json
import random
import sqlite3

DB_PATH = "/home/athena/kpop-quiz/app/data/kpop_quiz.db"
IMAGES_DIR = "/home/athena/kpop-quiz/app/public/images/members"


def get_artists_with_photos(db):
    """Get all artists that have photos."""
    return db.execute("""
        SELECT a.id, a.stage_name, a.group_id, g.name as group_name, 
               a.photo_path, a.gender, g.generation
        FROM artists a
        JOIN groups g ON a.group_id = g.id
        WHERE a.photo_path IS NOT NULL AND a.photo_path != ''
    """).fetchall()


def get_group_members_with_photos(db, group_id, exclude_artist_id=None):
    """Get other members of the same group with photos."""
    query = """
        SELECT a.id, a.stage_name, g.name as group_name
        FROM artists a
        JOIN groups g ON a.group_id = g.id
        WHERE a.group_id = ? AND a.photo_path IS NOT NULL
    """
    params = [group_id]
    if exclude_artist_id:
        query += " AND a.id != ?"
        params.append(exclude_artist_id)
    return db.execute(query, params).fetchall()


def get_similar_group_members(db, gender, generation, exclude_group_id, exclude_artist_id):
    """Get members from similar groups (same gender/generation) with photos."""
    # Try same generation first
    results = db.execute("""
        SELECT a.id, a.stage_name, g.name as group_name
        FROM artists a
        JOIN groups g ON a.group_id = g.id
        WHERE a.photo_path IS NOT NULL
          AND g.gender = ?
          AND g.id != ?
          AND a.id != ?
        ORDER BY RANDOM()
        LIMIT 20
    """, (gender, exclude_group_id, exclude_artist_id)).fetchall()
    return results


def verify_photo_exists(photo_path):
    """Check if the actual image file exists."""
    full_path = os.path.join("/home/athena/kpop-quiz/app/public", photo_path.lstrip('/'))
    return os.path.exists(full_path)


def generate_questions(db):
    """Generate face recognition questions."""
    artists = get_artists_with_photos(db)
    
    # Filter to only artists whose photos actually exist on disk
    valid_artists = []
    for a in artists:
        aid, sname, gid, gname, photo_path, gender, gen = a
        if verify_photo_exists(photo_path):
            valid_artists.append(a)
        else:
            print(f"  ⚠ Missing file: {photo_path} ({sname})")
    
    print(f"Found {len(valid_artists)} artists with valid photos (out of {len(artists)} in DB)")
    
    # Build lookup structures
    by_group = {}
    by_gender = {}
    all_names = set()
    
    for aid, sname, gid, gname, photo_path, gender, gen in valid_artists:
        by_group.setdefault(gid, []).append((aid, sname, gname))
        by_gender.setdefault(gender or 'unknown', []).append((aid, sname, gname, gid))
        all_names.add(sname)
    
    # Only generate questions for groups with 3+ members with photos
    # (so we can generate meaningful wrong answers from the same group)
    eligible_groups = {gid: members for gid, members in by_group.items() if len(members) >= 3}
    
    questions = []
    
    for aid, sname, gid, gname, photo_path, gender, gen in valid_artists:
        if gid not in eligible_groups:
            continue
        
        # Strategy 1: "Who is this member of [GROUP]?"
        # Wrong answers from same group
        same_group = [m for m in eligible_groups[gid] if m[0] != aid]
        if len(same_group) >= 3:
            wrong = random.sample(same_group, 3)
            wrong_answers = [w[1] for w in wrong]
        elif len(same_group) >= 1:
            wrong_answers = [w[1] for w in same_group]
            # Fill remaining with members from similar groups
            similar = by_gender.get(gender or 'unknown', [])
            similar = [s for s in similar if s[0] != aid and s[3] != gid and s[1] not in wrong_answers]
            random.shuffle(similar)
            for s in similar:
                if len(wrong_answers) >= 3:
                    break
                wrong_answers.append(s[1])
        else:
            continue
        
        if len(wrong_answers) < 3:
            continue
        
        wrong_answers = wrong_answers[:3]
        
        q = {
            'type': 'face',
            'difficulty': 1 if len(eligible_groups[gid]) <= 5 else 2,
            'category': 'face_recognition',
            'question_text': f"Who is this member of {gname}?",
            'correct_answer': sname,
            'metadata_json': json.dumps({
                'artist_id': aid,
                'group_id': gid,
                'group_name': gname,
                'photo_path': photo_path,
                'wrong_answers': wrong_answers,
                'options_pool': 'same_group'
            })
        }
        questions.append(q)
    
    # Strategy 2: For very popular groups, also generate harder questions
    # "Who is this K-pop idol?" (wrong answers from different groups of same gender)
    popular_threshold = 5  # Groups with 5+ members with photos
    popular_groups = {gid for gid, members in eligible_groups.items() if len(members) >= popular_threshold}
    
    for aid, sname, gid, gname, photo_path, gender, gen in valid_artists:
        if gid not in popular_groups:
            continue
        
        # Get wrong answers from different groups of same gender
        similar = by_gender.get(gender or 'unknown', [])
        candidates = [s for s in similar if s[0] != aid and s[3] != gid]
        
        if len(candidates) < 3:
            continue
        
        wrong = random.sample(candidates, 3)
        wrong_answers = [w[1] for w in wrong]
        
        q = {
            'type': 'face',
            'difficulty': 3,
            'category': 'face_recognition',
            'question_text': f"Who is this K-pop idol?",
            'correct_answer': sname,
            'metadata_json': json.dumps({
                'artist_id': aid,
                'group_id': gid,
                'group_name': gname,
                'photo_path': photo_path,
                'wrong_answers': wrong_answers,
                'options_pool': 'cross_group'
            })
        }
        questions.append(q)
    
    return questions


def insert_questions(db, questions):
    """Insert generated questions into the database."""
    # First, remove old face questions
    deleted = db.execute("DELETE FROM questions WHERE type = 'face'").rowcount
    if deleted:
        print(f"Removed {deleted} old face questions")
    
    inserted = 0
    for q in questions:
        try:
            db.execute("""
                INSERT INTO questions (type, difficulty, category, question_text, 
                                       correct_answer, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                q['type'], q['difficulty'], q['category'],
                q['question_text'], q['correct_answer'], q['metadata_json']
            ))
            inserted += 1
        except sqlite3.IntegrityError as e:
            print(f"  ⚠ Duplicate: {e}")
    
    db.commit()
    return inserted


def main():
    db = sqlite3.connect(DB_PATH)
    
    print("Generating face recognition questions...\n")
    
    questions = generate_questions(db)
    print(f"\nGenerated {len(questions)} questions total")
    
    # Count by difficulty
    by_diff = {}
    for q in questions:
        d = q['difficulty']
        by_diff[d] = by_diff.get(d, 0) + 1
    for d in sorted(by_diff):
        print(f"  Difficulty {d}: {by_diff[d]} questions")
    
    # Count by type
    by_pool = {}
    for q in questions:
        meta = json.loads(q['metadata_json'])
        pool = meta.get('options_pool', 'unknown')
        by_pool[pool] = by_pool.get(pool, 0) + 1
    for pool, count in sorted(by_pool.items()):
        print(f"  Pool '{pool}': {count} questions")
    
    # Insert
    print()
    inserted = insert_questions(db, questions)
    
    # Final summary
    total_questions = db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    face_questions = db.execute("SELECT COUNT(*) FROM questions WHERE type = 'face'").fetchone()[0]
    text_questions = db.execute("SELECT COUNT(*) FROM questions WHERE type = 'text'").fetchone()[0]
    
    print(f"\n{'='*50}")
    print(f"QUESTION GENERATION COMPLETE")
    print(f"{'='*50}")
    print(f"Face questions inserted: {inserted}")
    print(f"Total questions in DB: {total_questions}")
    print(f"  - Text questions: {text_questions}")
    print(f"  - Face questions: {face_questions}")
    
    # Show sample questions
    print(f"\nSample questions:")
    samples = db.execute("""
        SELECT question_text, correct_answer, metadata_json 
        FROM questions WHERE type = 'face' 
        ORDER BY RANDOM() LIMIT 5
    """).fetchall()
    for qt, ca, mj in samples:
        meta = json.loads(mj)
        wrong = meta.get('wrong_answers', [])
        photo = meta.get('photo_path', '')
        print(f"  Q: {qt}")
        print(f"  A: {ca} | Wrong: {', '.join(wrong)} | Photo: {photo}")
        print()
    
    db.close()


if __name__ == "__main__":
    main()
