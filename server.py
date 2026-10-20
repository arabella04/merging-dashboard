import http.server
import socketserver
import os
import json
import urllib.parse
from datetime import datetime
from import_extension_data import sync_all_extension_files, CORE_OPERATORS, format_discrepancy_html, parse_person_fields

PORT = 8095
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class QAAuditHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/api/audit-logs":
            json_path = os.path.join(BASE_DIR, "data.json")
            if not os.path.exists(json_path):
                sync_all_extension_files()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            with open(json_path, "rb") as f:
                self.wfile.write(f.read())
            return

        elif path == "/api/sync":
            scope = qs.get("scope", ["latest"])[0]
            combine_all = (scope == "combined")
            try:
                data = sync_all_extension_files(combine_all=combine_all)
                if not data:
                    json_path = os.path.join(BASE_DIR, "data.json")
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "synced_at": data.get("synced_at"),
                    "source": data.get("source"),
                    "total_records": len(data.get("records", [])),
                    "latest_count": data.get("latest_count", len(data.get("records", []))),
                    "combined_count": data.get("combined_count", len(data.get("records", []))),
                    "data": data
                }, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
            return

        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/api/extension-sync":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body) if body else {}
            ext_records = payload.get("records", [])

            records = []
            seq = 1001
            for item in ext_records:
                # Item comes from _0x589b37 in 1Life Audit Trail Exporter & Auditor Extension
                highest_risk = item.get("highestRisk", "SAFE")
                if highest_risk == "HIGH_RISK":
                    risk_level = "HIGH RISK"
                    risk_color = "#dc3545"
                elif highest_risk == "REVIEW":
                    risk_level = "MEDIUM / REVIEW"
                    risk_color = "#fd7e14"
                else:
                    risk_level = "SAFE MATCH"
                    risk_color = "#28a745"

                p_raw = item.get("primary") or {}
                p_id = str(p_raw.get("id") or "")
                p_full = str(p_raw.get("fullName") or item.get("primaryAccountRaw") or "")
                primary_obj = parse_person_fields(p_id, p_full)

                aff_raw = str(item.get("affectedAccountRaw") or "")
                affected_obj = parse_person_fields("", aff_raw)

                dt_display = str(item.get("dateTime") or "")
                iso_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                date_only = datetime.now().strftime("%Y-%m-%d")
                for fmt in ["%b %d, %Y %I:%M %p", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %I:%M %p"]:
                    try:
                        dt_obj = datetime.strptime(dt_display, fmt)
                        iso_str = dt_obj.strftime("%Y-%m-%dT%H:%M:%S")
                        date_only = dt_obj.strftime("%Y-%m-%d")
                        break
                    except Exception:
                        pass

                reasons_summary = str(item.get("reasonsSummary") or "All accounts matched")
                disc_html = format_discrepancy_html(reasons_summary, risk_level, primary_obj["formatted"])

                records.append({
                    "audit_id": f"EXT-{seq}",
                    "timestamp_iso": iso_str,
                    "timestamp_display": dt_display,
                    "date_only": date_only,
                    "qa_operator": str(item.get("user") or "unknown").strip(),
                    "action": str(item.get("action") or "Merge Completed"),
                    "status": str(item.get("status") or "Success"),
                    "total_dupes": len(item.get("duplicates") or [1]),
                    "primary_account": primary_obj,
                    "affected_account": affected_obj,
                    "risk_level": risk_level,
                    "risk_color": risk_color,
                    "risk_reason": str(item.get("overallIndicator") or risk_level),
                    "discrepancies": [],
                    "discrepancy_html": disc_html,
                    "discrepancy_text": reasons_summary,
                    "auditor_notes": str(item.get("details") or "")
                })
                seq += 1

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            out_data = {
                "generated_at": now_str,
                "synced_at": now_str,
                "source": "1Life Audit Trail Chrome Extension (Live Stream)",
                "latest_count": len(records),
                "combined_count": len(records),
                "operators": CORE_OPERATORS,
                "records": records,
                "latest_records": records,
                "combined_records": records
            }
            with open(os.path.join(BASE_DIR, "data.json"), "w", encoding="utf-8") as f:
                json.dump(out_data, f, indent=2, ensure_ascii=False)
            with open(os.path.join(BASE_DIR, "data.js"), "w", encoding="utf-8") as f:
                f.write("window.INITIAL_AUDIT_DATA = ")
                json.dump(out_data, f, indent=2, ensure_ascii=False)
                f.write(";\n")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "synced_records": len(records),
                "synced_at": now_str
            }).encode("utf-8"))
            return

        self.send_error(404, "Endpoint not found")


def run_server():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), QAAuditHandler) as httpd:
        print(f"QA Audit Trail & Risk Monitoring Server running at http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")

if __name__ == "__main__":
    run_server()
