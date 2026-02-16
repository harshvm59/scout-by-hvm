"""
SCOUT by HVM — Search Configuration
Target: Senior PM / Director of Growth / Head of Strategy & Ops roles
"""

# ── Search Queries ──────────────────────────────────────────────
SEARCH_QUERIES = [
    "Senior Program Manager",
    "Director of Growth",
    "Head of Strategy and Operations",
    "Senior Product Manager Growth",
    "Business Head",
    "Growth Strategy Lead",
    "Senior Business Manager",
    "Category Head",
    "P&L Manager",
    "Head of Business Operations",
    "AI Operations Manager",
    "Product Strategy Manager",
    "City Business Head",
    "Marketplace Operations Lead",
]

# ── Locations ───────────────────────────────────────────────────
LOCATIONS = [
    "Pune, India",
    "Bangalore, India",
    "Mumbai, India",
    "Gurgaon, India",
    "Hyderabad, India",
    "Delhi, India",
    "Remote",
]

# ── Job Sites ───────────────────────────────────────────────────
SITES = ["linkedin", "indeed", "glassdoor", "google"]

# ── Relevance Scoring ──────────────────────────────────────────
TITLE_KEYWORDS_HIGH = [
    "director", "head", "lead", "senior", "principal", "vp",
    "growth", "strategy", "program", "product", "business",
    "p&l", "marketplace", "category", "city",
]

DESCRIPTION_KEYWORDS_MUST = [
    "strategy", "growth", "program", "product", "operations",
    "p&l", "business", "stakeholder", "cross-functional",
]

DESCRIPTION_KEYWORDS_NICE = [
    "ai", "sql", "data", "analytics", "user acquisition",
    "marketplace", "food", "delivery", "consumer", "fintech",
    "tableau", "dashboard", "okr", "revenue",
]

EXCLUDE_TITLE_KEYWORDS = [
    "intern", "fresher", "junior", "associate", "entry level",
    "trainee", "graduate", "assistant",
]

# ── Filters ─────────────────────────────────────────────────────
MIN_RELEVANCE_SCORE = 30          # Minimum score to keep a job
RESULTS_PER_QUERY = 25            # Results per search query
HOURS_OLD = 24                    # Only scrape jobs posted in last 24h
TOP_JOBS_TO_TAILOR = 20           # Tailor resumes for top N jobs daily
TOP_JOBS_TO_OUTREACH = 10         # Draft outreach for top N jobs daily

# ── Salary (INR Annual) ────────────────────────────────────────
MIN_SALARY_PREFERRED = 2500000    # 25L — preferred minimum
SALARY_BOOST_THRESHOLD = 3500000  # 35L+ gets a score boost
