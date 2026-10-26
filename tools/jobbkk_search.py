import re
import urllib.parse

BASE = "https://www.jobbkk.com"
ALL_PROVINCES = "ทุกจังหวัด"

# JobBKK filters by Thai province name. English names the search agent may produce -> Thai.
_PROVINCES = {
    "bangkok": "กรุงเทพมหานคร", "bkk": "กรุงเทพมหานคร",
    "nonthaburi": "นนทบุรี", "pathum thani": "ปทุมธานี", "samut prakan": "สมุทรปราการ",
    "samut sakhon": "สมุทรสาคร", "nakhon pathom": "นครปฐม", "ayutthaya": "พระนครศรีอยุธยา",
    "chonburi": "ชลบุรี", "chon buri": "ชลบุรี", "pattaya": "ชลบุรี", "rayong": "ระยอง",
    "chachoengsao": "ฉะเชิงเทรา", "chiang mai": "เชียงใหม่", "chiang rai": "เชียงราย",
    "phuket": "ภูเก็ต", "khon kaen": "ขอนแก่น", "nakhon ratchasima": "นครราชสีมา", "korat": "นครราชสีมา",
    "songkhla": "สงขลา", "hat yai": "สงขลา", "udon thani": "อุดรธานี", "surat thani": "สุราษฎร์ธานี",
}
_ANYWHERE = {"", "thailand", "anywhere", "remote", "ทั่วประเทศ", "ประเทศไทย"}

# Google-style time filter -> maximum age in hours
_MAX_AGE_H = {"qdr:d": 24, "qdr:w": 24 * 7, "qdr:m": 24 * 31}
# Thai relative times on JobBKK cards, e.g. "7 ชั่วโมงที่แล้ว" (7 hours ago)
_UNIT_H = {"นาที": 1 / 60, "ชั่วโมง": 1, "วัน": 24, "สัปดาห์": 24 * 7, "เดือน": 24 * 30, "ปี": 24 * 365}
_AGO = re.compile(r"(\d+)\s*(นาที|ชั่วโมง|วัน|สัปดาห์|เดือน|ปี)")
_BADGES = {"รับสมัครด่วน"}  # "urgent hiring" tag that sits between the date and the location


def _province(location: str) -> str:
    loc = location.strip()
    if loc.lower() in _ANYWHERE:
        return ALL_PROVINCES
    if re.search(r"[฀-๿]", loc):  # already Thai
        return loc
    return _PROVINCES.get(loc.lower(), ALL_PROVINCES)


def jobbkk_search_url(keyword: str, location: str) -> str:
    """e.g. https://www.jobbkk.com/jobs/lists/1/หางาน,data analyst,กรุงเทพมหานคร,ทั้งหมด.html (percent-encoded)"""
    path = f"หางาน,{keyword.replace(',', ' ').strip()},{_province(location)},ทั้งหมด.html"
    return f"{BASE}/jobs/lists/1/{urllib.parse.quote(path)}"


def age_in_hours(text: str):
    """Hours since posting for a JobBKK relative time, or None if it can't be read."""
    if "เมื่อวาน" in text:  # "yesterday"
        return 24
    m = _AGO.search(text)
    return int(m.group(1)) * _UNIT_H[m.group(2)] if m else None


def _logo(src: str) -> str:
    """Card images go through Next.js (/_next/image?url=<real url>); return the real store.jobbkk.com URL."""
    if not src:
        return ""
    real = urllib.parse.parse_qs(urllib.parse.urlparse(src).query).get("url", [""])[0]
    return real or urllib.parse.urljoin(BASE, src)


def jobbkk_direct_search(keyword: str, location: str, num_jobs: int = 5, time_filter: str = "qdr:w") -> list:
    """Directly scrapes the JobBKK search page using Playwright (no Serper).

    JobBKK has no date filter in its search URL, so jobs older than the time filter are dropped here.
    """
    from playwright.sync_api import sync_playwright

    url = jobbkk_search_url(keyword, location)
    max_age = _MAX_AGE_H.get(time_filter, 24 * 7)
    jobs = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="th-TH",
            )
            # Let images load: when a logo fails, JobBKK swaps it for the company name as text.
            page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["media", "font"] else route.continue_())
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            try:
                page.wait_for_selector("a[href*='/jobs/detail']", timeout=8000)
            except Exception:
                pass

            # With no match, JobBKK shows "ขออภัยไม่พบตำแหน่งงาน" and unrelated recommended jobs: skip those.
            not_found = page.query_selector("text=ขออภัยไม่พบตำแหน่งงาน")
            if not_found and not_found.is_visible():
                browser.close()
                return []

            for card in page.query_selector_all("a[href*='/jobs/detail']"):
                if len(jobs) >= num_jobs:
                    break
                try:
                    lines = [s.strip() for s in card.inner_text().split("\n") if s.strip()]
                    # Anchor on the "… ago" line: title and company come right before it (a logo that
                    # didn't load can add the company name as an extra line at the top).
                    at = next((i for i, s in enumerate(lines) if age_in_hours(s) is not None), None)
                    if at is None or at < 2:
                        continue
                    title, company, posted = lines[at - 2], lines[at - 1], lines[at]
                    age = age_in_hours(posted)
                    if age > max_age:
                        continue
                    rest = [s for s in lines[at + 1:] if s not in _BADGES]
                    img = card.query_selector("img[alt='company-image']")
                    jobs.append({
                        "title": title,
                        "company": company,
                        "location": rest[0].rstrip(".").strip() if rest else "",
                        "snippet": " · ".join(rest[1:3]) if len(rest) > 1 else "",  # salary, transit/notes
                        "link": urllib.parse.urljoin(BASE, card.get_attribute("href")),
                        "platform": "JobBKK",
                        "date": posted,
                        "logo_url": _logo(img.get_attribute("src") if img else ""),
                    })
                except Exception:
                    continue
            browser.close()
    except Exception as e:
        print(f"JobBKK direct scrape error: {e}")

    return jobs
