"""Fixed lists the generator picks from: names, cities, venues, series, campaigns and programs.

Everything is made up. No real patron, donor or school data is used.
"""

FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda", "David", "Elizabeth",
    "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen",
    "Daniel", "Lisa", "Matthew", "Nancy", "Anthony", "Betty", "Mark", "Sandra", "Steven", "Ashley",
    "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle", "Kenneth", "Carol", "Kevin", "Amanda",
    "Brian", "Melissa", "George", "Deborah", "Timothy", "Stephanie", "Ronald", "Rebecca", "Jason", "Laura",
    "Wei", "Mei", "Hiroshi", "Yuki", "Priya", "Arjun", "Fatima", "Omar", "Aisha", "Musa",
    "Sofia", "Mateo", "Valentina", "Santiago", "Camila", "Diego", "Lucia", "Alejandro", "Isabella", "Gabriel",
    "Olga", "Ivan", "Anna", "Dmitri", "Chiara", "Luca", "Amara", "Kwame", "Nia", "Kofi",
    "Hannah", "Noah", "Leah", "Eli", "Miriam", "Samuel", "Grace", "Julian", "Clara", "Theo",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
    "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
    "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell", "Carter", "Roberts",
    "Chen", "Wang", "Kim", "Park", "Tanaka", "Sato", "Patel", "Shah", "Khan", "Touray",
    "Cohen", "Levy", "Goldberg", "Rossi", "Russo", "Ferrari", "Ivanova", "Petrov", "Mensah", "Okafor",
    "Diallo", "Ndiaye", "Silva", "Santos", "Costa", "Muller", "Schmidt", "Fischer", "Dubois", "Laurent",
]

STREETS = [
    "Broadway", "West 57th St", "Park Ave", "Amsterdam Ave", "Columbus Ave", "Riverside Dr", "Lexington Ave",
    "Madison Ave", "West End Ave", "Central Park West", "Atlantic Ave", "Flatbush Ave", "Court St",
    "Main St", "Elm St", "Oak Ave", "Maple Dr", "Washington St", "Hudson St", "Bleecker St",
]

# (city, state, first 3 digits of zip, weight). Mostly New York area.
CITIES = [
    ("New York", "NY", "100", 40), ("Brooklyn", "NY", "112", 12), ("Queens", "NY", "113", 6),
    ("Bronx", "NY", "104", 3), ("Staten Island", "NY", "103", 1), ("Yonkers", "NY", "107", 2),
    ("White Plains", "NY", "106", 2), ("Jersey City", "NJ", "073", 3), ("Hoboken", "NJ", "070", 2),
    ("Montclair", "NJ", "070", 2), ("Princeton", "NJ", "085", 1), ("Stamford", "CT", "069", 2),
    ("Greenwich", "CT", "068", 2), ("Boston", "MA", "021", 2), ("Philadelphia", "PA", "191", 2),
    ("Washington", "DC", "200", 2), ("Chicago", "IL", "606", 1), ("Los Angeles", "CA", "900", 1),
    ("Miami", "FL", "331", 1),
]

EMAIL_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "icloud.com", "aol.com", "nyu.edu", "columbia.edu", "proton.me"]

# Venues: (id, name, capacity, {price zone: base price})
VENUES = [
    ("V01", "Main Hall", 2800, {"Orchestra": 145, "Parquet": 125, "First Tier": 95, "Second Tier": 75, "Balcony": 45}),
    ("V02", "Recital Hall", 600, {"Orchestra": 75, "Mezzanine": 55, "Balcony": 40}),
    ("V03", "Studio Hall", 270, {"General Admission": 35}),
]

# Series: (genre, venues it plays in, popularity range, price multiplier)
SERIES = {
    "Great Orchestras":  ("Orchestral", ["V01"], (0.55, 1.05), 1.4),
    "Recital Series":    ("Classical Recital", ["V01", "V02"], (0.40, 0.95), 1.1),
    "Chamber Music":     ("Chamber", ["V02"], (0.35, 0.90), 1.0),
    "Jazz Nights":       ("Jazz", ["V01", "V02", "V03"], (0.45, 1.00), 1.0),
    "Global Voices":     ("World Music", ["V02", "V03"], (0.30, 0.90), 0.9),
    "Family Concerts":   ("Family", ["V01", "V03"], (0.60, 1.05), 0.5),
    "New Music Project": ("Contemporary", ["V03"], (0.25, 0.80), 0.8),
}

ARTISTS = [
    "Metropolitan Symphony", "Vienna Chamber Players", "Berlin Radio Orchestra", "Aurora String Quartet",
    "Lincoln Jazz Collective", "Soweto Gospel Ensemble", "Tokyo Philharmonic", "Havana Son Orchestra",
    "Maria Delacroix, piano", "Kenji Aoki, violin", "Amara Diallo, soprano", "Luca Ferri, cello",
    "The Harlem Brass", "Nordic Baroque Consort", "Sitar & Strings", "Youth Orchestra of the Americas",
    "Elena Petrova, piano", "Marcus Hale Trio", "Kora & Voice", "Chicago Wind Quintet",
]

WORKS = [
    "Beethoven 9", "Mahler 2", "Brahms Cycle", "Rachmaninoff Concerto", "Bach Suites", "Schubert Lieder",
    "Ellington Songbook", "Coltrane Tribute", "Songs of West Africa", "Tango Nuevo", "Peter and the Wolf",
    "Carnival of the Animals", "Premieres & Firsts", "Stravinsky Rite", "Debussy Preludes", "Mozart Requiem",
]

CHANNELS = [("Web", 62), ("Phone", 18), ("Box Office", 14), ("Group Sales", 6)]

SUBSCRIPTION_PACKAGES = [("Orchestra 6-Pack", 6, 720), ("Recital 4-Pack", 4, 300), ("Choose-Your-Own 5", 5, 450), ("Jazz 3-Pack", 3, 180)]

CAMPAIGNS = [  # (suffix, type, goal)
    ("Annual Fund", "Annual Fund", 6_000_000),
    ("Opening Night Gala", "Special Event", 4_000_000),
    ("Music Education Campaign", "Program", 2_500_000),
    ("Endowment Drive", "Capital", 10_000_000),
]

FUNDS = [
    ("F01", "Unrestricted Operating", False), ("F02", "Music Education", True), ("F03", "Artistic Excellence", True),
    ("F04", "Endowment", True), ("F05", "Community Access", True),
]

GIFT_TYPES = [("Credit Card", 55), ("Cash", 25), ("Stock", 5), ("Pledge Payment", 15)]

PROGRAMS = [  # (id, name, type, audience)
    ("E01", "Link Up (Orchestra & Classroom)", "In-School", "Grades 3-5"),
    ("E02", "Musical Explorers", "In-School", "Grades K-2"),
    ("E03", "Ensemble Coaching", "In-School", "High School"),
    ("E04", "Family Concert Workshops", "Family", "Families"),
    ("E05", "Youth Orchestra Training", "Youth Ensembles", "Ages 16-19"),
    ("E06", "Lullaby Project", "Community", "Parents & caregivers"),
    ("E07", "Music in Healthcare", "Community", "Adults"),
    ("E08", "Justice Program Workshops", "Community", "Young adults"),
    ("E09", "Teaching Artist Institute", "Professional Learning", "Educators"),
    ("E10", "Summer Music Camp", "Youth Ensembles", "Ages 12-15"),
]

BOROUGHS = [("Manhattan", 25), ("Brooklyn", 30), ("Queens", 25), ("Bronx", 15), ("Staten Island", 5)]

# Email marketing: (campaign type, audience segment, share of the opted-in list it goes to, promotes a series?)
EMAIL_CAMPAIGN_TYPES = [
    ("Weekly Picks", "All opted-in", 0.90, True),
    ("Last Chance", "Recent buyers", 0.35, True),
    ("Season Announcement", "All opted-in", 1.00, False),
    ("Subscriber News", "Current subscribers", 0.08, False),
    ("Lapsed Buyer Win-back", "Lapsed buyers", 0.25, False),
    ("Family Programs", "Family buyers", 0.12, True),
    ("Donor Appeal", "Donors and members", 0.15, False),
]

# Paid ads: (platform, short code, cost per 1,000 impressions, click-through rate)
AD_PLATFORMS = [("Meta Ads", "META", 9.5, 0.011), ("Google Ads", "GADS", 6.0, 0.018)]
