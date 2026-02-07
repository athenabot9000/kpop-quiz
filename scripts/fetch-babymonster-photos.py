#!/usr/bin/env python3
"""Quick retry for BABYMONSTER members missing photos - fetches from kprofiles."""

import sqlite3
import urllib.request
import json
import os
import re
import sys
import time

sys.stdout.reconfigure(line_buffering=True)

DB_PATH = "/home/athena/kpop-quiz/app/data/kpop_quiz.db"
IMAGES_DIR = "/home/athena/kpop-quiz/app/public/images/members"
URL = "https://kprofiles.com/babymonster-members-profile/"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,*/*',
}

def main():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    cursor = db.cursor()
    
    # Get BABYMONSTER members without photos
    cursor.execute("""
        SELECT a.id, a.stage_name FROM artists a JOIN groups g ON a.group_id=g.id
        WHERE g.name='BABYMONSTER' AND (a.photo_path IS NULL OR a.photo_path = '')
        ORDER BY a.id
    """)
    need_photos = [dict(r) for r in cursor.fetchall()]
    
    if not need_photos:
        print("All BABYMONSTER members already have photos!")
        db.close()
        return
    
    print(f"Need photos for: {[m['stage_name'] for m in need_photos]}")
    
    # Fetch kprofiles page
    req = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode('utf-8', errors='replace')
    
    # Extract all kprofiles images with alt text
    img_pattern = re.compile(
        r'<img[^>]*?(?:src|data-src|data-lazy-src)=["\']([^"\']*kprofiles\.com/wp-content/uploads[^"\']*)["\'][^>]*?(?:alt=["\']([^"\']*)["\'])?',
        re.IGNORECASE
    )
    img_pattern2 = re.compile(
        r'<img[^>]*?alt=["\']([^"\']*)["\'][^>]*?(?:src|data-src|data-lazy-src)=["\']([^"\']*kprofiles\.com/wp-content/uploads[^"\']*)["\']',
        re.IGNORECASE
    )
    
    all_images = []
    seen_urls = set()
    for match in img_pattern.finditer(html):
        url = match.group(1)
        alt = match.group(2) or ''
        if url not in seen_urls:
            all_images.append((url, alt))
            seen_urls.add(url)
    for match in img_pattern2.finditer(html):
        alt = match.group(1)
        url = match.group(2)
        if url not in seen_urls:
            all_images.append((url, alt))
            seen_urls.add(url)
    
    # Filter out non-photo images
    photo_images = [(url, alt) for url, alt in all_images 
                    if not any(skip in url.lower() for skip in ['logo', 'banner', 'herald', '1x1', 'sidebar'])
                    and any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp'])]
    
    print(f"Found {len(photo_images)} candidate images on kprofiles page")
    for i, (url, alt) in enumerate(photo_images[:20]):
        print(f"  [{i}] alt='{alt[:50]}' url=...{url[-40:]}")
    
    # Try name matching first
    matched = {}
    member_names = {m['stage_name'].lower(): m for m in need_photos}
    
    for url, alt in photo_images:
        alt_lower = alt.lower().strip()
        for name_lower, member in member_names.items():
            if member['id'] in matched:
                continue
            # Check various forms of the name in alt
            name_parts = name_lower.split()
            if (name_lower in alt_lower or 
                any(part in alt_lower for part in name_parts if len(part) > 3)):
                matched[member['id']] = url
                print(f"  Name matched: {member['stage_name']} via alt='{alt}'")
    
    # If still missing, try positional: on kprofiles, member photos typically 
    # appear after the group photo in order
    if len(matched) < len(need_photos):
        # Get ALL members in order to figure out positions
        cursor.execute("""
            SELECT a.id, a.stage_name, a.photo_path FROM artists a JOIN groups g ON a.group_id=g.id
            WHERE g.name='BABYMONSTER' ORDER BY a.id
        """)
        all_members = [dict(r) for r in cursor.fetchall()]
        
        # The page usually has: group photo first, then individual photos in order
        # Skip first image (group photo)
        if len(photo_images) > len(all_members):
            individual_photos = photo_images[1:]  # Skip group photo
            print(f"\n  Positional matching with {len(individual_photos)} individual images, {len(all_members)} members")
            
            for i, member in enumerate(all_members):
                if member['id'] in matched or member['photo_path']:
                    continue
                if i < len(individual_photos):
                    url, alt = individual_photos[i]
                    matched[member['id']] = url
                    print(f"  Positional: {member['stage_name']} → image {i} (alt='{alt[:30]}')")
    
    # Download matched photos
    downloaded = 0
    for member in need_photos:
        aid = member['id']
        name = member['stage_name']
        url = matched.get(aid)
        
        if not url:
            print(f"  ✗ No match for {name}")
            continue
        
        ext = '.jpg'
        if '.png' in url.lower(): ext = '.png'
        elif '.webp' in url.lower(): ext = '.webp'
        
        filename = f"{aid}{ext}"
        filepath = os.path.join(IMAGES_DIR, filename)
        photo_path = f"/images/members/{filename}"
        
        try:
            time.sleep(0.8)
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            
            if len(data) < 1000:
                print(f"  ✗ {name}: image too small ({len(data)} bytes)")
                continue
            
            with open(filepath, 'wb') as f:
                f.write(data)
            
            # Update DB
            cursor.execute("UPDATE artists SET photo_path=?, image_url=? WHERE id=?",
                         (photo_path, url, aid))
            
            # Add face_image if not exists
            cursor.execute("SELECT id FROM face_images WHERE artist_id=?", (aid,))
            if not cursor.fetchone():
                fmt = 'jpeg'
                if data[:4] == b'\x89PNG': fmt = 'png'
                elif data[:4] == b'RIFF': fmt = 'webp'
                cursor.execute("""
                    INSERT INTO face_images (artist_id, image, format, source_url)
                    VALUES (?, ?, ?, ?)
                """, (aid, data, fmt, url))
                
                # Create face questions
                fi_id = cursor.lastrowid
                for q_text, correct, answer_type in [
                    ('Who is this idol?', name, 'member_name'),
                    ('Which group is this idol from?', 'BABYMONSTER', 'group_name'),
                ]:
                    cursor.execute("""
                        SELECT id FROM questions WHERE type='face' AND face_image_id=? AND question_text=?
                    """, (fi_id, q_text))
                    if not cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO questions (type, difficulty, category, question_text,
                                                   face_image_id, correct_answer, metadata_json)
                            VALUES ('face', 2, 'face_recognition', ?, ?, ?, ?)
                        """, (q_text, fi_id, correct, json.dumps({
                            'artist_id': aid,
                            'answer_type': answer_type,
                            'group_name': 'BABYMONSTER',
                        })))
            
            db.commit()
            downloaded += 1
            print(f"  ✓ {name} → {photo_path} ({len(data)} bytes)")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
    
    print(f"\nDownloaded {downloaded}/{len(need_photos)} photos")
    
    # Final check
    cursor.execute("""
        SELECT a.stage_name, a.photo_path FROM artists a JOIN groups g ON a.group_id=g.id
        WHERE g.name='BABYMONSTER'
    """)
    for row in cursor.fetchall():
        status = "✓" if row['photo_path'] else "✗"
        print(f"  {status} {row['stage_name']}: {row['photo_path'] or 'NO PHOTO'}")
    
    db.close()

if __name__ == '__main__':
    main()
