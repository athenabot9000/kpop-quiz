#!/usr/bin/env python3
"""
K-Pop Quiz Question Generator
Generates hundreds of diverse text-based questions from the roster data in SQLite.
"""

import sqlite3
import json
import random
import re
from collections import defaultdict

DB_PATH = "/home/athena/kpop-quiz/app/data/kpop_quiz.db"
random.seed(42)  # Deterministic

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def load_data(conn):
    """Load all groups and artists into structured dicts."""
    groups = {}
    for row in conn.execute("SELECT * FROM groups"):
        g = dict(row)
        g['members'] = []
        groups[g['id']] = g
    
    artists = []
    for row in conn.execute("SELECT * FROM artists"):
        a = dict(row)
        artists.append(a)
        gid = a['group_id']
        if gid and gid in groups:
            groups[gid]['members'].append(a)
    
    return groups, artists

def parse_positions(position_str):
    """Parse a position string like 'Leader, Main Vocalist' into individual roles."""
    if not position_str or position_str in ('–', 'N/A', ''):
        return []
    return [p.strip() for p in position_str.split(',')]

def has_role(artist, role_keyword):
    """Check if an artist has a role containing the keyword (case-insensitive)."""
    positions = parse_positions(artist.get('position', ''))
    return any(role_keyword.lower() in p.lower() for p in positions)

def pick_wrong_answers(correct, pool, n=3):
    """Pick n wrong answers from pool, excluding correct answer."""
    candidates = [x for x in pool if x != correct and x]
    if len(candidates) < n:
        return None  # Not enough wrong answers
    return random.sample(candidates, n)

def difficulty_for_group(group):
    """Return difficulty 1-5. DB difficulty is popularity (higher = more popular).
    For quiz: popular groups = easier questions."""
    db_diff = group.get('difficulty', 1) or 1
    # Map: db_diff 5->1, 4->1, 3->2, 2->2, 1->3 (base difficulty)
    mapping = {5: 1, 4: 1, 3: 2, 2: 2, 1: 3}
    return mapping.get(db_diff, 3)

def make_question(q_text, correct, wrong_answers, category, difficulty, metadata=None):
    """Create a question dict matching the DB schema."""
    return {
        'type': 'text',
        'difficulty': max(1, min(5, difficulty)),
        'category': category,
        'question_text': q_text,
        'correct_answer': str(correct),
        'metadata_json': json.dumps(metadata or {}),
    }

def generate_leader_questions(groups, all_group_names):
    """Who is the leader of [group]?"""
    questions = []
    for gid, g in groups.items():
        leaders = [m for m in g['members'] if has_role(m, 'leader')]
        if len(leaders) == 1:
            leader = leaders[0]
            # Wrong answers: other members from same group
            other_members = [m['stage_name'] for m in g['members'] if m['id'] != leader['id']]
            if len(other_members) >= 3:
                wrong = random.sample(other_members, 3)
            else:
                continue
            q = make_question(
                f"Who is the leader of {g['name']}?",
                leader['stage_name'],
                wrong,
                'member',
                difficulty_for_group(g),
                {'wrong_answers': wrong, 'group_id': gid}
            )
            questions.append(q)
    return questions

def generate_member_count_questions(groups):
    """How many members does [group] have?"""
    questions = []
    for gid, g in groups.items():
        count = len(g['members'])
        if count < 3:
            continue
        # Wrong answers: nearby numbers
        possible_wrong = [x for x in range(max(1, count-3), count+4) if x != count and x > 0]
        if len(possible_wrong) < 3:
            continue
        wrong = random.sample(possible_wrong, 3)
        wrong = [str(w) for w in wrong]
        q = make_question(
            f"How many members does {g['name']} have?",
            str(count),
            wrong,
            'member',
            difficulty_for_group(g),
            {'wrong_answers': wrong, 'group_id': gid}
        )
        questions.append(q)
    return questions

def generate_position_questions(groups, all_artists):
    """Which member of [group] has the position of [role]?"""
    questions = []
    target_roles = [
        ('Main Vocalist', 'main vocalist'),
        ('Main Rapper', 'main rapper'),
        ('Main Dancer', 'main dancer'),
        ('Maknae', 'maknae (youngest member)'),
    ]
    for gid, g in groups.items():
        if len(g['members']) < 4:
            continue
        for role_key, role_display in target_roles:
            matches = [m for m in g['members'] if has_role(m, role_key)]
            if len(matches) == 1:
                correct = matches[0]
                other_members = [m['stage_name'] for m in g['members'] if m['id'] != correct['id']]
                if len(other_members) < 3:
                    continue
                wrong = random.sample(other_members, 3)
                q = make_question(
                    f"Which member of {g['name']} is the {role_display}?",
                    correct['stage_name'],
                    wrong,
                    'member',
                    difficulty_for_group(g) + 1,
                    {'wrong_answers': wrong, 'group_id': gid}
                )
                questions.append(q)
    return questions

def generate_member_group_questions(groups, all_artists):
    """[Member] is a member of which group?"""
    questions = []
    all_group_names = [g['name'] for g in groups.values() if len(g['members']) >= 3]
    
    for gid, g in groups.items():
        if len(g['members']) < 3:
            continue
        # Pick a couple members per group
        sample_members = g['members'][:3]
        for member in sample_members:
            if not member['stage_name'] or member['stage_name'] in ('–', 'N/A'):
                continue
            # Use same-gender groups for wrong answers
            same_gender_groups = [
                gr['name'] for gr in groups.values() 
                if gr['id'] != gid and gr['gender'] == g['gender'] and len(gr['members']) >= 3
            ]
            if len(same_gender_groups) < 3:
                continue
            wrong = random.sample(same_gender_groups, 3)
            q = make_question(
                f"{member['stage_name']} is a member of which group?",
                g['name'],
                wrong,
                'member',
                difficulty_for_group(g),
                {'wrong_answers': wrong, 'artist_id': member['id']}
            )
            questions.append(q)
    return questions

def generate_real_name_questions(groups, all_artists):
    """What is [member]'s real name?"""
    questions = []
    # Collect all real names for wrong answer pool
    all_real_names = [
        a['real_name'] for a in all_artists 
        if a['real_name'] and a['real_name'] not in ('–', 'N/A', '') 
        and a['real_name'] != a['stage_name']
    ]
    
    for gid, g in groups.items():
        if len(g['members']) < 3:
            continue
        for member in g['members']:
            if (not member['real_name'] or member['real_name'] in ('–', 'N/A', '')
                or member['real_name'] == member['stage_name']):
                continue
            wrong = pick_wrong_answers(member['real_name'], all_real_names, 3)
            if not wrong:
                continue
            q = make_question(
                f"What is {member['stage_name']} from {g['name']}'s real name?",
                member['real_name'],
                wrong,
                'member',
                difficulty_for_group(g) + 1,
                {'wrong_answers': wrong, 'artist_id': member['id']}
            )
            questions.append(q)
    return questions

def generate_nationality_questions(groups):
    """Which [group] member was born in [country]?"""
    questions = []
    for gid, g in groups.items():
        if len(g['members']) < 4:
            continue
        # Find members with non-Korean nationality
        nationality_map = defaultdict(list)
        for m in g['members']:
            nat = m.get('nationality', '')
            if nat and nat not in ('', '–', 'N/A'):
                nationality_map[nat].append(m)
        
        for nat, members in nationality_map.items():
            if nat.lower() in ('korean', 'south korean'):
                continue
            if len(members) == 1:
                correct = members[0]
                other_members = [m['stage_name'] for m in g['members'] if m['id'] != correct['id']]
                if len(other_members) < 3:
                    continue
                wrong = random.sample(other_members, 3)
                # Clean up nationality display for natural grammar
                nat_display = nat
                q = make_question(
                    f"Which member of {g['name']} is {nat_display}?",
                    correct['stage_name'],
                    wrong,
                    'member',
                    difficulty_for_group(g) + 1,
                    {'wrong_answers': wrong, 'group_id': gid}
                )
                questions.append(q)
    return questions

def generate_debut_year_questions(groups):
    """What year did [group] debut?"""
    questions = []
    for gid, g in groups.items():
        year = g.get('debut_year')
        if not year or len(g['members']) < 3:
            continue
        # Wrong answers: nearby years
        possible_wrong = [y for y in range(year - 3, year + 4) if y != year and y >= 1996 and y <= 2026]
        if len(possible_wrong) < 3:
            continue
        wrong = [str(w) for w in random.sample(possible_wrong, 3)]
        q = make_question(
            f"What year did {g['name']} debut?",
            str(year),
            wrong,
            'debut',
            difficulty_for_group(g),
            {'wrong_answers': wrong, 'group_id': gid}
        )
        questions.append(q)
    return questions

def generate_which_group_debuted_questions(groups):
    """Which of these groups debuted in [year]?"""
    questions = []
    year_groups = defaultdict(list)
    for gid, g in groups.items():
        if g.get('debut_year') and len(g['members']) >= 3:
            year_groups[g['debut_year']].append(g)
    
    for year, glist in year_groups.items():
        if len(glist) < 1:
            continue
        correct_group = random.choice(glist)
        # Wrong answers: groups from different years
        other_groups = [
            gr['name'] for gr in groups.values() 
            if gr.get('debut_year') != year 
            and gr['gender'] == correct_group['gender']
            and len(gr['members']) >= 3
        ]
        if len(other_groups) < 3:
            continue
        wrong = random.sample(other_groups, 3)
        q = make_question(
            f"Which of these groups debuted in {year}?",
            correct_group['name'],
            wrong,
            'debut',
            difficulty_for_group(correct_group) + 1,
            {'wrong_answers': wrong}
        )
        questions.append(q)
    return questions

def generate_company_questions(groups):
    """Which company manages [group]?"""
    questions = []
    all_companies = list(set(
        g['company'] for g in groups.values() 
        if g.get('company') and g['company'] not in ('', '–', 'N/A')
        and len(g['company']) < 50  # Skip overly long/messy company names
    ))
    
    for gid, g in groups.items():
        company = g.get('company')
        if not company or company in ('', '–', 'N/A') or len(company) > 50:
            continue
        if len(g['members']) < 3:
            continue
        wrong = pick_wrong_answers(company, all_companies, 3)
        if not wrong:
            continue
        q = make_question(
            f"Which company manages {g['name']}?",
            company,
            wrong,
            'group_fact',
            difficulty_for_group(g) + 1,
            {'wrong_answers': wrong, 'group_id': gid}
        )
        questions.append(q)
    return questions

def generate_most_members_questions(groups):
    """Which of these groups has the most members?"""
    questions = []
    eligible = [g for g in groups.values() if len(g['members']) >= 4]
    # Sort by actual member count
    eligible.sort(key=lambda g: len(g['members']), reverse=True)
    
    # Generate pairwise comparisons
    used = set()
    for i in range(min(50, len(eligible))):
        correct = eligible[i]
        # Find groups with fewer members for wrong answers
        fewer = [g for g in eligible if len(g['members']) < len(correct['members']) and g['id'] != correct['id']]
        if len(fewer) < 3:
            continue
        wrong_groups = random.sample(fewer[:20], 3)
        wrong = [g['name'] for g in wrong_groups]
        key = correct['name']
        if key in used:
            continue
        used.add(key)
        q = make_question(
            f"Which of these groups has the most members?",
            correct['name'],
            wrong,
            'group_fact',
            3,
            {'wrong_answers': wrong, 'correct_count': len(correct['members'])}
        )
        questions.append(q)
    return questions

def generate_not_member_questions(groups, all_artists):
    """Which group is [member] NOT a part of?"""
    questions = []
    for gid, g in groups.items():
        if len(g['members']) < 4:
            continue
        for member in g['members'][:2]:
            if not member['stage_name'] or member['stage_name'] in ('–', 'N/A'):
                continue
            # Correct answer: a group they're NOT in
            other_groups = [
                gr['name'] for gr in groups.values() 
                if gr['id'] != gid and gr['gender'] == g['gender'] and len(gr['members']) >= 3
            ]
            if len(other_groups) < 1:
                continue
            correct_not_group = random.choice(other_groups)
            # Wrong answers: the group they ARE in + 2 other groups
            wrong = [g['name']]
            more_groups = [gr for gr in other_groups if gr != correct_not_group]
            if len(more_groups) < 2:
                continue
            wrong.extend(random.sample(more_groups, 2))
            q = make_question(
                f"Which group is {member['stage_name']} NOT a part of?",
                correct_not_group,
                wrong,
                'group_fact',
                difficulty_for_group(g),
                {'wrong_answers': wrong, 'artist_id': member['id']}
            )
            questions.append(q)
    return questions

def generate_not_position_questions(groups, all_artists):
    """Which of these idols is NOT a [position]?"""
    questions = []
    role_categories = ['rapper', 'vocalist', 'dancer']
    
    for role in role_categories:
        role_artists = [a for a in all_artists if has_role(a, role) and a.get('group_id')]
        non_role_artists = [
            a for a in all_artists 
            if not has_role(a, role) 
            and a.get('group_id')
            and a.get('position') 
            and a['position'] not in ('–', 'N/A', '')
        ]
        
        if len(role_artists) < 3 or len(non_role_artists) < 1:
            continue
        
        for _ in range(min(30, len(non_role_artists))):
            correct = random.choice(non_role_artists)
            if not correct['stage_name'] or correct['stage_name'] in ('–', 'N/A'):
                continue
            wrong_pool = [a['stage_name'] for a in role_artists if a['stage_name'] != correct['stage_name']]
            if len(wrong_pool) < 3:
                continue
            wrong = random.sample(wrong_pool, 3)
            gname = groups.get(correct['group_id'], {}).get('name', 'Unknown')
            q = make_question(
                f"Which of these idols is NOT a {role}?",
                f"{correct['stage_name']} ({gname})",
                [f"{w}" for w in wrong],
                'cross_group',
                3,
                {'wrong_answers': wrong}
            )
            questions.append(q)
    return questions

def generate_birthday_month_questions(groups, all_artists):
    """Which of these idols shares a birthday month with [member]?"""
    questions = []
    month_map = defaultdict(list)
    for a in all_artists:
        bd = a.get('birth_date', '')
        if bd and len(bd) >= 7 and bd != '–':
            try:
                month = int(bd.split('-')[1])
                month_map[month].append(a)
            except (ValueError, IndexError):
                continue
    
    month_names = {
        1: 'January', 2: 'February', 3: 'March', 4: 'April',
        5: 'May', 6: 'June', 7: 'July', 8: 'August',
        9: 'September', 10: 'October', 11: 'November', 12: 'December'
    }
    
    for month, artists_in_month in month_map.items():
        if len(artists_in_month) < 2:
            continue
        other_months_artists = [a for m, alist in month_map.items() if m != month for a in alist]
        if len(other_months_artists) < 3:
            continue
        
        for _ in range(min(5, len(artists_in_month) // 2)):
            pair = random.sample(artists_in_month, 2)
            reference = pair[0]
            correct = pair[1]
            ref_group = groups.get(reference['group_id'], {}).get('name', '')
            cor_group = groups.get(correct['group_id'], {}).get('name', '')
            
            if not ref_group or not cor_group or reference['group_id'] == correct['group_id']:
                continue
            
            wrong_artists = random.sample(other_months_artists, 3)
            wrong = [f"{a['stage_name']} ({groups.get(a['group_id'], {}).get('name', '?')})" for a in wrong_artists]
            
            q = make_question(
                f"Which of these idols shares a birthday month ({month_names[month]}) with {reference['stage_name']} of {ref_group}?",
                f"{correct['stage_name']} ({cor_group})",
                wrong,
                'cross_group',
                4,
                {'wrong_answers': wrong, 'month': month}
            )
            questions.append(q)
    return questions

def generate_generation_questions(groups):
    """Which generation K-pop group is [group]?"""
    questions = []
    gen_labels = {1: '1st', 2: '2nd', 3: '3rd', 4: '4th', 5: '5th'}
    
    for gid, g in groups.items():
        gen = g.get('generation')
        if not gen or gen not in gen_labels or len(g['members']) < 3:
            continue
        correct = f"{gen_labels[gen]} generation"
        wrong = [f"{gen_labels[v]} generation" for v in gen_labels if v != gen]
        if len(wrong) < 3:
            continue
        wrong = random.sample(wrong, 3)
        q = make_question(
            f"Which generation K-pop group is {g['name']}?",
            correct,
            wrong,
            'group_fact',
            difficulty_for_group(g) + 1,
            {'wrong_answers': wrong, 'group_id': gid}
        )
        questions.append(q)
    return questions

def generate_gender_questions(groups):
    """Is [group] a boy group or girl group?"""
    questions = []
    for gid, g in groups.items():
        if len(g['members']) < 3:
            continue
        gender = g.get('gender', '')
        if gender == 'male':
            correct = 'Boy group'
            wrong = ['Girl group', 'Co-ed group', 'Solo artist']
        elif gender == 'female':
            correct = 'Girl group'
            wrong = ['Boy group', 'Co-ed group', 'Solo artist']
        else:
            continue
        q = make_question(
            f"Is {g['name']} a boy group or girl group?",
            correct,
            wrong,
            'group_fact',
            max(1, difficulty_for_group(g) - 1),
            {'wrong_answers': wrong, 'group_id': gid}
        )
        questions.append(q)
    return questions

def generate_how_many_from_country(groups):
    """How many members of [group] are from [country]?"""
    questions = []
    for gid, g in groups.items():
        if len(g['members']) < 4:
            continue
        nationality_counts = defaultdict(int)
        for m in g['members']:
            nat = m.get('nationality', '')
            if nat and nat not in ('', '–', 'N/A'):
                nationality_counts[nat] += 1
        
        for nat, count in nationality_counts.items():
            if nat.lower() in ('korean', 'south korean'):
                continue
            if count >= 1 and count < len(g['members']):
                possible_wrong = [str(x) for x in range(0, min(count + 4, len(g['members']) + 1)) if x != count]
                if len(possible_wrong) < 3:
                    continue
                wrong = random.sample(possible_wrong, 3)
                nat_display = nat
                q = make_question(
                    f"How many members of {g['name']} are {nat_display}?",
                    str(count),
                    wrong,
                    'group_fact',
                    difficulty_for_group(g) + 2,
                    {'wrong_answers': wrong, 'group_id': gid}
                )
                questions.append(q)
    return questions

def generate_odd_one_out_group(groups):
    """Which of these is NOT a [gender] group?"""
    questions = []
    male_groups = [g for g in groups.values() if g['gender'] == 'male' and len(g['members']) >= 3]
    female_groups = [g for g in groups.values() if g['gender'] == 'female' and len(g['members']) >= 3]
    
    for _ in range(20):
        if len(male_groups) >= 3 and len(female_groups) >= 1:
            # "Which is NOT a boy group?"
            correct = random.choice(female_groups)
            wrong_groups = random.sample(male_groups, 3)
            wrong = [g['name'] for g in wrong_groups]
            q = make_question(
                "Which of these is NOT a boy group?",
                correct['name'],
                wrong,
                'cross_group',
                2,
                {'wrong_answers': wrong}
            )
            questions.append(q)
        
        if len(female_groups) >= 3 and len(male_groups) >= 1:
            # "Which is NOT a girl group?"
            correct = random.choice(male_groups)
            wrong_groups = random.sample(female_groups, 3)
            wrong = [g['name'] for g in wrong_groups]
            q = make_question(
                "Which of these is NOT a girl group?",
                correct['name'],
                wrong,
                'cross_group',
                2,
                {'wrong_answers': wrong}
            )
            questions.append(q)
    
    return questions

def generate_stage_name_from_real(groups, all_artists):
    """What is [real name]'s stage name? (reverse of real name question)"""
    questions = []
    for gid, g in groups.items():
        if len(g['members']) < 3:
            continue
        for member in g['members']:
            if (not member['real_name'] or member['real_name'] in ('–', 'N/A', '')
                or member['real_name'] == member['stage_name']
                or not member['stage_name'] or member['stage_name'] in ('–', 'N/A')):
                continue
            other_stage_names = [m['stage_name'] for m in g['members'] 
                                if m['id'] != member['id'] and m['stage_name'] not in ('–', 'N/A', '')]
            if len(other_stage_names) < 3:
                # Use names from other groups
                other_stage_names = [a['stage_name'] for a in all_artists 
                                    if a['group_id'] != gid and a['stage_name'] not in ('–', 'N/A', '')]
            if len(other_stage_names) < 3:
                continue
            wrong = random.sample(other_stage_names[:50], 3)
            q = make_question(
                f"What is {member['real_name']}'s stage name in {g['name']}?",
                member['stage_name'],
                wrong,
                'member',
                difficulty_for_group(g) + 2,
                {'wrong_answers': wrong, 'artist_id': member['id']}
            )
            questions.append(q)
    return questions

def deduplicate_questions(questions):
    """Remove duplicates based on question text."""
    seen = set()
    unique = []
    for q in questions:
        key = q['question_text'].strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(q)
    return unique

def cap_per_category(questions, max_per_generator=None):
    """Cap questions per category to maintain balance."""
    return questions  # We'll handle this at insert time if needed

def insert_questions(conn, questions):
    """Insert questions into the database."""
    cursor = conn.cursor()
    count = 0
    for q in questions:
        try:
            cursor.execute("""
                INSERT INTO questions (type, difficulty, category, question_text, correct_answer, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                q['type'],
                q['difficulty'],
                q['category'],
                q['question_text'],
                q['correct_answer'],
                q['metadata_json'],
            ))
            count += 1
        except sqlite3.IntegrityError as e:
            print(f"  Skip duplicate: {e}")
    conn.commit()
    return count

def main():
    conn = get_db()
    groups, all_artists = load_data(conn)
    
    print(f"Loaded {len(groups)} groups, {len(all_artists)} artists")
    print(f"Groups with 3+ members: {sum(1 for g in groups.values() if len(g['members']) >= 3)}")
    print()
    
    # Generate questions by category
    generators = [
        ("Leader questions", generate_leader_questions, (groups, [g['name'] for g in groups.values()])),
        ("Member count", generate_member_count_questions, (groups,)),
        ("Position questions", generate_position_questions, (groups, all_artists)),
        ("Member→Group", generate_member_group_questions, (groups, all_artists)),
        ("Real name", generate_real_name_questions, (groups, all_artists)),
        ("Nationality", generate_nationality_questions, (groups,)),
        ("Debut year", generate_debut_year_questions, (groups,)),
        ("Which debuted in year", generate_which_group_debuted_questions, (groups,)),
        ("Company", generate_company_questions, (groups,)),
        ("Most members", generate_most_members_questions, (groups,)),
        ("NOT a member of", generate_not_member_questions, (groups, all_artists)),
        ("NOT a position", generate_not_position_questions, (groups, all_artists)),
        ("Birthday month", generate_birthday_month_questions, (groups, all_artists)),
        ("Generation", generate_generation_questions, (groups,)),
        ("Gender", generate_gender_questions, (groups,)),
        ("How many from country", generate_how_many_from_country, (groups,)),
        ("Odd one out (group type)", generate_odd_one_out_group, (groups,)),
        ("Stage name from real", generate_stage_name_from_real, (groups, all_artists)),
    ]
    
    all_questions = []
    category_counts = {}
    
    for name, gen_func, args in generators:
        qs = gen_func(*args)
        print(f"  {name}: {len(qs)} generated")
        category_counts[name] = len(qs)
        all_questions.extend(qs)
    
    print(f"\nTotal before dedup: {len(all_questions)}")
    all_questions = deduplicate_questions(all_questions)
    print(f"Total after dedup: {len(all_questions)}")
    
    # Cap some over-represented categories if total is way above target
    # We want balance — cap member→group and real name at 200 each
    category_caps = {
        'member': 350,  # total for member category
        'debut': 100,
        'group_fact': 200,
        'cross_group': 150,
    }
    
    by_category = defaultdict(list)
    for q in all_questions:
        by_category[q['category']].append(q)
    
    capped_questions = []
    for cat, qs in by_category.items():
        cap = category_caps.get(cat, 300)
        random.shuffle(qs)
        capped_questions.extend(qs[:cap])
    
    print(f"Total after capping: {len(capped_questions)}")
    
    # Shuffle for variety
    random.shuffle(capped_questions)
    
    # Get existing question count
    existing_count = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    print(f"\nExisting questions in DB: {existing_count}")
    
    # Check for existing text duplicates
    existing_texts = set()
    for row in conn.execute("SELECT question_text FROM questions"):
        existing_texts.add(row[0].strip().lower() if row[0] else '')
    
    new_questions = [q for q in capped_questions if q['question_text'].strip().lower() not in existing_texts]
    print(f"New questions (after filtering existing): {len(new_questions)}")
    
    inserted = insert_questions(conn, new_questions)
    print(f"Inserted: {inserted}")
    
    # Final stats
    print("\n=== Final Statistics ===")
    total = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    print(f"Total questions in DB: {total}")
    
    print("\nBy category:")
    for row in conn.execute("SELECT category, COUNT(*) FROM questions GROUP BY category ORDER BY COUNT(*) DESC"):
        print(f"  {row[0]}: {row[1]}")
    
    print("\nBy difficulty:")
    for row in conn.execute("SELECT difficulty, COUNT(*) FROM questions GROUP BY difficulty ORDER BY difficulty"):
        print(f"  Level {row[0]}: {row[1]}")
    
    print("\nBy type:")
    for row in conn.execute("SELECT type, COUNT(*) FROM questions GROUP BY type ORDER BY COUNT(*) DESC"):
        print(f"  {row[0]}: {row[1]}")
    
    conn.close()

if __name__ == '__main__':
    main()
