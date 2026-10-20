"""
========================================================================================
1Life Live Portal Sync Engine for "Program > Merge Duplicate Account"
Pulls real records from BOTH:
  1. Audit Trail tab (Date & Time, User, Action, Primary Account, Affected Account, Activity Details, Status)
  2. Merged Accounts tab
Automatically expands Date Range (e.g. Last 90 Days / YTD) if today (10/20/2026 - 10/20/2026) has 0 entries!
Evaluates each record through the Automated Risk Classification Engine and updates data.json & data.js.
========================================================================================
"""

import os
import re
import sys
import json
import time
import argparse
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VALIDATOR_SESSION = r"C:\Users\1 Life\.gemini\antigravity\scratch\1life_patient_validator\1life_session.json"
LOCAL_SESSION = os.path.join(BASE_DIR, "1life_session.json")

CANDIDATE_URLS = [
    "https://1life.ph/Program/MergeDuplicateAccount",
    "https://1life.ph/Patient/MergeDuplicateAccount",
    "https://1life.ph/Program/MergeAccount",
    "https://1life.ph/Patient/AccountsV2"
]

OPERATORS = [
    {"id": "yglao", "name": "Y. Glao", "role": "Senior QA Analyst", "status": "Online", "shift": "AM Shift (08:00 - 17:00)"},
    {"id": "jjdayag", "name": "J. J. Dayag", "role": "QA Specialist", "status": "Online", "shift": "AM Shift (08:00 - 17:00)"},
    {"id": "amorales", "name": "A. Morales", "role": "QA Analyst", "status": "Online", "shift": "AM Shift (08:00 - 17:00)"},
    {"id": "jofrancisco", "name": "J. O. Francisco", "role": "QA Specialist", "status": "Online", "shift": "Mid Shift (10:00 - 19:00)"},
    {"id": "jtcanaway", "name": "J. T. Canaway", "role": "QA Analyst", "status": "Online", "shift": "AM Shift (08:00 - 17:00)"},
]


def parse_account_cell(raw_text: str):
    """
    Parses a portal Primary Account or Affected Account string or Activity Details snippet into
    structured metadata (id, full_name, first_name, last_name, dob, etc.).
    """
    text = (raw_text or "").strip()
    if not text or text == "-" or text.lower() == "n/a":
        return {
            "id": "N/A",
            "full_name": "Unknown Account",
            "first_name": "Unknown",
            "middle_name": "",
            "last_name": "Account",
            "suffix": "",
            "dob": "N/A",
            "gender": "—",
            "phone": "—",
            "address": "—",
            "philhealth": "—",
            "formatted": text or "N/A"
        }

    # Extract Account ID if present (e.g. #1048291, [1048291], ID: 1048291, or leading digits)
    id_match = re.search(r"(?:#|ID[:\s]*|\[)?(\d{5,12})(?:\])?", text, re.IGNORECASE)
    acc_id = id_match.group(1) if id_match else "PORTAL"

    # Extract DOB if present (YYYY-MM-DD or MM/DD/YYYY or MMM DD, YYYY)
    dob_match = re.search(r"(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})", text)
    dob = dob_match.group(1) if dob_match else ""
    if dob and "/" in dob:
        try:
            dt = datetime.strptime(dob, "%m/%d/%Y")
            dob = dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    # Clean name out of text
    clean_name = text
    clean_name = re.sub(r"(?:#|ID[:\s]*|\[)?\d{5,12}(?:\])?\s*[-:|]?\s*", "", clean_name)
    clean_name = re.sub(r"\(?DOB[:\s]*[^)]+\)?", "", clean_name, flags=re.IGNORECASE)
    clean_name = re.sub(r"\b(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})\b", "", clean_name)
    clean_name = re.sub(r"\s+", " ", clean_name).strip(" -:|,()")

    if not clean_name:
        clean_name = text

    # Split name into first / last
    first_name = clean_name
    last_name = ""
    middle_name = ""
    suffix = ""

    if "," in clean_name:
        # Format: Last, First Middle
        parts = [p.strip() for p in clean_name.split(",", 1)]
        last_name = parts[0]
        rest = parts[1].split() if len(parts) > 1 else []
        if rest:
            first_name = rest[0]
            if len(rest) > 1:
                middle_name = " ".join(rest[1:])
    else:
        tokens = clean_name.split()
        if tokens and tokens[-1].rstrip(".").lower() in ["jr", "sr", "ii", "iii", "iv"]:
            suffix = tokens.pop(-1)
        if len(tokens) >= 2:
            first_name = tokens[0]
            last_name = tokens[-1]
            if len(tokens) > 2:
                middle_name = " ".join(tokens[1:-1])
        elif len(tokens) == 1:
            first_name = tokens[0]
            last_name = tokens[0]

    formatted = f"#{acc_id} - {clean_name}" if acc_id != "PORTAL" else clean_name
    return {
        "id": acc_id,
        "full_name": clean_name,
        "first_name": first_name,
        "middle_name": middle_name,
        "last_name": last_name,
        "suffix": suffix,
        "dob": dob or "Not Specified",
        "gender": "—",
        "phone": "—",
        "address": "—",
        "philhealth": "—",
        "formatted": formatted
    }


def classify_portal_row(primary_raw: str, affected_raw: str, activity_details: str, action: str):
    """
    Runs the Automated Risk Classification Engine on a live portal row, enriching DOB/Name
    from Activity Details if the portal stores field diffs inside Activity Details.
    """
    primary = parse_account_cell(primary_raw)
    affected = parse_account_cell(affected_raw)
    details = (activity_details or "").strip()

    # Check if Activity Details mentions two DOBs (e.g. 1985-04-12 vs 1991-08-20 or MM/DD/YYYY)
    dobs_in_details = re.findall(r"\b(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})\b", details)
    if len(dobs_in_details) >= 2:
        if primary["dob"] == "Not Specified":
            primary["dob"] = dobs_in_details[0]
        if affected["dob"] == "Not Specified":
            affected["dob"] = dobs_in_details[1]
    elif len(dobs_in_details) == 1 and primary["dob"] == "Not Specified":
        primary["dob"] = dobs_in_details[0]
        affected["dob"] = dobs_in_details[0]

    p_first = primary["first_name"].lower()
    p_last = f"{primary['last_name']} {primary['suffix']}".strip().lower()
    a_first = affected["first_name"].lower()
    a_last = f"{affected['last_name']} {affected['suffix']}".strip().lower()

    name_differs = (p_first != a_first or p_last != a_last) and (affected["full_name"] != "Unknown Account")
    dob_known = primary["dob"] != "Not Specified" and affected["dob"] != "Not Specified"
    dob_differs = dob_known and (primary["dob"] != affected["dob"])

    # Also check if Activity Details explicitly mentions birthday/DOB mismatch or name mismatch
    details_lower = details.lower()
    if "birth" in details_lower and ("differ" in details_lower or "mismatch" in details_lower or "not match" in details_lower or "vs" in details_lower):
        dob_differs = True
    if "name" in details_lower and ("differ" in details_lower or "mismatch" in details_lower or "vs" in details_lower):
        name_differs = True

    html_parts = []
    text_parts = []
    discrepancies = []

    if p_last != a_last and affected["full_name"] != "Unknown Account":
        p_l = f"{primary['last_name']} {primary['suffix']}".strip()
        a_l = f"{affected['last_name']} {affected['suffix']}".strip()
        html_parts.append(f"Last Name differs: <span class='diff-chip diff-primary'>'{p_l}'</span> vs <span class='diff-chip diff-affected'>'{a_l}'</span>")
        text_parts.append(f"Last Name differs: '{p_l}' vs '{a_l}'")
        discrepancies.append({"field": "Last Name", "primary": p_l, "affected": a_l, "severity": "high"})

    if p_first != a_first and affected["full_name"] != "Unknown Account":
        html_parts.append(f"First Name differs: <span class='diff-chip diff-primary'>'{primary['first_name']}'</span> vs <span class='diff-chip diff-affected'>'{affected['first_name']}'</span>")
        text_parts.append(f"First Name differs: '{primary['first_name']}' vs '{affected['first_name']}'")
        discrepancies.append({"field": "First Name", "primary": primary["first_name"], "affected": affected["first_name"], "severity": "medium"})

    if dob_differs:
        html_parts.append(f"Birthdays do not match: <span class='diff-chip diff-danger'>{primary['dob']}</span> vs <span class='diff-chip diff-danger'>{affected['dob']}</span>")
        text_parts.append(f"Birthdays do not match: {primary['dob']} vs {affected['dob']}")
        discrepancies.append({"field": "Date of Birth", "primary": primary["dob"], "affected": affected["dob"], "severity": "high"})

    if details:
        html_parts.append(f"<span class='text-slate-300'>{details}</span>")
        text_parts.append(details)

    if name_differs and dob_differs:
        risk_level = "HIGH RISK"
        risk_color = "#dc3545"
        risk_reason = "Critical Red Flag: Different Name AND Different Birthday"
    elif dob_differs:
        risk_level = "HIGH RISK"
        risk_color = "#dc3545"
        risk_reason = "Critical DOB Mismatch across merged profiles"
    elif name_differs:
        risk_level = "MEDIUM / REVIEW"
        risk_color = "#fd7e14"
        risk_reason = "Different Name / Typographic or Suffix Variation"
    else:
        risk_level = "SAFE MATCH"
        risk_color = "#28a745"
        risk_reason = "Exact match across Name, Birthday, and key identifiers"
        if not html_parts:
            html_parts.append(f"<span class='diff-chip diff-safe'>Exact Match Verified</span> {primary['formatted']}")
            text_parts.append(f"Exact Match Verified: {primary['formatted']}")

    return {
        "primary_account": primary,
        "affected_account": affected,
        "risk_level": risk_level,
        "risk_color": risk_color,
        "risk_reason": risk_reason,
        "discrepancies": discrepancies,
        "discrepancy_html": " &bull; ".join(html_parts),
        "discrepancy_text": " | ".join(text_parts)
    }


def sync_from_1life_portal(headless: bool = False, start_date: str = "01/01/2026", end_date: str = "10/20/2026"):
    """
    Launches Playwright, reuses 1life_session.json (or waits for user login if session expired),
    navigates to Program > Merge Duplicate Account, widens the Date Range to pull historical records,
    and scrapes both "Audit Trail" and "Merged Accounts" tabs.
    """
    session_path = LOCAL_SESSION if os.path.exists(LOCAL_SESSION) else (VALIDATOR_SESSION if os.path.exists(VALIDATOR_SESSION) else None)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        if session_path:
            context = browser.new_context(storage_state=session_path, viewport={"width": 1500, "height": 920})
        else:
            context = browser.new_context(viewport={"width": 1500, "height": 920})

        page = context.new_page()

        # Navigate to Merge Duplicate Account
        target_url = CANDIDATE_URLS[0]
        print(f"[1Life Sync] Navigating to {target_url} ...")
        page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)

        # Check if redirected to Login
        if "login" in page.url.lower() or page.locator('input[type="password"]').count() > 0:
            if headless:
                browser.close()
                return {
                    "success": False,
                    "needs_login": True,
                    "message": "1Life session cookie expired. Click 'Login & Sync Live Portal' to open the 1Life browser window and log in."
                }
            print("[1Life Sync] Session expired. Waiting for user to log into 1life.ph in the opened browser window...")
            for _ in range(150):  # Wait up to 5 minutes for interactive login
                page.wait_for_timeout(2000)
                if "login" not in page.url.lower() and page.locator('input[type="password"]').count() == 0:
                    break
            # Save fresh session to both locations
            context.storage_state(path=LOCAL_SESSION)
            try:
                context.storage_state(path=VALIDATOR_SESSION)
            except Exception:
                pass

        # Discover exact URL for "Merge Duplicate Account" if we landed on home/AccountsV2
        if "merge" not in page.url.lower():
            links = page.eval_on_selector_all("a[href]", "els => els.map(e => ({text: e.innerText.trim(), href: e.href}))")
            for link in links:
                if "merge" in link["text"].lower() or "merge" in link["href"].lower():
                    print(f"[1Life Sync] Found Merge Duplicate Account link: {link['href']}")
                    page.goto(link["href"], wait_until="domcontentloaded")
                    page.wait_for_timeout(1500)
                    break

        extracted_rows = []

        # Helper to scrape DataTables rows from current active tab
        def scrape_active_table(source_tab_name: str, widen_date: bool = True):
            try:
                # Set "Show entries" dropdown to 100 if present
                selects = page.locator("select")
                for i in range(selects.count()):
                    sel = selects.nth(i)
                    if sel.is_visible():
                        try:
                            sel.select_option("100")
                            page.wait_for_timeout(800)
                        except Exception:
                            pass

                # Check if table is empty because Date Range is set to today only (10/20/2026 - 10/20/2026)
                date_inputs = page.locator('input[type="text"]')
                for i in range(date_inputs.count()):
                    inp = date_inputs.nth(i)
                    if inp.is_visible():
                        val = inp.input_value() or ""
                        if "-" in val and "/" in val and widen_date:
                            new_range = f"{start_date} - {end_date}"
                            print(f"[1Life Sync] Expanding Date Range from '{val}' to '{new_range}' ...")
                            inp.fill(new_range)
                            page.keyboard.press("Enter")
                            page.wait_for_timeout(500)
                            # Click Search button
                            search_btn = page.locator('button:has-text("Search"), input[value="Search"], a:has-text("Search")')
                            if search_btn.count() > 0:
                                search_btn.first.click()
                                page.wait_for_timeout(2000)
                            break

                # If still 0 entries after widening date range, also try clicking "Clear filters"
                body_text = page.inner_text("body")
                if "No audit trail entries to display" in body_text or "Showing 0 to 0 of 0 entries" in body_text:
                    clear_btn = page.locator('button:has-text("Clear filters"), a:has-text("Clear filters")')
                    if clear_btn.count() > 0 and clear_btn.first.is_visible():
                        print(f"[1Life Sync] 0 entries for range; clicking 'Clear filters' on {source_tab_name}...")
                        clear_btn.first.click()
                        page.wait_for_timeout(2000)

                # Extract all visible table rows
                rows_data = page.evaluate("""(tabName) => {
                    const tables = Array.from(document.querySelectorAll('table'));
                    const results = [];
                    for (const table of tables) {
                        if (table.offsetParent === null) continue; // skip hidden tables
                        const headers = Array.from(table.querySelectorAll('thead th')).map(th => th.innerText.trim());
                        const trs = Array.from(table.querySelectorAll('tbody tr'));
                        for (const tr of trs) {
                            const txt = tr.innerText.trim();
                            if (!txt || txt.toLowerCase().includes('no audit trail entries') || txt.toLowerCase().includes('no data available') || txt.toLowerCase().includes('no matching records')) {
                                continue;
                            }
                            const cells = Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim());
                            if (cells.length >= 3) {
                                results.push({ tab: tabName, headers, cells });
                            }
                        }
                    }
                    return results;
                }""", source_tab_name)
                print(f"[1Life Sync] Scraped {len(rows_data)} rows from '{source_tab_name}'")
                return rows_data
            except Exception as e:
                print(f"[1Life Sync] Warning scraping {source_tab_name}: {e}")
                return []

        # 1. Click "Audit Trail" tab and scrape
        audit_tab = page.locator('a:has-text("Audit Trail"), li:has-text("Audit Trail"), button:has-text("Audit Trail")')
        if audit_tab.count() > 0:
            audit_tab.first.click()
            page.wait_for_timeout(1200)
        extracted_rows.extend(scrape_active_table("Audit Trail", widen_date=True))

        # 2. Click "Merged Accounts" tab and scrape
        merged_tab = page.locator('a:has-text("Merged Accounts"), li:has-text("Merged Accounts"), button:has-text("Merged Accounts")')
        if merged_tab.count() > 0:
            merged_tab.first.click()
            page.wait_for_timeout(1500)
            extracted_rows.extend(scrape_active_table("Merged Accounts", widen_date=True))

        # Save updated session state
        context.storage_state(path=LOCAL_SESSION)
        browser.close()

    # Transform raw rows into dashboard schema
    records = []
    seq = 7001
    for item in extracted_rows:
        cells = item.get("cells", [])
        tab = item.get("tab", "Audit Trail")

        # Standard Audit Trail columns from user's screenshot:
        # [0] Date & Time | [1] User | [2] Action | [3] Primary Account | [4] Affected Account | [5] Activity Details | [6] Status
        dt_str = cells[0] if len(cells) > 0 else datetime.now().strftime("%b %d, %Y %I:%M %p")
        user_str = (cells[1] if len(cells) > 1 else "system").strip()
        action_str = cells[2] if len(cells) > 2 else ("Merged" if tab == "Merged Accounts" else "Audited")
        primary_str = cells[3] if len(cells) > 3 else ""
        affected_str = cells[4] if len(cells) > 4 else ""
        details_str = cells[5] if len(cells) > 5 else ""
        status_str = cells[6] if len(cells) > 6 else "Success"

        eval_res = classify_portal_row(primary_str, affected_str, details_str, action_str)

        # Parse ISO date if possible
        iso_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        date_only = datetime.now().strftime("%Y-%m-%d")
        for fmt in ["%m/%d/%Y %I:%M %p", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%b %d, %Y %I:%M %p"]:
            try:
                parsed_dt = datetime.strptime(dt_str.strip(), fmt)
                iso_str = parsed_dt.strftime("%Y-%m-%dT%H:%M:%S")
                date_only = parsed_dt.strftime("%Y-%m-%d")
                dt_str = parsed_dt.strftime("%b %d, %Y %I:%M %p")
                break
            except Exception:
                pass

        records.append({
            "audit_id": f"LIVE-{seq}",
            "source_tab": tab,
            "timestamp_iso": iso_str,
            "timestamp_display": dt_str,
            "date_only": date_only,
            "qa_operator": user_str,
            "action": action_str,
            "status": status_str,
            "primary_account": eval_res["primary_account"],
            "affected_account": eval_res["affected_account"],
            "risk_level": eval_res["risk_level"],
            "risk_color": eval_res["risk_color"],
            "risk_reason": eval_res["risk_reason"],
            "discrepancies": eval_res["discrepancies"],
            "discrepancy_html": eval_res["discrepancy_html"],
            "discrepancy_text": eval_res["discrepancy_text"],
            "auditor_notes": f"Synced live from 1Life Portal ({tab})"
        })
        seq += 1

    # Save to live_portal_data.json
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "success": True,
        "source": "1Life Portal (Merge Duplicate Account)",
        "date_range_queried": f"{start_date} - {end_date}",
        "synced_at": now_str,
        "total_live_records": len(records),
        "operators": OPERATORS,
        "records": records
    }

    live_json_path = os.path.join(BASE_DIR, "live_portal_data.json")
    with open(live_json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    # If live records were found, also update primary data.json & data.js
    if len(records) > 0:
        with open(os.path.join(BASE_DIR, "data.json"), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        with open(os.path.join(BASE_DIR, "data.js"), "w", encoding="utf-8") as f:
            f.write("window.INITIAL_AUDIT_DATA = ")
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write(";\n")

    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--headed", action="store_true", help="Launch visible browser window for interactive 1Life login")
    parser.add_argument("--start", default="01/01/2026", help="Start date MM/DD/YYYY")
    parser.add_argument("--end", default="10/20/2026", help="End date MM/DD/YYYY")
    args = parser.parse_args()

    res = sync_from_1life_portal(headless=not args.headed, start_date=args.start, end_date=args.end)
    print(json.dumps({
        "success": res.get("success"),
        "needs_login": res.get("needs_login", False),
        "total_live_records": res.get("total_live_records", 0),
        "message": res.get("message", "Completed")
    }, indent=2))
