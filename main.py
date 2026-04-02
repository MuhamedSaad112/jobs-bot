"""
╔══════════════════════════════════════════════════════════════════╗
║          GULF JOB HUNTER — Professional Edition                  ║
║          Java / Spring Boot / Backend — خليج عربي               ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import re
import sys
import time
import json
import signal
import logging
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

import requests

# ══════════════════════════════════════════════════════════════════
#  ENV CONFIG  (نفس طريقتك الأصلية بالـ env variables)
# ══════════════════════════════════════════════════════════════════

BOT_TOKEN    = os.getenv("BOT_TOKEN")
CHAT_ID      = os.getenv("CHAT_ID")
SERVICE_NAME = os.getenv("SERVICE_NAME", "jobs-bot")

# Optional API keys — اتركهم فاضيين لو مش عندك
ADZUNA_APP_ID  = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_API_KEY = os.getenv("ADZUNA_API_KEY", "")
JSEARCH_KEY    = os.getenv("JSEARCH_KEY", "")

# ══════════════════════════════════════════════════════════════════
#  KEYWORDS
# ══════════════════════════════════════════════════════════════════

KEYWORDS = [
    "java",
    "backend",
    "back-end",
    "spring",
    "spring boot",
    "java developer",
    "java engineer",
    "backend developer",
    "backend engineer",
    "java backend",
    "software engineer java",
    "jvm",
    "kotlin",
    "microservice",
    "microservices",
    "hibernate",
    "rest api",
    "restful",
]

# ══════════════════════════════════════════════════════════════════
#  GULF LOCATION KEYWORDS
# ══════════════════════════════════════════════════════════════════

GULF_LOCATIONS = [
    "saudi", "ksa", "riyadh", "jeddah", "dammam", "mecca", "medina",
    "khobar", "tabuk", "saudi arabia",
    "uae", "dubai", "abu dhabi", "sharjah", "ajman",
    "united arab emirates", "abu-dhabi",
    "qatar", "doha",
    "kuwait", "kuwait city",
    "bahrain", "manama",
    "oman", "muscat",
    "egypt", "cairo",
    "remote", "worldwide", "global", "anywhere",
]

# ══════════════════════════════════════════════════════════════════
#  PERSISTENT DEDUP  (يتذكر الوظايف حتى بعد restart)
# ══════════════════════════════════════════════════════════════════

SEEN_FILE = "seen_jobs.json"


def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def save_seen(seen: set) -> None:
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen), f)
    except Exception as e:
        logging.warning(f"Could not save seen_jobs: {e}")


sent_jobs: set = load_seen()
running = True

# ══════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("gulf_bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("GulfBot")

# ══════════════════════════════════════════════════════════════════
#  TELEGRAM  (نفس اللي عندك)
# ══════════════════════════════════════════════════════════════════

def send_message(text: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN or CHAT_ID")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }, timeout=20)
        print("Telegram:", response.status_code)
    except Exception as e:
        print("Telegram send error:", e)


def startup_message() -> None:
    send_message(
        "بِسْمِ اللهِ الرَّحْمٰنِ الرَّحِيمِ 🌿\n"
        "اللَّهُمَّ صَلِّ عَلَىٰ مُحَمَّدٍ ﷺ 🤍\n"
        "أَسْتَغْفِرُ اللَّهَ الْعَظِيمَ وَأَتُوبُ إِلَيْهِ 🤲\n\n"
        "تم تشغيل البوت بنجاح ✅\n"
        f"الخدمة: {SERVICE_NAME}\n"
        "المصادر: 15 موقع خليجي وعالمي 🌍"
    )


def shutdown_message() -> None:
    send_message(
        "بِسْمِ اللهِ الرَّحْمٰنِ الرَّحِيمِ 🌿\n"
        "اللَّهُمَّ صَلِّ عَلَىٰ مُحَمَّدٍ ﷺ 🤍\n"
        "أَسْتَغْفِرُ اللَّهَ الْعَظِيمَ وَأَتُوبُ إِلَيْهِ 🤲\n\n"
        "تم إيقاف البوت 🛑\n"
        f"الخدمة: {SERVICE_NAME}"
    )

# ══════════════════════════════════════════════════════════════════
#  FILTER & FORMAT  (نفس منطق is_match الأصلي + location check)
# ══════════════════════════════════════════════════════════════════

def is_match(job: dict, check_location: bool = True) -> bool:
    keyword_text = " ".join([
        job.get("title", ""),
        job.get("company", ""),
        job.get("tags", ""),
        job.get("description", ""),
        job.get("category", ""),
    ]).lower()

    if not any(k in keyword_text for k in KEYWORDS):
        return False

    if check_location:
        loc_text = " ".join([
            job.get("location", ""),
            job.get("country", ""),
        ]).lower()
        if not any(g in loc_text for g in GULF_LOCATIONS):
            return False

    return True


def location_flag(loc: str) -> str:
    l = loc.lower()
    if any(x in l for x in ["saudi", "ksa", "riyadh", "jeddah"]): return "🇸🇦"
    if any(x in l for x in ["uae", "dubai", "abu dhabi", "sharjah"]): return "🇦🇪"
    if any(x in l for x in ["qatar", "doha"]): return "🇶🇦"
    if any(x in l for x in ["kuwait"]): return "🇰🇼"
    if any(x in l for x in ["bahrain", "manama"]): return "🇧🇭"
    if any(x in l for x in ["oman", "muscat"]): return "🇴🇲"
    if any(x in l for x in ["egypt", "cairo"]): return "🇪🇬"
    return "🌐"


def format_job_message(job: dict) -> str:
    loc    = job.get("location", "Remote")
    salary = job.get("salary", "")
    tags   = job.get("tags", "")
    flag   = location_flag(loc)

    lines = [
        "🔥 وظيفة جديدة",
        f"📌 {job['title']}",
        f"🏢 {job['company']}",
        f"{flag} {loc}",
        f"🌐 {job['source']}",
    ]
    if salary:
        lines.append(f"💰 {salary}")
    if tags:
        lines.append(f"🏷  {tags[:80]}")
    lines.append(f"🔗 {job['url']}")
    lines.append("")
    lines.append("اللَّهُمَّ صَلِّ عَلَىٰ مُحَمَّدٍ ﷺ 🤍")
    lines.append("أَسْتَغْفِرُ اللَّهَ الْعَظِيمَ وَأَتُوبُ إِلَيْهِ 🤲")

    return "\n".join(lines)

# ══════════════════════════════════════════════════════════════════
#  SAFE HTTP HELPERS
# ══════════════════════════════════════════════════════════════════

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; GulfJobBot/1.0)"}


def safe_get(url: str, headers: dict = None, params: dict = None, timeout: int = 20):
    try:
        r = requests.get(
            url,
            headers={**HEADERS, **(headers or {})},
            params=params,
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning(f"GET failed [{url[:55]}]: {e}")
        return None


def safe_get_xml(url: str, timeout: int = 20):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return ET.fromstring(r.content)
    except Exception as e:
        log.warning(f"XML GET failed [{url[:55]}]: {e}")
        return None


def extract_jsonld_jobs(html: str, page_url: str, source_name: str) -> list:
    jobs = []
    for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL):
        try:
            data = json.loads(m)
            items = data if isinstance(data, list) else [data]
            for j in items:
                if j.get("@type") != "JobPosting":
                    continue
                loc_data = j.get("jobLocation", {})
                if isinstance(loc_data, list):
                    loc_data = loc_data[0] if loc_data else {}
                addr = loc_data.get("address", {}) if isinstance(loc_data, dict) else {}
                loc  = f"{addr.get('addressLocality','')} {addr.get('addressCountry','')}".strip()
                jobs.append({
                    "title":    j.get("title", ""),
                    "company":  j.get("hiringOrganization", {}).get("name", ""),
                    "url":      j.get("url", page_url),
                    "location": loc,
                    "tags": "", "salary": "", "category": "", "description": "",
                    "source": source_name,
                })
        except Exception:
            pass
    return jobs

# ══════════════════════════════════════════════════════════════════
#  SOURCES
# ══════════════════════════════════════════════════════════════════

# ─── 1. Remotive (مصدرك الأصلي — محسّن)
def get_remotive_jobs() -> list:
    data = safe_get("https://remotive.com/api/remote-jobs?limit=50")
    if not data:
        return []
    jobs = []
    for j in data.get("jobs", []):
        jobs.append({
            "title":    j.get("title", ""),
            "company":  j.get("company_name", ""),
            "url":      j.get("url", ""),
            "location": j.get("candidate_required_location", "Remote"),
            "tags":     ", ".join(j.get("tags", [])),
            "salary":   j.get("salary", ""),
            "category": j.get("category", ""),
            "description": "",
            "source":   "Remotive",
        })
    return jobs


# ─── 2. Bayt.com  (أكبر موقع خليجي)
def get_bayt_jobs() -> list:
    jobs = []
    for q in ["java-developer", "spring-boot-developer", "backend-developer"]:
        url = f"https://www.bayt.com/en/international/jobs/{q}-jobs/"
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            jobs.extend(extract_jsonld_jobs(r.text, url, "Bayt.com"))
        except Exception as e:
            log.warning(f"Bayt error [{q}]: {e}")
    return jobs


# ─── 3. Naukrigulf
def get_naukrigulf_jobs() -> list:
    jobs = []
    for s in ["java-developer", "spring-boot-developer", "backend-developer"]:
        url = f"https://www.naukrigulf.com/{s}-jobs"
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            jobs.extend(extract_jsonld_jobs(r.text, url, "Naukrigulf"))
        except Exception as e:
            log.warning(f"Naukrigulf error [{s}]: {e}")
    return jobs


# ─── 4. GulfTalent
def get_gulftalent_jobs() -> list:
    jobs = []
    for q in ["java developer", "spring boot", "backend developer"]:
        url = f"https://www.gulftalent.com/jobs/search?q={quote_plus(q)}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            jobs.extend(extract_jsonld_jobs(r.text, url, "GulfTalent"))
        except Exception as e:
            log.warning(f"GulfTalent error: {e}")
    return jobs


# ─── 5. Wuzzuf (مصر والخليج)
def get_wuzzuf_jobs() -> list:
    try:
        r = requests.get(
            "https://wuzzuf.net/search/jobs/?q=java+spring&a=hpb",
            headers=HEADERS, timeout=25,
        )
        return extract_jsonld_jobs(r.text, "https://wuzzuf.net", "Wuzzuf")
    except Exception as e:
        log.warning(f"Wuzzuf error: {e}")
        return []


# ─── 6. LinkedIn Gulf (public guest API — no login needed)
def get_linkedin_jobs() -> list:
    jobs = []
    gulf_countries = [
        "UAE", "Saudi Arabia", "Qatar",
        "Kuwait", "Bahrain", "Oman", "Egypt",
    ]
    for country in gulf_countries:
        url = (
            "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
            f"?keywords=java+spring+boot+backend&location={quote_plus(country)}&start=0"
        )
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            titles    = re.findall(r'class="base-search-card__title"[^>]*>\s*(.*?)\s*</h3>', r.text, re.DOTALL)
            companies = re.findall(r'class="base-search-card__subtitle"[^>]*>\s*<[^>]+>\s*(.*?)\s*</a>', r.text, re.DOTALL)
            urls      = re.findall(r'class="base-card__full-link[^"]*"\s+href="([^"?]+)', r.text)
            for i, job_url in enumerate(urls):
                jobs.append({
                    "title":    titles[i].strip()    if i < len(titles)    else "Java/Backend Role",
                    "company":  companies[i].strip() if i < len(companies) else "",
                    "url":      job_url,
                    "location": country,
                    "tags": "", "salary": "", "category": "", "description": "",
                    "source": f"LinkedIn ({country})",
                })
        except Exception as e:
            log.warning(f"LinkedIn ({country}) error: {e}")
    return jobs


# ─── 7. Indeed Gulf (RSS feeds — واحدة لكل دولة)
def get_indeed_rss_jobs() -> list:
    feeds = [
        ("https://ae.indeed.com/rss?q=java+spring+boot+backend&l=",   "UAE"),
        ("https://sa.indeed.com/rss?q=java+spring+boot+backend&l=",   "Saudi Arabia"),
        ("https://qa.indeed.com/rss?q=java+spring+boot+backend&l=",   "Qatar"),
        ("https://kw.indeed.com/rss?q=java+spring+boot+backend&l=",   "Kuwait"),
        ("https://bh.indeed.com/rss?q=java+spring+boot+backend&l=",   "Bahrain"),
        ("https://www.indeed.com/rss?q=java+spring+boot&l=Dubai",     "Dubai"),
        ("https://www.indeed.com/rss?q=java+spring+boot&l=Riyadh",    "Riyadh"),
    ]
    jobs = []
    for feed_url, country in feeds:
        root = safe_get_xml(feed_url)
        if root is None:
            continue
        for item in root.iter("item"):
            title   = item.findtext("title", "")
            company = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title, company = parts[0].strip(), parts[1].strip()
            jobs.append({
                "title":    title,
                "company":  company,
                "url":      item.findtext("link", ""),
                "location": country,
                "tags": "", "salary": "", "category": "", "description": "",
                "source": f"Indeed ({country})",
            })
    return jobs


# ─── 8. Adzuna Gulf (free API — سجّل على developer.adzuna.com)
def get_adzuna_gulf_jobs() -> list:
    if not ADZUNA_APP_ID:
        return []
    jobs = []
    for country_code in ["ae", "sa", "qa", "kw"]:
        data = safe_get(
            f"https://api.adzuna.com/v1/api/jobs/{country_code}/search/1",
            params={
                "app_id":           ADZUNA_APP_ID,
                "app_key":          ADZUNA_API_KEY,
                "results_per_page": 30,
                "what":             "java spring boot backend",
                "content-type":     "application/json",
            },
        )
        if not data:
            continue
        for j in data.get("results", []):
            sal_min = j.get("salary_min", "")
            sal_max = j.get("salary_max", "")
            salary  = f"{sal_min}-{sal_max}".strip("-") if (sal_min or sal_max) else ""
            jobs.append({
                "title":    j.get("title", ""),
                "company":  j.get("company", {}).get("display_name", ""),
                "url":      j.get("redirect_url", ""),
                "location": j.get("location", {}).get("display_name", ""),
                "tags": "", "salary": salary, "category": "", "description": "",
                "source": f"Adzuna ({country_code.upper()})",
            })
    return jobs


# ─── 9. JSearch via RapidAPI (يجمع Indeed + LinkedIn + Glassdoor)
def get_jsearch_gulf_jobs() -> list:
    if not JSEARCH_KEY:
        return []
    jobs = []
    queries = [
        "java spring boot developer in UAE",
        "java backend developer in Saudi Arabia",
        "software engineer java in Qatar",
        "java developer in Kuwait OR Bahrain OR Oman",
    ]
    for q in queries:
        data = safe_get(
            "https://jsearch.p.rapidapi.com/search",
            headers={
                "X-RapidAPI-Key":  JSEARCH_KEY,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
            },
            params={"query": q, "page": "1", "num_pages": "1", "date_posted": "week"},
        )
        if not data:
            continue
        for j in data.get("data", []):
            salary = ""
            if j.get("job_min_salary"):
                salary = f"{j.get('job_salary_currency','')} {j.get('job_min_salary','')}".strip()
            jobs.append({
                "title":    j.get("job_title", ""),
                "company":  j.get("employer_name", ""),
                "url":      j.get("job_apply_link", ""),
                "location": f"{j.get('job_city','')} {j.get('job_country','')}".strip(),
                "tags": "", "salary": salary, "category": "", "description": "",
                "source": "JSearch",
            })
    return jobs


# ─── 10. RemoteOK
def get_remoteok_jobs() -> list:
    data = safe_get("https://remoteok.com/api")
    if not isinstance(data, list):
        return []
    jobs = []
    for j in data[1:50]:
        jobs.append({
            "title":    j.get("position", ""),
            "company":  j.get("company", ""),
            "url":      "https://remoteok.com" + j.get("url", ""),
            "location": j.get("location", "Remote"),
            "tags":     ", ".join(j.get("tags", [])),
            "salary":   j.get("salary", ""),
            "category": "", "description": "",
            "source":   "RemoteOK",
        })
    return jobs


# ─── 11. Arbeitnow
def get_arbeitnow_jobs() -> list:
    data = safe_get("https://www.arbeitnow.com/api/job-board-api")
    if not data:
        return []
    jobs = []
    for j in data.get("data", [])[:40]:
        jobs.append({
            "title":    j.get("title", ""),
            "company":  j.get("company_name", ""),
            "url":      j.get("url", ""),
            "location": j.get("location", ""),
            "tags":     ", ".join(j.get("tags", [])),
            "salary": "", "category": "", "description": "",
            "source": "Arbeitnow",
        })
    return jobs


# ─── 12. Jobicy
def get_jobicy_jobs() -> list:
    data = safe_get("https://jobicy.com/api/v2/remote-jobs?count=30&tag=java")
    if not data:
        return []
    jobs = []
    for j in data.get("jobs", []):
        jobs.append({
            "title":    j.get("jobTitle", ""),
            "company":  j.get("companyName", ""),
            "url":      j.get("url", ""),
            "location": j.get("jobGeo", "Remote"),
            "tags":     ", ".join(j.get("jobIndustry", [])),
            "salary":   str(j.get("annualSalaryMin", "")) if j.get("annualSalaryMin") else "",
            "category": "", "description": "",
            "source":   "Jobicy",
        })
    return jobs


# ─── 13. Himalayas
def get_himalayas_jobs() -> list:
    data = safe_get("https://himalayas.app/jobs/api?skills=java&skills=spring-boot&limit=30")
    if not data:
        return []
    jobs = []
    for j in data.get("jobs", []):
        jobs.append({
            "title":    j.get("title", ""),
            "company":  j.get("company", {}).get("name", ""),
            "url":      j.get("applicationLink", ""),
            "location": j.get("location", "Remote"),
            "tags":     ", ".join(s.get("name", "") for s in j.get("skills", [])),
            "salary": "", "category": "", "description": "",
            "source": "Himalayas",
        })
    return jobs


# ─── 14. WeWorkRemotely RSS
def get_wwr_jobs() -> list:
    root = safe_get_xml("https://weworkremotely.com/categories/remote-programming-jobs.rss")
    if root is None:
        return []
    jobs = []
    for item in root.iter("item"):
        title   = item.findtext("title", "")
        company = ""
        if ": " in title:
            company, title = title.split(": ", 1)
        jobs.append({
            "title":    title.strip(),
            "company":  company.strip(),
            "url":      item.findtext("link", ""),
            "location": "Remote",
            "tags": "", "salary": "", "category": "", "description": "",
            "source": "WeWorkRemotely",
        })
    return jobs


# ─── 15. Greenhouse (open company boards — Stripe, Shopify, Coinbase …)
GREENHOUSE_COMPANIES = [
    "stripe", "shopify", "coinbase", "figma", "notion",
    "brex", "plaid", "gusto", "rippling", "intercom",
]


def get_greenhouse_jobs() -> list:
    jobs = []
    for company in GREENHOUSE_COMPANIES:
        data = safe_get(f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs")
        if not data:
            continue
        for j in data.get("jobs", []):
            jobs.append({
                "title":    j.get("title", ""),
                "company":  company.capitalize(),
                "url":      j.get("absolute_url", ""),
                "location": j.get("location", {}).get("name", ""),
                "tags": "", "salary": "", "category": "", "description": "",
                "source": "Greenhouse",
            })
    return jobs

# ══════════════════════════════════════════════════════════════════
#  SOURCE REGISTRY
#  (name, function, check_gulf_location?)
#  False = مصدر خليجي اصلاً → مش محتاج location filter
#  True  = مصدر عالمي      → محتاج نتأكد من location
# ══════════════════════════════════════════════════════════════════

SOURCES = [
    ("Bayt.com",        get_bayt_jobs,          False),
    ("Naukrigulf",      get_naukrigulf_jobs,     False),
    ("GulfTalent",      get_gulftalent_jobs,     False),
    ("Wuzzuf",          get_wuzzuf_jobs,         False),
    ("LinkedIn Gulf",   get_linkedin_jobs,       False),
    ("Indeed Gulf",     get_indeed_rss_jobs,     False),
    ("Adzuna Gulf",     get_adzuna_gulf_jobs,    False),
    ("JSearch",         get_jsearch_gulf_jobs,   False),
    ("Remotive",        get_remotive_jobs,       True),
    ("RemoteOK",        get_remoteok_jobs,       True),
    ("Arbeitnow",       get_arbeitnow_jobs,      True),
    ("Jobicy",          get_jobicy_jobs,         True),
    ("Himalayas",       get_himalayas_jobs,      True),
    ("WeWorkRemotely",  get_wwr_jobs,            True),
    ("Greenhouse",      get_greenhouse_jobs,     True),
]

# ══════════════════════════════════════════════════════════════════
#  GET JOBS  (نفس اسم الدالة في كودك الأصلي)
# ══════════════════════════════════════════════════════════════════

def get_jobs() -> list:
    all_jobs = []
    for name, fn, check_loc in SOURCES:
        try:
            batch = fn()
            log.info(f"[{name}] {len(batch)} jobs fetched")
            for j in batch:
                j["_check_location"] = check_loc
            all_jobs.extend(batch)
        except Exception as e:
            log.error(f"[{name}] error: {e}")
    return all_jobs

# ══════════════════════════════════════════════════════════════════
#  SIGNAL HANDLING  (نفس كودك بالظبط)
# ══════════════════════════════════════════════════════════════════

def handle_exit(signum, frame):
    global running
    print(f"Received signal: {signum}")
    running = False
    shutdown_message()
    sys.exit(0)

# ══════════════════════════════════════════════════════════════════
#  MAIN  (نفس structure كودك الأصلي)
# ══════════════════════════════════════════════════════════════════

def main():
    global running

    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)

    if not BOT_TOKEN or not CHAT_ID:
        print("Error: BOT_TOKEN or CHAT_ID is missing")
        return

    startup_message()
    print("Bot started...")

    while running:
        try:
            jobs = get_jobs()

            for job in jobs:
                job_url = job.get("url", "").strip()
                if not job_url:
                    continue

                if job_url in sent_jobs:
                    continue

                check_loc = job.pop("_check_location", True)
                if not is_match(job, check_location=check_loc):
                    continue

                send_message(format_job_message(job))
                sent_jobs.add(job_url)
                save_seen(sent_jobs)
                time.sleep(1.5)  # avoid Telegram flood

            print("Checked jobs...")
            time.sleep(300)  # 5 minutes

        except Exception as e:
            print("Error:", e)
            time.sleep(10)


if __name__ == "__main__":
    main()
