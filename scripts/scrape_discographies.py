#!/usr/bin/env python3
"""
Scrape K-pop group discographies from Wikipedia and build comprehensive song database.
Uses Wikipedia's structured discography pages for reliable data extraction.
"""

import sqlite3
import requests
from bs4 import BeautifulSoup
import time
import re
import json
import sys
from datetime import datetime

DB_PATH = "/home/athena/kpop-quiz/app/data/kpop_quiz.db"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Map of group_id -> (group_name, wikipedia_discography_slug)
# Prioritized by global popularity
TOP_GROUPS = {
    35: ("BTS", "BTS_discography"),
    208: ("BLACKPINK", "Blackpink_discography"),
    275: ("TWICE", "Twice_discography"),
    66: ("EXO", "EXO_discography"),
    264: ("Red Velvet", "Red_Velvet_discography"),
    287: ("NCT", "NCT_discography"),  
    141: ("Stray Kids", "Stray_Kids_discography"),
    134: ("SEVENTEEN", "Seventeen_(South_Korean_band)_discography"),
    21: ("ATEEZ", "Ateez_discography"),
    165: ("TXT", "TXT_discography"),
    59: ("ENHYPEN", "Enhypen_discography"),
    199: ("aespa", "Aespa_discography"),
    237: ("ITZY", "Itzy_discography"),
    238: ("IVE", "Ive_(group)_discography"),
    247: ("LE SSERAFIM", "Le_Sserafim_discography"),
    256: ("NewJeans", "NewJeans_discography"),
    72: ("GOT7", "Got7_discography"),
    103: ("MONSTA X", "Monsta_X_discography"),
    252: ("MAMAMOO", "Mamamoo_discography"),
    137: ("SHINee", "Shinee_discography"),
    28: ("BIGBANG", "Big_Bang_discography"),
    143: ("SUPER JUNIOR", "Super_Junior_discography"),
    225: ("Girls' Generation", "Girls%27_Generation_discography"),
    197: ("2NE1", "2NE1_discography"),
    77: ("iKON", "IKON_discography"),
    185: ("WINNER", "Winner_(band)_discography"),
    149: ("THE BOYZ", "The_Boyz_(South_Korean_band)_discography"),
    231: ("(G)I-DLE", "(G)I-dle_discography"),
    258: ("NMIXX", "Nmixx_discography"),
    269: ("STAYC", "StayC_discography"),
    217: ("EVERGLOW", "Everglow_discography"),
    249: ("LOONA", "Loona_discography"),
    215: ("Dreamcatcher", "Dreamcatcher_(group)_discography"),
    260: ("OH MY GIRL", "Oh_My_Girl_discography"),
    158: ("TREASURE", "Treasure_(band)_discography"),
    175: ("VIXX", "VIXX_discography"),
    34: ("BTOB", "BtoB_discography"),
    123: ("P1Harmony", "P1Harmony_discography"),
    43: ("CRAVITY", "Cravity_discography"),
    10: ("AB6IX", "AB6IX_discography"),
    121: ("ONEUS", "Oneus_discography"),
    222: ("fromis_9", "Fromis_9_discography"),
    242: ("Kep1er", "Kep1er_discography"),
    173: ("VERIVERY", "Verivery_discography"),
    39: ("CIX", "CIX_discography"),
    254: ("MOMOLAND", "Momoland_discography"),
    5: ("2PM", "2PM_discography"),
    4: ("2AM", "2AM_discography"),
}

# Additional groups — use direct Wikipedia article (not separate discography page)
ADDITIONAL_GROUPS_MAIN_PAGE = {
    # These groups may not have separate discography pages
}

# Well-known title tracks per group (fallback/supplement data)
# This ensures we have the most iconic songs even if scraping misses them
KNOWN_TITLE_TRACKS = {
    35: [  # BTS
        ("No More Dream", "2 Cool 4 Skool", 2013, "dMBFeTi8kHY"),
        ("Boy In Luv", "Skool Luv Affair", 2014, "m8MfJg68oCs"),
        ("Danger", "Dark & Wild", 2014, "bagj78IQ3l0"),
        ("I Need U", "The Most Beautiful Moment in Life, Part 1", 2015, "NMdTd9e-LEI"),
        ("Dope", "The Most Beautiful Moment in Life, Part 1", 2015, "BVwAVbKYYeM"),
        ("Run", "The Most Beautiful Moment in Life, Part 2", 2015, "wKysONrSmew"),
        ("Fire", "The Most Beautiful Moment in Life: Young Forever", 2016, "4ujQOR2DMFM"),
        ("Blood Sweat & Tears", "Wings", 2016, "hmE9f-TEutc"),
        ("Spring Day", "You Never Walk Alone", 2017, "xEeFrLSkMm8"),
        ("DNA", "Love Yourself: Her", 2017, "MBdVXkSdhwU"),
        ("Fake Love", "Love Yourself: Tear", 2018, "7C2z4GqqS5E"),
        ("IDOL", "Love Yourself: Answer", 2018, "pBuZEGYXA6E"),
        ("Boy With Luv", "Map of the Soul: Persona", 2019, "XsX3ATc3FbA"),
        ("ON", "Map of the Soul: 7", 2020, "gwMa6gpoE9I"),
        ("Dynamite", "BE", 2020, "gdZLi9oWNZg"),
        ("Life Goes On", "BE", 2020, "OovWV8xFCJc"),
        ("Butter", None, 2021, "WMweEpGlu_U"),
        ("Permission to Dance", None, 2021, "CuklIb9d3fI"),
        ("Yet To Come", "Proof", 2022, "kXpOEbB1jGo"),
        ("Take Two", None, 2023, None),
    ],
    208: [  # BLACKPINK
        ("Boombayah", "Square One", 2016, "bwmSjveL3Lc"),
        ("Whistle", "Square One", 2016, "dISNgvVpWlo"),
        ("Playing with Fire", "Square Two", 2016, "9pdj4iJD08s"),
        ("Stay", "Square Two", 2016, "FzVR_fymZw4"),
        ("As If It's Your Last", None, 2017, "Amq-qlqbjYA"),
        ("DDU-DU DDU-DU", "Square Up", 2018, "IHNzOHi8sJs"),
        ("Kill This Love", "Kill This Love", 2019, "2S24-y0Ij3Y"),
        ("How You Like That", "The Album", 2020, "ioNng23DkIM"),
        ("Ice Cream", "The Album", 2020, "vRXZj0DzXIA"),
        ("Lovesick Girls", "The Album", 2020, "dyRsYk0LyA8"),
        ("Pink Venom", "Born Pink", 2022, "gQlMMD8auMs"),
        ("Shut Down", "Born Pink", 2022, "POe9SOEKotk"),
    ],
    275: [  # TWICE
        ("Like Ooh-Ahh", "The Story Begins", 2015, "0rtV5esQT6I"),
        ("Cheer Up", "Page Two", 2016, "c7rCyll5AeY"),
        ("TT", "TWICEcoaster: Lane 1", 2016, "ePpPVE-GGJw"),
        ("Knock Knock", "TWICEcoaster: Lane 2", 2017, "8A2t_tAjMz8"),
        ("Signal", "Signal", 2017, "VQtonf1fv_s"),
        ("Likey", "Twicetagram", 2017, "V2hlQkVJZhE"),
        ("Heart Shaker", "Merry & Happy", 2017, "rRzxEiBLQCA"),
        ("What is Love?", "What is Love?", 2018, "i0p1bmr0EmE"),
        ("Dance the Night Away", "Summer Nights", 2018, "Fm5iP0S1z9w"),
        ("Yes or Yes", "Yes or Yes", 2018, "mAKsZ26SabQ"),
        ("Fancy", "Fancy You", 2019, "kOHB85vDuow"),
        ("Feel Special", "Feel Special", 2019, "3ymwOvFkMUk"),
        ("More & More", "More & More", 2020, "mH0_XpSHkZo"),
        ("I Can't Stop Me", "Eyes Wide Open", 2020, "CM4CkVFmTds"),
        ("Cry for Me", None, 2020, "bkQw-F1QTq4"),
        ("Alcohol-Free", "Taste of Love", 2021, "XA2YEHn-A8Q"),
        ("Scientist", "Formula of Love", 2021, "vPwaXytZcgI"),
        ("Talk That Talk", "Between 1&2", 2022, "k6jqx9kZgPM"),
        ("Moonlight Sunrise", None, 2023, "thVOOGHZDIo"),
        ("Set Me Free", "Ready to Be", 2023, "fgBk3dk0FeA"),
    ],
    66: [  # EXO
        ("Mama", "MAMA", 2012, "KH6ZwnqZ7Wo"),
        ("Wolf", "XOXO", 2013, "gAal8xHfV0c"),
        ("Growl", "XOXO", 2013, "I3dezFzsNss"),
        ("Overdose", "Overdose", 2014, "TI0DGvqKZTI"),
        ("Call Me Baby", "Exodus", 2015, "yWfsla_Uh80"),
        ("Love Me Right", "Love Me Right", 2015, "RuqaVryDRd0"),
        ("Monster", "EX'ACT", 2016, "KSH-FVVtTf0"),
        ("Lucky One", "EX'ACT", 2016, "73QzQYN8FtE"),
        ("Ko Ko Bop", "The War", 2017, "IdssxDHpIBU"),
        ("Power", "The War", 2017, "sGRv8ZBLuW0"),
        ("Tempo", "Don't Mess Up My Tempo", 2018, "iwd8idUStsA"),
        ("Love Shot", "Love Shot", 2018, "pSudEWAYvVs"),
        ("Obsession", "Obsession", 2019, "uxmP4b2a0uY"),
        ("Don't Fight the Feeling", "Don't Fight the Feeling", 2021, "2IkoKhr6Tss"),
        ("Cream Soda", "Exist", 2023, "NHDOKGEaSQs"),
    ],
    264: [  # Red Velvet
        ("Happiness", None, 2014, "JFgv8bKfxEs"),
        ("Be Natural", None, 2014, "QpAn9ryoB4Y"),
        ("Ice Cream Cake", "Ice Cream Cake", 2015, "glXgSSOKlls"),
        ("Dumb Dumb", "The Red", 2015, "XGdbaEDVWp0"),
        ("One of These Nights", "The Velvet", 2016, "9xWiro_tS1k"),
        ("Russian Roulette", "Russian Roulette", 2016, "QslJYDX3o8s"),
        ("Rookie", "Rookie", 2017, "J0h8-OTC38I"),
        ("Red Flavor", "The Red Summer", 2017, "WyiIGEHQP8o"),
        ("Peek-A-Boo", "Perfect Velvet", 2017, "6uJf2IT2Zh8"),
        ("Bad Boy", "The Perfect Red Velvet", 2018, "J_CFBjAyPWE"),
        ("Power Up", "Summer Magic", 2018, "aiHSVQy9xN8"),
        ("RBB (Really Bad Boy)", "RBB", 2018, "IWJUPY-2EIM"),
        ("Zimzalabim", "The ReVe Festival: Day 1", 2019, "YBnGBb1wg98"),
        ("Umpah Umpah", "The ReVe Festival: Day 2", 2019, "vHS9E6JFja8"),
        ("Psycho", "The ReVe Festival: Finale", 2019, "uR8Mrt1IpXg"),
        ("Queendom", "Queendom", 2021, "c9RzZpV4MiE"),
        ("Feel My Rhythm", "The ReVe Festival 2022 - Feel My Rhythm", 2022, "R9At2ICm4LQ"),
        ("Birthday", "Birthday", 2022, "YmY9Bmb3dK0"),
        ("Cosmic", "Cosmic", 2024, "JEkV0DknwtE"),
    ],
    141: [  # Stray Kids
        ("District 9", "I Am NOT", 2018, "u6unJQownW4"),
        ("My Pace", "I Am WHO", 2018, "pok5yDw77uM"),
        ("I Am YOU", "I Am YOU", 2018, "CNfodZluR-Q"),
        ("Miroh", "Clé 1: Miroh", 2019, "Dab4EENTW5I"),
        ("Side Effects", "Clé 2: Yellow Wood", 2019, "5rPluw_-Eb4"),
        ("Levanter", "Clé: LEVANTER", 2019, "Fpgd3ac3_nM"),
        ("God's Menu", "Go Live", 2020, "TQTlCHxyuu8"),
        ("Back Door", "In Life", 2020, "X-uJtV8ScYk"),
        ("Thunderous", "NOEASY", 2021, "EaswWiwKVz8"),
        ("Christmas EveL", "Christmas EveL", 2021, "57n4dZAPMOA"),
        ("MANIAC", "ODDINARY", 2022, "OvioeS1ZZ7o"),
        ("CASE 143", "MAXIDENT", 2022, "jk6bEABqOkc"),
        ("VENOM", "ODDINARY", 2022, "pM-jzOVFaL8"),
        ("S-Class", "5-STAR", 2023, "1LYOrkCsNkg"),
        ("LALALALA", "ROCK-STAR", 2023, "2T635RJ__QI"),
        ("Lose My Breath", None, 2024, "g5jJFROR6sQ"),
        ("Chk Chk Boom", "ATE", 2024, "SE4BrsXZGWk"),
        ("Jjam", "SKZHOP HIPTAPE", 2024, "MjUZUUtWz4s"),
    ],
    134: [  # SEVENTEEN
        ("Adore U", "17 Carat", 2015, "9rUFQJrCT7M"),
        ("Mansae", "Boys Be", 2015, "MKbwrcIjfy0"),
        ("Pretty U", "Love & Letter", 2016, "j59LLNr_1MI"),
        ("Very Nice", "Love & Letter Repackage", 2016, "J-wFp43XOrA"),
        ("Boom Boom", "Going Seventeen", 2016, "IzplmS-VeBc"),
        ("Don't Wanna Cry", "Al1", 2017, "zEkg4GBQumc"),
        ("Clap", "Teen, Age", 2017, "CyzEtbG-sxY"),
        ("Thanks", "Director's Cut", 2018, "ShVRP09NCO4"),
        ("Oh My!", "You Make My Day", 2018, "47TgGWHI5Gs"),
        ("Home", "You Made My Dawn", 2019, "R9VDPMk5ls0"),
        ("Fear", "An Ode", 2019, "ap14O5-O-Wc"),
        ("Left & Right", "Heng:garae", 2020, "HdZdxocqOb0"),
        ("Ready to Love", "Your Choice", 2021, "eVaC5rBSuBQ"),
        ("Rock with You", "Attacca", 2021, "WpuatuzSDK4"),
        ("HOT", "Face the Sun", 2022, "grdlejKCOVo"),
        ("Super", "FML", 2023, "x-zx-IIhOt4"),
        ("Fighting", "FML", 2023, "4xlQXNVuMrg"),
        ("Maestro", "17 Is Right Here", 2024, "SnNxk75KFrQ"),
        ("LOVE, MONEY, FAME", None, 2024, "8mPKBwVrVog"),
    ],
    21: [  # ATEEZ
        ("Pirate King", "Treasure EP.1: All to Zero", 2018, "RqJ1rH9M5G0"),
        ("Say My Name", "Treasure EP.2: Zero to One", 2019, "nKU4OVH18mE"),
        ("HALA HALA", "Treasure EP.2: Zero to One", 2019, "QbjmVyP9RFg"),
        ("Wave", "Treasure EP.3: One to All", 2019, "FIInyEWWW-s"),
        ("Wonderland", "Treasure EP.Fin: All to Action", 2019, "Z_BhMhZpAug"),
        ("Answer", "Treasure Epilogue: Action to Answer", 2020, "yW7wZX3DUaY"),
        ("Inception", "Zero: Fever Part.1", 2020, "2NArH91kHoQ"),
        ("Thanxx", "Zero: Fever Part.1", 2020, "K7LY9j4bEVk"),
        ("Fireworks (I'm the One)", "Zero: Fever Part.2", 2021, "xtcVf3FC3cE"),
        ("Deja Vu", "Zero: Fever Part.3", 2021, "nlnMDttgTbk"),
        ("Turbulence", "Zero: Fever Epilogue", 2021, "80WvAnsHOdM"),
        ("Guerrilla", "The World EP.1: Movement", 2022, "2HcVZm_4qAI"),
        ("Halazia", "The World EP.2: Outlaw", 2022, None),
        ("Bouncy (K-Hot Chilli Peppers)", "The World EP.2: Outlaw", 2023, "eHCdlMV7kLI"),
        ("Work", "The World EP.Fin: Will", 2023, "bWkrVHiCLVA"),
        ("WORK", "The World EP.Fin: Will", 2023, "bWkrVHiCLVA"),
    ],
    165: [  # TXT
        ("Crown", "The Dream Chapter: Star", 2019, "W3iSnIMp59s"),
        ("Cat & Dog", "The Dream Chapter: Star", 2019, "NaKrke1EL1A"),
        ("Run Away", "The Dream Chapter: Magic", 2019, "6yWPfUz0z94"),
        ("Can't You See Me?", "The Dream Chapter: Eternity", 2020, "cMFHUTJ13Ys"),
        ("Blue Hour", "Minisode 1: Blue Hour", 2020, "Vd9QkWsd5pQ"),
        ("0X1=LOVESONG", "The Chaos Chapter: Freeze", 2021, "d5bbqKYu51I"),
        ("LO$ER=LO♡ER", "The Chaos Chapter: Fight or Escape", 2021, "JzODRUBBXpc"),
        ("Good Boy Gone Bad", "Minisode 2: Thursday's Child", 2022, "Os_heh8vPfs"),
        ("Sugar Rush Ride", "The Name Chapter: Temptation", 2023, "pDfnQGFIEh4"),
        ("Chasing That Feeling", "The Name Chapter: Freefall", 2023, "2piMJypxH1Q"),
        ("Deja Vu", "Minisode 3: Tomorrow", 2024, "u2Dkl3HlCzo"),
    ],
    59: [  # ENHYPEN
        ("Given-Taken", "Border: Day One", 2020, "nQ6wLuYvGd4"),
        ("Drunk-Dazed", "Border: Carnival", 2021, "Fc7-Si7IVBI"),
        ("Tamed-Dashed", "Dimension: Dilemma", 2021, "W3mIylIDuQ4"),
        ("Blessed-Cursed", "Dimension: Answer", 2022, "6fNqrlb0pyo"),
        ("Future Perfect (Pass the MIC)", "Manifesto: Day 1", 2022, "eroT95nYgqs"),
        ("ParadoXXX Invasion", "Dark Blood", 2023, "IbzU_eLlsWA"),
        ("Sweet Venom", "Orange Blood", 2023, "gJMF1nnPfBo"),
        ("XO (Only If You Say Yes)", "Romance: Untold", 2024, "wKkjz0fWSPg"),
        ("No Doubt", "Romance: Untold - daydream", 2024, "J8kfHwkMqbY"),
    ],
    199: [  # aespa
        ("Black Mamba", None, 2020, "ZeerrnuLi5E"),
        ("Next Level", None, 2021, "4TWR90KJl84"),
        ("Savage", "Savage", 2021, "WPdWvnAAurg"),
        ("Dreams Come True", None, 2022, "5GXzMb1zSbg"),
        ("Girls", "Girls", 2022, "NjgBnx56wYE"),
        ("Spicy", "My World", 2023, "Os_heh8vPfs"),
        ("Drama", "Drama", 2023, "k_cYHP1KnOI"),
        ("Supernova", "Armageddon", 2024, "phuiiNCBaKk"),
        ("Armageddon", "Armageddon", 2024, "ai7iJVHoXPE"),
        ("Whiplash", "Whiplash", 2024, "jWJgPVbyNd4"),
    ],
    238: [  # IVE
        ("ELEVEN", "Eleven", 2021, "EhUvGRN_71Y"),  
        ("LOVE DIVE", "Love Dive", 2022, "Y8JFxS1HlDo"),
        ("After LIKE", "After Like", 2022, "F0B7HDiY-10"),
        ("Kitsch", "I've Mine", 2023, "0hGIwSLeCqo"),
        ("I AM", "I've Mine", 2023, "6ZUIwj3FgUY"),
        ("Baddie", "I've Mine", 2023, "PBcT-wk1TqE"),
        ("Heya", "IVE Switch", 2024, "mEbDsxGhbSk"),
        ("REBEL HEART", "IVE Mine", 2024, None),
    ],
    247: [  # LE SSERAFIM
        ("FEARLESS", "Fearless", 2022, "4vbDFu0PUew"),
        ("ANTIFRAGILE", "Antifragile", 2022, "pyf8cbqyfPs"),
        ("UNFORGIVEN", "Unforgiven", 2023, "oJSzRlIWotA"),
        ("Eve, Psyche & the Bluebeard's wife", "Unforgiven", 2023, None),
        ("Perfect Night", None, 2023, "hLvhIdgB83E"),
        ("EASY", "Easy", 2024, "grGR4DYCMXU"),
        ("Smart", "Easy", 2024, "hFUZN9L6O_I"),
        ("CRAZY", "Crazy", 2024, "JTkMprvzkag"),
    ],
    256: [  # NewJeans
        ("Attention", "New Jeans", 2022, "js1CtxSY38I"),
        ("Hype Boy", "New Jeans", 2022, "11cta61wi0g"),
        ("Cookie", "New Jeans", 2022, "p1bjnDEBJM8"),
        ("Ditto", "OMG", 2022, "pSUydWEqKwE"),
        ("OMG", "OMG", 2023, "sVTy_wmn5SU"),
        ("Super Shy", "Get Up", 2023, "ArmDp-zijuc"),
        ("ETA", "Get Up", 2023, "jOTfBlKSLOA"),
        ("Cool With You", "Get Up", 2023, None),
        ("How Sweet", "How Sweet", 2024, "9cTq6LHhKHs"),
        ("Supernatural", "Supernatural", 2024, "ZncbtRo7RXs"),
        ("Right Now", None, 2024, "f9jlZ6lz_Zs"),
    ],
    237: [  # ITZY
        ("Dalla Dalla", "It'z Different", 2019, "pNfTK39k55U"),
        ("ICY", "It'z ICY", 2019, "zndvqTc4P9I"),
        ("Wannabe", "IT'z ME", 2020, "fE2h3lGlOsk"),
        ("Not Shy", "Not Shy", 2020, "wTowEKjDGkU"),
        ("In the Morning", "Guess Who", 2021, "Hi4hFNB_wBc"),
        ("LOCO", "Crazy in Love", 2021, "MjCZfZfucEc"),
        ("SNEAKERS", "Checkmate", 2022, "Hbb5GPxXF1w"),
        ("Cheshire", "Cheshire", 2022, "tag00oXJbOM"),
        ("CAKE", "Kill My Doubt", 2023, "X6FGSLBw710"),
        ("UNTOUCHABLE", "Born to Be", 2024, "qgMBaOh_kwY"),
    ],
    72: [  # GOT7
        ("Girls Girls Girls", "Got It?", 2014, "2sAoKmg7qPI"),
        ("A", "Got Love", 2014, "eISomerx_wI"),
        ("Stop Stop It", "Identify", 2014, "R_DX64EwH9M"),
        ("Just Right", "Just Right", 2015, "vrdk3IGcau8"),
        ("If You Do", "Mad", 2015, "T0iPB_JyS5g"),
        ("Fly", "Flight Log: Departure", 2016, "Q4vFviMBkXc"),
        ("Hard Carry", "Flight Log: Turbulence", 2016, "O57jr1oZDIw"),
        ("Never Ever", "Flight Log: Arrival", 2017, "IZ1t7CQfvOY"),
        ("You Are", "7 for 7", 2017, "ktc8XDBq93k"),
        ("Lullaby", "Present: You", 2018, "9RUeTYiJCyA"),
        ("Eclipse", "Spinning Top: Between Security & Insecurity", 2019, "_SXi27JKIvg"),
        ("Not by the Moon", "Dye", 2020, "ladClnnJhqg"),
        ("Breath", "Breath of Love: Last Piece", 2020, "g5idjxf4jHI"),
        ("NANANA", "Got7", 2022, "sOjTeAiPlBo"),
    ],
    103: [  # MONSTA X
        ("Trespass", "Trespass", 2015, "WLeFYKDtw1I"),
        ("Hero", "Rush", 2015, "FZ9lJ5ctd0s"),
        ("All In", "The Clan Pt. 1 Lost", 2016, "ppOWR7ZLl7Q"),
        ("Fighter", "The Clan Pt. 2 Guilty", 2016, "5jTtU8EPxgg"),
        ("Beautiful", "The Clan 2.5 The Final Chapter", 2017, "f5Zedh_5DDM"),
        ("Dramarama", "The Code", 2017, "r1afdZk0qcI"),
        ("Jealousy", "The Connect: Dejavu", 2018, "TSA0JTgPCJo"),
        ("Shoot Out", "Take.1: Are You There?", 2018, "MS10Zz49FHE"),
        ("Alligator", "Take.2: We Are Here", 2019, "3dZdnlRBfHs"),
        ("Follow", "Follow: Find You", 2019, "aa7hl8L_1vk"),
        ("Love Killa", "Fatal Love", 2020, "MZ4JGye4dQU"),
        ("Gambler", "One of a Kind", 2021, "yY13X0GEhKw"),
        ("Rush Hour", "Rush Hour", 2022, "JJjAemuvPOA"),
    ],
    252: [  # MAMAMOO
        ("Mr. Ambiguous", "Hello", 2014, "D15-XYRubsc"),
        ("Piano Man", "Piano Man", 2014, "3IIBVnn4eTM"),
        ("Um Oh Ah Yeh", "Pink Funky", 2015, "pFuJAIMQjHk"),
        ("You're the Best", "Melting", 2016, "QbhmTM1cRro"),
        ("Decalcomanie", "Memory", 2016, "y2OFPvYxZuY"),
        ("Yes I Am", "Purple", 2017, "Ue9NG1hAr78"),
        ("Starry Night", "Yellow Flower", 2018, "0FB2EoKTK_Q"),
        ("Egotistic", "Red Moon", 2018, "pHtxTSiPh5I"),
        ("Wind Flower", "Blue;s", 2018, "H8NCOA2bK6k"),
        ("gogobebe", "White Wind", 2019, "Cp56JdkmE9s"),
        ("HIP", "reality in BLACK", 2019, "KhTeiaCezwM"),
        ("Dingga", "Travel", 2020, "dfl9KIX1WpU"),
        ("AYA", "Travel", 2020, "UoI9riNffEU"),
    ],
    137: [  # SHINee
        ("Replay", "Replay", 2008, "VTASffPQGhY"),
        ("Ring Ding Dong", "Romeo", 2009, "roughtziaRM"),
        ("Lucifer", "Lucifer", 2010, "Dww9UjJ4owE"),
        ("Hello", "Hello", 2010, "skIewTscsTg"),
        ("Sherlock", "Sherlock", 2012, "8kyG5tTZ1iE"),
        ("Dream Girl", "Dream Girl – The Misconceptions of You", 2013, "vhxjEXDAy6s"),
        ("Everybody", "Everybody", 2013, "hKbNV-4b_g8"),
        ("View", "Odd", 2015, "UF53cptEE5k"),
        ("Married to the Music", "Odd Repackage", 2015, "bcu7yZBeSKw"),
        ("1 of 1", "1 of 1", 2016, "WJua7KEP_oE"),
        ("Don't Call Me", "Don't Call Me", 2021, "p6OoY6xneI0"),
        ("Atlantis", "Atlantis", 2021, "PSYxT9GM0fQ"),
        ("Hard", "Hard", 2023, "PNVq0VqVHTk"),
    ],
    28: [  # BIGBANG
        ("Lies", "Always", 2007, "2Cv3phvP8Ro"),
        ("Haru Haru", "Stand Up", 2008, "MzCbEdtNbJ0"),
        ("Tonight", "Tonight", 2011, "8d5QEWdHchk"),
        ("Fantastic Baby", "Alive", 2012, "AAbokV76tkU"),
        ("Bad Boy", "Alive", 2012, None),
        ("Blue", "Alive", 2012, "2GRP1rkE4O0"),
        ("Monster", "Alive", 2012, None),
        ("Bae Bae", "MADE", 2015, "TKD03uPVD-Q"),
        ("Bang Bang Bang", "MADE", 2015, "2ips2mM7Zqw"),
        ("Loser", "MADE", 2015, "1CTced9CMMk"),
        ("Let's Not Fall In Love", "MADE", 2015, "9jTo6hTpMIA"),
        ("FXXK IT", "MADE: The Full Album", 2016, "iIPH8LFYFRk"),
        ("Last Dance", "MADE: The Full Album", 2016, "--zku6TB5NY"),
        ("Still Life", None, 2022, "q44I_mMBbcY"),
    ],
    143: [  # SUPER JUNIOR
        ("Twins (Knock Out)", "SuperJunior05", 2005, None),
        ("U", "U", 2006, None),
        ("Don't Don", "Don't Don", 2007, "veEh0RYy9t4"),
        ("Sorry, Sorry", "Sorry, Sorry", 2009, "x6QA3m58DQw"),
        ("It's You", "It's You", 2009, None),
        ("Bonamana", "Bonamana", 2010, "tSOSxwEWFA4"),
        ("Mr. Simple", "Mr. Simple", 2011, "r6TwzSGYycM"),
        ("Sexy, Free & Single", "Sexy, Free & Single", 2012, "gWIkiI_UmeE"),
        ("Mamacita", "Mamacita", 2014, "q_krT_wOYS4"),
        ("Devil", "Devil", 2015, "gOwERHxXcTs"),
        ("Black Suit", "Play", 2017, "MvqB6JMRxYk"),
        ("Lo Siento", "Replay", 2018, "ZbB4SYJhKTo"),
        ("2YA2YAO!", "Timeless", 2020, "90nyrmNSdMI"),
        ("House Party", "The Renaissance", 2021, "EusqRWfUkyA"),
    ],
    225: [  # Girls' Generation (SNSD)
        ("Into the New World", "Girls' Generation", 2007, "0k2Zzkw_-0I"),
        ("Kissing You", "Girls' Generation", 2008, "r3yxxe66LXs"),
        ("Gee", "Gee", 2009, "U7mPqycQ0tQ"),
        ("Genie", "Genie", 2009, "6SwiSpudKWI"),
        ("Oh!", "Oh!", 2010, "TGbwL8kSpEk"),
        ("Run Devil Run", "Run Devil Run", 2010, "q_gfD3nvh-8"),
        ("Hoot", "Hoot", 2010, "F4-SxcCO5d0"),
        ("The Boys", "The Boys", 2011, "6pA_Tou-DPI"),
        ("I Got a Boy", "I Got a Boy", 2013, "wv7BqGKUY_Q"),
        ("Mr. Mr.", "Mr. Mr.", 2014, "Z8j_XEn9b_8"),
        ("Catch Me If You Can", None, 2015, "b09U0KLv6I4"),
        ("Lion Heart", "Lion Heart", 2015, "nVCubhQ454c"),
        ("Party", "Party", 2015, "HQzu7NYlZNQ"),
        ("Holiday", "Holiday Night", 2017, "YwN-7EiKYsE"),
        ("All Night", "Holiday Night", 2017, None),
        ("FOREVER 1", "Forever 1", 2022, "gNSiCYqFRj4"),
    ],
    197: [  # 2NE1
        ("Fire", "2NE1", 2009, "ISEoXdHb4W4"),
        ("I Don't Care", "2NE1", 2009, "zdZya6yATn0"),
        ("Go Away", "To Anyone", 2010, "3yW13T2sfKg"),
        ("Can't Nobody", "To Anyone", 2010, "jYB-KWb--2Q"),
        ("Lonely", "Lonely", 2011, "5n4V3lGEyG4"),
        ("I Am the Best", "2NE1", 2011, "j7_lSP8Vc3o"),
        ("Ugly", "2NE1", 2011, "NGe0hHvAGkc"),
        ("I Love You", None, 2012, "LUrUPzLm5SI"),
        ("Missing You", "Missing You", 2013, "AG0biczqB3s"),
        ("Come Back Home", "Crush", 2014, "vLbfv-AAyvQ"),
        ("Gotta Be You", "Crush", 2014, None),
    ],
    77: [  # iKON
        ("My Type", "Welcome Back (Half Album)", 2015, "ZS6vfv4sszg"),
        ("Rhythm Ta", "Welcome Back", 2015, "tYI5CriE6XU"),
        ("Dumb & Dumber", "Welcome Back", 2016, "QjZkpm7_WpE"),
        ("Love Scenario", "Return", 2018, "vecSVX1QYbQ"),
        ("Killing Me", "New Kids: Continue", 2018, "RyVS7R9PN6U"),
        ("Goodbye Road", "New Kids: The Final", 2018, "2O6dRaBbFoo"),
        ("I'm OK", "New Kids Repackage", 2019, "yqszm_3fyBo"),
        ("Dive", "I Decide", 2020, "fxOCqAuXQ_o"),
        ("Why Why Why", "Song for You", 2021, "zLrWIgkvoB0"),
        ("But You", "FLASHBACK", 2022, "0mhbxnJzEBo"),
    ],
    185: [  # WINNER
        ("Empty", "2014 S/S", 2014, "gEqlF5N8UMs"),
        ("Color Ring", "2014 S/S", 2014, "vQIfKJfFAqQ"),
        ("Sentimental", "Exit: E", 2016, "OV9NJGTLm-4"),
        ("Really Really", "Fate Number For", 2017, "4tBnF46ybZk"),
        ("Love Me Love Me", "Our Twenty For", 2017, "ppOWR7ZLl7Q"),
        ("Island", "Our Twenty For", 2017, None),
        ("Everyday", "Everyd4y", 2018, "d1D1SJ-KqYg"),
        ("Millions", "Millions", 2018, "6tl-MG38-0E"),
        ("Ah Yeah", "We", 2019, "Pm0_G8Yc0JI"),
        ("Hold", "Remember", 2020, "YURT0erwtSA"),
    ],
    149: [  # THE BOYZ
        ("Boy", "The First", 2017, "UOmqTJpnKWs"),
        ("Giddy Up", "The Start", 2018, "DNH7X46gMjQ"),
        ("Right Here", "The Only", 2018, "FWj1c1SUQmg"),
        ("No Air", "The Sphere", 2018, "8n6pRkpjsUI"),
        ("Bloom Bloom", "Bloom Bloom", 2019, "Ty_3Vyqrlr4"),
        ("D.D.D", "DreamLike", 2019, "bTTfz1Fxqo8"),
        ("Reveal", "Reveal", 2020, "PugZA26sj-8"),
        ("The Stealer", "Chase", 2020, "c_A8Etk_jSQ"),
        ("Thrill Ride", "Thrill-ing", 2021, "XSOMzI80kbw"),
        ("MAVERICK", "Maverick", 2021, "AYMPYPcTfdk"),
        ("Whisper", "Be Aware", 2022, "lmfvQMOGfks"),
        ("LIP GLOSS", "Phantasy, Pt. 1 Christmas in August", 2023, None),
        ("WATCH IT", "Phantasy, Pt. 2 Sixth Sense", 2023, None),
    ],
    231: [  # (G)I-DLE
        ("LATATA", "I Am", 2018, "9mQk7Evt6Vs"),
        ("HANN (Alone)", "I Made", 2018, "OKNXn2qCEws"),
        ("Senorita", "I Made", 2019, "2cevbhEBJ_4"),
        ("Oh My God", "I Trust", 2020, "om3n2ni8luE"),
        ("DUMDi DUMDi", "DUMDi DUMDi", 2020, "HPQ5mqovXHo"),
        ("HWAA", "I Burn", 2021, "z3szNvgQxHo"),
        ("TOMBOY", "I Never Die", 2022, "Jh4QFaPmdss"),
        ("Nxde", "I Love", 2022, "fCO7f0SmrDc"),
        ("Queencard", "I Feel", 2023, "VOaKSYOa-xY"),
        ("Super Lady", "2", 2024, "1fAmEXslFGE"),
        ("Klaxon", "I Sway", 2024, "MBUqAGXFRZk"),
    ],
    258: [  # NMIXX
        ("O.O", "AD MARE", 2022, "RGnGXycMbUo"),
        ("DICE", "ENTWURF", 2022, "dy98E23gRDk"),
        ("DASH", "EXPÉRGO", 2023, "X9NeQxUNO0Y"),
        ("Love Me Like This", "EXPÉRGO", 2023, "GYGmmjk9K1M"),
        ("Young, Dumb, Stupid", None, 2023, None),
        ("Roller Coaster", "Fe3O4: BREAK", 2024, "tgbTIDFKPGI"),
        ("See That?", "Fe3O4: STICK OUT", 2024, "_G0f6AGQJ98"),
    ],
    269: [  # STAYC
        ("SO BAD", "Star to a Young Culture", 2020, "gMe1c4UegBY"),
        ("ASAP", "STAYDOM", 2021, "NsY-9MCOIAQ"),
        ("Stereotype", "Stereotype", 2021, "Xmxcnf2v40s"),
        ("RUN2U", "Young-Luv.com", 2022, "grG41kS4MUA"),
        ("Beautiful Monster", "We Need Love", 2022, "juQvizeZJFM"),
        ("Teddy Bear", "Teddy Bear", 2023, "AKGXnAKnNeE"),
        ("Bubble", "Metamorphic", 2023, "AL2E-0XDLWU"),
        ("Cheeky Icy Thang", "Metamorphic", 2023, "yeghW3DjCMM"),
        ("GPT", "Metamorphic", 2024, "EBG6EqKffPs"),
    ],
    217: [  # EVERGLOW
        ("Bon Bon Chocolat", "Arrival of Everglow", 2019, "HvGql8HwOF0"),
        ("Adios", "Hush", 2019, "4gX_p1VkgA4"),
        ("DUN DUN", "Reminiscence", 2020, "NoYKBAajoyo"),
        ("LA DI DA", "-77.82X-78.29", 2020, "jeI992mvlEY"),
        ("First", "Last.1", 2021, "Z3RA7BiZol0"),
        ("PIRATE", "Return of the Girl", 2021, "S0LT_f3TSag"),
        ("Slay", "All My Girls", 2023, "JfIgmAokv_I"),
    ],
    249: [  # LOONA
        ("Hi High", "[+ +]", 2018, "846cjX0ZTrk"),
        ("Butterfly", "[X X]", 2019, "XEOCbFJjRw0"),
        ("So What", "[#]", 2020, "GEo5bmUKFvI"),
        ("Why Not?", "[12:00]", 2020, "b6li05zh3Kg"),
        ("PTT (Paint the Town)", "&", 2021, "_EEo-iE5Igk"),
        ("Flip That", "Flip That", 2022, "jYAVFvEBDBE"),
    ],
    215: [  # Dreamcatcher
        ("Chase Me", "Nightmare", 2017, "zihoyz0u_cs"),
        ("Good Night", "Nightmare: Fall Asleep in the Mirror", 2017, "Lxfl8LRab_I"),
        ("Fly High", "Prequel", 2017, "39yeTdIuKJU"),
        ("You and I", "Nightmare: Escape the ERA", 2018, "I5_BQAtwHws"),
        ("What", "Nightmare: Escape the ERA", 2018, "pN0dkjp1deQ"),
        ("Piri", "The End of Nightmare", 2019, "Pq_mbTSR-a0"),
        ("Deja Vu", "Raid of Dream", 2019, "W761DtH1oRg"),
        ("Scream", "Dystopia: The Tree of Language", 2020, "FKlGHHhTOsQ"),
        ("BOCA", "Dystopia: Lose Myself", 2020, "MZ4JGye4dQU"),
        ("Odd Eye", "Dystopia: Road to Utopia", 2021, "1QD0FeZyDtQ"),
        ("BEcause", "Summer Holiday", 2021, "PEKkdIT8JPM"),
        ("MAISON", "Apocalypse: Save Us", 2022, "z4t9LLq1Nk0"),
        ("VISION", "Apocalypse: Follow Us", 2022, "jKrEMdWbSGk"),
        ("OOTD", "VillainS", 2023, "AKGMupnU9qI"),
    ],
    260: [  # OH MY GIRL
        ("Cupid", "Cupid", 2015, None),
        ("Closer", "Closer", 2015, "isUudT58Xfk"),
        ("Liar Liar", "Pink Ocean", 2016, "LNZKqhXCv5c"),
        ("Windy Day", "Windy Day", 2016, "AJqhKWo89FE"),
        ("Coloring Book", "Coloring Book", 2017, "7cjZFjWBZI0"),
        ("Secret Garden", "Secret Garden", 2018, "_fy0gMNihtM"),
        ("Remember Me", "Remember Me", 2018, "RrvdjyIgJbA"),
        ("The Fifth Season (SSFWL)", "The Fifth Season", 2019, "udGwca1HBM4"),
        ("NONSTOP", "Nonstop", 2020, "iDjQSdN_ig8"),
        ("Dun Dun Dance", "Dear OHMYGIRL", 2021, "HzOjwL7IP_o"),
        ("Real Love", "Real Love", 2022, "kR3u7mNZY6Q"),
    ],
    158: [  # TREASURE
        ("BOY", "The First Step: Chapter One", 2020, "gfmqDqBaGnI"),
        ("I LOVE YOU", "The First Step: Chapter Two", 2020, "KOLNBFIsitM"),
        ("My Treasure", "The First Step: Treasure Effect", 2021, "p9LLoijPnYY"),
        ("JIKJIN", "The Second Step: Chapter One", 2022, "hKb8mhpS6VE"),
        ("HELLO", "The Second Step: Chapter Two", 2022, "1_jRUkVVJSE"),
        ("BONA BONA", "Reboot", 2023, "6Hk_ncxYP4Y"),
    ],
    175: [  # VIXX
        ("Super Hero", "Super Hero", 2012, None),
        ("Rock Ur Body", "Rock Ur Body", 2012, None),
        ("On and On", "On and On", 2013, "d0C6EktpC20"),
        ("Hyde", "Jekyll", 2013, "Le0CwBy4SRA"),
        ("Voodoo Doll", "Voodoo", 2013, "MOG7BexjPjM"),
        ("Eternity", "Eternity", 2014, "cIfoNcm8dwA"),
        ("Error", "Error", 2014, "IF8kySIcWNw"),
        ("Love Equation", "Love Equation", 2015, "OjuDs-nwgRE"),
        ("Chained Up", "Chained Up", 2015, "vqzBrI76e4g"),
        ("Dynamite", "Hades", 2016, "4bnIBrTCzyY"),
        ("Fantasy", "Eau de VIXX", 2017, "IuaRdAozUI0"),
        ("Scentist", "Eau de VIXX", 2018, "MctZLEYlU4s"),
    ],
    34: [  # BTOB
        ("Insane", "Born to Beat", 2012, "FG0nTVU3fRM"),
        ("WOW", "Press Play", 2012, "cXcUXWL1mJA"),
        ("Second Confession", "Second Confession", 2013, None),
        ("Beep Beep", "Beep Beep", 2014, "qgtaSAG_OLo"),
        ("It's Okay", "Complete", 2015, "f4rN5Y7Dx_I"),
        ("Way Back Home", "Remember That", 2016, "amOSaNX7KaY"),
        ("I'll Be Your Man", "New Men", 2016, "u-b2r0uXsgE"),
        ("Movie", "Brother Act.", 2017, "42A-rFhiyLA"),
        ("Missing You", "Brother Act.", 2017, "4bykMy6dBQ4"),
        ("Beautiful Pain", "This is Us", 2018, "KLNr84h5qL4"),
        ("Only One for Me", "Hour Moment", 2018, "pFMtR5z0jEk"),
        ("Outsider", "4U: Outside", 2021, "5ZH_L3cQoK8"),
    ],
    222: [  # fromis_9
        ("To Heart", "To. Heart", 2018, "iFUHS1Ei7qw"),
        ("DKDK", "To. Day", 2018, "B3KuJqEB3OE"),
        ("Love Bomb", "From.9", 2018, "1gN1IN1A7yQ"),
        ("FUN!", "Fun Factory", 2019, "zsRyyLtcXZ4"),
        ("Feel Good", "My Little Society", 2020, "1cXc_yz-MDs"),
        ("WE GO", "9 Way Ticket", 2021, "HM6UpQZvbhY"),
        ("Talk & Talk", "Talk & Talk", 2021, "PjXpjY0DBbU"),
        ("DM", "Midnight Guest", 2022, "b2bJfJlYkf0"),
        ("Stay This Way", "from Our Memento Box", 2022, "JtoRkNE7OjQ"),
        ("Supersonic", "Unlock My World", 2023, "nOCnOkNXY2s"),
    ],
    242: [  # Kep1er
        ("WA DA DA", "First Impact", 2022, "n0j5NPptyM0"),
        ("Up!", "DOUBLAST", 2022, "zFOEJWKU9Kg"),
        ("We Fresh", "TROUBLESHOOTER", 2022, "nbyxCfWFmq0"),
        ("Giddy", "Lovestruck!", 2023, "kPmGfFi4Mlw"),
        ("Shooting Star", "Magic Hour", 2023, None),
    ],
    254: [  # MOMOLAND
        ("JJan! Koong! Kwang!", "Welcome to Momoland", 2016, "sE3z5Wjkho4"),
        ("Freeze!", "Freeze!", 2017, "ywAXmiEiwRo"),
        ("BBoom BBoom", "Great!", 2018, "JQGRg8XBnB4"),
        ("BAAM", "Fun to the World", 2018, "txWmd7QKFe8"),
        ("I'm So Hot", "Show Me", 2019, "tsN-MkpiZB0"),
        ("Thumbs Up", "Thumbs Up", 2020, "p3tSS0gLbkA"),
        ("Yummy Yummy Love", "Yummy Yummy Love", 2022, "MFHSyu7-siY"),
    ],
    5: [  # 2PM
        ("Again & Again", "2:00PM Time for Change", 2009, "cRzu0WgAISo"),
        ("Heartbeat", "Heartbeat", 2009, "bKtvDv7eykg"),
        ("Without U", "Don't Stop Can't Stop", 2010, "rW4ILU9YnIE"),
        ("I'll Be Back", "Still 2:00PM", 2010, "jMHqih-DRBY"),
        ("Hands Up", "Hands Up", 2011, "KgrB2KBZws4"),
        ("A.D.T.O.Y.", "Grown", 2013, "AFnV7Y6iwrA"),
        ("Go Crazy!", "Go Crazy!", 2014, "uwD9bEsSIaQ"),
        ("My House", "No.5", 2015, "u2pFB1dCSo4"),
        ("Make It", "Must", 2021, "eFjOzpVr0NQ"),
    ],
}

def ensure_schema(conn):
    """Ensure the songs table has all needed columns."""
    cursor = conn.cursor()
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(songs)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    
    # Add missing columns
    new_cols = {
        'release_date': 'TEXT',
        'song_type': 'TEXT DEFAULT "title_track"',
    }
    
    for col, col_type in new_cols.items():
        if col not in existing_cols:
            cursor.execute(f"ALTER TABLE songs ADD COLUMN {col} {col_type}")
            print(f"  Added column: {col}")
    
    conn.commit()

def insert_song(conn, title, group_id, album, year, is_title_track, youtube_id=None, song_type="title_track"):
    """Insert a song, skip if duplicate."""
    cursor = conn.cursor()
    
    # Clean title
    title = title.strip()
    if not title:
        return False
    
    # Check for duplicate
    cursor.execute("SELECT id FROM songs WHERE title = ? AND group_id = ?", (title, group_id))
    if cursor.fetchone():
        return False
    
    difficulty = 1 if is_title_track else 3
    
    try:
        cursor.execute("""
            INSERT INTO songs (title, group_id, album, year, is_title_track, youtube_id, difficulty, song_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, group_id, album, year, 1 if is_title_track else 0, youtube_id, difficulty, song_type))
        return True
    except sqlite3.IntegrityError:
        return False

def scrape_wikipedia_discography(group_name, wiki_slug, group_id, conn):
    """Scrape a Wikipedia discography page for songs."""
    url = f"https://en.wikipedia.org/wiki/{wiki_slug}"
    songs_added = 0
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  ⚠ HTTP {resp.status_code} for {url}")
            return 0
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Find all tables (Wikipedia discography pages use wikitables)
        tables = soup.find_all('table', class_='wikitable')
        
        for table in tables:
            rows = table.find_all('tr')
            if not rows:
                continue
            
            # Analyze header to understand table structure
            header = rows[0]
            headers = [th.get_text(strip=True).lower() for th in header.find_all(['th', 'td'])]
            
            # Look for title/album column indices  
            title_idx = None
            year_idx = None
            album_idx = None
            
            for i, h in enumerate(headers):
                if 'title' in h or 'single' in h or 'name' in h:
                    title_idx = i
                if 'year' in h or 'date' in h or 'released' in h or 'release' in h:
                    year_idx = i
                if 'album' in h:
                    album_idx = i
            
            if title_idx is None:
                # Try first column as title
                if len(headers) > 0:
                    title_idx = 0
                else:
                    continue
            
            # Determine if this is a singles table
            # Check section headers before this table
            prev_elem = table.find_previous(['h2', 'h3', 'h4'])
            section_title = prev_elem.get_text(strip=True).lower() if prev_elem else ""
            
            is_singles_section = any(kw in section_title for kw in ['single', 'digital', 'promotional'])
            is_album_section = any(kw in section_title for kw in ['studio album', 'compilation', 'extended play', 'ep', 'mini album', 'repackage'])
            
            # Parse rows
            current_rowspan_title = None
            rowspan_count = 0
            
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if not cells or len(cells) < 2:
                    continue
                
                try:
                    # Handle rowspan
                    cell = cells[title_idx] if title_idx < len(cells) else cells[0]
                    
                    # Extract text, cleaning up references
                    for sup in cell.find_all('sup'):
                        sup.decompose()
                    
                    title_text = cell.get_text(strip=True)
                    title_text = re.sub(r'\[.*?\]', '', title_text).strip()
                    title_text = title_text.strip('"').strip("'").strip()
                    
                    if not title_text or title_text == '—' or title_text == '-' or len(title_text) > 100:
                        continue
                    
                    # Skip header-like rows
                    if title_text.lower() in ['title', 'year', 'single details', 'album details', 'name']:
                        continue
                    
                    # Extract year
                    year = None
                    if year_idx and year_idx < len(cells):
                        year_text = cells[year_idx].get_text(strip=True)
                        year_match = re.search(r'(20\d{2}|199\d|198\d)', year_text)
                        if year_match:
                            year = int(year_match.group(1))
                    
                    # If no year found, try to find any year in the row
                    if not year:
                        row_text = row.get_text()
                        year_match = re.search(r'(20\d{2}|199\d)', row_text)
                        if year_match:
                            year = int(year_match.group(1))
                    
                    # Extract album name
                    album = None
                    if album_idx and album_idx < len(cells):
                        album = cells[album_idx].get_text(strip=True)
                        album = re.sub(r'\[.*?\]', '', album).strip().strip('"')
                    
                    # For album tables, the title IS the album name — we want individual tracks
                    if is_album_section and not is_singles_section:
                        # This is likely album names, not individual songs
                        # Still add them as album title tracks
                        if insert_song(conn, title_text, group_id, title_text, year, True, song_type="album_title"):
                            songs_added += 1
                    elif is_singles_section or 'single' in section_title:
                        if insert_song(conn, title_text, group_id, album, year, True, song_type="single"):
                            songs_added += 1
                    else:
                        # Default: add as potential title track
                        if insert_song(conn, title_text, group_id, album, year, True, song_type="title_track"):
                            songs_added += 1
                            
                except (IndexError, ValueError, AttributeError) as e:
                    continue
        
        # Also try to find songs from the main article text (for lists)
        # Look for discography lists
        for ul in soup.find_all('ul'):
            prev = ul.find_previous(['h2', 'h3', 'h4'])
            if not prev:
                continue
            section = prev.get_text(strip=True).lower()
            if not any(kw in section for kw in ['single', 'discograph', 'song']):
                continue
            
            for li in ul.find_all('li', recursive=False):
                for sup in li.find_all('sup'):
                    sup.decompose()
                text = li.get_text(strip=True)
                text = re.sub(r'\[.*?\]', '', text)
                
                # Pattern: "Song Title" (year) or Song Title (year)
                match = re.match(r'"([^"]+)".*?(\d{4})', text)
                if not match:
                    match = re.match(r"'([^']+)'.*?(\d{4})", text)
                if match:
                    song_title = match.group(1).strip()
                    year = int(match.group(2))
                    if insert_song(conn, song_title, group_id, None, year, True, song_type="single"):
                        songs_added += 1
        
        conn.commit()
        return songs_added
        
    except Exception as e:
        print(f"  ✗ Error scraping {group_name}: {e}")
        return 0

def insert_known_tracks(conn):
    """Insert our curated list of known title tracks."""
    total = 0
    for group_id, tracks in KNOWN_TITLE_TRACKS.items():
        group_added = 0
        for track_data in tracks:
            title, album, year, youtube_id = track_data
            if insert_song(conn, title, group_id, album, year, True, youtube_id, "title_track"):
                group_added += 1
        total += group_added
        if group_added > 0:
            print(f"  ✓ Known tracks for group {group_id}: +{group_added}")
    conn.commit()
    return total

def generate_questions(conn):
    """Generate quiz questions from the song database."""
    cursor = conn.cursor()
    questions_added = 0
    
    # Get all songs with group info
    cursor.execute("""
        SELECT s.id, s.title, s.group_id, g.name as group_name, s.album, s.year, s.is_title_track
        FROM songs s
        JOIN groups g ON s.group_id = g.id
        WHERE s.is_title_track = 1
        ORDER BY RANDOM()
    """)
    songs = cursor.fetchall()
    
    # Get all group names for wrong answers
    cursor.execute("SELECT id, name, gender FROM groups WHERE name != '' ORDER BY name")
    all_groups = cursor.fetchall()
    male_groups = [g for g in all_groups if g[2] == 'male']
    female_groups = [g for g in all_groups if g[2] == 'female']
    
    # Get songs per group for "NOT a song" questions
    cursor.execute("""
        SELECT s.group_id, g.name, s.title 
        FROM songs s JOIN groups g ON s.group_id = g.id
        WHERE s.is_title_track = 1
    """)
    group_songs = {}
    for row in cursor.fetchall():
        gid, gname, title = row
        if gid not in group_songs:
            group_songs[gid] = (gname, [])
        group_songs[gid][1].append(title)
    
    # Count existing questions to avoid too many dupes
    cursor.execute("SELECT question_text FROM questions")
    existing_questions = {row[0] for row in cursor.fetchall()}
    
    def add_question(qtype, difficulty, category, question_text, correct_answer, metadata):
        nonlocal questions_added
        if question_text in existing_questions:
            return False
        try:
            cursor.execute("""
                INSERT INTO questions (type, difficulty, category, question_text, correct_answer, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (qtype, difficulty, category, question_text, correct_answer, json.dumps(metadata)))
            existing_questions.add(question_text)
            questions_added += 1
            return True
        except:
            return False
    
    print("\nGenerating questions...")
    
    # Type 1: "Which group released [song]?"
    for song in songs:
        sid, title, gid, gname, album, year, is_tt = song
        q = f'Which group released the song "{title}"?'
        
        # Find similar groups for wrong answers
        gender = 'male'
        for g in all_groups:
            if g[0] == gid:
                gender = g[2]
                break
        pool = male_groups if gender == 'male' else female_groups
        wrong_pool = [g[1] for g in pool if g[0] != gid]
        
        metadata = {
            "correct_group_id": gid,
            "options_pool": f"groups_{gender}",
            "wrong_answers": wrong_pool[:20] if len(wrong_pool) > 20 else wrong_pool
        }
        
        diff = 1 if gname in ['BTS', 'BLACKPINK', 'TWICE', 'EXO', 'Red Velvet', 'Stray Kids', 'SEVENTEEN', 'aespa', 'IVE', 'NewJeans / NJZ', "Girls' Generation (SNSD)", 'BIGBANG', 'SUPER JUNIOR'] else 2
        
        add_question('text', diff, 'song_group', q, gname, metadata)
    
    # Type 2: "What year was [song] released?" (only for songs with year)
    for song in songs:
        sid, title, gid, gname, album, year, is_tt = song
        if not year:
            continue
        
        q = f'What year was "{title}" by {gname} released?'
        
        # Generate plausible wrong years
        wrong_years = [str(year + d) for d in [-2, -1, 1, 2] if 2005 <= year + d <= 2025]
        
        metadata = {
            "correct_year": year,
            "options_pool": "years",
            "wrong_answers": wrong_years
        }
        
        add_question('text', 2, 'song_year', q, str(year), metadata)
    
    # Type 3: "Which album features [song]?" (only for songs with album)
    for song in songs:
        sid, title, gid, gname, album, year, is_tt = song
        if not album or album == title:
            continue
        
        q = f'Which album features the song "{title}" by {gname}?'
        
        # Get other albums by the same group for wrong answers
        cursor.execute("SELECT DISTINCT album FROM songs WHERE group_id = ? AND album IS NOT NULL AND album != ? AND album != ''", (gid, album))
        other_albums = [row[0] for row in cursor.fetchall()]
        
        # Also get albums from other groups
        cursor.execute("SELECT DISTINCT album FROM songs WHERE group_id != ? AND album IS NOT NULL AND album != '' ORDER BY RANDOM() LIMIT 10", (gid,))
        other_group_albums = [row[0] for row in cursor.fetchall()]
        
        all_wrong = other_albums + other_group_albums
        if len(all_wrong) < 3:
            continue  # Need at least 3 wrong answers
        
        metadata = {
            "correct_album": album,
            "options_pool": "albums",
            "wrong_answers": all_wrong[:15]
        }
        
        add_question('text', 3, 'song_album', q, album, metadata)
    
    # Type 4: "Which of these is NOT a [group] song?"
    for gid, (gname, songs_list) in group_songs.items():
        if len(songs_list) < 4:
            continue
        
        # Get songs from OTHER groups to use as the correct answer (the NOT one)
        other_songs = []
        for other_gid, (other_gname, other_songs_list) in group_songs.items():
            if other_gid != gid:
                other_songs.extend(other_songs_list)
        
        if not other_songs:
            continue
        
        # Pick a few "not" songs
        import random
        random.shuffle(other_songs)
        
        for not_song in other_songs[:3]:
            q = f'Which of these is NOT a {gname} song?'
            
            # Use 3 real songs + 1 fake as options
            real_songs = random.sample(songs_list, min(3, len(songs_list)))
            
            metadata = {
                "correct_answer_is_not": True,
                "real_songs": real_songs,
                "options_pool": "songs",
                "wrong_answers": real_songs  # The "wrong" answers for this question are the REAL songs
            }
            
            diff = 2
            add_question('text', diff, 'song_not', q, not_song, metadata)
    
    # Type 5: "Which song is by [group]?" (reverse of type 1)
    for gid, (gname, songs_list) in group_songs.items():
        if not songs_list:
            continue
        
        import random
        for real_song in random.sample(songs_list, min(3, len(songs_list))):
            q = f'Which of these songs is by {gname}?'
            
            # Get wrong songs from other groups
            wrong_songs = []
            for other_gid, (_, other_songs_list) in group_songs.items():
                if other_gid != gid:
                    wrong_songs.extend(other_songs_list[:2])
            
            random.shuffle(wrong_songs)
            
            metadata = {
                "correct_group_id": gid,
                "options_pool": "songs_mixed",
                "wrong_answers": wrong_songs[:15]
            }
            
            diff = 1 if gname in ['BTS', 'BLACKPINK', 'TWICE'] else 2
            add_question('text', diff, 'group_song', q, real_song, metadata)
    
    conn.commit()
    return questions_added

def main():
    print("=" * 60)
    print("K-POP DISCOGRAPHY SCRAPER & QUESTION GENERATOR")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Step 0: Ensure schema
    print("\n📋 Checking schema...")
    ensure_schema(conn)
    
    # Check initial count
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM songs")
    initial_songs = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM questions")
    initial_questions = cursor.fetchone()[0]
    print(f"  Starting with {initial_songs} songs, {initial_questions} questions")
    
    # Step 1: Insert known title tracks (curated data — highest quality)
    print("\n🎵 Inserting curated title tracks...")
    known_added = insert_known_tracks(conn)
    print(f"  Added {known_added} curated title tracks")
    
    # Step 2: Scrape Wikipedia discographies
    print("\n🌐 Scraping Wikipedia discographies...")
    wiki_total = 0
    groups_scraped = []
    
    for group_id, (group_name, wiki_slug) in TOP_GROUPS.items():
        print(f"  Scraping {group_name}...", end=" ", flush=True)
        added = scrape_wikipedia_discography(group_name, wiki_slug, group_id, conn)
        wiki_total += added
        if added > 0:
            groups_scraped.append(group_name)
        print(f"+{added} songs")
        time.sleep(1)  # Be nice to Wikipedia
    
    # Step 3: Generate questions
    print("\n❓ Generating questions...")
    questions_added = generate_questions(conn)
    
    # Final report
    cursor.execute("SELECT COUNT(*) FROM songs")
    final_songs = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM questions")
    final_questions = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT group_id) FROM songs")
    groups_with_songs = cursor.fetchone()[0]
    
    # Per-group breakdown
    cursor.execute("""
        SELECT g.name, COUNT(s.id) as song_count 
        FROM songs s JOIN groups g ON s.group_id = g.id 
        GROUP BY g.id ORDER BY song_count DESC
    """)
    group_breakdown = cursor.fetchall()
    
    # Question breakdown
    cursor.execute("SELECT category, COUNT(*) FROM questions GROUP BY category ORDER BY COUNT(*) DESC")
    q_breakdown = cursor.fetchall()
    
    print("\n" + "=" * 60)
    print("📊 FINAL REPORT")
    print("=" * 60)
    print(f"  Songs: {initial_songs} → {final_songs} (+{final_songs - initial_songs})")
    print(f"  Questions: {initial_questions} → {final_questions} (+{final_questions - initial_questions})")
    print(f"  Groups with songs: {groups_with_songs}")
    print(f"  Curated tracks added: {known_added}")
    print(f"  Wikipedia tracks added: {wiki_total}")
    print(f"  Groups scraped from Wikipedia: {len(groups_scraped)}")
    
    print(f"\n  📀 Songs per group (top 30):")
    for gname, count in group_breakdown[:30]:
        print(f"    {gname}: {count}")
    
    print(f"\n  ❓ Questions by category:")
    for cat, count in q_breakdown:
        print(f"    {cat}: {count}")
    
    conn.close()
    print("\n✅ Done!")

if __name__ == "__main__":
    main()
