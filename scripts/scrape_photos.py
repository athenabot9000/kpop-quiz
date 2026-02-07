#!/usr/bin/env python3
"""
Scrape K-pop idol profile photos from kprofiles.com.
Matches photos to existing artists in the database using fuzzy name matching.
Stores photos as files and updates the database.
"""

import os
import re
import sys
import time
import sqlite3
import hashlib
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from difflib import SequenceMatcher

# Paths
DB_PATH = "/home/athena/kpop-quiz/app/data/kpop_quiz.db"
IMAGES_DIR = "/home/athena/kpop-quiz/app/public/images/members"
os.makedirs(IMAGES_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://kprofiles.com/",
}

# Priority groups to scrape (most popular)
PRIORITY_GROUPS = [
    "BTS (Bangtan Boys)", "BLACKPINK", "TWICE", "Stray Kids", "aespa",
    "NewJeans / NJZ", "ITZY", "Red Velvet", "EXO", "GOT7", "SEVENTEEN",
    "NCT", "i-dle", "IVE", "LE SSERAFIM", "TXT", "ENHYPEN", "ATEEZ",
    "MAMAMOO", "SHINee", "NMIXX", "Dreamcatcher", "MONSTA X", "LOONA",
    "TREASURE", "Apink", "2NE1",
    # Add more popular groups
    "ASTRO", "THE BOYZ", "AB6IX", "EVERGLOW", "fromis_9", "Kep1er",
    "Wanna One", "iKON", "WINNER", "DAY6", "BTOB", "VIXX",
    "MOMOLAND", "OH MY GIRL", "Brave Girls", "VIVIZ",
    "(G)I-DLE",  # alias
    "SUPER JUNIOR", "Girls' Generation", "BIGBANG", "2PM",
    "PENTAGON", "SF9", "Stayc", "Billlie", "tripleS",
]


def normalize_name(name):
    """Normalize a name for fuzzy matching."""
    name = name.lower().strip()
    # Remove common suffixes/prefixes
    name = re.sub(r'\s*\[.*?\]\s*', '', name)  # [formerly ...]
    name = re.sub(r'\s*/\s*.*$', '', name)  # V / Taehyung -> V
    name = re.sub(r'[^\w\s-]', '', name)  # Remove special chars except hyphen
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def fuzzy_match(name1, name2, threshold=0.6):
    """Check if two names match with fuzzy matching."""
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)
    
    # Exact match
    if n1 == n2:
        return True
    
    # Check if one contains the other
    if n1 in n2 or n2 in n1:
        return True
    
    # Sequence matcher
    ratio = SequenceMatcher(None, n1, n2).ratio()
    return ratio >= threshold


def extract_member_name_from_alt(alt_text):
    """Extract member name from image alt text."""
    if not alt_text:
        return None
    
    # Patterns like "Jisoo-Blackpink-2025", "RM from BTS", "JIHYO of TWICE"
    # Remove group names and years
    name = alt_text.strip()
    
    # "Name from Group" or "Name of Group"
    match = re.match(r'^(.+?)\s+(?:from|of)\s+', name, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # "Name-Group-Year" pattern
    parts = name.split('-')
    if len(parts) >= 2:
        return parts[0].strip()
    
    # Just the name (single word or compound)
    return name


def get_group_members(db, group_id):
    """Get all members of a group from the database."""
    cursor = db.execute(
        "SELECT id, stage_name FROM artists WHERE group_id = ?",
        (group_id,)
    )
    return cursor.fetchall()


def scrape_group_photos(session, profile_url, group_name, members, delay=1.5):
    """
    Scrape member photos from a group's kprofiles page.
    Returns list of (artist_id, image_url, image_data) tuples.
    """
    results = []
    
    try:
        resp = session.get(profile_url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  ✗ Failed to fetch {profile_url}: {e}")
        return results
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    entry = soup.find('div', class_='entry-content')
    if not entry:
        print(f"  ✗ No entry-content found for {group_name}")
        return results
    
    # Get all kprofiles images (skip emojis, ads, etc.)
    member_images = []
    for img in entry.find_all('img'):
        src = img.get('src', '') or img.get('data-src', '') or img.get('data-lazy-src', '')
        alt = img.get('alt', '')
        
        if not src or 'kprofiles.com/wp-content/uploads' not in src:
            continue
        if not any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
            continue
        # Skip logos, ads, banners
        if any(skip in src.lower() for skip in ['logo', 'herald', 'banner', 'ad-', 'sidebar']):
            continue
        if any(skip in alt.lower() for skip in ['logo', 'herald']):
            continue
            
        member_images.append((alt, src))
    
    if len(member_images) <= 1:
        print(f"  ✗ Only {len(member_images)} images found for {group_name}")
        return results
    
    # First image is usually the group photo, skip it
    # But verify by checking if it matches any member name
    first_alt = member_images[0][0].lower() if member_images[0][0] else ''
    member_names_lower = [normalize_name(m[1]) for m in members]
    
    skip_first = True
    for mname in member_names_lower:
        if mname and mname in first_alt:
            skip_first = False
            break
    
    candidate_images = member_images[1:] if skip_first else member_images
    
    # Try to match images to members
    matched = set()
    for alt, src in candidate_images:
        extracted_name = extract_member_name_from_alt(alt)
        if not extracted_name:
            continue
        
        # Try to match to a member
        best_match = None
        best_score = 0
        for artist_id, stage_name in members:
            if artist_id in matched:
                continue
            
            # Try various matching strategies
            en = normalize_name(extracted_name)
            sn = normalize_name(stage_name)
            
            # Direct match
            if en == sn:
                best_match = (artist_id, stage_name)
                best_score = 1.0
                break
            
            # Containment
            if en in sn or sn in en:
                score = 0.9
                if score > best_score:
                    best_match = (artist_id, stage_name)
                    best_score = score
            
            # Fuzzy
            score = SequenceMatcher(None, en, sn).ratio()
            if score > best_score and score >= 0.6:
                best_match = (artist_id, stage_name)
                best_score = score
        
        if best_match:
            artist_id, stage_name = best_match
            matched.add(artist_id)
            results.append((artist_id, stage_name, src))
    
    # If matching by name didn't work well, try positional matching
    # (members appear in same order on the page as in our DB)
    if len(results) < len(members) * 0.5 and len(candidate_images) == len(members):
        print(f"  ⚠ Falling back to positional matching for {group_name}")
        results = []
        matched = set()
        for i, (artist_id, stage_name) in enumerate(members):
            if i < len(candidate_images):
                _, src = candidate_images[i]
                results.append((artist_id, stage_name, src))
                matched.add(artist_id)
    
    return results


def download_image(session, url, artist_id, delay=1.0):
    """Download an image and save it. Returns the local path or None."""
    try:
        time.sleep(delay)
        resp = session.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        
        content_type = resp.headers.get('content-type', '')
        if 'image' not in content_type and len(resp.content) < 1000:
            print(f"    ✗ Not an image for artist {artist_id}: {content_type}")
            return None
        
        # Determine extension
        ext = '.jpg'
        if '.png' in url.lower():
            ext = '.png'
        elif '.webp' in url.lower():
            ext = '.webp'
        elif '.jpeg' in url.lower():
            ext = '.jpg'
        
        filename = f"{artist_id}{ext}"
        filepath = os.path.join(IMAGES_DIR, filename)
        
        with open(filepath, 'wb') as f:
            f.write(resp.content)
        
        return f"/images/members/{filename}"
    
    except requests.RequestException as e:
        print(f"    ✗ Failed to download image for artist {artist_id}: {e}")
        return None


def main():
    db = sqlite3.connect(DB_PATH)
    
    # Ensure photo_path column exists on artists table
    try:
        db.execute("ALTER TABLE artists ADD COLUMN photo_path TEXT")
        db.commit()
        print("Added photo_path column to artists table")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Get all groups with profile URLs
    groups = db.execute(
        "SELECT id, name, profile_url FROM groups WHERE profile_url IS NOT NULL AND profile_url != ''"
    ).fetchall()
    
    # Build priority order
    priority_set = set(g.lower() for g in PRIORITY_GROUPS)
    priority_groups = []
    other_groups = []
    
    for gid, gname, gurl in groups:
        if gname.lower() in priority_set or any(gname.lower() == p.lower() for p in PRIORITY_GROUPS):
            priority_groups.append((gid, gname, gurl))
        else:
            other_groups.append((gid, gname, gurl))
    
    # Also match partial names (e.g., "i-dle" matches "(G)I-DLE")
    remaining_priority = []
    for gid, gname, gurl in other_groups:
        is_priority = False
        for pname in PRIORITY_GROUPS:
            pn = pname.lower().replace('(', '').replace(')', '')
            gn = gname.lower().replace('(', '').replace(')', '')
            if pn in gn or gn in pn:
                is_priority = True
                break
        if is_priority:
            remaining_priority.append((gid, gname, gurl))
    
    priority_groups.extend(remaining_priority)
    
    # Process priority groups first, then others (up to a limit)
    all_groups = priority_groups + [g for g in other_groups if g not in remaining_priority]
    
    print(f"Found {len(priority_groups)} priority groups, {len(all_groups)} total groups with URLs")
    print(f"Will scrape priority groups first\n")
    
    session = requests.Session()
    total_scraped = 0
    total_failed = 0
    group_count = 0
    
    # Process up to 100 groups (priority first)
    max_groups = min(120, len(all_groups))
    
    for idx, (gid, gname, gurl) in enumerate(all_groups[:max_groups]):
        members = get_group_members(db, gid)
        if not members:
            continue
        
        # Check if we already have photos for this group
        already_done = db.execute(
            "SELECT COUNT(*) FROM artists WHERE group_id = ? AND photo_path IS NOT NULL",
            (gid,)
        ).fetchone()[0]
        
        if already_done == len(members):
            print(f"[{idx+1}/{max_groups}] {gname} — already done ({already_done} photos)")
            total_scraped += already_done
            continue
        
        print(f"[{idx+1}/{max_groups}] {gname} ({len(members)} members) — {gurl}")
        
        # Respectful delay between group pages
        time.sleep(1.5)
        
        matches = scrape_group_photos(session, gurl, gname, members)
        
        if not matches:
            print(f"  ✗ No matches found")
            total_failed += len(members)
            continue
        
        # Download each matched photo
        downloaded = 0
        for artist_id, stage_name, img_url in matches:
            # Check if already downloaded
            existing = db.execute(
                "SELECT photo_path FROM artists WHERE id = ? AND photo_path IS NOT NULL",
                (artist_id,)
            ).fetchone()
            if existing:
                downloaded += 1
                continue
            
            local_path = download_image(session, img_url, artist_id, delay=0.8)
            if local_path:
                db.execute(
                    "UPDATE artists SET photo_path = ?, image_url = ? WHERE id = ?",
                    (local_path, img_url, artist_id)
                )
                db.commit()
                downloaded += 1
                print(f"  ✓ {stage_name} → {local_path}")
            else:
                total_failed += 1
        
        total_scraped += downloaded
        print(f"  Downloaded {downloaded}/{len(matches)} matched, {len(members)} total members")
        group_count += 1
    
    # Summary
    total_with_photos = db.execute(
        "SELECT COUNT(*) FROM artists WHERE photo_path IS NOT NULL"
    ).fetchone()[0]
    
    print(f"\n{'='*60}")
    print(f"SCRAPING COMPLETE")
    print(f"{'='*60}")
    print(f"Groups processed: {group_count}")
    print(f"Photos downloaded this run: {total_scraped}")
    print(f"Failed: {total_failed}")
    print(f"Total artists with photos in DB: {total_with_photos}")
    
    db.close()


if __name__ == "__main__":
    main()
