import re

titles = [
    "Krungthai Bank hiring AI Engineer in Bangkok ...",
    "Beryl8 hiring Solution Architect - AI (Lead AI)",
    "SKY ICT PCL. hiring Lead Software Engineer – AI & ...",
    "AI Language Experts (Thai/English proficiency)",
    "Lead / Senior Fullstack Engineer (Good AI Adoption)",
    "Software Engineer (Senior/Lead Squad) at Tech Co",
    "Customer Engineer, AI, Google Cloud (Thai, English) - Singapore"
]

def extract_better(title):
    company = "Unknown Company"
    clean_title = title
    
    # 1. Handle "Company hiring Title" (LinkedIn format)
    if " hiring " in title:
        parts = title.split(" hiring ", 1)
        company = parts[0].strip()
        clean_title = parts[1].strip()
        # Clean up trailing location like " in Bangkok ..."
        clean_title = re.sub(r' in .*$', '', clean_title).strip()
        
    # 2. Handle "Title at Company"
    elif " at " in title:
        parts = title.rsplit(" at ", 1)
        clean_title = parts[0].strip()
        company = parts[1].strip()
        
    # 3. Handle "Title - Company"
    elif " - " in title:
        parts = title.rsplit(" - ", 1)
        clean_title = parts[0].strip()
        company = parts[1].strip()
        
    return clean_title, company

for t in titles:
    title, comp = extract_better(t)
    print(f"RAW: {t}")
    print(f"TITLE: '{title}' | COMPANY: '{comp}'\n")
