#!/usr/bin/env python3
"""
Targeted scraper for priority groups still missing photos.
Uses filename-based matching and positional fallback.
"""

import os, re, sys, time, sqlite3, requests
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

def name_from_url(url):
    path = url.split('/')[-1]
    path = re.sub(r'\.\w+$', '', path)
    path = re.sub(r'-\d+x\d+$', '', path)
    path = re.sub(r'-\d{4}$', '', path)
    path = re.sub(r'-\d+$', '', path)
    parts = path.split('-')
    return parts[0].strip() if parts else path

def name_from_alt(alt):
    if not alt: return None
    m = re.match(r'^(.+?)\s+(?:from|of)\s+', alt, re.IGNORECASE)
    if m: return m.group(1).strip()
    parts = alt.split('-')
    if len(parts) >= 2: return parts[0].strip()
    return alt

def try_match(candidate, members, matched):
    cn = normalize(candidate)
    if not cn or len(cn) < 2: return None
    for aid, sname in members:
        if aid in matched: continue
        sn = normalize(sname)
        if cn == sn: return (aid, sname)
        if cn in sn or sn in cn: return (aid, sname)
    for aid, sname in members:
        if aid in matched: continue
        sn = normalize(sname)
        if SequenceMatcher(None, cn, sn).ratio() >= 0.55:
            return (aid, sname)
    return None

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
        print(f"    ✗ {e}")
        return None

def scrape_group(session, db, gid, gname, gurl):
    members = db.execute("SELECT id, stage_name FROM artists WHERE group_id = ?", (gid,)).fetchall()
    need = [(a,s) for a,s in members if not db.execute(
        "SELECT 1 FROM artists WHERE id=? AND photo_path IS NOT NULL", (a,)).fetchone()]
    if not need:
        print(f"  Already complete")
        return 0
    print(f"  Need {len(need)}/{len(members)} photos")
    
    try:
        resp = session.get(gurl, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ✗ {e}")
        return 0
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    entry = soup.find('div', class_='entry-content')
    if not entry:
        print(f"  ✗ No content")
        return 0
    
    imgs = []
    for img in entry.find_all('img'):
        src = img.get('src', '') or img.get('data-src', '') or ''
        alt = img.get('alt', '')
        if 'kprofiles.com/wp-content/uploads' not in src: continue
        if not any(e in src.lower() for e in ['.jpg','.jpeg','.png','.webp']): continue
        if any(s in src.lower() for s in ['logo','herald','banner']): continue
        imgs.append((alt, src))
    
    if len(imgs) < 2:
        print(f"  ✗ Only {len(imgs)} images")
        return 0
    
    # Skip first if it's likely the group photo
    first_n = name_from_alt(imgs[0][0]) or name_from_url(imgs[0][1])
    if not try_match(first_n, members, set()):
        imgs = imgs[1:]
    
    # Match by alt text + filename
    matched = set(a for a,s in members if (a,s) not in need)  # already done
    results = []
    
    for alt, src in imgs:
        for candidate in [name_from_alt(alt), name_from_url(src)]:
            if candidate:
                m = try_match(candidate, need, matched)
                if m:
                    matched.add(m[0])
                    results.append((m[0], m[1], src))
                    break
    
    # Positional fallback
    if len(results) < len(need) * 0.4 and len(imgs) >= len(need):
        print(f"  ⚠ Positional fallback ({len(results)} matched)")
        results = []
        matched_pos = set(a for a,s in members if (a,s) not in need)
        for i, (aid, sname) in enumerate(need):
            if i < len(imgs):
                results.append((aid, sname, imgs[i][1]))
    
    count = 0
    for aid, sname, url in results:
        if db.execute("SELECT 1 FROM artists WHERE id=? AND photo_path IS NOT NULL", (aid,)).fetchone():
            count += 1; continue
        time.sleep(0.8)
        path = download(session, url, aid)
        if path:
            db.execute("UPDATE artists SET photo_path=?, image_url=? WHERE id=?", (path, url, aid))
            db.commit()
            count += 1
            print(f"  ✓ {sname} → {path}")
    
    print(f"  Got {count}/{len(results)}")
    return count

def main():
    db = sqlite3.connect(DB_PATH)
    try:
        db.execute("ALTER TABLE artists ADD COLUMN photo_path TEXT")
        db.commit()
    except: pass
    
    # Get ALL groups with incomplete photos, priority first
    all_groups = db.execute("""
        SELECT g.id, g.name, g.profile_url,
               COUNT(a.id) as total, COUNT(a.photo_path) as done
        FROM groups g JOIN artists a ON a.group_id = g.id
        WHERE g.profile_url IS NOT NULL AND g.profile_url != ''
        GROUP BY g.id HAVING done < total
        ORDER BY g.name
    """).fetchall()
    
    session = requests.Session()
    total = 0
    print(f"Processing {len(all_groups)} groups with missing photos\n")
    
    for i, (gid, gname, gurl, mc, pc) in enumerate(all_groups):
        print(f"[{i+1}/{len(all_groups)}] {gname} ({pc}/{mc})")
        time.sleep(1.5)
        try:
            total += scrape_group(session, db, gid, gname, gurl)
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    final = db.execute("SELECT COUNT(*) FROM artists WHERE photo_path IS NOT NULL").fetchone()[0]
    print(f"\n{'='*50}\nDone: +{total} photos, {final} total with photos")
    db.close()

if __name__ == "__main__":
    main()
