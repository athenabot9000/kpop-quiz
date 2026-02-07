#!/usr/bin/env python3
"""Seed the database with sample data for app development."""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'kpop_quiz.db')

GROUPS = [
    ("TWICE", "트와이스", "JYP Entertainment", 2015, None, 3, "female", 9, 1, 1),
    ("BLACKPINK", "블랙핑크", "YG Entertainment", 2016, None, 3, "female", 4, 1, 1),
    ("BTS", "방탄소년단", "BIGHIT MUSIC", 2013, None, 3, "male", 7, 1, 1),
    ("Stray Kids", "스트레이 키즈", "JYP Entertainment", 2018, None, 4, "male", 8, 1, 1),
    ("NewJeans", "뉴진스", "ADOR", 2022, None, 4, "female", 5, 1, 1),
    ("aespa", "에스파", "SM Entertainment", 2020, None, 4, "female", 4, 1, 1),
    ("IVE", "아이브", "Starship Entertainment", 2021, None, 4, "female", 6, 1, 1),
    ("LE SSERAFIM", "르세라핌", "SOURCE MUSIC", 2022, None, 4, "female", 5, 1, 1),
    ("EXO", "엑소", "SM Entertainment", 2012, None, 3, "male", 9, 2, 1),
    ("Red Velvet", "레드벨벳", "SM Entertainment", 2014, None, 3, "female", 5, 2, 1),
    ("SEVENTEEN", "세븐틴", "PLEDIS Entertainment", 2015, None, 3, "male", 13, 2, 1),
    ("(G)I-DLE", "(여자)아이들", "CUBE Entertainment", 2018, None, 4, "female", 5, 2, 1),
    ("ITZY", "있지", "JYP Entertainment", 2019, None, 4, "female", 5, 2, 1),
    ("TXT", "투모로우바이투게더", "BIGHIT MUSIC", 2019, None, 4, "male", 5, 2, 1),
    ("ENHYPEN", "엔하이픈", "BELIFT LAB", 2020, None, 4, "male", 7, 2, 1),
    ("ATEEZ", "에이티즈", "KQ Entertainment", 2018, None, 4, "male", 8, 2, 1),
    ("MAMAMOO", "마마무", "RBW", 2014, None, 3, "female", 4, 2, 1),
    ("GOT7", "갓세븐", "JYP Entertainment", 2014, None, 3, "male", 7, 2, 1),
    ("NMIXX", "엔믹스", "JYP Entertainment", 2022, None, 4, "female", 6, 2, 1),
    ("RIIZE", "라이즈", "SM Entertainment", 2023, None, 5, "male", 6, 2, 1),
]

ARTISTS = [
    # TWICE members
    ("Jihyo", "Park Ji-hyo", "박지효", "TWICE", "1997-02-01", "Leader, Main Vocalist", "Korean", "female"),
    ("Nayeon", "Im Na-yeon", "임나연", "TWICE", "1995-09-22", "Lead Vocalist, Center", "Korean", "female"),
    ("Jeongyeon", "Yoo Jeong-yeon", "유정연", "TWICE", "1996-11-01", "Lead Vocalist", "Korean", "female"),
    ("Momo", "Hirai Momo", "히라이 모모", "TWICE", "1996-11-09", "Main Dancer, Sub-Vocalist", "Japanese", "female"),
    ("Sana", "Minatozaki Sana", "미나토자키 사나", "TWICE", "1996-12-29", "Sub-Vocalist", "Japanese", "female"),
    ("Mina", "Myoui Mina", "묘이 미나", "TWICE", "1997-03-24", "Main Dancer, Sub-Vocalist", "Japanese-American", "female"),
    ("Dahyun", "Kim Da-hyun", "김다현", "TWICE", "1998-05-28", "Lead Rapper", "Korean", "female"),
    ("Chaeyoung", "Son Chae-young", "손채영", "TWICE", "1999-04-23", "Main Rapper", "Korean", "female"),
    ("Tzuyu", "Chou Tzu-yu", "저우쯔위", "TWICE", "1999-06-14", "Lead Dancer, Sub-Vocalist, Visual", "Taiwanese", "female"),
    # BLACKPINK members
    ("Jisoo", "Kim Ji-soo", "김지수", "BLACKPINK", "1995-01-03", "Lead Vocalist, Visual", "Korean", "female"),
    ("Jennie", "Kim Jennie", "김제니", "BLACKPINK", "1996-01-16", "Main Rapper, Lead Vocalist", "Korean", "female"),
    ("Rosé", "Park Chae-young", "박채영", "BLACKPINK", "1997-02-11", "Main Vocalist, Lead Dancer", "Korean-New Zealander", "female"),
    ("Lisa", "Lalisa Manobal", "리사", "BLACKPINK", "1997-03-27", "Main Dancer, Lead Rapper", "Thai", "female"),
    # BTS members
    ("RM", "Kim Nam-joon", "김남준", "BTS", "1994-09-12", "Leader, Main Rapper", "Korean", "male"),
    ("Jin", "Kim Seok-jin", "김석진", "BTS", "1992-12-04", "Sub-Vocalist, Visual", "Korean", "male"),
    ("Suga", "Min Yoon-gi", "민윤기", "BTS", "1993-03-09", "Lead Rapper", "Korean", "male"),
    ("J-Hope", "Jung Ho-seok", "정호석", "BTS", "1994-02-18", "Main Dancer, Sub-Rapper", "Korean", "male"),
    ("Jimin", "Park Ji-min", "박지민", "BTS", "1995-10-13", "Main Dancer, Lead Vocalist", "Korean", "male"),
    ("V", "Kim Tae-hyung", "김태형", "BTS", "1995-12-30", "Lead Dancer, Sub-Vocalist, Visual", "Korean", "male"),
    ("Jungkook", "Jeon Jung-kook", "전정국", "BTS", "1997-09-01", "Main Vocalist, Lead Dancer, Sub-Rapper, Center", "Korean", "male"),
    # NewJeans members
    ("Minji", "Kim Min-ji", "김민지", "NewJeans", "2004-05-07", "Lead Vocalist, Lead Dancer", "Korean", "female"),
    ("Hanni", "Pham Ngoc Han", "팜응옥한", "NewJeans", "2004-10-06", "Sub-Vocalist", "Vietnamese-Australian", "female"),
    ("Danielle", "Mo Hye-in", "모혜인", "NewJeans", "2005-04-11", "Sub-Vocalist", "Korean-Australian", "female"),
    ("Haerin", "Kang Hae-rin", "강해린", "NewJeans", "2006-05-15", "Sub-Vocalist", "Korean", "female"),
    ("Hyein", "Lee Hye-in", "이혜인", "NewJeans", "2008-04-21", "Sub-Vocalist, Maknae", "Korean", "female"),
    # Stray Kids members
    ("Bang Chan", "Christopher Bang", "방찬", "Stray Kids", "1997-10-03", "Leader, Main Rapper, Sub-Vocalist", "Korean-Australian", "male"),
    ("Lee Know", "Lee Min-ho", "이민호", "Stray Kids", "1998-10-25", "Main Dancer, Sub-Vocalist", "Korean", "male"),
    ("Changbin", "Seo Chang-bin", "서창빈", "Stray Kids", "1999-08-11", "Main Rapper", "Korean", "male"),
    ("Hyunjin", "Hwang Hyun-jin", "황현진", "Stray Kids", "2000-03-20", "Lead Dancer, Sub-Rapper, Visual", "Korean", "male"),
    ("Han", "Han Ji-sung", "한지성", "Stray Kids", "2000-09-14", "Main Rapper, Lead Vocalist", "Korean", "male"),
    ("Felix", "Lee Yong-bok", "이용복", "Stray Kids", "2000-09-15", "Lead Dancer, Sub-Rapper", "Korean-Australian", "male"),
    ("Seungmin", "Kim Seung-min", "김승민", "Stray Kids", "2000-09-22", "Lead Vocalist", "Korean", "male"),
    ("I.N", "Yang Jeong-in", "양정인", "Stray Kids", "2001-02-08", "Sub-Vocalist, Maknae", "Korean", "male"),
    # aespa members
    ("Karina", "Yoo Ji-min", "유지민", "aespa", "2000-04-11", "Leader, Main Dancer, Lead Vocalist", "Korean", "female"),
    ("Giselle", "Uchinaga Aeri", "우치나가 아에리", "aespa", "2000-10-30", "Main Rapper, Sub-Vocalist", "Korean-Japanese", "female"),
    ("Winter", "Kim Min-jeong", "김민정", "aespa", "2001-01-01", "Lead Vocalist, Lead Dancer", "Korean", "female"),
    ("Ningning", "Ning Yi-zhuo", "닝이줘", "aespa", "2002-10-23", "Main Vocalist", "Chinese", "female"),
]

SONGS = [
    ("Cheer Up", "TWICE", 2016, 1, "PAGE TWO"),
    ("TT", "TWICE", 2016, 1, "TWICEcoaster: LANE 1"),
    ("What is Love?", "TWICE", 2018, 1, "What is Love?"),
    ("Fancy", "TWICE", 2019, 1, "FANCY YOU"),
    ("Feel Special", "TWICE", 2019, 1, "Feel Special"),
    ("DDU-DU DDU-DU", "BLACKPINK", 2018, 1, "SQUARE UP"),
    ("Kill This Love", "BLACKPINK", 2019, 1, "KILL THIS LOVE"),
    ("How You Like That", "BLACKPINK", 2020, 1, "THE ALBUM"),
    ("Lovesick Girls", "BLACKPINK", 2020, 1, "THE ALBUM"),
    ("Pink Venom", "BLACKPINK", 2022, 1, "BORN PINK"),
    ("Dynamite", "BTS", 2020, 1, "BE"),
    ("Butter", "BTS", 2021, 1, "Butter"),
    ("Boy With Luv", "BTS", 2019, 1, "MAP OF THE SOUL: PERSONA"),
    ("Blood Sweat & Tears", "BTS", 2016, 1, "WINGS"),
    ("Spring Day", "BTS", 2017, 1, "You Never Walk Alone"),
    ("God's Menu", "Stray Kids", 2020, 1, "GO生"),
    ("MANIAC", "Stray Kids", 2022, 1, "ODDINARY"),
    ("S-Class", "Stray Kids", 2023, 1, "★★★★★"),
    ("Attention", "NewJeans", 2022, 1, "New Jeans"),
    ("Hype Boy", "NewJeans", 2022, 1, "New Jeans"),
    ("Super Shy", "NewJeans", 2023, 1, "Get Up"),
    ("Ditto", "NewJeans", 2022, 1, "Ditto"),
    ("Next Level", "aespa", 2021, 1, "Next Level"),
    ("Savage", "aespa", 2021, 1, "Savage"),
    ("Supernova", "aespa", 2024, 1, "Armageddon"),
    ("ELEVEN", "IVE", 2021, 1, "ELEVEN"),
    ("Love Dive", "IVE", 2022, 1, "LOVE DIVE"),
    ("After LIKE", "IVE", 2022, 1, "After LIKE"),
    ("FEARLESS", "LE SSERAFIM", 2022, 1, "FEARLESS"),
    ("ANTIFRAGILE", "LE SSERAFIM", 2022, 1, "ANTIFRAGILE"),
    ("TOMBOY", "(G)I-DLE", 2022, 1, "I NEVER DIE"),
    ("Queencard", "(G)I-DLE", 2023, 1, "I feel"),
    ("WANNABE", "ITZY", 2020, 1, "IT'z ME"),
    ("LOCO", "ITZY", 2021, 1, "CRAZY IN LOVE"),
]

QUESTIONS = [
    # Text trivia - Difficulty 1 (Easy)
    ("text", 1, "debut", "Which group debuted in 2015 with the song 'Like Ooh-Ahh'?", "TWICE", '{"options_pool": "groups_female_gen3"}'),
    ("text", 1, "member", "How many members does BLACKPINK have?", "4", '{"options_pool": "numbers_small"}'),
    ("text", 1, "song", "Which group released the hit song 'Dynamite'?", "BTS", '{"options_pool": "groups_male_gen3"}'),
    ("text", 1, "member", "Who is the leader of TWICE?", "Jihyo", '{"options_pool": "members_twice"}'),
    ("text", 1, "group_fact", "Which company manages BLACKPINK?", "YG Entertainment", '{"options_pool": "companies"}'),
    ("text", 1, "song", "Which group sang 'How You Like That'?", "BLACKPINK", '{"options_pool": "groups_female_gen3"}'),
    ("text", 1, "member", "Which BTS member's stage name is 'V'?", "Kim Tae-hyung", '{"options_pool": "members_bts_real"}'),
    ("text", 1, "debut", "Which group debuted with the song 'ELEVEN' in 2021?", "IVE", '{"options_pool": "groups_female_gen4"}'),
    ("text", 1, "song", "Which group released 'Super Shy'?", "NewJeans", '{"options_pool": "groups_female_gen4"}'),
    ("text", 1, "member", "Which BLACKPINK member is from Thailand?", "Lisa", '{"options_pool": "members_blackpink"}'),
    # Text trivia - Difficulty 2 (Medium)  
    ("text", 2, "member", "Who is the main rapper of Stray Kids' producing unit 3RACHA?", "Changbin", '{"options_pool": "members_skz"}'),
    ("text", 2, "group_fact", "How many members does SEVENTEEN have?", "13", '{"options_pool": "numbers_medium"}'),
    ("text", 2, "song", "Which aespa song samples the 'Next Level' theme from Fast & Furious?", "Next Level", '{"options_pool": "songs_aespa"}'),
    ("text", 2, "member", "Which NewJeans member is Vietnamese-Australian?", "Hanni", '{"options_pool": "members_newjeans"}'),
    ("text", 2, "debut", "In what year did Stray Kids debut?", "2018", '{"options_pool": "years_2018"}'),
    ("text", 2, "member", "Which aespa member is Chinese?", "Ningning", '{"options_pool": "members_aespa"}'),
    ("text", 2, "group_fact", "Which group was formed through the survival show 'SIXTEEN'?", "TWICE", '{"options_pool": "groups_female_gen3"}'),
    ("text", 2, "song", "Which Stray Kids song is about cooking?", "God's Menu", '{"options_pool": "songs_skz"}'),
    ("text", 2, "member", "Who are the Australian members of Stray Kids?", "Bang Chan and Felix", '{"options_pool": "member_pairs_skz"}'),
    ("text", 2, "song", "Which (G)I-DLE song became a viral hit in 2022?", "TOMBOY", '{"options_pool": "songs_gidle"}'),
    # Text trivia - Difficulty 3 (Hard)
    ("text", 3, "member", "What is Rosé from BLACKPINK's real Korean name?", "Park Chae-young", '{"options_pool": "korean_names_female"}'),
    ("text", 3, "group_fact", "Which entertainment company was BTS's original label?", "Big Hit Entertainment", '{"options_pool": "companies"}'),
    ("text", 3, "member", "Which TWICE member trained for 10 years before debuting?", "Jihyo", '{"options_pool": "members_twice"}'),
    ("text", 3, "song", "What was BLACKPINK's debut song?", "Whistle", '{"options_pool": "songs_bp"}'),
    ("text", 3, "member", "What position does Karina hold in aespa?", "Leader, Main Dancer, Lead Vocalist", '{"options_pool": "positions"}'),
]

def seed():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Clear existing seed data
    c.execute("DELETE FROM questions")
    c.execute("DELETE FROM songs")
    c.execute("DELETE FROM artists")
    c.execute("DELETE FROM groups")
    
    # Insert groups
    for g in GROUPS:
        c.execute("""INSERT INTO groups (name, korean_name, company, debut_year, disband_year, 
                     generation, gender, member_count, difficulty, active) 
                     VALUES (?,?,?,?,?,?,?,?,?,?)""", g)
    
    # Build group name -> id map
    c.execute("SELECT id, name FROM groups")
    group_map = {name: gid for gid, name in c.fetchall()}
    
    # Insert artists
    for a in ARTISTS:
        stage, real, korean, group_name, bday, pos, nat, gender = a
        gid = group_map.get(group_name)
        diff = 1  # all seed artists are easy
        c.execute("""INSERT OR IGNORE INTO artists (stage_name, real_name, korean_name, group_id, 
                     birth_date, position, nationality, gender, difficulty) 
                     VALUES (?,?,?,?,?,?,?,?,?)""",
                  (stage, real, korean, gid, bday, pos, nat, gender, diff))
    
    # Insert songs
    for s in SONGS:
        title, group_name, year, is_title, album = s
        gid = group_map.get(group_name)
        diff = 1 if group_name in ["TWICE", "BLACKPINK", "BTS", "Stray Kids", "NewJeans"] else 2
        c.execute("""INSERT OR IGNORE INTO songs (title, group_id, year, is_title_track, album, difficulty) 
                     VALUES (?,?,?,?,?,?)""",
                  (title, gid, year, is_title, album, diff))
    
    # Insert questions
    for q in QUESTIONS:
        qtype, diff, cat, text, answer, meta = q
        c.execute("""INSERT INTO questions (type, difficulty, category, question_text, 
                     correct_answer, metadata_json) VALUES (?,?,?,?,?,?)""",
                  (qtype, diff, cat, text, answer, meta))
    
    conn.commit()
    
    # Report
    c.execute("SELECT COUNT(*) FROM groups")
    print(f"Groups: {c.fetchone()[0]}")
    c.execute("SELECT COUNT(*) FROM artists")
    print(f"Artists: {c.fetchone()[0]}")
    c.execute("SELECT COUNT(*) FROM songs")
    print(f"Songs: {c.fetchone()[0]}")
    c.execute("SELECT COUNT(*) FROM questions")
    print(f"Questions: {c.fetchone()[0]}")
    
    conn.close()

if __name__ == '__main__':
    seed()
