#!/usr/bin/env python3
"""
Fix scraper for groups that had 0 or partial matches.
Tries filename-based matching and positional fallback.
"""

import os
import re
import sys
import time
import sqlite3
import requests
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

DB_PATH = "/home/athena/kpop-quiz/app/data/kpop_quiz.db"
IMAGES_DIR = "/home/athena/kpop-quiz/app/public/images/members"
os.makedirs(IMAGES_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://kprofiles.com/",
}


def normalize(name):
    name = name.lower().strip()
    name = re.sub(r'\s*\[.*?\]\s*', '', name)
    name = re.sub(r'\s*/\s*.*$', '', name)
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def extract_name_from_url(url):
    """Extract a likely member name from the image URL filename."""
    # Get filename without extension
    path = url.split('/')[-1]
    path = re.sub(r'\.\w+$', '', path)  # Remove extension
    path = re.sub(r'-\d+x\d+$', '', path)  # Remove dimension suffix like -533x800
    path = re.sub(r'-\d{4}$', '', path)  # Remove year
    path = re.sub(r'-\d+$', '', path)  # Remove trailing numbers
    # Split on hyphens
    parts = path.split('-')
    if parts:
        # Usually the first part or first few parts are the name
        # Return first part as candidate
        return parts[0].strip()
    return path


def extract_name_from_alt(alt_text):
    if not alt_text:
        return None
    name = alt_text.strip()
    match = re.match(r'^(.+?)\s+(?:from|of)\s+', name, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    parts = name.split('-')
    if len(parts) >= 2:
        return parts[0].strip()
    return name


def match_name(candidate, members, matched_ids):
    """Try to match a candidate name to an unmatched member."""
    cn = normalize(candidate)
    if not cn or len(cn) < 2:
        return None
    
    best = None
    best_score = 0
    
    for aid, sname in members:
        if aid in matched_ids:
            continue
        sn = normalize(sname)
        
        if cn == sn:
            return (aid, sname)
        if cn in sn or sn in cn:
            score = 0.9
            if score > best_score:
                best = (aid, sname)
                best_score = score
        else:
            score = SequenceMatcher(None, cn, sn).ratio()
            if score > best_score and score >= 0.55:
                best = (aid, sname)
                best_score = score
    
    return best


def download_image(session, url, artist_id):
    """Download an image. Returns local path or None."""
    try:
        time.sleep(0.8)
        resp = session.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        
        if len(resp.content) < 500:
            return None
        
        ext = '.jpg'
        if '.png' in url.lower(): ext = '.png'
        elif '.webp' in url.lower(): ext = '.webp'
        
        filename = f"{artist_id}{ext}"
        filepath = os.path.join(IMAGES_DIR, filename)
        with open(filepath, 'wb') as f:
            f.write(resp.content)
        return f"/images/members/{filename}"
    except Exception as e:
        print(f"    ✗ Download failed for {artist_id}: {e}")
        return None


def scrape_group(session, db, group_id, group_name, profile_url):
    """Scrape photos for a group, using both alt text and filename matching."""
    members = db.execute(
        "SELECT id, stage_name FROM artists WHERE group_id = ?", (group_id,)
    ).fetchall()
    
    # Which members still need photos?
    need_photos = []
    for aid, sname in members:
        existing = db.execute(
            "SELECT photo_path FROM artists WHERE id = ? AND photo_path IS NOT NULL", (aid,)
        ).fetchone()
        if not existing:
            need_photos.append((aid, sname))
    
    if not need_photos:
        print(f"  Already complete ({len(members)} photos)")
        return 0
    
    print(f"  Need photos for {len(need_photos)}/{len(members)} members")
    
    try:
        resp = session.get(profile_url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ✗ Failed to fetch page: {e}")
        return 0
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    entry = soup.find('div', class_='entry-content')
    if not entry:
        print(f"  ✗ No entry-content div")
        return 0
    
    # Collect all candidate member images
    candidate_images = []
    for img in entry.find_all('img'):
        src = img.get('src', '') or img.get('data-src', '') or ''
        alt = img.get('alt', '')
        
        if 'kprofiles.com/wp-content/uploads' not in src:
            continue
        if not any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
            continue
        if any(skip in src.lower() for skip in ['logo', 'herald', 'banner']):
            continue
        
        candidate_images.append((alt, src))
    
    if len(candidate_images) < 2:
        print(f"  ✗ Only {len(candidate_images)} images found")
        return 0
    
    # Skip group photo (first image) if it doesn't match any member
    first_name = extract_name_from_alt(candidate_images[0][0]) or extract_name_from_url(candidate_images[0][1])
    if not match_name(first_name, members, set()):
        candidate_images = candidate_images[1:]
    
    # Pass 1: Match by alt text
    matched = set()
    results = []
    for alt, src in candidate_images:
        name = extract_name_from_alt(alt)
        if name:
            m = match_name(name, need_photos, matched)
            if m:
                matched.add(m[0])
                results.append((m[0], m[1], src))
    
    # Pass 2: Match by filename for unmatched images
    for alt, src in candidate_images:
        fname = extract_name_from_url(src)
        if fname:
            m = match_name(fname, need_photos, matched)
            if m:
                matched.add(m[0])
                results.append((m[0], m[1], src))
    
    # Pass 3: Positional fallback if we matched less than half
    if len(results) < len(need_photos) * 0.4 and len(candidate_images) >= len(need_photos):
        print(f"  ⚠ Falling back to positional matching ({len(results)} matched so far)")
        results = []
        matched = set()
        for i, (aid, sname) in enumerate(need_photos):
            if i < len(candidate_images):
                results.append((aid, sname, candidate_images[i][1]))
                matched.add(aid)
    
    # Download
    downloaded = 0
    for aid, sname, img_url in results:
        path = download_image(session, img_url, aid)
        if path:
            db.execute(
                "UPDATE artists SET photo_path = ?, image_url = ? WHERE id = ?",
                (path, img_url, aid)
            )
            db.commit()
            downloaded += 1
            print(f"  ✓ {sname} → {path}")
    
    print(f"  Downloaded {downloaded}/{len(results)} matched")
    return downloaded


def main():
    db = sqlite3.connect(DB_PATH)
    
    # Get groups with incomplete photos
    groups = db.execute("""
        SELECT g.id, g.name, g.profile_url,
               COUNT(a.id) as total,
               COUNT(a.photo_path) as with_photo
        FROM groups g
        JOIN artists a ON a.group_id = g.id
        WHERE g.profile_url IS NOT NULL AND g.profile_url != ''
        GROUP BY g.id
        HAVING with_photo < total
        ORDER BY g.name
    """).fetchall()
    
    session = requests.Session()
    total = 0
    
    print(f"Found {len(groups)} groups with incomplete photos\n")
    
    for i, (gid, gname, gurl, member_count, photo_count) in enumerate(groups):
        print(f"[{i+1}/{len(groups)}] {gname} ({photo_count}/{member_count} photos) — {gurl}")
        time.sleep(1.5)
        
        try:
            downloaded = scrape_group(session, db, gid, gname, gurl)
            total += downloaded
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    final = db.execute("SELECT COUNT(*) FROM artists WHERE photo_path IS NOT NULL").fetchone()[0]
    print(f"\n{'='*50}")
    print(f"Fix complete: {total} new photos downloaded")
    print(f"Total artists with photos: {final}")
    
    db.close()


if __name__ == "__main__":
    main()
