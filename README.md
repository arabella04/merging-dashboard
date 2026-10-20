# 🛡️ QA Audit Trail & Risk Monitoring Dashboard

A real-time **Quality Assurance Supervisor Console** for monitoring account deduplication and merge operations, featuring an automated demographic risk classification engine, operator workload tracking, side-by-side account inspection, and a customizable styled Excel (`.xlsx`) exporter.

---

## ✨ Key Architectural Highlights

1. **Real-Time Auto-Sync Engine**
   - Configurable polling interval (`Every 30s`, `Every 60s`, `Every 5m`, or `Paused`) with a live countdown badge.
   - Pulsating green status dot (`Synced just now`), relative freshness indicator, last synchronized timestamp, and a manual **Sync Now** button.

2. **Automated Risk Classification Engine**
   - **`HIGH RISK` (`#dc3545` Crimson):** Triggered when **Name AND Birthday differ** (or critical DOB divergence across merged profiles), highlighting potential erroneous merges such as parent/child or sibling collisions.
   - **`MEDIUM / REVIEW` (`#fd7e14` / `#ffc107` Amber):** Triggered when **Name has minor typographic, suffix, or maiden/married surname variations with the Same Birthday**.
   - **`SAFE MATCH` (`#28a745` Green):** Exact match verified across Full Name, Date of Birth, and key identifiers.
   - **Inline Discrepancy Diffs:** Explicitly highlights field-by-field differences (e.g., `Last Name differs: 'Mata Jr' vs 'Mata' • Birthdays do not match: 1985-04-12 vs 1961-08-20`).

3. **Dedicated QA Operator Tracking & Workload Bar**
   - Tracks all 5 QA operators (`yglao`, `jjdayag`, `amorales`, `jofrancisco`, `jtcanaway`) with total operations performed, High Risk flags, and proportional risk distribution bars.
   - Clicking any operator chip immediately filters the primary data grid.

4. **Customizable Styled Excel (`.xlsx`) Report Exporter**
   - Choose which columns to include (`Date/Time`, `QA User`, `Action`, `Primary Account`, `Affected Account`, `Risk Level`, `Discrepancies`, `Status`).
   - Filter by Date Range, Selected QA Operators, and Risk Levels (including one-click **"High Risk Only (Audit Meeting)"** preset).
   - Generates a styled `.xlsx` workbook with dark headers, auto-fit column widths, and color-coded risk cells.

5. **Side-by-Side Demographic Inspection Modal**
   - Click any account or **Inspect** button to view a field-by-field comparison (`Account ID`, `First Name`, `Middle Name`, `Last Name & Suffix`, `DOB`, `Gender`, `Phone`, `Address`, `PhilHealth ID`) and execute supervisor actions (`Revert & Unmerge`, `Escalate for Review`, `Approve & Mark Verified`).

6. **Dark & Light Enterprise Portal Theme**
   - Default sleek dark mode (`#1e222d` cards, `#2e3446` subtle borders) with instant one-click toggle to crisp Light Admin theme.

---

## 🚀 Quick Start

### Option 1: Launch Local Live Server
Double-click `start_dashboard.bat` or run:
```powershell
python server.py
```
Then open **[http://localhost:8095](http://localhost:8095)** in your browser.

### Option 2: Direct Browser Launch
Open `index.html` directly in any modern browser (preloaded with `data.js`).
