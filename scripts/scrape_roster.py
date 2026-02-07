#!/usr/bin/env python3
"""
Phase 1: K-pop Roster Scraper (v2 — clean rewrite)
Scrapes kprofiles.com to populate groups and artists tables.
Priority: 3rd generation onwards (2012+).
"""

import re
import os
import sys
import time
import sqlite3
import logging
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# ─── Config ──────────────────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'kpop_quiz.db')
REQUEST_DELAY = 1.5  # seconds between requests
USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)

LISTING_URLS = {
    'male':   'https://kprofiles.com/k-pop-boy-groups/',
    'female': 'https://kprofiles.com/k-pop-girl-groups/',
}

# Generation ranges (by debut year)
GENERATION_RANGES = [
    (1, 1996, 2002),
    (2, 2003, 2011),
    (3, 2012, 2017),
    (4, 2018, 2022),
    (5, 2023, 2099),
]

# Default difficulty by generation
GEN_DIFFICULTY = {1: 5, 2: 4, 3: 2, 4: 1, 5: 1}

# Filter patterns — exclude groups matching these in listing context text
EXCLUDE_PATTERNS = re.compile(
    r'(?i)'
    r'(?:rock\s*band|virtual\s*(?:group|girl\s*group)|trot\s*group'
    r'|indie\s*(?:band|rock\s*band)|producer[s]?\s*(?:group|crew)'
    r'|comic\s*group|ballad\s*group|crossover\s*group|one[- ]?man\s*band'
    r'|vocal\s*group|ai\s*group'
    r'|crew\b|sub[- ]?unit|j-?pop\s*sub[- ]?unit)'
)

# Pre-debut filter (separate so we can be precise)
PREDEBUT_PATTERN = re.compile(r'(?i)\*?\s*pre[- ]?debut')

# Sub-unit indicators
SUBUNIT_INDICATOR = re.compile(r'(?:sub[- ]?unit|composed of .* members|collab\b)', re.I)

# Explicit skip list
EXPLICIT_SKIP = {
    'Disbanded Kpop Boy Groups', 'Disbanded Kpop Girl Groups',
    'Disbanded K-pop Girl Groups',
}

# ─── Manual overrides for groups that fail auto-parse ─────────────────────────
# {url_fragment: {field: value}} — merged into parsed data
MANUAL_OVERRIDES = {
    'exo-members-profile': {'debut_year': 2012, 'company': 'SM Entertainment'},
    'nct-members-profile': {'debut_year': 2016, 'company': 'SM Entertainment'},
    'shinee-members-profile': {'debut_year': 2008, 'company': 'SM Entertainment'},
    'super-junior-members-profile': {'debut_year': 2005, 'company': 'SM Entertainment'},
    'tvxq': {'debut_year': 2003, 'company': 'SM Entertainment'},
    'big-bang-members-profile': {'debut_year': 2006, 'company': 'YG Entertainment'},
    '2pm-members-profile': {'debut_year': 2008, 'company': 'JYP Entertainment'},
    '2am-members-profile': {'debut_year': 2008, 'company': 'JYP Entertainment'},
    'cosmic-girls-wjsn-profile': {'debut_year': 2016, 'company': 'Starship Entertainment'},
    'everglow-members-profile': {'debut_year': 2019, 'company': 'Yuehua Entertainment'},
    'highlight-members-profile': {'debut_year': 2009, 'company': 'Around Us Entertainment'},
    'girls-generation-snsd-members-profile': {'debut_year': 2007, 'company': 'SM Entertainment'},
    'idle-profile-facts': {'company': 'CUBE Entertainment'},
    'bts-bangtan-boys-members-profile': {'company': 'BIGHIT MUSIC'},
    'enhypen-profile-facts': {'company': 'BELIFT LAB'},
    'ill-it-members-profile': {'company': 'BELIFT LAB'},
    'le-sserafim-members-profile': {'company': 'SOURCE MUSIC'},
    'newjeans-members-profile-facts': {'company': 'ADOR'},
    'txt-members-profile': {'company': 'BIGHIT MUSIC'},
}

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    stream=sys.stdout,
)
sys.stdout.reconfigure(line_buffering=True)
log = logging.getLogger('scraper')

# ─── HTTP Session ────────────────────────────────────────────────────────────

http_session = requests.Session()
http_session.headers.update({'User-Agent': USER_AGENT})


def fetch(url: str, retries: int = 3) -> requests.Response | None:
    """Fetch URL with retries and rate limiting."""
    for attempt in range(retries):
        try:
            time.sleep(REQUEST_DELAY)
            resp = http_session.get(url, timeout=30)
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 429:
                wait = 10 * (attempt + 1)
                log.warning(f'Rate limited, waiting {wait}s: {url}')
                time.sleep(wait)
            else:
                log.warning(f'HTTP {resp.status_code} for {url}')
                return None
        except requests.RequestException as e:
            log.warning(f'Request error (attempt {attempt+1}): {e}')
            time.sleep(5 * (attempt + 1))
    return None


# ─── Listing Page Parser ─────────────────────────────────────────────────────

def _build_link_context_map(entry_div) -> dict:
    """Build href → {link_text, before, after} by splitting HTML on <br> tags.

    Each <br>-delimited segment is one listing entry. For segments with multiple
    links (group + sub-units on same line), we isolate each link's local context.
    """
    raw_html = str(entry_div)
    html_segments = re.split(r'<br\s*/?>', raw_html)

    href_to_context = {}

    for segment in html_segments:
        link_matches = list(re.finditer(
            r'<a\s[^>]*href="(https://kprofiles\.com/[^"]+)"[^>]*>(.*?)</a>',
            segment, re.DOTALL,
        ))
        if not link_matches:
            continue

        for i, match in enumerate(link_matches):
            href = match.group(1)

            # Text AFTER this link, before next link or end of segment
            after_start = match.end()
            after_end = link_matches[i + 1].start() if i + 1 < len(link_matches) else len(segment)
            after_text = BeautifulSoup(segment[after_start:after_end], 'html.parser').get_text().strip()

            # Text BEFORE this link (between previous link end and this link start)
            before_start = link_matches[i - 1].end() if i > 0 else 0
            before_text = BeautifulSoup(segment[before_start:match.start()], 'html.parser').get_text().strip()

            link_text = BeautifulSoup(match.group(2), 'html.parser').get_text().strip()

            href_to_context[href] = {
                'link_text': link_text,
                'before': before_text,
                'after': after_text,
            }

    return href_to_context


def get_group_links(gender: str) -> list[dict]:
    """Parse listing page → [{name, url, gender}] for valid idol groups."""
    url = LISTING_URLS[gender]
    log.info(f'Fetching {gender} groups listing: {url}')
    resp = fetch(url)
    if not resp:
        log.error(f'Failed to fetch listing page: {url}')
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')
    entry = soup.find('div', class_='entry-content')
    if not entry:
        log.error('No entry-content div found')
        return []

    context_map = _build_link_context_map(entry)

    groups = []
    seen_urls = set()

    for a_tag in entry.find_all('a'):
        href = a_tag.get('href', '').strip()
        name = a_tag.get_text().strip()

        if not href or not name:
            continue
        if 'kprofiles.com' not in href:
            continue
        if name in EXPLICIT_SKIP:
            continue
        if href in seen_urls:
            continue
        if '/disbanded-' in href or '/quiz-' in href or '/poll-' in href:
            continue

        # Skip if inside a <ul>/<li> (sub-unit list)
        in_list = False
        p = a_tag.parent
        while p:
            if p.name in ('ul', 'ol', 'li'):
                in_list = True
                break
            if p.name == 'p':
                break
            p = p.parent
        if in_list:
            continue

        ctx = context_map.get(href, {})
        before_text = ctx.get('before', '')
        after_text = ctx.get('after', '')
        filter_text = name + ' ' + after_text

        # • prefix = sub-unit on girl groups page
        if '•' in before_text:
            continue

        # Pre-debut check
        if PREDEBUT_PATTERN.search(filter_text):
            continue

        # Exclude patterns (rock band, virtual, etc.)
        if EXCLUDE_PATTERNS.search(filter_text):
            continue

        # Sub-unit check
        if SUBUNIT_INDICATOR.search(filter_text):
            continue

        seen_urls.add(href)
        groups.append({'name': name, 'url': href, 'gender': gender})

    log.info(f'Found {len(groups)} {gender} group links after filtering')
    return groups


# ─── Profile Page Parser ─────────────────────────────────────────────────────

def compute_generation(debut_year: int | None) -> int | None:
    if not debut_year:
        return None
    for gen, start, end in GENERATION_RANGES:
        if start <= debut_year <= end:
            return gen
    return None


def compute_difficulty(generation: int | None) -> int:
    if generation is None:
        return 3
    return GEN_DIFFICULTY.get(generation, 3)


def extract_year_from_text(text: str) -> int | None:
    """Extract debut year from profile text using multiple strategies."""
    # Strategy 1: "debuted on <date>, <year>" or "debuted in <year>"
    m = re.search(
        r'debut(?:ed)?\s+(?:under\s+[\w\s&\'.]+?\s+)?'
        r'(?:on\s+|in\s+)?(?:\w+\s+\d{1,2},?\s+)?(\d{4})',
        text, re.I,
    )
    if m:
        year = int(m.group(1))
        if 1990 <= year <= 2030:
            return year

    # Strategy 2: "Debut Date: <date>" style
    m = re.search(r'Debut\s*(?:Date)?\s*:\s*(?:\w+\s+\d{1,2},?\s+)?(\d{4})', text, re.I)
    if m:
        year = int(m.group(1))
        if 1990 <= year <= 2030:
            return year

    # Strategy 3: "<date> with their first single/album" (debut implied)
    m = re.search(
        r'(?:on|in)\s+(?:\w+\s+\d{1,2},?\s+)?(\d{4})(?:,?\s+with\s+their\s+(?:first|debut))',
        text, re.I,
    )
    if m:
        year = int(m.group(1))
        if 1990 <= year <= 2030:
            return year

    return None


def extract_korean_name(text: str) -> str | None:
    """Extract Korean name from patterns like 'BTS (방탄소년단)' or 'IVE (아이브)'."""
    m = re.search(r'[（(]\s*([가-힣]+(?:\s*[가-힣]+)*)\s*[）)]', text)
    return m.group(1) if m else None


def extract_company(text: str) -> str | None:
    """Extract company/label from intro paragraph."""
    patterns = [
        r'under\s+([A-Za-z0-9\s&\'.,]+?(?:Entertainment|Ent\.|Music|Records|Labels?|Lab|MUSIC))',
        r'under\s+([A-Za-z0-9\s&\'.]+?)(?:,|\.\s|that\s|consisting)',
        r'managed\s+by\s+([A-Za-z0-9\s&\'.,]+?)(?:,|\.|and\s)',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            company = m.group(1).strip().rstrip('.,;')
            company = re.sub(r'\s+(?:that|consisting|which|who|they).*$', '', company, flags=re.I)
            if 3 < len(company) < 80:
                return company
    return None


def parse_date(text: str) -> str | None:
    """Parse birthday string to YYYY-MM-DD."""
    if not text:
        return None
    text = text.strip()
    for fmt in ('%B %d, %Y', '%b %d, %Y', '%d %B %Y', '%d %b %Y',
                '%B %d %Y', '%Y-%m-%d', '%m/%d/%Y'):
        try:
            return datetime.strptime(text, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None


def parse_member_block(text: str) -> dict | None:
    """Parse a member-info paragraph into structured data."""
    lines = text.strip().split('\n')
    if len(lines) < 3:
        return None

    member = {
        'stage_name': None,
        'real_name': None,
        'korean_name': None,
        'birth_date': None,
        'position': None,
        'nationality': None,
    }

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Stage Name / Stage / Birth Name
        m = re.match(r'Stage\s*(?:/\s*Birth)?\s*Name\s*:\s*(.+)', line, re.I)
        if m:
            val = m.group(1).strip()
            km = re.search(r'[（(]\s*([가-힣]+(?:\s[가-힣]+)*)\s*[）)]', val)
            if km:
                member['korean_name'] = km.group(1)
            stage = re.sub(r'\s*[（(].*?[）)]', '', val).strip()
            member['stage_name'] = stage
            if '/ birth' in line.lower():
                member['real_name'] = stage
            continue

        # Birth Name
        m = re.match(r'Birth\s*Name\s*:\s*(.+)', line, re.I)
        if m:
            val = m.group(1).strip()
            km = re.search(r'[（(]\s*([가-힣]+(?:\s[가-힣]+)*)\s*[）)]', val)
            if km and not member['korean_name']:
                member['korean_name'] = km.group(1)
            real = re.sub(r'\s*[（(].*?[）)]', '', val).strip()
            real = re.sub(r'\s*/\s*[가-힣\s]+$', '', real).strip()
            member['real_name'] = real
            continue

        # Korean Name (separate line)
        m = re.match(r'Korean\s*Name\s*:\s*(.+)', line, re.I)
        if m:
            km = re.search(r'([가-힣]+(?:\s[가-힣]+)*)', m.group(1))
            if km:
                member['korean_name'] = km.group(1)
            continue

        # Position
        m = re.match(r'Position\s*(?:\(s\))?\s*:\s*(.+)', line, re.I)
        if m:
            member['position'] = m.group(1).strip()
            continue

        # Birthday
        m = re.match(r'Birth\s*day\s*:\s*(.+)', line, re.I)
        if m:
            member['birth_date'] = parse_date(m.group(1).strip())
            continue

        # Nationality
        m = re.match(r'Nationality\s*:\s*(.+)', line, re.I)
        if m:
            member['nationality'] = m.group(1).strip()
            continue

    return member if member['stage_name'] else None


def scrape_group_profile(url: str, name: str, gender: str) -> dict | None:
    """Scrape a single group profile page → group info + members."""
    resp = fetch(url)
    if not resp:
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')
    entry = soup.find('div', class_='entry-content')
    if not entry:
        log.warning(f'No entry-content for {name}')
        return None

    paragraphs = entry.find_all('p')
    if not paragraphs:
        return None

    # ── Gather intro text (all paragraphs BEFORE member profiles) ──
    intro_parts = []
    for p in paragraphs:
        t = p.get_text()
        if re.search(r'Stage\s+(?:/\s*Birth\s+)?Name\s*:', t):
            break
        intro_parts.append(t)
    intro = '\n'.join(intro_parts)

    # ── Extract group metadata ──
    debut_year = extract_year_from_text(intro)
    korean_name = extract_korean_name(intro)
    company = extract_company(intro)

    member_count_match = re.search(r'(\d+)[- ]?member', intro, re.I)
    member_count = int(member_count_match.group(1)) if member_count_match else None

    # Apply manual overrides if available
    for url_frag, overrides in MANUAL_OVERRIDES.items():
        if url_frag in url:
            for k, v in overrides.items():
                if k == 'debut_year' and debut_year is None:
                    debut_year = v
                elif k == 'company' and company is None:
                    company = v
            break

    generation = compute_generation(debut_year)
    difficulty = compute_difficulty(generation)

    is_active = 1
    if re.search(r'disbanded|disband', intro, re.I):
        is_active = 0
    disband_year = None
    dm = re.search(r'disbanded\s+(?:on\s+)?(?:\w+\s+\d{1,2},?\s+)?(\d{4})', intro, re.I)
    if dm:
        disband_year = int(dm.group(1))

    detected_gender = gender
    if re.search(r'co[- ]?ed\s+group', intro, re.I):
        detected_gender = 'coed'

    group_info = {
        'name': name,
        'korean_name': korean_name,
        'company': company,
        'debut_year': debut_year,
        'disband_year': disband_year,
        'generation': generation,
        'gender': detected_gender,
        'member_count': member_count,
        'difficulty': difficulty,
        'active': is_active,
        'profile_url': url,
    }

    # ── Build image map from alt text ──
    images_by_name = {}
    for img in entry.find_all('img'):
        src = img.get('data-src') or img.get('src', '')
        alt = img.get('alt', '')
        if not src or not alt:
            continue
        if 'emoji' in src or 'svg' in src:
            continue
        if 'wp-content/uploads' in src:
            images_by_name[alt.strip()] = src

    # ── Parse members ──
    members = []
    seen_stage_names = set()

    for p in paragraphs:
        ptext = p.get_text()
        if 'Stage' not in ptext and 'Birth Name' not in ptext:
            continue
        if 'Birthday' not in ptext and 'Position' not in ptext:
            continue

        member = parse_member_block(ptext)
        if not member:
            continue

        stage = member['stage_name']
        # Deduplicate (e.g., NingNing vs Ningning)
        norm_key = re.sub(r'\s+', '', stage).lower()
        if norm_key in seen_stage_names:
            continue
        seen_stage_names.add(norm_key)

        # Find image by stage name match in alt text
        image_url = None
        for alt_text, src in images_by_name.items():
            if stage and stage.upper() in alt_text.upper():
                image_url = src
                break
        member['image_url'] = image_url
        member['gender'] = detected_gender if detected_gender != 'coed' else gender
        members.append(member)

    group_info['members'] = members

    if not member_count and members:
        group_info['member_count'] = len(members)

    return group_info


# ─── Database Writer ─────────────────────────────────────────────────────────

def write_to_db(groups_data: list[dict]) -> tuple[int, int]:
    """Write scraped data to SQLite. Returns (groups_inserted, artists_inserted)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    groups_inserted = 0
    artists_inserted = 0

    for g in groups_data:
        try:
            cur.execute('''
                INSERT OR IGNORE INTO groups
                (name, korean_name, company, debut_year, disband_year, generation,
                 gender, member_count, difficulty, active, profile_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                g['name'], g['korean_name'], g['company'], g['debut_year'],
                g['disband_year'], g['generation'], g['gender'],
                g['member_count'], g['difficulty'], g['active'], g['profile_url'],
            ))

            if cur.rowcount > 0:
                groups_inserted += 1
                group_id = cur.lastrowid
            else:
                cur.execute('SELECT id FROM groups WHERE name = ?', (g['name'],))
                row = cur.fetchone()
                group_id = row[0] if row else None
                if not group_id:
                    continue

            for m in g.get('members', []):
                try:
                    cur.execute('''
                        INSERT OR IGNORE INTO artists
                        (stage_name, real_name, korean_name, group_id, birth_date,
                         position, nationality, gender, difficulty, image_url)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        m['stage_name'], m.get('real_name'), m.get('korean_name'),
                        group_id, m.get('birth_date'), m.get('position'),
                        m.get('nationality'), m.get('gender', g['gender']),
                        g['difficulty'], m.get('image_url'),
                    ))
                    if cur.rowcount > 0:
                        artists_inserted += 1
                except sqlite3.Error as e:
                    log.warning(f'  DB error for artist {m["stage_name"]}: {e}')

        except sqlite3.Error as e:
            log.warning(f'DB error for group {g["name"]}: {e}')

    conn.commit()
    conn.close()
    return groups_inserted, artists_inserted


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    log.info('=' * 60)
    log.info('K-pop Roster Scraper — Phase 1 (v2)')
    log.info('=' * 60)

    all_groups_data = []
    total_links = 0

    for gender in ('male', 'female'):
        links = get_group_links(gender)
        total_links += len(links)

        log.info(f'Processing {len(links)} {gender} groups...')

        for i, link in enumerate(links):
            name = link['name']
            url = link['url']

            log.info(f'  [{i+1}/{len(links)}] {name}')

            result = scrape_group_profile(url, name, gender)
            if result:
                if result.get('debut_year'):
                    n_members = len(result.get('members', []))
                    log.info(
                        f'    → {result["debut_year"]} | gen {result["generation"]} | '
                        f'diff {result["difficulty"]} | '
                        f'{result["company"] or "?"} | {n_members} members'
                    )
                    all_groups_data.append(result)
                else:
                    log.info(f'    → No debut year found, skipping')
            else:
                log.warning(f'    → Failed to fetch/parse')

    # Write to database
    log.info('')
    log.info('Writing to database...')
    groups_n, artists_n = write_to_db(all_groups_data)

    # Summary
    log.info('')
    log.info('=' * 60)
    log.info('SUMMARY')
    log.info('=' * 60)
    log.info(f'Total group links found: {total_links}')
    log.info(f'Groups with data parsed: {len(all_groups_data)}')
    log.info(f'Groups inserted to DB:   {groups_n}')
    log.info(f'Artists inserted to DB:  {artists_n}')

    gen_counts: dict[int, int] = {}
    for g in all_groups_data:
        gen = g.get('generation') or 0
        gen_counts[gen] = gen_counts.get(gen, 0) + 1
    for gen in sorted(gen_counts):
        label = f'Gen {gen}' if gen else 'Unknown'
        log.info(f'  {label}: {gen_counts[gen]} groups')

    # Verify DB totals
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM groups')
    total_groups = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM artists')
    total_artists = c.fetchone()[0]
    c.execute('SELECT COUNT(*) FROM artists WHERE image_url IS NOT NULL')
    with_images = c.fetchone()[0]
    conn.close()

    log.info(f'')
    log.info(f'DB totals: {total_groups} groups, {total_artists} artists ({with_images} with images)')


if __name__ == '__main__':
    main()
