import os
import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import google.generativeai as genai

# إعداد نموذج الذكاء الاصطناعي
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

LOG_FILE = "published_log.txt"

def get_logged_ids():
    if not os.path.exists(LOG_FILE):
        return set()
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_new_id(paper_id):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(paper_id + "\n")

# 1. جلب أبحاث الذكاء الاصطناعي الحديثة من arXiv
def fetch_ai_papers():
    url = "http://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.LG&sortBy=submittedDate&sortOrder=descending&max_results=5"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    papers = []
    try:
        with urllib.request.urlopen(req) as response:
            tree = ET.fromstring(response.read())
            for entry in tree.findall('{http://www.w3.org/2005/Atom}entry'):
                paper_id = entry.find('{http://www.w3.org/2005/Atom}id').text.split('/abs/')[-1]
                title = entry.find('{http://www.w3.org/2005/Atom}title').text.strip().replace('\n', ' ')
                summary = entry.find('{http://www.w3.org/2005/Atom}summary').text.strip().replace('\n', ' ')
                published = entry.find('{http://www.w3.org/2005/Atom}published').text[:10]
                link = entry.find('{http://www.w3.org/2005/Atom}id').text
                papers.append({
                    "id": paper_id,
                    "title": title,
                    "summary": summary,
                    "date": published,
                    "url": link,
                    "journal": "arXiv"
                })
    except Exception as e:
        print(f"Error fetching AI papers: {e}")
    return papers

# 2. جلب أبحاث البيولوجيا من Europe PMC (PubMed/Biotech)
def fetch_bio_papers():
    query = '(METHODS:"Microbiology" OR METHODS:"Biotechnology") AND (FIRST_PDATE:[TODAY-2DAYS TO TODAY])'
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={urllib.parse.quote(query)}&format=json&pageSize=5"
    papers = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            results = data.get("resultList", {}).get("result", [])
            for res in results:
                paper_id = res.get("doi") or res.get("id")
                if not paper_id:
                    continue
                papers.append({
                    "id": paper_id,
                    "title": res.get("title", "").strip(),
                    "summary": res.get("abstractText", "No abstract available"),
                    "date": res.get("firstPublicationDate", ""),
                    "url": f"https://doi.org/{res.get('doi')}" if res.get("doi") else f"https://europepmc.org/article/MED/{res.get('id')}",
                    "journal": res.get("journalTitle", "Bio Journal")
                })
    except Exception as e:
        print(f"Error fetching Bio papers: {e}")
    return papers

# 3. صياغة المنشور وفق القالب الإلزامي
def format_post(branch_title, research_idx, paper):
    prompt = f"""
أنت مساعد علمي صارم. التزم بهيكل الصياغة التالي دون أي مقدمات أو هوامش أو اختلاق:

{branch_title}
Research {research_idx:02d}
[اسم النموذج / التقنية]: [عنوان الورقة بالعربية]
المؤسسات والنشر: [المؤسسات المشاركة إن وجدت أو مؤلفي الورقة] — منشور في {paper['journal']} ({paper['date'][:4] if paper['date'] else 'حديثاً'}).
المنهجية والأثر العلمي: [سطران إلى ثلاثة أسطر فقط تشرح التقنية أو المنهج المستخدم والتطبيق والأثر العلمي بدقة، مستنداً فقط للبيانات المرفقة].
المصادر والروابط:
الورقة العلمية: {paper['url']}

بيانات الورقة العلمية الأصلية:
العنوان: {paper['title']}
الملخص: {paper['summary']}

تنبيه إلزامي: احذف سطر GitHub تماماً ولا تذكره أبداً.
"""
    response = model.generate_content(prompt)
    return response.text.strip()

def main():
    logged_ids = get_logged_ids()
    today_str = datetime.now().strftime("%Y-%m-%d")
    daily_bulletin = [f"# 🧬 AI Biology | Microbiology & Biochemistry\nالتاريخ: {today_str}\n"]

    # معالجة فرع الذكاء الاصطناعي
    ai_candidates = fetch_ai_papers()
    ai_new = [p for p in ai_candidates if p['id'] not in logged_ids]
    if ai_new:
        daily_bulletin.append("## 🤖 Artificial Intelligence & AI Technologies\n")
        for i, paper in enumerate(ai_new[:2], 1):
            post = format_post("🧬 AI Biology | Microbiology & Biochemistry\n🤖 Artificial Intelligence & AI Technologies", i, paper)
            daily_bulletin.append(post + "\n\n---\n")
            save_new_id(paper['id'])

    # معالجة فرع البيولوجيا
    bio_candidates = fetch_bio_papers()
    bio_new = [p for p in bio_candidates if p['id'] not in logged_ids]
    if bio_new:
        daily_bulletin.append("## 🧬 Biology | Microbiology & Biotechnology\n")
        for i, paper in enumerate(bio_new[:2], 1):
            post = format_post("🧬 AI Biology | Microbiology & Biochemistry\n🧬 Biology | Microbiology & Biotechnology", i, paper)
            daily_bulletin.append(post + "\n\n---\n")
            save_new_id(paper['id'])

    if len(daily_bulletin) > 1:
        os.makedirs("daily-reports", exist_ok=True)
        filename = f"daily-reports/Report-{today_str}.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(daily_bulletin))
        print(f"تم إنشاء وتوثيق التقرير بنجاح في: {filename}")
    else:
        print("لا توجد أبحاث جديدة مطابقة للشروط اليوم.")

if __name__ == "__main__":
    main()
