import json
import os
import random
from datetime import datetime, timedelta
from difflib import SequenceMatcher

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

OPERATORS = [
    {"id": "yglao", "name": "Y. Glao", "role": "Senior QA Analyst", "status": "Online", "shift": "AM Shift (08:00 - 17:00)"},
    {"id": "jjdayag", "name": "J. J. Dayag", "role": "QA Specialist", "status": "Online", "shift": "AM Shift (08:00 - 17:00)"},
    {"id": "amorales", "name": "A. Morales", "role": "QA Analyst", "status": "Online", "shift": "AM Shift (08:00 - 17:00)"},
    {"id": "jofrancisco", "name": "J. O. Francisco", "role": "QA Specialist", "status": "Online", "shift": "Mid Shift (10:00 - 19:00)"},
    {"id": "jtcanaway", "name": "J. T. Canaway", "role": "QA Analyst", "status": "Online", "shift": "AM Shift (08:00 - 17:00)"},
]

def evaluate_risk(primary, affected, action="Merged"):
    """
    Automated Risk Classification Engine:
    Evaluates Primary vs. Affected account metadata and returns:
    - risk_level: 'HIGH RISK' | 'MEDIUM / REVIEW' | 'SAFE MATCH'
    - risk_badge_color: '#dc3545' | '#fd7e14' | '#28a745'
    - discrepancies: List of structured discrepancy items
    - summary_html: Inline colored diff text for the table
    - summary_text: Plain text discrepancy description for Excel export
    """
    p_first = primary.get("first_name", "").strip()
    p_last = primary.get("last_name", "").strip()
    p_mid = primary.get("middle_name", "").strip()
    p_suffix = primary.get("suffix", "").strip()
    p_full = f"{p_first} {p_mid} {p_last} {p_suffix}".replace("  ", " ").strip()
    p_dob = primary.get("dob", "").strip()
    p_phone = primary.get("phone", "").strip()
    p_addr = primary.get("address", "").strip()
    p_gender = primary.get("gender", "").strip()

    a_first = affected.get("first_name", "").strip()
    a_last = affected.get("last_name", "").strip()
    a_mid = affected.get("middle_name", "").strip()
    a_suffix = affected.get("suffix", "").strip()
    a_full = f"{a_first} {a_mid} {a_last} {a_suffix}".replace("  ", " ").strip()
    a_dob = affected.get("dob", "").strip()
    a_phone = affected.get("phone", "").strip()
    a_addr = affected.get("address", "").strip()
    a_gender = affected.get("gender", "").strip()

    name_exact = (
        p_first.lower() == a_first.lower() and
        p_last.lower() == a_last.lower() and
        p_suffix.lower() == a_suffix.lower() and
        (p_mid.lower() == a_mid.lower() or not p_mid or not a_mid)
    )
    dob_exact = (p_dob == a_dob)

    name_similarity = SequenceMatcher(None, f"{p_first} {p_last}".lower(), f"{a_first} {a_last}".lower()).ratio()

    discrepancies = []
    html_parts = []
    text_parts = []

    # Check Name differences
    p_last_full = f"{p_last} {p_suffix}".strip()
    a_last_full = f"{a_last} {a_suffix}".strip()

    if p_last_full.lower() != a_last_full.lower():
        msg_text = f"Last Name differs: '{p_last_full}' vs '{a_last_full}'"
        msg_html = f"Last Name differs: <span class='diff-chip diff-primary'>'{p_last_full}'</span> vs <span class='diff-chip diff-affected'>'{a_last_full}'</span>"
        discrepancies.append({"field": "Last Name", "primary": p_last_full, "affected": a_last_full, "severity": "high" if p_last.lower() != a_last.lower() else "medium"})
        html_parts.append(msg_html)
        text_parts.append(msg_text)

    if p_first.lower() != a_first.lower():
        msg_text = f"First Name differs: '{p_first}' vs '{a_first}'"
        msg_html = f"First Name differs: <span class='diff-chip diff-primary'>'{p_first}'</span> vs <span class='diff-chip diff-affected'>'{a_first}'</span>"
        discrepancies.append({"field": "First Name", "primary": p_first, "affected": a_first, "severity": "medium" if name_similarity >= 0.75 else "high"})
        html_parts.append(msg_html)
        text_parts.append(msg_text)

    if p_mid and a_mid and p_mid.lower() != a_mid.lower():
        msg_text = f"Middle Name differs: '{p_mid}' vs '{a_mid}'"
        msg_html = f"Middle Name differs: <span class='diff-chip diff-warn'>'{p_mid}'</span> vs <span class='diff-chip diff-warn'>'{a_mid}'</span>"
        discrepancies.append({"field": "Middle Name", "primary": p_mid, "affected": a_mid, "severity": "low"})
        html_parts.append(msg_html)
        text_parts.append(msg_text)

    # Check DOB differences
    if not dob_exact:
        msg_text = f"Birthdays do not match: {p_dob} vs {a_dob}"
        msg_html = f"Birthdays do not match: <span class='diff-chip diff-danger'>{p_dob}</span> vs <span class='diff-chip diff-danger'>{a_dob}</span>"
        discrepancies.append({"field": "Date of Birth", "primary": p_dob, "affected": a_dob, "severity": "high"})
        html_parts.append(msg_html)
        text_parts.append(msg_text)

    # Check Gender
    if p_gender and a_gender and p_gender != a_gender:
        msg_text = f"Gender mismatch: {p_gender} vs {a_gender}"
        msg_html = f"Gender mismatch: <span class='diff-chip diff-danger'>{p_gender}</span> vs <span class='diff-chip diff-danger'>{a_gender}</span>"
        discrepancies.append({"field": "Gender", "primary": p_gender, "affected": a_gender, "severity": "high"})
        html_parts.append(msg_html)
        text_parts.append(msg_text)

    # Check Phone / Address for secondary info
    if p_phone != a_phone:
        discrepancies.append({"field": "Phone", "primary": p_phone, "affected": a_phone, "severity": "info"})
    if p_addr.lower() != a_addr.lower():
        discrepancies.append({"field": "Address", "primary": p_addr, "affected": a_addr, "severity": "info"})

    # Risk Classification Rules:
    # HIGH RISK (#dc3545): Different Name and Different Birthday (critical red flag for erroneous merges)
    # Also if Birthday differs significantly with any name variation or completely different identity
    name_differs = (p_first.lower() != a_first.lower()) or (p_last_full.lower() != a_last_full.lower())

    if name_differs and not dob_exact:
        risk_level = "HIGH RISK"
        risk_color = "#dc3545"
        risk_reason = "Critical Red Flag: Different Name AND Different Birthday"
    elif not dob_exact:
        # Even if name looks similar, different birthday is a high/review risk depending on similarity, let's classify completely different DOB + suffix/middle diff or standalone DOB mismatch
        risk_level = "HIGH RISK"
        risk_color = "#dc3545"
        risk_reason = "Critical DOB Mismatch across merged profiles"
    elif name_differs and dob_exact:
        risk_level = "MEDIUM / REVIEW"
        risk_color = "#fd7e14"
        risk_reason = "Different Name / Typographic or Suffix Variation with Same Birthday"
    elif p_mid.lower() != a_mid.lower() and (p_mid and a_mid):
        risk_level = "MEDIUM / REVIEW"
        risk_color = "#ffc107"
        risk_reason = "Middle Name / Maiden Name Variation with Same Birthday"
    else:
        risk_level = "SAFE MATCH"
        risk_color = "#28a745"
        risk_reason = "Exact match across Name, Birthday, and key identifiers"
        html_parts = [
            f"<span class='diff-chip diff-safe'>Exact Match Verified</span> Full Name (<span class='font-mono'>{p_full}</span>) & DOB (<span class='font-mono'>{p_dob}</span>) match 100%."
        ]
        text_parts = [f"Exact Match Verified: Full Name ({p_full}) & DOB ({p_dob}) match 100%."]
        if p_phone != a_phone:
            html_parts.append(f"<span class='text-xs opacity-75'>Consolidated secondary phone {a_phone}</span>")
            text_parts.append(f"Consolidated secondary phone {a_phone}")

    return {
        "risk_level": risk_level,
        "risk_color": risk_color,
        "risk_reason": risk_reason,
        "similarity_score": round(name_similarity * 100, 1) if dob_exact else round(name_similarity * 65, 1),
        "discrepancies": discrepancies,
        "summary_html": " &bull; ".join(html_parts),
        "summary_text": " | ".join(text_parts)
    }


CURATED_SCENARIOS = [
    # HIGH RISK CASES (Different Name AND Different Birthday)
    {
        "operator": "yglao",
        "action": "Merged",
        "status": "Under Review",
        "minutes_ago": 8,
        "primary": {"id": "1048291", "first_name": "Ricardo", "middle_name": "Santos", "last_name": "Mata", "suffix": "Jr", "dob": "1985-04-12", "gender": "M", "phone": "+63 917 842 1109", "address": "42 Kalayaan Ave, Diliman, Quezon City", "barangay": "Central", "philhealth": "12-094817263-1"},
        "affected": {"id": "1093812", "first_name": "Ricardo", "middle_name": "Cruz", "last_name": "Mata", "suffix": "", "dob": "1961-08-20", "gender": "M", "phone": "+63 918 221 9044", "address": "42 Kalayaan Ave, Diliman, Quezon City", "barangay": "Central", "philhealth": "04-112948102-8"},
        "notes": "Father and Son accounts erroneously merged due to shared address and first/last name."
    },
    {
        "operator": "jjdayag",
        "action": "Flagged for Review",
        "status": "Under Review",
        "minutes_ago": 19,
        "primary": {"id": "1059201", "first_name": "Maria Luisa", "middle_name": "Reyes", "last_name": "Bautista", "suffix": "", "dob": "1991-08-20", "gender": "F", "phone": "+63 917 550 3812", "address": "Blk 4 Lot 12 Camella Homes, Bacoor, Cavite", "barangay": "Mambog IV", "philhealth": "19-203948172-4"},
        "affected": {"id": "1084410", "first_name": "Marilou", "middle_name": "Reyes", "last_name": "Evangelista", "suffix": "", "dob": "1984-11-03", "gender": "F", "phone": "+63 920 918 4410", "address": "18 Aguinaldo Hwy, Imus, Cavite", "barangay": "Tanzang Luma", "philhealth": "11-948271635-0"},
        "notes": "Different First/Last Name and different Birthday. High probability of distinct individuals."
    },
    {
        "operator": "amorales",
        "action": "Unmerged",
        "status": "Reverted",
        "minutes_ago": 34,
        "primary": {"id": "1033918", "first_name": "Antonio", "middle_name": "Gomez", "last_name": "Dela Cruz", "suffix": "III", "dob": "1996-02-14", "gender": "M", "phone": "+63 915 339 8172", "address": "115 Rizal St, Brgy Poblacion, Makati City", "barangay": "Poblacion", "philhealth": "21-009384716-2"},
        "affected": {"id": "1077219", "first_name": "Antonino", "middle_name": "Garcia", "last_name": "Dela Cruz", "suffix": "Sr", "dob": "1968-09-29", "gender": "M", "phone": "+63 917 401 2938", "address": "88 J.P. Rizal St, Makati City", "barangay": "Tejeros", "philhealth": "02-883746192-5"},
        "notes": "Merged in error during batch deduplication; QA supervisor triggered immediate unmerge."
    },
    {
        "operator": "jofrancisco",
        "action": "Merged",
        "status": "Under Review",
        "minutes_ago": 47,
        "primary": {"id": "1061209", "first_name": "Kristine Joy", "middle_name": "Lim", "last_name": "Soriano", "suffix": "", "dob": "1993-05-18", "gender": "F", "phone": "+63 917 612 0944", "address": "Unit 904 Avida Towers, BGC, Taguig", "barangay": "Fort Bonifacio", "philhealth": "15-394810293-7"},
        "affected": {"id": "1098231", "first_name": "Kristina", "middle_name": "Tan", "last_name": "Serrano", "suffix": "", "dob": "1989-12-09", "gender": "F", "phone": "+63 998 771 2309", "address": "Phase 2 Pinagsama Village, Taguig City", "barangay": "Pinagsama", "philhealth": "08-293847102-3"},
        "notes": "Phonetic surname collision ('Soriano' vs 'Serrano') with mismatched birthdates."
    },
    {
        "operator": "jtcanaway",
        "action": "Flagged for Review",
        "status": "Under Review",
        "minutes_ago": 62,
        "primary": {"id": "1029481", "first_name": "Eduardo", "middle_name": "Mendoza", "last_name": "Villanueva", "suffix": "", "dob": "1975-07-22", "gender": "M", "phone": "+63 917 889 1023", "address": "24 Mindanao Ave, Project 6, Quezon City", "barangay": "Project 6", "philhealth": "07-192837465-9"},
        "affected": {"id": "1089104", "first_name": "Edgardo", "middle_name": "Mendoza", "last_name": "Villanueva", "suffix": "", "dob": "1978-03-11", "gender": "M", "phone": "+63 917 889 1023", "address": "24 Mindanao Ave, Project 6, Quezon City", "barangay": "Project 6", "philhealth": "07-998273645-1"},
        "notes": "Brothers sharing household contact number; distinct first names and birthdays."
    },
    {
        "operator": "yglao",
        "action": "Unmerged",
        "status": "Reverted",
        "minutes_ago": 95,
        "primary": {"id": "1041102", "first_name": "Analyn", "middle_name": "Diaz", "last_name": "Mendoza", "suffix": "", "dob": "1988-01-15", "gender": "F", "phone": "+63 916 441 0921", "address": "71 Shaw Blvd, Mandaluyong City", "barangay": "Wack-Wack", "philhealth": "14-002938471-6"},
        "affected": {"id": "1073891", "first_name": "Annaliza", "middle_name": "Dizon", "last_name": "Mendoza", "suffix": "", "dob": "1994-06-30", "gender": "F", "phone": "+63 927 819 3011", "address": "12 Boni Ave, Mandaluyong City", "barangay": "Barangka Drive", "philhealth": "18-928374615-2"},
        "notes": "Reverted after QA audit spotted 6-year DOB discrepancy and distinct given names."
    },
    {
        "operator": "jjdayag",
        "action": "Merged",
        "status": "Under Review",
        "minutes_ago": 130,
        "primary": {"id": "1050192", "first_name": "Roberto", "middle_name": "Castro", "last_name": "Aquino", "suffix": "Jr", "dob": "1982-10-05", "gender": "M", "phone": "+63 917 309 4811", "address": "302 Katipunan Ave, Loyola Heights, QC", "barangay": "Loyola Heights", "philhealth": "09-384756102-4"},
        "affected": {"id": "1091204", "first_name": "Robert", "middle_name": "Castillo", "last_name": "Aquino", "suffix": "Sr", "dob": "1956-10-05", "gender": "M", "phone": "+63 917 309 4811", "address": "302 Katipunan Ave, Loyola Heights, QC", "barangay": "Loyola Heights", "philhealth": "01-293847561-0"},
        "notes": "Same month/day of birth (Oct 5) but birth year differs by 26 years (1982 vs 1956) and Jr vs Sr."
    },
    {
        "operator": "jtcanaway",
        "action": "Merged",
        "status": "Under Review",
        "minutes_ago": 175,
        "primary": {"id": "1018920", "first_name": "Clarissa", "middle_name": "Ocampo", "last_name": "Pascual", "suffix": "", "dob": "1999-09-12", "gender": "F", "phone": "+63 915 901 2281", "address": "55 España Blvd, Sampaloc, Manila", "barangay": "Barangay 452", "philhealth": "22-102938475-3"},
        "affected": {"id": "1068392", "first_name": "Clarisse", "middle_name": "Olivares", "last_name": "Padua", "suffix": "", "dob": "1990-04-25", "gender": "F", "phone": "+63 919 882 3104", "address": "19 Lacson Ave, Sampaloc, Manila", "barangay": "Barangay 410", "philhealth": "16-847362519-8"},
        "notes": "Critical mismatch across Last Name ('Pascual' vs 'Padua') and DOB (1999 vs 1990)."
    },

    # MEDIUM / REVIEW CASES (Different Name / Fuzzy / Maiden / Suffix variation with Same Birthday)
    {
        "operator": "yglao",
        "action": "Merged",
        "status": "Success",
        "minutes_ago": 14,
        "primary": {"id": "1049921", "first_name": "Ma. Theresa", "middle_name": "Velasco", "last_name": "Ramos", "suffix": "", "dob": "1987-06-15", "gender": "F", "phone": "+63 917 204 9912", "address": "14 Emerald Ave, Ortigas Center, Pasig", "barangay": "San Antonio", "philhealth": "13-485769102-1"},
        "affected": {"id": "1082910", "first_name": "Maria Teresa", "middle_name": "Velasco", "last_name": "Ramos", "suffix": "", "dob": "1987-06-15", "gender": "F", "phone": "+63 917 204 9912", "address": "14 Emerald Ave, Ortigas, Pasig City", "barangay": "San Antonio", "philhealth": "13-485769102-1"},
        "notes": "Abbreviated 'Ma. Theresa' vs spelled-out 'Maria Teresa'; identical DOB and PhilHealth ID."
    },
    {
        "operator": "amorales",
        "action": "Flagged for Review",
        "status": "Under Review",
        "minutes_ago": 23,
        "primary": {"id": "1052310", "first_name": "Jennifer", "middle_name": "Salazar", "last_name": "Tolentino", "suffix": "", "dob": "1992-11-28", "gender": "F", "phone": "+63 918 662 3901", "address": "89 Marcos Hwy, Antipolo, Rizal", "barangay": "Mayamot", "philhealth": "17-394857612-9"},
        "affected": {"id": "1090123", "first_name": "Jennifer", "middle_name": "Mercado", "last_name": "Salazar", "suffix": "", "dob": "1992-11-28", "gender": "F", "phone": "+63 918 662 3901", "address": "89 Marcos Hwy, Antipolo, Rizal", "barangay": "Mayamot", "philhealth": "17-394857612-9"},
        "notes": "Married surname ('Tolentino') vs Maiden surname ('Salazar'); same birthday and PhilHealth."
    },
    {
        "operator": "jofrancisco",
        "action": "Accounts Compared",
        "status": "Under Review",
        "minutes_ago": 39,
        "primary": {"id": "1038471", "first_name": "Ferdinand", "middle_name": "Lozano", "last_name": "Macapagal", "suffix": "Jr", "dob": "1980-03-09", "gender": "M", "phone": "+63 917 773 1829", "address": "77 Commonwealth Ave, Fairview, QC", "barangay": "Greater Lagro", "philhealth": "06-283746591-4"},
        "affected": {"id": "1074829", "first_name": "Ferdinand", "middle_name": "Lozano", "last_name": "Macapagal", "suffix": "", "dob": "1980-03-09", "gender": "M", "phone": "+63 917 773 1829", "address": "77 Commonwealth Ave, Fairview, QC", "barangay": "Greater Lagro", "philhealth": "06-283746591-4"},
        "notes": "Suffix omitted on secondary clinic intake ('Macapagal Jr' vs 'Macapagal'); DOB matches."
    },
    {
        "operator": "jjdayag",
        "action": "Merged",
        "status": "Success",
        "minutes_ago": 51,
        "primary": {"id": "1064821", "first_name": "Jonnel", "middle_name": "Pangilinan", "last_name": "De Guzman", "suffix": "", "dob": "1995-07-04", "gender": "M", "phone": "+63 922 419 8872", "address": "102 MacArthur Hwy, Malolos, Bulacan", "barangay": "Bulihan", "philhealth": "20-918273645-5"},
        "affected": {"id": "1095512", "first_name": "Jonel", "middle_name": "Pangilinan", "last_name": "Deguzman", "suffix": "", "dob": "1995-07-04", "gender": "M", "phone": "+63 922 419 8872", "address": "102 MacArthur Hwy, Malolos, Bulacan", "barangay": "Bulihan", "philhealth": "20-918273645-5"},
        "notes": "Minor typographic variation ('Jonnel De Guzman' vs 'Jonel Deguzman') with identical DOB."
    },
    {
        "operator": "jtcanaway",
        "action": "Flagged for Review",
        "status": "Under Review",
        "minutes_ago": 68,
        "primary": {"id": "1047182", "first_name": "Catherine", "middle_name": "Yap", "last_name": "Chua-Lim", "suffix": "", "dob": "1989-02-19", "gender": "F", "phone": "+63 917 990 1122", "address": "608 Ongpin St, Binondo, Manila", "barangay": "Barangay 289", "philhealth": "12-837465910-3"},
        "affected": {"id": "1088301", "first_name": "Katherine", "middle_name": "Yap", "last_name": "Chua", "suffix": "", "dob": "1989-02-19", "gender": "F", "phone": "+63 917 990 1122", "address": "608 Ongpin St, Binondo, Manila", "barangay": "Barangay 289", "philhealth": "12-837465910-3"},
        "notes": "Hyphenated married surname & C/K spelling difference; same DOB and residential address."
    },
    {
        "operator": "yglao",
        "action": "Merged",
        "status": "Success",
        "minutes_ago": 84,
        "primary": {"id": "1058391", "first_name": "Reynaldo", "middle_name": "Navarro", "last_name": "Delos Santos", "suffix": "", "dob": "1973-12-21", "gender": "M", "phone": "+63 919 304 5518", "address": "19 Alabang-Zapote Rd, Las Piñas City", "barangay": "Pamplona Tres", "philhealth": "05-192837460-7"},
        "affected": {"id": "1092108", "first_name": "Reynaldo", "middle_name": "Navarro", "last_name": "De Los Santos", "suffix": "", "dob": "1973-12-21", "gender": "M", "phone": "+63 919 304 5518", "address": "19 Alabang-Zapote Rd, Las Piñas City", "barangay": "Pamplona Tres", "philhealth": "05-192837460-7"},
        "notes": "Spacing variation in compound surname ('Delos Santos' vs 'De Los Santos')."
    },
    {
        "operator": "amorales",
        "action": "Accounts Compared",
        "status": "Under Review",
        "minutes_ago": 110,
        "primary": {"id": "1031904", "first_name": "Rosario", "middle_name": "Ilagan", "last_name": "Dimaculangan", "suffix": "", "dob": "1966-05-02", "gender": "F", "phone": "+63 917 512 8093", "address": "33 P. Burgos St, Batangas City", "barangay": "Poblacion", "philhealth": "03-918273640-2"},
        "affected": {"id": "1079012", "first_name": "Charito", "middle_name": "Ilagan", "last_name": "Dimaculangan", "suffix": "", "dob": "1966-05-02", "gender": "F", "phone": "+63 917 512 8093", "address": "33 P. Burgos St, Batangas City", "barangay": "Poblacion", "philhealth": "03-918273640-2"},
        "notes": "Nickname ('Charito') used instead of legal first name ('Rosario') with matching DOB."
    },
    {
        "operator": "jofrancisco",
        "action": "Merged",
        "status": "Success",
        "minutes_ago": 145,
        "primary": {"id": "1067291", "first_name": "Mark Anthony", "middle_name": "Salonga", "last_name": "Vergara", "suffix": "", "dob": "1998-08-14", "gender": "M", "phone": "+63 915 782 3310", "address": "410 Maginhawa St, Teachers Village, QC", "barangay": "Teachers Village East", "philhealth": "21-837465192-6"},
        "affected": {"id": "1096401", "first_name": "Marc Anthony", "middle_name": "Salonga", "last_name": "Vergara", "suffix": "", "dob": "1998-08-14", "gender": "M", "phone": "+63 915 782 3310", "address": "410 Maginhawa St, QC", "barangay": "Teachers Village East", "philhealth": "21-837465192-6"},
        "notes": "Spelling variation 'Mark' vs 'Marc'; verified via government ID scan."
    },

    # SAFE MATCH / LOW RISK CASES (Exact Match across Name, Birthday, and key identifiers)
    {
        "operator": "yglao",
        "action": "Merged",
        "status": "Success",
        "minutes_ago": 4,
        "primary": {"id": "1051120", "first_name": "Gabriel", "middle_name": "Atienza", "last_name": "Mercado", "suffix": "", "dob": "1990-01-23", "gender": "M", "phone": "+63 917 601 4429", "address": "120 Pioneer St, Kapitolyo, Pasig City", "barangay": "Kapitolyo", "philhealth": "14-918273645-8"},
        "affected": {"id": "1089912", "first_name": "Gabriel", "middle_name": "Atienza", "last_name": "Mercado", "suffix": "", "dob": "1990-01-23", "gender": "M", "phone": "+63 917 601 4429", "address": "120 Pioneer St, Kapitolyo, Pasig City", "barangay": "Kapitolyo", "philhealth": "14-918273645-8"},
        "notes": "Duplicate portal registration from mobile app; 100% demographic match."
    },
    {
        "operator": "jjdayag",
        "action": "Merged",
        "status": "Success",
        "minutes_ago": 11,
        "primary": {"id": "1054409", "first_name": "Patricia Anne", "middle_name": "Guevarra", "last_name": "Sandoval", "suffix": "", "dob": "1994-03-17", "gender": "F", "phone": "+63 917 839 2019", "address": "28 Paseo de Roxas, Legazpi Village, Makati", "barangay": "San Lorenzo", "philhealth": "18-293847165-0"},
        "affected": {"id": "1091823", "first_name": "Patricia Anne", "middle_name": "Guevarra", "last_name": "Sandoval", "suffix": "", "dob": "1994-03-17", "gender": "F", "phone": "+63 998 201 9941", "address": "28 Paseo de Roxas, Legazpi Village, Makati", "barangay": "San Lorenzo", "philhealth": "18-293847165-0"},
        "notes": "Exact match across full name, DOB, and address. Consolidated secondary mobile number."
    },
    {
        "operator": "amorales",
        "action": "Merged",
        "status": "Success",
        "minutes_ago": 16,
        "primary": {"id": "1043819", "first_name": "Lorenzo", "middle_name": "Pangilinan", "last_name": "Magbanua", "suffix": "Jr", "dob": "1983-09-08", "gender": "M", "phone": "+63 918 402 1183", "address": "64 Timog Ave, Sacred Heart, Quezon City", "barangay": "Sacred Heart", "philhealth": "10-394857162-3"},
        "affected": {"id": "1081104", "first_name": "Lorenzo", "middle_name": "Pangilinan", "last_name": "Magbanua", "suffix": "Jr", "dob": "1983-09-08", "gender": "M", "phone": "+63 918 402 1183", "address": "64 Timog Ave, Sacred Heart, Quezon City", "barangay": "Sacred Heart", "philhealth": "10-394857162-3"},
        "notes": "Verified duplicate teleconsultation profile; safely merged."
    },
    {
        "operator": "jofrancisco",
        "action": "Merged",
        "status": "Success",
        "minutes_ago": 27,
        "primary": {"id": "1060291", "first_name": "Beatriz", "middle_name": "Legaspi", "last_name": "Romualdez", "suffix": "", "dob": "1997-11-11", "gender": "F", "phone": "+63 917 559 0291", "address": "15 McKinley Pkwy, BGC, Taguig City", "barangay": "Fort Bonifacio", "philhealth": "20-102938471-9"},
        "affected": {"id": "1094012", "first_name": "Beatriz", "middle_name": "Legaspi", "last_name": "Romualdez", "suffix": "", "dob": "1997-11-11", "gender": "F", "phone": "+63 917 559 0291", "address": "15 McKinley Pkwy, BGC, Taguig City", "barangay": "Fort Bonifacio", "philhealth": "20-102938471-9"},
        "notes": "Exact demographic match across all fields."
    },
    {
        "operator": "jtcanaway",
        "action": "Merged",
        "status": "Success",
        "minutes_ago": 31,
        "primary": {"id": "1039102", "first_name": "Christian", "middle_name": "David", "last_name": "Policarpio", "suffix": "", "dob": "1986-04-30", "gender": "M", "phone": "+63 916 778 9012", "address": "91 Sumulong Hwy, Marikina City", "barangay": "Sto. Niño", "philhealth": "11-394857601-2"},
        "affected": {"id": "1078291", "first_name": "Christian", "middle_name": "David", "last_name": "Policarpio", "suffix": "", "dob": "1986-04-30", "gender": "M", "phone": "+63 916 778 9012", "address": "91 Sumulong Hwy, Marikina City", "barangay": "Sto. Niño", "philhealth": "11-394857601-2"},
        "notes": "Walk-in clinic account merged with online booking account; 100% match."
    }
]

FIRST_NAMES_M = ["Jerome", "Nathaniel", "Vincent", "Dominic", "Rafael", "Kenneth", "angelo", "Paolo", "Miguel", "Francis", "benjamin", "Noel", "Arnel", "Dennis", "Ronald"]
FIRST_NAMES_F = ["Camille", "Angelica", "Bianca", "Veronica", "Michelle", "Stephanie", "Rochelle", "grace", "Jasmine", "Danica", "Katrina", "eloisa", "Rowena", "Maricel", "Glenda"]
MIDDLE_NAMES = ["Santos", "Reyes", "Cruz", "Bautista", "Ocampo", "Garcia", "Mendoza", "Torres", "Flores", "Castillo", "Rivera", "Navarro", "Ramos", "Salazar", "estrada"]
LAST_NAMES = ["Hernandez", "Gonzales", "Lopez", "Perez", "Sanchez", "Ramirez", "fuentebella", "Macaraeg", "Manalo", "Capistrano", "Dizon", "Galang", "Laconsay", "Malabanan", "Panganiban", "Quijano", "Sarmiento", "Tupas", "Umali", "Valdez"]
CITIES = [
    ("108 Roces Ave, Diliman, Quezon City", "Paligsahan"),
    ("214 Taft Ave, Malate, Manila", "Barangay 704"),
    ("45 Ayala Ave, Bel-Air, Makati City", "Bel-Air"),
    ("82 Ortigas Ave, Greenhills, San Juan", "Greenhills"),
    ("19 Alabang Town Center Rd, Muntinlupa", "Ayala Alabang"),
    ("305 Gov. Drive, Dasmariñas, Cavite", "Sampaloc I"),
    ("76 Национал Rd, Calamba, Laguna", "Real"),
    ("12 MacArthur Hwy, Angeles City, Pampanga", "Balibago"),
]


def generate_dataset():
    now = datetime(2026, 10, 20, 9, 8, 0)
    records = []
    seq = 5001

    # 1. Process curated scenarios first
    for item in CURATED_SCENARIOS:
        ts = now - timedelta(minutes=item["minutes_ago"])
        p = item["primary"]
        a = item["affected"]
        # Ensure Title case
        p_full = f"{p['first_name']} {p['middle_name']} {p['last_name']} {p['suffix']}".replace("  ", " ").strip()
        a_full = f"{a['first_name']} {a['middle_name']} {a['last_name']} {a['suffix']}".replace("  ", " ").strip()

        eval_res = evaluate_risk(p, a, item["action"])
        records.append({
            "audit_id": f"AUD-{seq}",
            "timestamp_iso": ts.strftime("%Y-%m-%dT%H:%M:%S"),
            "timestamp_display": ts.strftime("%b %d, %Y %I:%M %p"),
            "date_only": ts.strftime("%Y-%m-%d"),
            "qa_operator": item["operator"],
            "action": item["action"],
            "status": item["status"],
            "primary_account": {
                **p,
                "full_name": p_full,
                "formatted": f"#{p['id']} - {p_full}"
            },
            "affected_account": {
                **a,
                "full_name": a_full,
                "formatted": f"#{a['id']} - {a_full}"
            },
            "risk_level": eval_res["risk_level"],
            "risk_color": eval_res["risk_color"],
            "risk_reason": eval_res["risk_reason"],
            "similarity_score": eval_res["similarity_score"],
            "discrepancies": eval_res["discrepancies"],
            "discrepancy_html": eval_res["summary_html"],
            "discrepancy_text": eval_res["summary_text"],
            "auditor_notes": item["notes"]
        })
        seq += 1

    # 2. Generate additional realistic operations across all 5 operators so workload bar has rich counts
    # Target counts per operator to make it look realistic and rich (total ~85 records)
    operator_weights = [
        ("yglao", 18),
        ("jjdayag", 15),
        ("amorales", 13),
        ("jofrancisco", 12),
        ("jtcanaway", 11),
    ]

    rng = random.Random(20261020)

    for op_id, count in operator_weights:
        for i in range(count):
            minutes_offset = rng.randint(45, 4320) # Across last 3 days
            ts = now - timedelta(minutes=minutes_offset)
            gender = rng.choice(["M", "F"])
            first = rng.choice(FIRST_NAMES_M if gender == "M" else FIRST_NAMES_F).title()
            mid = rng.choice(MIDDLE_NAMES).title()
            last = rng.choice(LAST_NAMES).title()
            addr, brgy = rng.choice(CITIES)
            addr = addr.replace("Национал", "National")
            dob_year = rng.randint(1962, 2003)
            dob_month = rng.randint(1, 12)
            dob_day = rng.randint(1, 28)
            dob_str = f"{dob_year:04d}-{dob_month:02d}-{dob_day:02d}"
            phone_str = f"+63 917 {rng.randint(100,999)} {rng.randint(1000,9999)}"
            ph_id = f"{rng.randint(10,22):02d}-{rng.randint(100000000,999999999)}-{rng.randint(0,9)}"

            p_id = str(rng.randint(1010000, 1069999))
            a_id = str(rng.randint(1070000, 1099999))

            # Decide tier: mostly SAFE MATCH (78%), some MEDIUM / REVIEW (16%), rare HIGH RISK (6%)
            roll = rng.random()
            if roll < 0.06:
                # HIGH RISK
                a_first = first if rng.random() < 0.5 else rng.choice(FIRST_NAMES_M if gender == "M" else FIRST_NAMES_F).title()
                a_last = last if a_first != first else (last + " Jr" if gender == "M" else rng.choice(LAST_NAMES).title())
                a_dob = f"{dob_year + rng.choice([-18, -7, 5, 11]):04d}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}"
                action = rng.choice(["Flagged for Review", "Unmerged", "Merged"])
                status = "Reverted" if action == "Unmerged" else "Under Review"
                notes = "Automated QA Rule #101 triggered: Simultaneous Name & DOB divergence."
                a_suffix = "Jr" if "Jr" in a_last else ""
                a_last_clean = a_last.replace(" Jr", "")
            elif roll < 0.24:
                # MEDIUM / REVIEW
                a_dob = dob_str
                a_last_clean = last
                a_suffix = ""
                if rng.random() < 0.5:
                    # Typo in first name
                    a_first = first + "e" if not first.endswith("e") else first[:-1]
                    notes = "Minor spelling variation in First Name with identical Birthday."
                else:
                    # Suffix or compound last name diff
                    a_first = first
                    a_suffix = "Jr" if gender == "M" else ""
                    if not a_suffix:
                        a_last_clean = f"{mid}-{last}"
                    notes = "Surname/Suffix variation with matching Date of Birth."
                action = rng.choice(["Merged", "Accounts Compared", "Flagged for Review"])
                status = "Success" if action == "Merged" else "Under Review"
            else:
                # SAFE MATCH
                a_first = first
                a_last_clean = last
                a_suffix = ""
                a_dob = dob_str
                action = rng.choice(["Merged", "Merged", "Merged", "Accounts Compared"])
                status = "Success"
                notes = "Exact match verified across Full Name, Birthday, and PhilHealth ID."

            p_obj = {
                "id": p_id,
                "first_name": first,
                "middle_name": mid,
                "last_name": last,
                "suffix": "",
                "dob": dob_str,
                "gender": gender,
                "phone": phone_str,
                "address": addr,
                "barangay": brgy,
                "philhealth": ph_id
            }
            a_obj = {
                "id": a_id,
                "first_name": a_first,
                "middle_name": mid,
                "last_name": a_last_clean,
                "suffix": a_suffix,
                "dob": a_dob,
                "gender": gender,
                "phone": phone_str if rng.random() < 0.7 else f"+63 918 {rng.randint(100,999)} {rng.randint(1000,9999)}",
                "address": addr,
                "barangay": brgy,
                "philhealth": ph_id
            }

            p_full = f"{p_obj['first_name']} {p_obj['middle_name']} {p_obj['last_name']} {p_obj['suffix']}".replace("  ", " ").strip()
            a_full = f"{a_obj['first_name']} {a_obj['middle_name']} {a_obj['last_name']} {a_obj['suffix']}".replace("  ", " ").strip()
            eval_res = evaluate_risk(p_obj, a_obj, action)

            records.append({
                "audit_id": f"AUD-{seq}",
                "timestamp_iso": ts.strftime("%Y-%m-%dT%H:%M:%S"),
                "timestamp_display": ts.strftime("%b %d, %Y %I:%M %p"),
                "date_only": ts.strftime("%Y-%m-%d"),
                "qa_operator": op_id,
                "action": action,
                "status": status,
                "primary_account": {
                    **p_obj,
                    "full_name": p_full,
                    "formatted": f"#{p_obj['id']} - {p_full}"
                },
                "affected_account": {
                    **a_obj,
                    "full_name": a_full,
                    "formatted": f"#{a_obj['id']} - {a_full}"
                },
                "risk_level": eval_res["risk_level"],
                "risk_color": eval_res["risk_color"],
                "risk_reason": eval_res["risk_reason"],
                "similarity_score": eval_res["similarity_score"],
                "discrepancies": eval_res["discrepancies"],
                "discrepancy_html": eval_res["summary_html"],
                "discrepancy_text": eval_res["summary_text"],
                "auditor_notes": notes
            })
            seq += 1

    # Sort newest first
    records.sort(key=lambda r: r["timestamp_iso"], reverse=True)

    payload = {
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "operators": OPERATORS,
        "records": records
    }

    json_path = os.path.join(BASE_DIR, "data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    js_path = os.path.join(BASE_DIR, "data.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.INITIAL_AUDIT_DATA = ")
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write(";\n")

    print(f"Generated {len(records)} QA audit records in data.json and data.js")
    return payload

if __name__ == "__main__":
    generate_dataset()
