#!/usr/bin/env python3
"""Quick manual fix for specific priority groups with known patterns."""

import os, re, time, sqlite3, requests
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

DB_PATH = "/home/athena/kpop-quiz/app/data/kpop_quiz.db"
IMAGES_DIR = "/home/athena/kpop-quiz/app/public/images/members"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://kprofiles.com/",
}

def normalize(name):
    return re.sub(r'[^\w]', '', name.lower().strip())

def download(session, url, artist_id):
    try:
        resp = session.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        if len(resp.content) < 500: return None
        ext = '.jpg'
        if '.png' in url.lower(): ext = '.png'
        elif '.webp' in url.lower(): ext = '.webp'
        fn = f"{artist_id}{ext}"
        with open(os.path.join(IMAGES_DIR, fn), 'wb') as f:
            f.write(resp.content)
        return f"/images/members/{fn}"
    except Exception as e:
        print(f"  ✗ Download failed: {e}")
        return None

def get_member_images(session, url):
    """Get all member-type images from a kprofiles page."""
    resp = session.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    entry = soup.find('div', class_='entry-content')
    if not entry: return []
    
    imgs = []
    for img in entry.find_all('img'):
        src = img.get('src', '') or img.get('data-src', '') or ''
        alt = img.get('alt', '')
        if 'kprofiles.com/wp-content/uploads' not in src: continue
        if not any(e in src.lower() for e in ['.jpg','.jpeg','.png','.webp']): continue
        if any(s in src.lower() for s in ['logo','herald','banner']): continue
        # Extract name from filename
        fname = src.split('/')[-1]
        fname = re.sub(r'\.\w+$', '', fname)
        fname = re.sub(r'-\d+x\d+$', '', fname)
        fname = re.sub(r'-\d+$', '', fname)
        name_parts = fname.split('-')
        imgs.append({'src': src, 'alt': alt, 'fname': name_parts[0] if name_parts else ''})
    return imgs

def process_group(session, db, group_name):
    group = db.execute(
        "SELECT id, name, profile_url FROM groups WHERE name = ?", (group_name,)
    ).fetchone()
    if not group:
        print(f"Group '{group_name}' not found")
        return 0
    
    gid, gname, gurl = group
    members = db.execute(
        "SELECT id, stage_name FROM artists WHERE group_id = ?", (gid,)
    ).fetchall()
    
    need = [(a,s) for a,s in members if not db.execute(
        "SELECT 1 FROM artists WHERE id=? AND photo_path IS NOT NULL", (a,)).fetchone()]
    
    if not need:
        print(f"{gname}: Already complete ({len(members)} photos)")
        return 0
    
    print(f"{gname}: Need {len(need)}/{len(members)} photos from {gurl}")
    
    try:
        imgs = get_member_images(session, gurl)
    except Exception as e:
        print(f"  ✗ {e}")
        return 0
    
    if len(imgs) < 2:
        print(f"  ✗ Only {len(imgs)} images found")
        return 0
    
    # Skip group photo (first)
    candidate_imgs = imgs[1:]
    
    # Try matching by filename
    matched = set()
    results = []
    
    for img in candidate_imgs:
        fname = img['fname']
        alt_name = img['alt'].split('-')[0].strip() if img['alt'] else ''
        
        for candidate in [fname, alt_name]:
            if not candidate: continue
            cn = normalize(candidate)
            if not cn: continue
            
            best_match = None
            best_score = 0
            for aid, sname in need:
                if aid in matched: continue
                sn = normalize(sname)
                if cn == sn:
                    best_match = (aid, sname)
                    break
                if cn in sn or sn in cn:
                    if 0.85 > best_score:
                        best_match = (aid, sname)
                        best_score = 0.85
                score = SequenceMatcher(None, cn, sn).ratio()
                if score > best_score and score >= 0.5:
                    best_match = (aid, sname)
                    best_score = score
            
            if best_match:
                matched.add(best_match[0])
                results.append((best_match[0], best_match[1], img['src']))
                break
    
    # Positional fallback
    if len(results) < len(need) * 0.4 and len(candidate_imgs) >= len(need):
        print(f"  ⚠ Positional fallback")
        results = []
        for i, (aid, sname) in enumerate(need):
            if i < len(candidate_imgs):
                results.append((aid, sname, candidate_imgs[i]['src']))
    
    # Download
    count = 0
    for aid, sname, url in results:
        time.sleep(0.8)
        path = download(session, url, aid)
        if path:
            db.execute("UPDATE artists SET photo_path=?, image_url=? WHERE id=?", (path, url, aid))
            db.commit()
            count += 1
            print(f"  ✓ {sname} → {path}")
    
    return count

def main():
    db = sqlite3.connect(DB_PATH)
    session = requests.Session()
    
    # Priority groups that still need fixing
    targets = ['Red Velvet', 'SHINee', 'STAYC', 'IVE', 'LOONA', 'BTOB', 'WINNER',
               'EXO', 'NCT', 'Stray Kids', 'i-dle', 'Dreamcatcher', 'NMIXX',
               'ITZY', 'Apink', 'TREASURE', 'iKON', 'DAY6']
    
    total = 0
    for gname in targets:
        time.sleep(1.5)
        try:
            total += process_group(session, db, gname)
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    final = db.execute("SELECT COUNT(*) FROM artists WHERE photo_path IS NOT NULL").fetchone()[0]
    print(f"\nDone: +{total} photos, {final} total")
    db.close()

if __name__ == "__main__":
    main()
