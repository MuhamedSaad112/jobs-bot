import os
import sys
import time
import signal
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SERVICE_NAME = os.getenv("SERVICE_NAME", "jobs-bot")

KEYWORDS = [
    "java",
    "backend",
    "back-end",
    "spring",
    "spring boot",
    "java developer",
    "backend developer",
    "java backend",
    "software engineer java",
]

sent_jobs = set()
running = True


def send_message(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN or CHAT_ID")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        response = requests.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "disable_web_page_preview": False
            },
            timeout=20
        )
        print("Telegram:", response.json())
    except Exception as e:
        print("Telegram send error:", e)


def startup_message():
    send_message(
        f"""بِسْمِ اللهِ الرَّحْمٰنِ الرَّحِيمِ 🌿

اللَّهُمَّ صَلِّ عَلَىٰ مُحَمَّدٍ ﷺ 🤍
أَسْتَغْفِرُ اللَّهَ الْعَظِيمَ وَأَتُوبُ إِلَيْهِ 🤲

تم تشغيل البوت بنجاح ✅
الخدمة: {SERVICE_NAME}"""
    )


def shutdown_message():
    send_message(
        f"""بِسْمِ اللهِ الرَّحْمٰنِ الرَّحِيمِ 🌿

اللَّهُمَّ صَلِّ عَلَىٰ مُحَمَّدٍ ﷺ 🤍
أَسْتَغْفِرُ اللَّهَ الْعَظِيمَ وَأَتُوبُ إِلَيْهِ 🤲

تم إيقاف البوت 🛑
الخدمة: {SERVICE_NAME}"""
    )


def get_jobs():
    url = "https://remotive.com/api/remote-jobs"
    response = requests.get(url, timeout=30)
    data = response.json()
    return data.get("jobs", [])[:50]


def is_match(job):
    text = " ".join([
        job.get("title", ""),
        job.get("company_name", ""),
        job.get("category", ""),
        job.get("description", ""),
        job.get("candidate_required_location", ""),
    ]).lower()

    return any(keyword in text for keyword in KEYWORDS)


def format_job_message(job):
    return f"""🔥 وظيفة جديدة

📌 {job.get('title', 'N/A')}
🏢 {job.get('company_name', 'N/A')}
📍 {job.get('candidate_required_location', 'Remote')}
🗂 {job.get('category', 'N/A')}

🔗 {job.get('url', 'N/A')}

اللَّهُمَّ صَلِّ عَلَىٰ مُحَمَّدٍ ﷺ 🤍
أَسْتَغْفِرُ اللَّهَ الْعَظِيمَ وَأَتُوبُ إِلَيْهِ 🤲"""


def handle_exit(signum, frame):
    global running
    print(f"Received signal: {signum}")
    running = False
    shutdown_message()
    sys.exit(0)


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
                job_url = job.get("url")
                if not job_url:
                    continue

                if job_url in sent_jobs:
                    continue

                if not is_match(job):
                    continue

                send_message(format_job_message(job))
                sent_jobs.add(job_url)

            print("Checked jobs...")
            time.sleep(30)

        except Exception as e:
            print("Error:", e)
            time.sleep(10)


if __name__ == "__main__":
    main()