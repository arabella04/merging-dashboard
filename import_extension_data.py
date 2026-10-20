"""
========================================================================================
1Life Audit Trail Extension Database Sync & Importer
Syncs data directly from:
  1. Exported 1Life_Audit_Trail_Merges_*.xlsx files in C:\\Users\\1 Life\\Downloads (or uploaded)
  2. Live POST payloads streamed directly from the 1Life Audit Trail Exporter & Auditor Chrome Extension
========================================================================================
"""

import os
import re
import glob
import json
from datetime import datetime
import openpyxl

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.expanduser("~/Downloads")

# Standard operators + any discovered operators in the extension
CORE_OPERATORS = [
    {"id": "yglao", "name": "Y. Glao", "role": "Senior QA Analyst", "status": "Online", "shift": "AM Shift"},
    {"id": "jjdayag", "name": "J. J. Dayag", "role": "QA Specialist", "status": "Online", "shift": "AM Shift"},
    {"id": "amorales", "name": "A. Morales", "role": "QA Analyst", "status": "Online", "shift": "AM Shift"},
    {"id": "jofrancisco", "name": "J. O. Francisco", "role": "QA Specialist", "status": "Online", "shift": "Mid Shift"},
    {"id": "jtcanaway", "name": "J. T. Canaway", "role": "QA Lead / Developer", "status": "Online", "shift": "AM Shift"},
    {"id": "jasilva", "name": "J. A. Silva", "role": "QA Analyst", "status": "Online", "shift": "AM Shift"},
    {"id": "cmnarsico", "name": "C. M. Narsico", "role": "QA Analyst", "status": "Online", "shift": "AM Shift"},
]


def format_discrepancy_html(discrepancy_text: str, risk_level: str, primary_fmt: str):
    """Converts extension discrepancy text into rich inline colored diff chips."""
    txt = (discrepancy_text or "").strip()
    if not txt or txt.lower() == "all accounts matched":
        return f"<span class='diff-chip diff-safe'>Exact Match Verified</span> All accounts matched (<span class='font-mono'>{primary_fmt}</span>)"

    # Highlight 'Value1' vs 'Value2'
    def repl_vs(match):
        left = match.group(1)
        right = match.group(2)
        if risk_level == "HIGH RISK":
            return f"<span class='diff-chip diff-danger'>'{left}'</span> vs <span class='diff-chip diff-danger'>'{right}'</span>"
        return f"<span class='diff-chip diff-primary'>'{left}'</span> vs <span class='diff-chip diff-affected'>'{right}'</span>"

    html = re.sub(r"'([^']+)'\s+vs\s+'([^']+)'", repl_vs, txt)
    # Highlight [#ID Name]: prefix
    html = re.sub(r"\[(#\d+\s+[^\]]+)\]:", r"<span class='font-mono font-semibold text-amber-400'>[\1]</span>:", html)
    return html


def parse_person_fields(account_id: str, full_name: str):
    """Splits 'Last, First Middle' into structured fields for the Side-by-Side Inspect modal."""
    acc_id = str(account_id or "").strip().lstrip("#")
    name = str(full_name or "").strip()
    # If full_name still has #ID - Name prefix, strip it
    m = re.match(r"^#?(\d+)\s*[-–—:]\s*(.+)$", name)
    if m:
        if not acc_id:
            acc_id = m.group(1).strip()
        name = m.group(2).strip()

    suffix = ""
    suf_match = re.search(r"\b(Jr|Sr|II|III|IV)\.?$", name, re.IGNORECASE)
    if suf_match:
        suffix = suf_match.group(1)

    last_name = ""
    first_name = name
    middle_name = ""

    if "," in name:
        parts = [p.strip() for p in name.split(",", 1)]
        last_name = parts[0]
        rest = parts[1].split() if len(parts) > 1 else []
        if len(rest) == 1:
            first_name = rest[0]
        elif len(rest) > 1:
            middle_name = rest[-1]
            first_name = " ".join(rest[:-1])
    else:
        tokens = name.split()
        if len(tokens) >= 2:
            first_name = tokens[0]
            last_name = tokens[-1]
            if len(tokens) > 2:
                middle_name = " ".join(tokens[1:-1])

    formatted = f"#{acc_id} - {name}" if acc_id else name
    return {
        "id": acc_id or "N/A",
        "full_name": name,
        "first_name": first_name,
        "middle_name": middle_name,
        "last_name": last_name,
        "suffix": suffix,
        "dob": "Verified in 1Life",
        "gender": "—",
        "phone": "—",
        "address": "—",
        "philhealth": "—",
        "formatted": formatted
    }


def parse_extension_excel(excel_path: str):
    """
    Reads '📋 All Merged Accounts' and '👥 Flattened Pairs' from an exported
    1Life_Audit_Trail_Merges_*.xlsx file produced by the Chrome Extension.
    """
    wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)

    # Map pair details by Primary ID + Audit Date & Time if available
    pairs_map = {}
    if "👥 Flattened Pairs" in wb.sheetnames:
        ws_pairs = wb["👥 Flattened Pairs"]
        pair_rows = list(ws_pairs.iter_rows(values_only=True))
        if len(pair_rows) > 1:
            for r in pair_rows[1:]:
                if not r or len(r) < 13:
                    continue
                p_id = str(r[2] or "").strip()
                dt_str = str(r[12] or "").strip()
                key = f"{p_id}|{dt_str}"
                pairs_map[key] = {
                    "pair_risk_flag": str(r[0] or ""),
                    "mismatch_reason": str(r[1] or ""),
                    "p_id": p_id,
                    "p_full": str(r[3] or ""),
                    "p_last": str(r[4] or ""),
                    "p_first": str(r[5] or ""),
                    "p_mid": str(r[6] or ""),
                    "d_id": str(r[7] or ""),
                    "d_full": str(r[8] or ""),
                    "d_last": str(r[9] or ""),
                    "d_first": str(r[10] or ""),
                    "d_mid": str(r[11] or ""),
                }

    target_sheet = "📋 All Merged Accounts" if "📋 All Merged Accounts" in wb.sheetnames else wb.sheetnames[0]
    ws = wb[target_sheet]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        wb.close()
        return []

    headers = [str(c or "").strip() for c in rows[0]]
    records = []
    seq = 1001

    for row in rows[1:]:
        if not row or all(c is None for c in row):
            continue

        row_dict = dict(zip(headers, row))
        risk_ind = str(row_dict.get("Risk Indicator") or "")
        p_id = str(row_dict.get("Primary Account ID") or "").strip()
        p_name = str(row_dict.get("Primary Account Name") or "").strip()
        aff_raw = str(row_dict.get("Affected Account(s)") or "").strip()
        disc_details = str(row_dict.get("Discrepancy Details") or "").strip()
        total_dupes = int(row_dict.get("Total Duplicates Merged") or 1)
        dt_display = str(row_dict.get("Date & Time") or "").strip()
        user = str(row_dict.get("Merged By (User)") or "unknown").strip()
        action = str(row_dict.get("Action") or "Merge Completed").strip()
        activity_details = str(row_dict.get("Activity Details") or "").strip()
        status = str(row_dict.get("Status") or "Success").strip()

        if "HIGH RISK" in risk_ind.upper():
            risk_level = "HIGH RISK"
            risk_color = "#dc3545"
        elif "REVIEW" in risk_ind.upper():
            risk_level = "MEDIUM / REVIEW"
            risk_color = "#fd7e14"
        else:
            risk_level = "SAFE MATCH"
            risk_color = "#28a745"

        primary_obj = parse_person_fields(p_id, p_name)
        affected_obj = parse_person_fields("", aff_raw)

        # Enrich with exact parsed columns from Flattened Pairs sheet if available
        pair_info = pairs_map.get(f"{p_id}|{dt_display}")
        if pair_info:
            primary_obj["last_name"] = pair_info["p_last"] or primary_obj["last_name"]
            primary_obj["first_name"] = pair_info["p_first"] or primary_obj["first_name"]
            primary_obj["middle_name"] = pair_info["p_mid"] or primary_obj["middle_name"]
            affected_obj["id"] = pair_info["d_id"] or affected_obj["id"]
            affected_obj["full_name"] = pair_info["d_full"] or affected_obj["full_name"]
            affected_obj["last_name"] = pair_info["d_last"] or affected_obj["last_name"]
            affected_obj["first_name"] = pair_info["d_first"] or affected_obj["first_name"]
            affected_obj["middle_name"] = pair_info["d_mid"] or affected_obj["middle_name"]
            if affected_obj["id"] and affected_obj["id"] != "N/A":
                affected_obj["formatted"] = f"#{affected_obj['id']} - {affected_obj['full_name']}"

        # Parse timestamp to ISO
        iso_str = "2026-10-19T17:00:00"
        date_only = "2026-10-19"
        for fmt in ["%b %d, %Y %I:%M %p", "%b %d, %Y %H:%M", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %I:%M %p"]:
            try:
                dt_obj = datetime.strptime(dt_display, fmt)
                iso_str = dt_obj.strftime("%Y-%m-%dT%H:%M:%S")
                date_only = dt_obj.strftime("%Y-%m-%d")
                break
            except Exception:
                pass

        disc_html = format_discrepancy_html(disc_details, risk_level, primary_obj["formatted"])
        risk_reason = pair_info["pair_risk_flag"] if pair_info and pair_info.get("pair_risk_flag") else risk_ind

        records.append({
            "audit_id": f"EXT-{seq}",
            "timestamp_iso": iso_str,
            "timestamp_display": dt_display,
            "date_only": date_only,
            "qa_operator": user,
            "action": action,
            "status": status,
            "total_dupes": total_dupes,
            "primary_account": primary_obj,
            "affected_account": affected_obj,
            "risk_level": risk_level,
            "risk_color": risk_color,
            "risk_reason": risk_reason,
            "discrepancies": [],
            "discrepancy_html": disc_html,
            "discrepancy_text": disc_details,
            "auditor_notes": activity_details
        })
        seq += 1

    wb.close()
    return records


def sync_all_extension_files(combine_all: bool = False):
    """
    Finds all 1Life_Audit_Trail_Merges_*.xlsx files in Downloads (or local project folder),
    and builds the dashboard database.
    - If combine_all=False (default): loads the latest scan (211 records from Oct 19, 2026) while also storing
      the combined 611-record master database so the user can toggle between 'Latest Scan (211)' and 'All Scanned History (611)'!
    """
    pattern1 = os.path.join(DOWNLOADS_DIR, "*1Life_Audit_Trail*.xlsx")
    pattern2 = os.path.join(BASE_DIR, "*1Life_Audit_Trail*.xlsx")
    files = sorted(
        glob.glob(pattern1) + glob.glob(pattern2),
        key=lambda p: os.path.getmtime(p),
        reverse=True
    )

    if not files:
        print("No 1Life_Audit_Trail_*.xlsx files found in Downloads.")
        return None

    latest_file = os.path.basename(files[0])
    latest_records = parse_extension_excel(files[0])

    # Also build combined master list across all unique exports in Downloads
    all_combined = list(latest_records)
    seen_batch_signatures = {f"{latest_records[0]['timestamp_display']}|{latest_records[-1]['timestamp_display']}|{len(latest_records)}"} if latest_records else set()
    seq_offset = len(all_combined) + 1001

    for fpath in files[1:]:
        recs = parse_extension_excel(fpath)
        if not recs:
            continue
        # Check if this file is a different date/batch
        sig = f"{recs[0]['timestamp_display']}|{recs[-1]['timestamp_display']}|{len(recs)}"
        if sig not in seen_batch_signatures:
            seen_batch_signatures.add(sig)
            for r in recs:
                r["audit_id"] = f"EXT-{seq_offset}"
                seq_offset += 1
                all_combined.append(r)

    active_records = all_combined if combine_all else latest_records

    # Discover all operators present in the data + core operators
    op_map = {op["id"]: op for op in CORE_OPERATORS}
    for r in all_combined:
        u = r["qa_operator"]
        if u and u not in op_map:
            op_map[u] = {"id": u, "name": u, "role": "QA Operator", "status": "Online", "shift": "Active"}

    operators_list = list(op_map.values())

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "generated_at": now_str,
        "synced_at": now_str,
        "source": f"1Life Audit Trail Extension ({'All Exports Combined' if combine_all else latest_file})",
        "source_file": files[0],
        "latest_count": len(latest_records),
        "combined_count": len(all_combined),
        "available_exports": [
            {
                "filename": os.path.basename(f),
                "path": f,
                "modified": datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %I:%M:%S %p"),
                "size_kb": round(os.path.getsize(f) / 1024, 1)
            }
            for f in files
        ],
        "operators": operators_list,
        "records": active_records,
        "latest_records": latest_records,
        "combined_records": all_combined
    }

    with open(os.path.join(BASE_DIR, "data.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    with open(os.path.join(BASE_DIR, "data.js"), "w", encoding="utf-8") as f:
        f.write("window.INITIAL_AUDIT_DATA = ")
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write(";\n")

    print(f"Synced {len(active_records)} active records (Latest: {len(latest_records)}, Combined History: {len(all_combined)}) into data.json & data.js")
    return payload


if __name__ == "__main__":
    sync_all_extension_files()
