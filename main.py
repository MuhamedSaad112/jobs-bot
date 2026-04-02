import requests
import time

BOT_TOKEN = "8721068528"
CHAT_ID = "5524888947"

KEYWORDS = ["java", "backend", "spring", "spring boot"]

sent_jobs = set()

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": text
    })

def get_jobs():
    url = "https://remotive.com/api/remote-jobs"
    data = requests.get(url).json()
    return data.get("jobs", [])[:20]

def is_match(job):
    text = (
        job.get("title", "") + " " +
        job.get("company_name", "") + " " +
        job.get("description", "")
    ).lower()
    return any(k in text for k in KEYWORDS)

print("Started...")

while True:
    try:
        jobs = get_jobs()

        for job in jobs:
            if job["url"] in sent_jobs:
                continue

            if not is_match(job):
                continue

            msg = f"""🔥 وظيفة جديدة

📌 {job['title']}
🏢 {job['company_name']}

🔗 {job['url']}"""

            send_message(msg)
            sent_jobs.add(job["url"])

        print("Checked...")
        time.sleep(30)

    except Exception as e:
        print("Error:", e)
        time.sleep(10)