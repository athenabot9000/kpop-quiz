#!/usr/bin/env python3
"""
Fetch member photos for BABYMONSTER and KATSEYE from Deezer artist images.
Stores photos as files and in face_images table for face quiz questions.
"""

import sqlite3
import urllib.request
import urllib.parse
import json
import os
import sys
import time

sys.stdout.reconfigure(line_buffering=True)

DB_PATH = "/home/athena/kpop-quiz/app/data/kpop_quiz.db"
IMAGES_DIR = "/home/athena/kpop-quiz/app/public/images/members"
os.makedirs(IMAGES_DIR, exist_ok=True)

HEADERS = {'User-Agent': 'KpopQuizBot/1.0'}

TARGET_GROUPS = ('BABYMONSTER', 'KATSEYE')

# Manual Deezer artist IDs for reliable matching
DEEZER_ARTIST_IDS = {
    # BABYMONSTER members - search by "BABYMONSTER member_name"
    # KATSEYE members
}

# Backup: Wikipedia/Wikimedia commons URLs for member photos
# We'll use Deezer's public API to search for group images first,
# then try kprofiles for individual member photos

KPROFILES_URLS = {
    'BABYMONSTER': 'https://kprofiles.com/babymonster-members-profile/',
    'KATSEYE': 'https://kprofiles.com/katseye-members-profile/',
}


def search_deezer_artist(name, group_name):
    """Search Deezer for an artist and return their image URL."""
    queries = [
        f"{name} {group_name}",
        f"{group_name} {name}",
    ]
    for query in queries:
        url = f"https://api.deezer.com/search/artist?q={urllib.parse.quote(query)}&limit=5"
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            print(f"  ⚠ Deezer error: {e}")
            time.sleep(1)
            continue
        
        for artist in data.get('data', []):
            artist_name = artist.get('name', '').lower()
            picture = artist.get('picture_xl') or artist.get('picture_big') or artist.get('picture_medium')
            if not picture:
                continue
            # Check if this is the right group/member
            if group_name.lower() in artist_name or name.lower() in artist_name:
                return picture
        time.sleep(0.3)
    return None


def download_image(url, filepath):
    """Download an image from URL to filepath."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        if len(data) < 1000:
            return None
        with open(filepath, 'wb') as f:
            f.write(data)
        return data
    except Exception as e:
        print(f"  ✗ Download failed: {e}")
        return None


def fetch_kprofiles_photos(group_name, members, session=None):
    """Try to fetch individual member photos from kprofiles."""
    import re
    
    url = KPROFILES_URLS.get(group_name)
    if not url:
        return {}
    
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,*/*',
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"  ⚠ kprofiles fetch failed: {e}")
        return {}
    
    # Parse out image URLs that contain member names in alt text
    results = {}
    member_names = {m['stage_name'].lower(): m for m in members}
    
    # Find all img tags with kprofiles uploads
    img_pattern = re.compile(
        r'<img[^>]*?(?:src|data-src|data-lazy-src)=["\']([^"\']*kprofiles\.com/wp-content/uploads[^"\']*)["\'][^>]*?(?:alt=["\']([^"\']*)["\'])?',
        re.IGNORECASE
    )
    # Also try alt before src
    img_pattern2 = re.compile(
        r'<img[^>]*?alt=["\']([^"\']*)["\'][^>]*?(?:src|data-src|data-lazy-src)=["\']([^"\']*kprofiles\.com/wp-content/uploads[^"\']*)["\']',
        re.IGNORECASE
    )
    
    all_images = []
    for match in img_pattern.finditer(html):
        img_url = match.group(1)
        alt = match.group(2) or ''
        all_images.append((img_url, alt))
    for match in img_pattern2.finditer(html):
        alt = match.group(1)
        img_url = match.group(2)
        if (img_url, alt) not in all_images:
            all_images.append((img_url, alt))
    
    print(f"  Found {len(all_images)} kprofiles images for {group_name}")
    
    matched = set()
    for img_url, alt in all_images:
        alt_lower = alt.lower().strip()
        # Skip tiny images, logos, etc.
        if any(skip in img_url.lower() for skip in ['logo', 'banner', 'herald', '1x1']):
            continue
        
        for name_lower, member in member_names.items():
            if name_lower in matched:
                continue
            # Check if member name appears in alt text
            if name_lower in alt_lower or alt_lower.startswith(name_lower.split()[0]):
                results[member['id']] = img_url
                matched.add(name_lower)
                print(f"    Matched {member['stage_name']} via alt='{alt}'")
                break
    
    # If we didn't match everyone, try positional matching
    # Filter to likely member photos (skip first group photo)
    if len(matched) < len(members):
        # Get images that look like profile photos (typically uploaded same year)
        profile_images = [(url, alt) for url, alt in all_images 
                         if 'logo' not in url.lower() and 'banner' not in url.lower()
                         and any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp'])]
        
        # Skip first image (usually group photo), try to match remaining
        if len(profile_images) > len(members):
            # Try starting from index 1
            remaining_members = [m for m in members if m['stage_name'].lower() not in matched]
            candidate_images = [img for img in profile_images[1:] if img[0] not in [results.get(m['id']) for m in members]]
            
            if len(candidate_images) >= len(remaining_members):
                print(f"  Trying positional matching for {len(remaining_members)} remaining members")
                for i, member in enumerate(remaining_members):
                    if i < len(candidate_images):
                        results[member['id']] = candidate_images[i][0]
                        print(f"    Positional match: {member['stage_name']} → image {i+1}")
    
    return results


def main():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    cursor = db.cursor()
    
    # Ensure photo_path column exists
    try:
        cursor.execute("ALTER TABLE artists ADD COLUMN photo_path TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE artists ADD COLUMN image_url TEXT")
    except sqlite3.OperationalError:
        pass
    db.commit()
    
    for group_name in TARGET_GROUPS:
        print(f"\n{'='*50}")
        print(f"Processing {group_name}")
        print(f"{'='*50}")
        
        # Get members
        cursor.execute("""
            SELECT a.id, a.stage_name, a.photo_path
            FROM artists a JOIN groups g ON a.group_id = g.id
            WHERE g.name = ?
        """, (group_name,))
        members = [dict(row) for row in cursor.fetchall()]
        
        # Check which members need photos
        need_photos = [m for m in members if not m['photo_path']]
        if not need_photos:
            print(f"  All {len(members)} members already have photos")
            continue
        
        print(f"  {len(need_photos)}/{len(members)} members need photos")
        
        # Try kprofiles first
        kprofile_results = fetch_kprofiles_photos(group_name, need_photos)
        time.sleep(1)
        
        downloaded = 0
        for member in need_photos:
            artist_id = member['id']
            stage_name = member['stage_name']
            
            img_url = kprofile_results.get(artist_id)
            source = 'kprofiles'
            
            if not img_url:
                # Fallback: try Deezer
                img_url = search_deezer_artist(stage_name, group_name)
                source = 'deezer'
                time.sleep(0.5)
            
            if not img_url:
                print(f"  ✗ No photo found for {stage_name}")
                continue
            
            # Download
            ext = '.jpg'
            if '.png' in img_url.lower():
                ext = '.png'
            elif '.webp' in img_url.lower():
                ext = '.webp'
            
            filename = f"{artist_id}{ext}"
            filepath = os.path.join(IMAGES_DIR, filename)
            photo_path = f"/images/members/{filename}"
            
            print(f"  Downloading {stage_name} from {source}...", end=' ', flush=True)
            data = download_image(img_url, filepath)
            
            if data:
                print(f"✓ {len(data)} bytes")
                
                # Update artists table
                cursor.execute("""
                    UPDATE artists SET photo_path = ?, image_url = ? WHERE id = ?
                """, (photo_path, img_url, artist_id))
                
                # Check if face_image already exists
                cursor.execute("SELECT id FROM face_images WHERE artist_id = ?", (artist_id,))
                if not cursor.fetchone():
                    # Determine format from data
                    fmt = 'jpeg'
                    if data[:4] == b'\x89PNG':
                        fmt = 'png'
                    elif data[:4] == b'RIFF':
                        fmt = 'webp'
                    
                    cursor.execute("""
                        INSERT INTO face_images (artist_id, image, format, source_url)
                        VALUES (?, ?, ?, ?)
                    """, (artist_id, data, fmt, img_url))
                    print(f"    → Stored in face_images table")
                
                db.commit()
                downloaded += 1
                time.sleep(0.8)
            else:
                print("✗ failed")
        
        print(f"\n  Downloaded {downloaded}/{len(need_photos)} photos for {group_name}")
    
    # Create face quiz questions for new face_images
    print(f"\n{'='*50}")
    print("Creating face quiz questions...")
    
    cursor.execute("""
        SELECT fi.id, fi.artist_id, a.stage_name, g.name as group_name, g.id as group_id
        FROM face_images fi
        JOIN artists a ON fi.artist_id = a.id
        JOIN groups g ON a.group_id = g.id
        WHERE g.name IN ('BABYMONSTER', 'KATSEYE')
    """)
    face_images = cursor.fetchall()
    
    questions_created = 0
    for fi in face_images:
        fi = dict(fi)
        # "Who is this member?" question
        cursor.execute("""
            SELECT id FROM questions 
            WHERE type = 'face' AND face_image_id = ? AND question_text = 'Who is this idol?'
        """, (fi['id'],))
        if cursor.fetchone():
            continue
        
        metadata = json.dumps({
            'group_name': fi['group_name'],
            'artist_id': fi['artist_id'],
            'answer_type': 'member_name',
        })
        
        cursor.execute("""
            INSERT INTO questions (type, difficulty, category, question_text,
                                   face_image_id, correct_answer, metadata_json)
            VALUES ('face', 2, 'face_recognition', 'Who is this idol?', ?, ?, ?)
        """, (fi['id'], fi['stage_name'], metadata))
        questions_created += 1
        
        # "Which group is this idol from?" question
        cursor.execute("""
            SELECT id FROM questions 
            WHERE type = 'face' AND face_image_id = ? AND question_text = 'Which group is this idol from?'
        """, (fi['id'],))
        if cursor.fetchone():
            continue
        
        metadata2 = json.dumps({
            'member_name': fi['stage_name'],
            'artist_id': fi['artist_id'],
            'answer_type': 'group_name',
        })
        
        cursor.execute("""
            INSERT INTO questions (type, difficulty, category, question_text,
                                   face_image_id, correct_answer, metadata_json)
            VALUES ('face', 2, 'face_recognition', 'Which group is this idol from?', ?, ?, ?)
        """, (fi['id'], fi['group_name'], metadata2))
        questions_created += 1
    
    db.commit()
    print(f"Created {questions_created} face quiz questions")
    
    # Summary
    for group_name in TARGET_GROUPS:
        cursor.execute("""
            SELECT COUNT(*) FROM artists a JOIN groups g ON a.group_id=g.id 
            WHERE g.name=? AND a.photo_path IS NOT NULL
        """, (group_name,))
        with_photos = cursor.fetchone()[0]
        cursor.execute("""
            SELECT COUNT(*) FROM artists a JOIN groups g ON a.group_id=g.id WHERE g.name=?
        """, (group_name,))
        total = cursor.fetchone()[0]
        print(f"  {group_name}: {with_photos}/{total} members have photos")
    
    db.close()


if __name__ == '__main__':
    import json
    main()
