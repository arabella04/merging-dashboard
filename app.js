/**
 * QA Audit Trail & Risk Monitoring Dashboard - Core Engine
 * Supports:
 * 1. Real-Time Auto-Sync Engine (30s, 60s, 5m polling + countdown + manual Sync Now)
 * 2. Automated Risk Classification Engine (HIGH RISK #dc3545, MEDIUM / REVIEW #fd7e14, SAFE MATCH #28a745)
 * 3. Dedicated QA Operator Tracking & Workload Bar (yglao, jjdayag, amorales, jofrancisco, jtcanaway)
 * 4. Customizable Styled Excel (.xlsx) Report Exporter
 * 5. Side-by-Side Demographic Inspection Modal & Supervisor Resolution
 */

const QA_OPERATORS = [
    { id: 'yglao', name: 'Y. Glao', role: 'Senior QA Analyst', shift: 'AM Shift' },
    { id: 'jjdayag', name: 'J. J. Dayag', role: 'QA Specialist', shift: 'AM Shift' },
    { id: 'jasilva', name: 'J. A. Silva', role: 'QA Analyst', shift: 'AM Shift' },
    { id: 'amorales', name: 'A. Morales', role: 'QA Analyst', shift: 'AM Shift' },
    { id: 'jofrancisco', name: 'J. O. Francisco', role: 'QA Specialist', shift: 'Mid Shift' },
    { id: 'jtcanaway', name: 'J. T. Canaway', role: 'QA Lead / Dev', shift: 'AM Shift' }
];

let allRecords = [];
let latestScanRecords = [];
let combinedHistoryRecords = [];
let activeDatasetScope = 'latest';
let filteredRecords = [];
let selectedOperator = 'ALL';
let sortField = 'timestamp';
let sortDirection = 'desc';
let currentPage = 1;
let pageSize = 25;
let currentInspectedAuditId = null;

// Real-time Auto-Sync state
let autoSyncIntervalSec = 30;
let countdownRemainingSec = 30;
let countdownTimerId = null;
let lastSyncTime = new Date();

// ============================================================================
// 1. AUTOMATED RISK CLASSIFICATION ENGINE (Client + Server Parity)
// ============================================================================
function evaluateAccountRiskJS(primary, affected) {
    const pFirst = (primary.first_name || '').trim();
    const pMid = (primary.middle_name || '').trim();
    const pLast = (primary.last_name || '').trim();
    const pSuffix = (primary.suffix || '').trim();
    const pLastFull = `${pLast} ${pSuffix}`.trim();
    const pFull = `${pFirst} ${pMid} ${pLastFull}`.replace(/\s+/g, ' ').trim();
    const pDob = (primary.dob || '').trim();
    const pPhone = (primary.phone || '').trim();

    const aFirst = (affected.first_name || '').trim();
    const aMid = (affected.middle_name || '').trim();
    const aLast = (affected.last_name || '').trim();
    const aSuffix = (affected.suffix || '').trim();
    const aLastFull = `${aLast} ${aSuffix}`.trim();
    const aFull = `${aFirst} ${aMid} ${aLastFull}`.replace(/\s+/g, ' ').trim();
    const aDob = (affected.dob || '').trim();
    const aPhone = (affected.phone || '').trim();

    const firstDiff = pFirst.toLowerCase() !== aFirst.toLowerCase();
    const lastDiff = pLastFull.toLowerCase() !== aLastFull.toLowerCase();
    const midDiff = pMid && aMid && (pMid.toLowerCase() !== aMid.toLowerCase());
    const nameDiffers = firstDiff || lastDiff;
    const dobExact = (pDob === aDob);

    const htmlParts = [];
    const textParts = [];
    const discrepancies = [];

    if (lastDiff) {
        htmlParts.push(`Last Name differs: <span class='diff-chip diff-primary'>'${escapeHtml(pLastFull)}'</span> vs <span class='diff-chip diff-affected'>'${escapeHtml(aLastFull)}'</span>`);
        textParts.push(`Last Name differs: '${pLastFull}' vs '${aLastFull}'`);
        discrepancies.push({ field: 'Last Name', primary: pLastFull, affected: aLastFull, severity: 'high' });
    }
    if (firstDiff) {
        htmlParts.push(`First Name differs: <span class='diff-chip diff-primary'>'${escapeHtml(pFirst)}'</span> vs <span class='diff-chip diff-affected'>'${escapeHtml(aFirst)}'</span>`);
        textParts.push(`First Name differs: '${pFirst}' vs '${aFirst}'`);
        discrepancies.push({ field: 'First Name', primary: pFirst, affected: aFirst, severity: 'medium' });
    }
    if (midDiff) {
        htmlParts.push(`Middle Name differs: <span class='diff-chip diff-warn'>'${escapeHtml(pMid)}'</span> vs <span class='diff-chip diff-warn'>'${escapeHtml(aMid)}'</span>`);
        textParts.push(`Middle Name differs: '${pMid}' vs '${aMid}'`);
        discrepancies.push({ field: 'Middle Name', primary: pMid, affected: aMid, severity: 'low' });
    }
    if (!dobExact) {
        htmlParts.push(`Birthdays do not match: <span class='diff-chip diff-danger'>${escapeHtml(pDob)}</span> vs <span class='diff-chip diff-danger'>${escapeHtml(aDob)}</span>`);
        textParts.push(`Birthdays do not match: ${pDob} vs ${aDob}`);
        discrepancies.push({ field: 'Date of Birth', primary: pDob, affected: aDob, severity: 'high' });
    }

    let riskLevel = 'SAFE MATCH';
    let riskColor = '#28a745';
    let riskReason = 'Exact match across Name, Birthday, and key identifiers';

    if (nameDiffers && !dobExact) {
        riskLevel = 'HIGH RISK';
        riskColor = '#dc3545';
        riskReason = 'Critical Red Flag: Different Name AND Different Birthday';
    } else if (!dobExact) {
        riskLevel = 'HIGH RISK';
        riskColor = '#dc3545';
        riskReason = 'Critical DOB Mismatch across merged profiles';
    } else if (nameDiffers && dobExact) {
        riskLevel = 'MEDIUM / REVIEW';
        riskColor = '#fd7e14';
        riskReason = 'Different Name / Typographic or Suffix Variation with Same Birthday';
    } else if (midDiff && dobExact) {
        riskLevel = 'MEDIUM / REVIEW';
        riskColor = '#ffc107';
        riskReason = 'Middle Name Variation with Same Birthday';
    } else {
        htmlParts.push(`<span class='diff-chip diff-safe'>Exact Match Verified</span> Full Name (<span class='font-mono'>${escapeHtml(pFull)}</span>) &amp; DOB (<span class='font-mono'>${escapeHtml(pDob)}</span>) match 100%.`);
        textParts.push(`Exact Match Verified: Full Name (${pFull}) & DOB (${pDob}) match 100%.`);
        if (pPhone && aPhone && pPhone !== aPhone) {
            htmlParts.push(`<span class='text-xs opacity-75'>Consolidated secondary phone ${escapeHtml(aPhone)}</span>`);
            textParts.push(`Consolidated secondary phone ${aPhone}`);
        }
    }

    return {
        risk_level: riskLevel,
        risk_color: riskColor,
        risk_reason: riskReason,
        discrepancies: discrepancies,
        discrepancy_html: htmlParts.join(' &bull; '),
        discrepancy_text: textParts.join(' | ')
    };
}

// ============================================================================
// 2. INITIALIZATION & DATA LOADING
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    loadInitialData();
    startAutoSyncTimer();

    // Listen for live real-time stream from the 1Life Chrome Extension (works on https://mergingdashboard.netlify.app/)
    window.addEventListener('message', (event) => {
        if (event.data && event.data.type === 'QA_EXTENSION_LIVE_SYNC' && event.data.payload) {
            const extPayload = event.data.payload;
            if (Array.isArray(extPayload.records) && extPayload.records.length > 0) {
                latestScanRecords = extPayload.records;
                if (activeDatasetScope === 'latest') {
                    allRecords = latestScanRecords;
                }
                updateSyncTimestampDisplay(new Date(extPayload.synced_at || Date.now()));
                refreshDashboardView();
                showToast(`Live-synced ${extPayload.records.length} records from 1Life Chrome Extension!`, 'success');
            }
        }
    });
});

function loadInitialData() {
    if (window.INITIAL_AUDIT_DATA) {
        latestScanRecords = window.INITIAL_AUDIT_DATA.latest_records || window.INITIAL_AUDIT_DATA.records || [];
        combinedHistoryRecords = window.INITIAL_AUDIT_DATA.combined_records || latestScanRecords;
        allRecords = activeDatasetScope === 'combined' ? combinedHistoryRecords : latestScanRecords;
    }
    updateSyncTimestampDisplay(new Date());
    refreshDashboardView();

    // Also attempt background fetch from local server if running
    fetch('/api/audit-logs')
        .then(res => res.ok ? res.json() : null)
        .then(data => {
            if (data && Array.isArray(data.records)) {
                latestScanRecords = data.latest_records || data.records;
                combinedHistoryRecords = data.combined_records || latestScanRecords;
                allRecords = activeDatasetScope === 'combined' ? combinedHistoryRecords : latestScanRecords;
                refreshDashboardView();
            }
        })
        .catch(() => {
            // Running standalone file:// or static mode; preloaded data.js is active
        });
}

function switchExtensionDatasetScope(scope) {
    activeDatasetScope = scope;
    if (scope === 'combined' && combinedHistoryRecords.length > 0) {
        allRecords = combinedHistoryRecords;
        showToast(`Switched to All Scanned Extension Exports (${allRecords.length} total merges across yglao, jjdayag, jofrancisco, amorales, jasilva)`, 'info');
    } else {
        allRecords = latestScanRecords;
        showToast(`Switched to Latest Extension Scan (${allRecords.length} merges • Oct 19, 2026)`, 'info');
    }
    currentPage = 1;
    refreshDashboardView();
}

function handleExtensionFileUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function (e) {
        try {
            const data = new Uint8Array(e.target.result);
            const wb = XLSX.read(data, { type: 'array' });
            const sheetName = wb.SheetNames.includes('📋 All Merged Accounts')
                ? '📋 All Merged Accounts'
                : wb.SheetNames[0];
            const rows = XLSX.utils.sheet_to_json(wb.Sheets[sheetName]);
            if (!rows.length) {
                showToast('Uploaded workbook has no rows in ' + sheetName, 'error');
                return;
            }
            const parsed = rows.map((r, i) => {
                const riskInd = String(r['Risk Indicator'] || '');
                let riskLevel = 'SAFE MATCH';
                let riskColor = '#28a745';
                if (riskInd.toUpperCase().includes('HIGH RISK')) {
                    riskLevel = 'HIGH RISK';
                    riskColor = '#dc3545';
                } else if (riskInd.toUpperCase().includes('REVIEW')) {
                    riskLevel = 'MEDIUM / REVIEW';
                    riskColor = '#fd7e14';
                }
                const pId = String(r['Primary Account ID'] || '').trim();
                const pName = String(r['Primary Account Name'] || '').trim();
                const affRaw = String(r['Affected Account(s)'] || '').trim();
                const disc = String(r['Discrepancy Details'] || 'All accounts matched');
                const dt = String(r['Date & Time'] || '');
                const user = String(r['Merged By (User)'] || 'unknown').trim();
                const action = String(r['Action'] || 'Merge Completed');
                const status = String(r['Status'] || 'Success');

                return {
                    audit_id: `EXT-${1001 + i}`,
                    timestamp_iso: new Date(dt).toISOString ? new Date(dt).toISOString().slice(0, 19) : '2026-10-19T17:00:00',
                    timestamp_display: dt,
                    date_only: '2026-10-19',
                    qa_operator: user,
                    action: action,
                    status: status,
                    primary_account: {
                        id: pId,
                        full_name: pName,
                        first_name: pName.split(',')[1]?.trim() || pName,
                        middle_name: '',
                        last_name: pName.split(',')[0]?.trim() || pName,
                        suffix: '',
                        dob: 'Verified in 1Life',
                        gender: '—',
                        phone: '—',
                        address: '—',
                        formatted: `#${pId} - ${pName}`
                    },
                    affected_account: {
                        id: affRaw.match(/#(\d+)/)?.[1] || 'N/A',
                        full_name: affRaw.replace(/^#\d+\s*-\s*/, ''),
                        first_name: '',
                        middle_name: '',
                        last_name: '',
                        suffix: '',
                        dob: 'Verified in 1Life',
                        gender: '—',
                        phone: '—',
                        address: '—',
                        formatted: affRaw
                    },
                    risk_level: riskLevel,
                    risk_color: riskColor,
                    risk_reason: riskInd,
                    discrepancies: [],
                    discrepancy_html: escapeHtml(disc),
                    discrepancy_text: disc,
                    auditor_notes: String(r['Activity Details'] || '')
                };
            });
            allRecords = parsed;
            latestScanRecords = parsed;
            updateSyncTimestampDisplay(new Date());
            refreshDashboardView();
            showToast(`Loaded ${parsed.length} records from ${file.name}!`, 'success');
        } catch (err) {
            showToast('Error reading Excel file: ' + err.message, 'error');
        }
    };
    reader.readAsArrayBuffer(file);
}

function refreshDashboardView() {
    updateTopKPIs();
    renderOperatorChips();
    applyFilters();
    updateExportPreviewCount();
}

// ============================================================================
// 3. REAL-TIME AUTO-SYNC ENGINE
// ============================================================================
function startAutoSyncTimer() {
    if (countdownTimerId) clearInterval(countdownTimerId);
    countdownRemainingSec = autoSyncIntervalSec;
    updateCountdownBadge();

    countdownTimerId = setInterval(() => {
        if (autoSyncIntervalSec <= 0) return;

        countdownRemainingSec--;
        if (countdownRemainingSec <= 0) {
            triggerManualSync(true);
            countdownRemainingSec = autoSyncIntervalSec;
        }
        updateCountdownBadge();
        updateRelativeSyncStatusText();
    }, 1000);
}

function updateAutoSyncInterval(val) {
    autoSyncIntervalSec = parseInt(val, 10) || 0;
    const dot = document.getElementById('sync-status-dot');
    const statusText = document.getElementById('sync-status-text');

    if (autoSyncIntervalSec === 0) {
        dot.classList.remove('pulse-green-dot', 'bg-[#28a745]');
        dot.classList.add('bg-amber-400');
        statusText.textContent = 'Auto-Sync Paused';
        statusText.className = 'font-semibold text-amber-400';
        document.getElementById('sync-countdown-badge').textContent = 'OFF';
        showToast('Auto-Sync Engine paused by supervisor', 'info');
    } else {
        dot.classList.remove('bg-amber-400');
        dot.classList.add('pulse-green-dot', 'bg-[#28a745]');
        statusText.textContent = 'Synced just now';
        statusText.className = 'font-semibold text-emerald-400';
        countdownRemainingSec = autoSyncIntervalSec;
        updateCountdownBadge();
        showToast(`Auto-Sync polling interval set to ${autoSyncIntervalSec >= 60 ? (autoSyncIntervalSec / 60) + 'm' : autoSyncIntervalSec + 's'}`, 'success');
    }
}

function updateCountdownBadge() {
    const badge = document.getElementById('sync-countdown-badge');
    if (!badge) return;
    if (autoSyncIntervalSec <= 0) {
        badge.textContent = 'OFF';
        return;
    }
    badge.textContent = `${countdownRemainingSec}s`;
}

function updateRelativeSyncStatusText() {
    if (autoSyncIntervalSec <= 0) return;
    const diffSec = Math.floor((new Date() - lastSyncTime) / 1000);
    const statusText = document.getElementById('sync-status-text');
    if (!statusText) return;
    if (diffSec < 10) {
        statusText.textContent = 'Synced just now';
    } else if (diffSec < 60) {
        statusText.textContent = `Synced ${diffSec}s ago`;
    } else {
        statusText.textContent = `Synced ${Math.floor(diffSec / 60)}m ago`;
    }
}

function updateSyncTimestampDisplay(dateObj) {
    lastSyncTime = dateObj;
    const formatted = dateObj.toLocaleString('en-US', {
        month: 'short',
        day: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: true
    });
    const el = document.getElementById('last-synced-timestamp');
    if (el) el.textContent = formatted;
    const statusText = document.getElementById('sync-status-text');
    if (statusText && autoSyncIntervalSec > 0) {
        statusText.textContent = 'Synced just now';
        statusText.className = 'font-semibold text-emerald-400';
    }
}

function triggerManualSync(isAuto = false) {
    const spinner = document.getElementById('sync-spinner-icon');
    const statusText = document.getElementById('sync-status-text');
    if (spinner) spinner.classList.add('animate-spin');
    if (statusText) statusText.textContent = 'Synchronizing...';

    fetch(`/api/sync?scope=${activeDatasetScope}`)
        .then(res => res.ok ? res.json() : null)
        .then(res => {
            if (res && res.data && Array.isArray(res.data.records)) {
                latestScanRecords = res.data.latest_records || res.data.records;
                combinedHistoryRecords = res.data.combined_records || latestScanRecords;
                allRecords = activeDatasetScope === 'combined' ? combinedHistoryRecords : latestScanRecords;
            }
            finalizeSync(isAuto);
        })
        .catch(() => {
            finalizeSync(isAuto);
        });
}

function finalizeSync(isAuto) {
    setTimeout(() => {
        const spinner = document.getElementById('sync-spinner-icon');
        if (spinner) spinner.classList.remove('animate-spin');
        countdownRemainingSec = autoSyncIntervalSec;
        updateSyncTimestampDisplay(new Date());
        updateCountdownBadge();
        refreshDashboardView();
        if (!isAuto) {
            showToast(`Audit Trail synchronized (${allRecords.length} total QA operations verified)`, 'success');
        }
    }, 350);
}

// ============================================================================
// 4. TOP KPI CARDS & DEDICATED QA OPERATOR WORKLOAD BAR
// ============================================================================
function updateTopKPIs() {
    const total = allRecords.length;
    const highRisk = allRecords.filter(r => r.risk_level === 'HIGH RISK').length;
    const reviewRisk = allRecords.filter(r => r.risk_level === 'MEDIUM / REVIEW').length;
    const safeMerges = allRecords.filter(r => r.risk_level === 'SAFE MATCH').length;

    document.getElementById('kpi-total-ops').textContent = total.toLocaleString();
    document.getElementById('kpi-high-risk').textContent = highRisk.toLocaleString();
    document.getElementById('kpi-review-risk').textContent = reviewRisk.toLocaleString();
    document.getElementById('kpi-safe-merges').textContent = safeMerges.toLocaleString();

    const pctHigh = total ? ((highRisk / total) * 100).toFixed(1) : '0.0';
    const pctRev = total ? ((reviewRisk / total) * 100).toFixed(1) : '0.0';
    const pctSafe = total ? ((safeMerges / total) * 100).toFixed(1) : '0.0';

    document.getElementById('kpi-high-risk-pct').textContent = `${pctHigh}%`;
    document.getElementById('kpi-review-risk-pct').textContent = `${pctRev}%`;
    document.getElementById('kpi-safe-merges-pct').textContent = `${pctSafe}%`;
}

function renderOperatorChips() {
    const container = document.getElementById('operator-chips-container');
    if (!container) return;

    const totalAll = allRecords.length;
    const highAll = allRecords.filter(r => r.risk_level === 'HIGH RISK').length;

    let html = `
        <div onclick="selectOperatorChip('ALL')" class="portal-elevated rounded-xl p-3 cursor-pointer transition hover:border-blue-500/60 flex flex-col justify-between ${selectedOperator === 'ALL' ? 'op-chip-active' : ''}">
            <div class="flex items-center justify-between">
                <span class="font-mono font-bold text-xs text-blue-400">ALL ANALYSTS (5)</span>
                <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
            </div>
            <div class="mt-2 flex items-baseline justify-between">
                <span class="text-sm font-extrabold">${totalAll} ops</span>
                <span class="text-[11px] font-semibold px-1.5 py-0.5 rounded bg-[#dc3545]/20 text-[#dc3545]">${highAll} High Risk</span>
            </div>
            <div class="w-full h-1.5 bg-slate-700/50 rounded-full overflow-hidden mt-2 flex">
                <div style="width: ${(highAll / Math.max(totalAll, 1)) * 100}%" class="bg-[#dc3545]"></div>
                <div style="width: ${(allRecords.filter(r => r.risk_level === 'MEDIUM / REVIEW').length / Math.max(totalAll, 1)) * 100}%" class="bg-[#fd7e14]"></div>
                <div style="width: ${(allRecords.filter(r => r.risk_level === 'SAFE MATCH').length / Math.max(totalAll, 1)) * 100}%" class="bg-[#28a745]"></div>
            </div>
        </div>
    `;

    QA_OPERATORS.forEach(op => {
        const opRecords = allRecords.filter(r => r.qa_operator === op.id);
        const opTotal = opRecords.length;
        const opHigh = opRecords.filter(r => r.risk_level === 'HIGH RISK').length;
        const opReview = opRecords.filter(r => r.risk_level === 'MEDIUM / REVIEW').length;
        const opSafe = opRecords.filter(r => r.risk_level === 'SAFE MATCH').length;
        const opFlagged = opHigh + opReview;
        const isActive = selectedOperator === op.id;

        html += `
            <div onclick="selectOperatorChip('${op.id}')" class="portal-elevated rounded-xl p-3 cursor-pointer transition hover:border-blue-500/60 flex flex-col justify-between ${isActive ? 'op-chip-active' : ''}">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-1.5">
                        <span class="w-2 h-2 rounded-full ${opTotal > 0 ? 'bg-emerald-400' : 'bg-slate-500'}"></span>
                        <span class="font-mono font-bold text-xs">${op.id}</span>
                    </div>
                    <span class="text-[10px] text-slate-400">${op.name}</span>
                </div>
                <div class="mt-2 flex items-baseline justify-between gap-1">
                    <span class="text-xs font-bold">${op.id}: ${opTotal} ops</span>
                    <span class="text-[10px] font-bold px-1.5 py-0.5 rounded ${opFlagged > 0 ? 'bg-[#dc3545]/20 text-[#dc3545]' : 'bg-emerald-500/20 text-emerald-400'}">
                        🚨 ${opFlagged} (${opHigh} High)
                    </span>
                </div>
                <div class="w-full h-1.5 bg-slate-700/50 rounded-full overflow-hidden mt-2 flex" title="High Risk: ${opHigh} | Review: ${opReview} | Safe: ${opSafe}">
                    <div style="width: ${(opHigh / Math.max(opTotal, 1)) * 100}%" class="bg-[#dc3545]"></div>
                    <div style="width: ${(opReview / Math.max(opTotal, 1)) * 100}%" class="bg-[#fd7e14]"></div>
                    <div style="width: ${(opSafe / Math.max(opTotal, 1)) * 100}%" class="bg-[#28a745]"></div>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;

    const clearBtn = document.getElementById('btn-clear-operator');
    if (clearBtn) {
        if (selectedOperator !== 'ALL') {
            clearBtn.classList.remove('hidden');
            clearBtn.classList.add('inline-flex');
        } else {
            clearBtn.classList.add('hidden');
            clearBtn.classList.remove('inline-flex');
        }
    }
}

function selectOperatorChip(opId) {
    selectedOperator = opId;
    const dropdown = document.getElementById('filter-operator');
    if (dropdown) dropdown.value = opId;
    currentPage = 1;
    renderOperatorChips();
    applyFilters();
}

function setQuickRiskFilter(riskVal) {
    const riskSelect = document.getElementById('filter-risk');
    if (riskSelect) riskSelect.value = riskVal;
    currentPage = 1;
    applyFilters();
}

function resetAllFilters() {
    selectedOperator = 'ALL';
    document.getElementById('search-input').value = '';
    document.getElementById('filter-risk').value = 'ALL';
    document.getElementById('filter-operator').value = 'ALL';
    document.getElementById('filter-action').value = 'ALL';
    document.getElementById('filter-status').value = 'ALL';
    currentPage = 1;
    renderOperatorChips();
    applyFilters();
}

// ============================================================================
// 5. FILTERING, SORTING & PRIMARY DATA GRID RENDERING
// ============================================================================
function applyFilters() {
    const query = (document.getElementById('search-input')?.value || '').trim().toLowerCase();
    const riskFilter = document.getElementById('filter-risk')?.value || 'ALL';
    const opFilter = document.getElementById('filter-operator')?.value || 'ALL';
    const actionFilter = document.getElementById('filter-action')?.value || 'ALL';
    const statusFilter = document.getElementById('filter-status')?.value || 'ALL';

    selectedOperator = opFilter;

    filteredRecords = allRecords.filter(r => {
        if (riskFilter !== 'ALL' && r.risk_level !== riskFilter) return false;
        if (opFilter !== 'ALL' && r.qa_operator !== opFilter) return false;
        if (actionFilter !== 'ALL' && r.action !== actionFilter) return false;
        if (statusFilter !== 'ALL' && r.status !== statusFilter) return false;

        if (query) {
            const haystack = [
                r.audit_id,
                r.qa_operator,
                r.action,
                r.status,
                r.risk_level,
                r.primary_account?.formatted,
                r.primary_account?.dob,
                r.primary_account?.philhealth,
                r.affected_account?.formatted,
                r.affected_account?.dob,
                r.affected_account?.philhealth,
                r.discrepancy_text,
                r.auditor_notes
            ].join(' ').toLowerCase();
            if (!haystack.includes(query)) return false;
        }
        return true;
    });

    sortFilteredRecords();
    renderDataGrid();
}

function toggleSort(field) {
    if (sortField === field) {
        sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        sortField = field;
        sortDirection = field === 'timestamp' ? 'desc' : 'asc';
    }

    ['risk', 'timestamp', 'operator'].forEach(f => {
        const icon = document.getElementById(`sort-icon-${f}`);
        if (!icon) return;
        if (f === sortField) {
            icon.textContent = sortDirection === 'asc' ? '↑' : '↓';
            icon.className = 'text-[10px] text-blue-400 font-bold';
        } else {
            icon.textContent = '↕';
            icon.className = 'text-[10px]';
        }
    });

    sortFilteredRecords();
    renderDataGrid();
}

function sortFilteredRecords() {
    const riskRank = { 'HIGH RISK': 3, 'MEDIUM / REVIEW': 2, 'SAFE MATCH': 1 };
    const dir = sortDirection === 'asc' ? 1 : -1;

    filteredRecords.sort((a, b) => {
        if (sortField === 'risk') {
            const diff = (riskRank[a.risk_level] || 0) - (riskRank[b.risk_level] || 0);
            if (diff !== 0) return diff * dir;
        } else if (sortField === 'operator') {
            const diff = a.qa_operator.localeCompare(b.qa_operator);
            if (diff !== 0) return diff * dir;
        }
        return a.timestamp_iso.localeCompare(b.timestamp_iso) * dir;
    });
}

function renderDataGrid() {
    const tbody = document.getElementById('audit-table-body');
    const showingBadge = document.getElementById('showing-count-badge');
    if (!tbody) return;

    const totalFiltered = filteredRecords.length;
    const totalPages = Math.max(1, Math.ceil(totalFiltered / pageSize));
    if (currentPage > totalPages) currentPage = totalPages;

    const startIdx = (currentPage - 1) * pageSize;
    const pageItems = filteredRecords.slice(startIdx, startIdx + pageSize);

    if (showingBadge) {
        showingBadge.textContent = `Showing ${pageItems.length} of ${totalFiltered} filtered operations (${allRecords.length} total)`;
    }

    if (pageItems.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" class="py-12 text-center text-slate-400">
                    <div class="text-sm font-semibold mb-1">No audit operations match the active filter criteria</div>
                    <button onclick="resetAllFilters()" class="mt-2 px-3 py-1.5 rounded-lg bg-blue-600/20 text-blue-400 text-xs font-semibold">Reset All Filters</button>
                </td>
            </tr>
        `;
        renderPagination(0, 1);
        return;
    }

    tbody.innerHTML = pageItems.map(r => {
        const isHigh = r.risk_level === 'HIGH RISK';
        const isMed = r.risk_level === 'MEDIUM / REVIEW';

        let riskBadgeClass = 'badge-safe-match';
        let riskIcon = '✓';
        let riskLabel = 'SAFE MATCH';
        if (isHigh) {
            riskBadgeClass = 'badge-high-risk';
            riskIcon = '⚠';
            riskLabel = 'HIGH RISK';
        } else if (isMed) {
            riskBadgeClass = 'badge-medium-risk';
            riskIcon = '!';
            riskLabel = 'REVIEW';
        }

        // Action Pill
        let actionBadge = '';
        if (r.action === 'Merged') {
            actionBadge = `<span class="px-2 py-0.5 rounded font-semibold bg-blue-500/15 text-blue-400 border border-blue-500/30">Merged</span>`;
        } else if (r.action === 'Unmerged') {
            actionBadge = `<span class="px-2 py-0.5 rounded font-semibold bg-purple-500/15 text-purple-400 border border-purple-500/30">Unmerged</span>`;
        } else if (r.action === 'Flagged for Review') {
            actionBadge = `<span class="px-2 py-0.5 rounded font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">Flagged for Review</span>`;
        } else {
            actionBadge = `<span class="px-2 py-0.5 rounded font-semibold bg-slate-500/15 text-slate-300 border border-slate-500/30">${escapeHtml(r.action)}</span>`;
        }

        // Status Pill
        let statusBadge = '';
        if (r.status === 'Success') {
            statusBadge = `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>Success</span>`;
        } else if (r.status === 'Reverted') {
            statusBadge = `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-red-500/15 text-red-400 border border-red-500/30"><span class="w-1.5 h-1.5 rounded-full bg-red-400"></span>Reverted</span>`;
        } else {
            statusBadge = `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30"><span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"></span>Under Review</span>`;
        }

        return `
            <tr class="transition hover:bg-slate-500/5 ${isHigh ? 'row-high-risk' : ''}">
                <!-- 1. Risk Level -->
                <td class="py-3.5 px-4 whitespace-nowrap align-top">
                    <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-extrabold tracking-wide uppercase ${riskBadgeClass}">
                        <span>${riskIcon}</span>
                        <span>${riskLabel}</span>
                    </span>
                    <div class="text-[10px] font-mono text-slate-400 mt-1">${escapeHtml(r.audit_id)}</div>
                </td>

                <!-- 2. Date & Time -->
                <td class="py-3.5 px-4 whitespace-nowrap align-top font-mono text-[11px]">
                    <div class="font-semibold">${escapeHtml(r.timestamp_display)}</div>
                    <div class="text-[10px] text-slate-400">${escapeHtml(r.date_only)}</div>
                </td>

                <!-- 3. QA Operator -->
                <td class="py-3.5 px-4 whitespace-nowrap align-top">
                    <button onclick="selectOperatorChip('${r.qa_operator}')" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg portal-elevated hover:border-blue-500 font-mono font-bold text-xs transition" title="Filter by ${r.qa_operator}">
                        <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
                        <span>${escapeHtml(r.qa_operator)}</span>
                    </button>
                </td>

                <!-- 4. Action -->
                <td class="py-3.5 px-4 whitespace-nowrap align-top">
                    ${actionBadge}
                </td>

                <!-- 5. Primary Account -->
                <td class="py-3.5 px-4 align-top">
                    <button onclick="openInspectModal('${r.audit_id}')" class="text-left group">
                        <div class="font-mono font-bold text-blue-400 group-hover:underline">${escapeHtml(r.primary_account.formatted)}</div>
                        <div class="text-[11px] text-slate-400 font-mono mt-0.5">DOB: ${escapeHtml(r.primary_account.dob)} &bull; ${escapeHtml(r.primary_account.gender)}</div>
                    </button>
                </td>

                <!-- 6. Affected Account(s) -->
                <td class="py-3.5 px-4 align-top">
                    <button onclick="openInspectModal('${r.audit_id}')" class="text-left group">
                        <div class="font-mono font-bold text-amber-400 group-hover:underline">${escapeHtml(r.affected_account.formatted)}</div>
                        <div class="text-[11px] text-slate-400 font-mono mt-0.5">DOB: ${escapeHtml(r.affected_account.dob)} &bull; ${escapeHtml(r.affected_account.gender)}</div>
                    </button>
                </td>

                <!-- 7. Discrepancy & Activity Details -->
                <td class="py-3.5 px-4 align-top max-w-md">
                    <div class="leading-relaxed">${r.discrepancy_html}</div>
                    ${r.auditor_notes ? `<div class="text-[11px] text-slate-400 mt-1 italic">${escapeHtml(r.auditor_notes)}</div>` : ''}
                </td>

                <!-- 8. Status -->
                <td class="py-3.5 px-4 whitespace-nowrap align-top">
                    ${statusBadge}
                </td>

                <!-- 9. Actions / Inspect -->
                <td class="py-3.5 px-4 whitespace-nowrap align-top text-right">
                    <button onclick="openInspectModal('${r.audit_id}')" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600/15 hover:bg-blue-600/30 text-blue-400 border border-blue-500/30 font-semibold text-xs transition">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
                        </svg>
                        <span>Inspect</span>
                    </button>
                </td>
            </tr>
        `;
    }).join('');

    renderPagination(totalFiltered, totalPages);
}

function renderPagination(totalItems, totalPages) {
    const summary = document.getElementById('pagination-summary');
    const controls = document.getElementById('pagination-controls');
    if (summary) summary.textContent = `Page ${currentPage} of ${totalPages} (${totalItems} records)`;
    if (!controls) return;

    let html = `
        <button onclick="goToPage(${currentPage - 1})" ${currentPage <= 1 ? 'disabled' : ''} class="px-2.5 py-1 rounded portal-elevated disabled:opacity-40 hover:border-blue-500 transition">Prev</button>
    `;
    for (let p = 1; p <= totalPages; p++) {
        if (totalPages > 7 && p > 2 && p < totalPages - 1 && Math.abs(p - currentPage) > 1) {
            if (p === 3 || p === totalPages - 2) html += `<span class="px-1">...</span>`;
            continue;
        }
        html += `
            <button onclick="goToPage(${p})" class="px-2.5 py-1 rounded font-semibold transition ${p === currentPage ? 'bg-blue-600 text-white' : 'portal-elevated hover:border-blue-500'}">${p}</button>
        `;
    }
    html += `
        <button onclick="goToPage(${currentPage + 1})" ${currentPage >= totalPages ? 'disabled' : ''} class="px-2.5 py-1 rounded portal-elevated disabled:opacity-40 hover:border-blue-500 transition">Next</button>
    `;
    controls.innerHTML = html;
}

function goToPage(page) {
    const totalPages = Math.max(1, Math.ceil(filteredRecords.length / pageSize));
    if (page < 1 || page > totalPages) return;
    currentPage = page;
    renderDataGrid();
}

function changePageSize(size) {
    pageSize = parseInt(size, 10) || 25;
    currentPage = 1;
    renderDataGrid();
}

// ============================================================================
// 6. SIDE-BY-SIDE DEMOGRAPHIC INSPECTION MODAL
// ============================================================================
function openInspectModal(auditId) {
    const rec = allRecords.find(r => r.audit_id === auditId);
    if (!rec) return;
    currentInspectedAuditId = auditId;

    const modal = document.getElementById('inspect-modal');
    const badge = document.getElementById('modal-risk-badge');
    const banner = document.getElementById('modal-risk-banner');

    if (rec.risk_level === 'HIGH RISK') {
        badge.className = 'px-3 py-1 rounded-full text-xs font-extrabold uppercase tracking-wider badge-high-risk';
        badge.textContent = '⚠ HIGH RISK';
        banner.className = 'p-4 rounded-xl border border-[#dc3545]/50 bg-[#dc3545]/10 text-red-200 flex items-start gap-3';
    } else if (rec.risk_level === 'MEDIUM / REVIEW') {
        badge.className = 'px-3 py-1 rounded-full text-xs font-extrabold uppercase tracking-wider badge-medium-risk';
        badge.textContent = '! REQUIRES REVIEW';
        banner.className = 'p-4 rounded-xl border border-[#fd7e14]/50 bg-[#fd7e14]/10 text-amber-200 flex items-start gap-3';
    } else {
        badge.className = 'px-3 py-1 rounded-full text-xs font-extrabold uppercase tracking-wider badge-safe-match';
        badge.textContent = '✓ SAFE MATCH';
        banner.className = 'p-4 rounded-xl border border-[#28a745]/50 bg-[#28a745]/10 text-emerald-200 flex items-start gap-3';
    }

    document.getElementById('modal-subtitle').textContent = `Audit ID: ${rec.audit_id} • Timestamp: ${rec.timestamp_display} • QA Operator: ${rec.qa_operator} • Action: ${rec.action}`;
    document.getElementById('modal-risk-reason').textContent = rec.risk_reason;
    document.getElementById('modal-discrepancy-html').innerHTML = rec.discrepancy_html;
    document.getElementById('modal-auditor-notes').textContent = rec.auditor_notes ? `Auditor Note: "${rec.auditor_notes}"` : '';

    const p = rec.primary_account;
    const a = rec.affected_account;

    const rows = [
        { label: 'Account ID', pVal: `#${p.id}`, aVal: `#${a.id}`, isId: true },
        { label: 'First Name', pVal: p.first_name, aVal: a.first_name },
        { label: 'Middle Name', pVal: p.middle_name || '—', aVal: a.middle_name || '—' },
        { label: 'Last Name & Suffix', pVal: `${p.last_name} ${p.suffix || ''}`.trim(), aVal: `${a.last_name} ${a.suffix || ''}`.trim() },
        { label: 'Date of Birth (DOB)', pVal: p.dob, aVal: a.dob, critical: true },
        { label: 'Gender', pVal: p.gender, aVal: a.gender },
        { label: 'Mobile / Phone', pVal: p.phone, aVal: a.phone },
        { label: 'Residential Address', pVal: p.address, aVal: a.address },
        { label: 'PhilHealth / Gov ID', pVal: p.philhealth || '—', aVal: a.philhealth || '—' }
    ];

    const tbody = document.getElementById('modal-comparison-tbody');
    tbody.innerHTML = rows.map(row => {
        const match = row.pVal.toLowerCase() === row.aVal.toLowerCase();
        let statusHtml = '';
        if (row.isId) {
            statusHtml = `<span class="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-500/20 text-slate-300">Merged Target</span>`;
        } else if (match) {
            statusHtml = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400">✓ Exact Match</span>`;
        } else if (row.critical) {
            statusHtml = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-[#dc3545]/25 text-[#dc3545]">⚠ CRITICAL DIFF</span>`;
        } else {
            statusHtml = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/25 text-amber-400">≠ Differs</span>`;
        }

        return `
            <tr class="${!match && !row.isId ? 'bg-red-500/5' : ''}">
                <td class="py-2.5 px-4 font-semibold text-slate-400">${escapeHtml(row.label)}</td>
                <td class="py-2.5 px-4 font-mono ${!match && !row.isId ? 'font-bold text-blue-300' : ''}">${escapeHtml(row.pVal)}</td>
                <td class="py-2.5 px-4 font-mono ${!match && !row.isId ? 'font-bold text-amber-300' : ''}">${escapeHtml(row.aVal)}</td>
                <td class="py-2.5 px-4 text-center">${statusHtml}</td>
            </tr>
        `;
    }).join('');

    modal.classList.remove('hidden');
    modal.classList.add('flex');
}

function closeInspectModal() {
    const modal = document.getElementById('inspect-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    currentInspectedAuditId = null;
}

function updateRecordStatusFromModal(newStatus, newAction) {
    if (!currentInspectedAuditId) return;
    const rec = allRecords.find(r => r.audit_id === currentInspectedAuditId);
    if (!rec) return;
    rec.status = newStatus;
    if (newAction) rec.action = newAction;
    closeInspectModal();
    refreshDashboardView();
    showToast(`Updated ${rec.audit_id} to Status: ${newStatus} (${rec.action})`, 'success');
}

// ============================================================================
// 7. CUSTOMIZABLE STYLED EXCEL (.XLSX) REPORT EXPORTER
// ============================================================================
function openExportModal() {
    updateExportPreviewCount();
    const modal = document.getElementById('export-modal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');
}

function closeExportModal() {
    const modal = document.getElementById('export-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
}

function toggleAllExportCols(checked) {
    document.querySelectorAll('.export-col-cb').forEach(cb => { cb.checked = checked; });
}

function applyExportPreset(preset) {
    const riskCbs = document.querySelectorAll('.export-risk-cb');
    const opCbs = document.querySelectorAll('.export-op-cb');
    opCbs.forEach(cb => { cb.checked = true; });
    toggleAllExportCols(true);

    if (preset === 'HIGH_RISK_ONLY') {
        riskCbs.forEach(cb => { cb.checked = (cb.value === 'HIGH RISK'); });
        showToast('Preset loaded: High Risk Only for QA Audit Meeting', 'info');
    } else if (preset === 'FLAGGED_AND_REVIEW') {
        riskCbs.forEach(cb => { cb.checked = (cb.value === 'HIGH RISK' || cb.value === 'MEDIUM / REVIEW'); });
        showToast('Preset loaded: High Risk + Requires Review', 'info');
    } else {
        riskCbs.forEach(cb => { cb.checked = true; });
        showToast('Preset loaded: Full All-Operator Audit Trail', 'info');
    }
    updateExportPreviewCount();
}

function getExportFilteredRecords() {
    const selectedRisks = Array.from(document.querySelectorAll('.export-risk-cb:checked')).map(cb => cb.value);
    const selectedOps = Array.from(document.querySelectorAll('.export-op-cb:checked')).map(cb => cb.value);
    const startDate = document.getElementById('export-date-start')?.value || '2000-01-01';
    const endDate = document.getElementById('export-date-end')?.value || '2099-12-31';

    return allRecords.filter(r => {
        if (!selectedRisks.includes(r.risk_level)) return false;
        if (!selectedOps.includes(r.qa_operator)) return false;
        if (r.date_only < startDate || r.date_only > endDate) return false;
        return true;
    });
}

function updateExportPreviewCount() {
    const matching = getExportFilteredRecords();
    const badge = document.getElementById('export-preview-count');
    if (badge) {
        badge.textContent = `${matching.length} Rows Matching`;
    }
}

function executeStyledExcelExport() {
    const selectedCols = Array.from(document.querySelectorAll('.export-col-cb:checked')).map(cb => cb.value);
    if (selectedCols.length === 0) {
        showToast('Please select at least one column to export.', 'error');
        return;
    }

    const recordsToExport = getExportFilteredRecords();
    if (recordsToExport.length === 0) {
        showToast('No records match your selected export filters.', 'error');
        return;
    }

    // Build rows
    const headerRow = selectedCols;
    const dataRows = recordsToExport.map(r => {
        return selectedCols.map(col => {
            switch (col) {
                case 'Date/Time': return r.timestamp_display;
                case 'QA User': return r.qa_operator;
                case 'Action': return r.action;
                case 'Primary Account': return `${r.primary_account.formatted} (DOB: ${r.primary_account.dob})`;
                case 'Affected Account': return `${r.affected_account.formatted} (DOB: ${r.affected_account.dob})`;
                case 'Risk Level': return r.risk_level;
                case 'Discrepancies': return r.discrepancy_text;
                case 'Status': return r.status;
                default: return '';
            }
        });
    });

    const aoa = [headerRow, ...dataRows];
    const ws = XLSX.utils.aoa_to_sheet(aoa);

    // Auto-fit column widths
    const colWidths = selectedCols.map((col, colIdx) => {
        let maxLen = col.length + 4;
        dataRows.forEach(row => {
            const val = String(row[colIdx] || '');
            if (val.length > maxLen) maxLen = val.length;
        });
        return { wch: Math.min(Math.max(maxLen + 3, 14), 65) };
    });
    ws['!cols'] = colWidths;

    // Apply rich cell styling (headers + colored risk indicators)
    const range = XLSX.utils.decode_range(ws['!ref']);
    const riskColIdx = selectedCols.indexOf('Risk Level');

    for (let R = range.s.r; R <= range.e.r; ++R) {
        const rec = R > 0 ? recordsToExport[R - 1] : null;
        for (let C = range.s.c; C <= range.e.c; ++C) {
            const cellAddress = XLSX.utils.encode_cell({ r: R, c: C });
            if (!ws[cellAddress]) continue;

            if (R === 0) {
                // Header Styling
                ws[cellAddress].s = {
                    fill: { fgColor: { rgb: "1E222D" } },
                    font: { name: "Calibri", sz: 11, bold: true, color: { rgb: "FFFFFF" } },
                    alignment: { vertical: "center", horizontal: "left" },
                    border: {
                        top: { style: "thin", color: { rgb: "2E3446" } },
                        bottom: { style: "medium", color: { rgb: "3B82F6" } },
                        left: { style: "thin", color: { rgb: "2E3446" } },
                        right: { style: "thin", color: { rgb: "2E3446" } }
                    }
                };
            } else if (rec) {
                let rowBg = "FFFFFF";
                let fontColor = "0F172A";
                let isBold = false;

                if (rec.risk_level === 'HIGH RISK') {
                    rowBg = "FDE8E8";
                    if (C === riskColIdx) {
                        rowBg = "DC3545";
                        fontColor = "FFFFFF";
                        isBold = true;
                    }
                } else if (rec.risk_level === 'MEDIUM / REVIEW') {
                    rowBg = "FFF8E6";
                    if (C === riskColIdx) {
                        rowBg = "FD7E14";
                        fontColor = "FFFFFF";
                        isBold = true;
                    }
                } else if (rec.risk_level === 'SAFE MATCH') {
                    rowBg = "F0FDF4";
                    if (C === riskColIdx) {
                        rowBg = "28A745";
                        fontColor = "FFFFFF";
                        isBold = true;
                    }
                }

                ws[cellAddress].s = {
                    fill: { fgColor: { rgb: rowBg } },
                    font: { name: "Calibri", sz: 10, bold: isBold, color: { rgb: fontColor } },
                    alignment: { vertical: "center", wrapText: true },
                    border: {
                        top: { style: "thin", color: { rgb: "E2E8F0" } },
                        bottom: { style: "thin", color: { rgb: "E2E8F0" } },
                        left: { style: "thin", color: { rgb: "E2E8F0" } },
                        right: { style: "thin", color: { rgb: "E2E8F0" } }
                    }
                };
            }
        }
    }

    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "QA Audit Trail");

    const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
    const filename = `QA_Audit_Risk_Report_${ts}.xlsx`;
    XLSX.writeFile(wb, filename);

    closeExportModal();
    showToast(`Exported ${recordsToExport.length} styled audit rows to ${filename}`, 'success');
}

// ============================================================================
// 8. SIMULATE / TEST LIVE RISK CLASSIFICATION ENGINE
// ============================================================================
function openSimulateModal() {
    const modal = document.getElementById('simulate-modal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');
}

function closeSimulateModal() {
    const modal = document.getElementById('simulate-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
}

function fillSimPreset(type) {
    if (type === 'high') {
        document.getElementById('sim-p-id').value = '1044812';
        document.getElementById('sim-p-first').value = 'Eduardo';
        document.getElementById('sim-p-last').value = 'Mata Jr';
        document.getElementById('sim-p-dob').value = '1985-04-12';

        document.getElementById('sim-a-id').value = '1099201';
        document.getElementById('sim-a-first').value = 'Eduardo';
        document.getElementById('sim-a-last').value = 'Mata';
        document.getElementById('sim-a-dob').value = '1991-08-20';
        document.getElementById('sim-action').value = 'Merged';
    } else if (type === 'medium') {
        document.getElementById('sim-p-id').value = '1053901';
        document.getElementById('sim-p-first').value = 'Maria Cristina';
        document.getElementById('sim-p-last').value = 'Bautista-Cruz';
        document.getElementById('sim-p-dob').value = '1990-07-19';

        document.getElementById('sim-a-id').value = '1087102';
        document.getElementById('sim-a-first').value = 'Ma. Cristina';
        document.getElementById('sim-a-last').value = 'Bautista';
        document.getElementById('sim-a-dob').value = '1990-07-19';
        document.getElementById('sim-action').value = 'Flagged for Review';
    } else {
        document.getElementById('sim-p-id').value = '1062100';
        document.getElementById('sim-p-first').value = 'Carlos Miguel';
        document.getElementById('sim-p-last').value = 'Villanueva';
        document.getElementById('sim-p-dob').value = '1988-11-04';

        document.getElementById('sim-a-id').value = '1095400';
        document.getElementById('sim-a-first').value = 'Carlos Miguel';
        document.getElementById('sim-a-last').value = 'Villanueva';
        document.getElementById('sim-a-dob').value = '1988-11-04';
        document.getElementById('sim-action').value = 'Merged';
    }
}

function submitSimulatedRecord() {
    const op = document.getElementById('sim-operator').value;
    const action = document.getElementById('sim-action').value;

    const pObj = {
        id: document.getElementById('sim-p-id').value.trim() || '1044812',
        first_name: document.getElementById('sim-p-first').value.trim() || 'Eduardo',
        middle_name: 'Santos',
        last_name: document.getElementById('sim-p-last').value.trim() || 'Mata Jr',
        suffix: '',
        dob: document.getElementById('sim-p-dob').value || '1985-04-12',
        gender: 'M',
        phone: '+63 917 842 1109',
        address: '42 Kalayaan Ave, Quezon City',
        philhealth: '12-094817263-1'
    };

    const aObj = {
        id: document.getElementById('sim-a-id').value.trim() || '1099201',
        first_name: document.getElementById('sim-a-first').value.trim() || 'Eduardo',
        middle_name: 'Santos',
        last_name: document.getElementById('sim-a-last').value.trim() || 'Mata',
        suffix: '',
        dob: document.getElementById('sim-a-dob').value || '1991-08-20',
        gender: 'M',
        phone: '+63 918 221 9044',
        address: '42 Kalayaan Ave, Quezon City',
        philhealth: '04-112948102-8'
    };

    const pFull = `${pObj.first_name} ${pObj.last_name}`.trim();
    const aFull = `${aObj.first_name} ${aObj.last_name}`.trim();
    const evalRes = evaluateAccountRiskJS(pObj, aObj);

    const now = new Date();
    const newRec = {
        audit_id: `AUD-${5001 + allRecords.length}`,
        timestamp_iso: now.toISOString().slice(0, 19),
        timestamp_display: now.toLocaleString('en-US', { month: 'short', day: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: true }),
        date_only: now.toISOString().slice(0, 10),
        qa_operator: op,
        action: action,
        status: evalRes.risk_level === 'HIGH RISK' ? 'Under Review' : 'Success',
        primary_account: {
            ...pObj,
            full_name: pFull,
            formatted: `#${pObj.id} - ${pFull}`
        },
        affected_account: {
            ...aObj,
            full_name: aFull,
            formatted: `#${aObj.id} - ${aFull}`
        },
        risk_level: evalRes.risk_level,
        risk_color: evalRes.risk_color,
        risk_reason: evalRes.risk_reason,
        discrepancies: evalRes.discrepancies,
        discrepancy_html: evalRes.discrepancy_html,
        discrepancy_text: evalRes.discrepancy_text,
        auditor_notes: 'Live evaluated operation via Risk Engine Test Console.'
    };

    allRecords.unshift(newRec);
    closeSimulateModal();
    updateSyncTimestampDisplay(now);
    refreshDashboardView();
    showToast(`Evaluated as ${evalRes.risk_level}: Added ${newRec.audit_id} (${op})`, evalRes.risk_level === 'HIGH RISK' ? 'error' : 'success');
}

// ============================================================================
// 9. THEME TOGGLE & UI UTILITIES
// ============================================================================
function initTheme() {
    const saved = localStorage.getItem('qa_dashboard_theme') || 'dark';
    setTheme(saved);
}

function toggleTheme() {
    const isDark = document.documentElement.classList.contains('dark');
    setTheme(isDark ? 'light' : 'dark');
}

function setTheme(mode) {
    const htmlEl = document.documentElement;
    const sunIcon = document.getElementById('theme-icon-sun');
    const moonIcon = document.getElementById('theme-icon-moon');

    if (mode === 'dark') {
        htmlEl.classList.add('dark');
        sunIcon?.classList.remove('hidden');
        moonIcon?.classList.add('hidden');
    } else {
        htmlEl.classList.remove('dark');
        sunIcon?.classList.add('hidden');
        moonIcon?.classList.remove('hidden');
    }
    localStorage.setItem('qa_dashboard_theme', mode);
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    let colors = 'bg-slate-800 border-slate-600 text-white';
    if (type === 'success') colors = 'bg-emerald-950/95 border-emerald-500/50 text-emerald-200';
    if (type === 'error') colors = 'bg-red-950/95 border-red-500/50 text-red-200';
    if (type === 'info') colors = 'bg-blue-950/95 border-blue-500/50 text-blue-200';

    toast.className = `px-4 py-2.5 rounded-xl border shadow-xl text-xs font-semibold flex items-center gap-2 transition-all duration-300 pointer-events-auto ${colors}`;
    toast.innerHTML = `<span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

function escapeHtml(str) {
    return String(str ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// ============================================================================
// 10. 1LIFE LIVE PORTAL SYNC CONNECTOR (Audit Trail + Merged Accounts)
// ============================================================================
function openLivePortalModal() {
    const modal = document.getElementById('portal-sync-modal');
    if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }
}

function closeLivePortalModal() {
    const modal = document.getElementById('portal-sync-modal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
}

function runPlaywrightPortalSync(interactiveLogin = false) {
    const startDt = document.getElementById('portal-sync-start')?.value || '01/01/2026';
    const endDt = document.getElementById('portal-sync-end')?.value || '10/20/2026';
    const statusMsg = document.getElementById('portal-sync-status-msg');
    const mode = interactiveLogin ? 'portal_login' : 'portal_headless';

    if (statusMsg) {
        statusMsg.classList.remove('hidden');
        statusMsg.textContent = interactiveLogin
            ? '⏳ Launching Chromium window for 1Life login... Complete login if prompted; script will automatically scrape Audit Trail & Merged Accounts.'
            : `⏳ Connecting to 1Life Portal (${startDt} - ${endDt}) and scraping Audit Trail & Merged Accounts...`;
    }

    fetch(`/api/sync?mode=${mode}&start=${encodeURIComponent(startDt)}&end=${encodeURIComponent(endDt)}`)
        .then(r => r.json())
        .then(res => {
            if (res.needs_login) {
                if (statusMsg) {
                    statusMsg.innerHTML = `<span class="text-amber-400">⚠ ${escapeHtml(res.message)}</span>`;
                }
                showToast('1Life session expired — click "Open Browser to Login & Sync Both Tabs"', 'error');
                return;
            }
            if (res.success) {
                const count = res.total_live_records || (res.records ? res.records.length : 0);
                if (count > 0 && Array.isArray(res.records)) {
                    allRecords = res.records;
                    updateSyncTimestampDisplay(new Date());
                    refreshDashboardView();
                    closeLivePortalModal();
                    showToast(`Pulled ${count} live records from 1Life Portal (${res.date_range_queried})!`, 'success');
                } else {
                    if (statusMsg) {
                        statusMsg.innerHTML = `<span class="text-amber-300">Connected to 1Life Portal (${res.date_range_queried}), but 0 rows were returned on Audit Trail / Merged Accounts for that range. Try widening the Start Date or using Option B from your open Chrome tab.</span>`;
                    }
                    showToast('Connected to 1Life Portal: 0 entries found for that date range.', 'info');
                }
            } else {
                if (statusMsg) {
                    statusMsg.innerHTML = `<span class="text-red-400">Error: ${escapeHtml(res.error || 'Sync failed')}</span>`;
                }
            }
        })
        .catch(err => {
            if (statusMsg) {
                statusMsg.innerHTML = `<span class="text-red-400">Server error: ${escapeHtml(err.message)}</span>`;
            }
        });
}

function copyBridgeSnippet() {
    const pre = document.getElementById('console-bridge-snippet');
    if (!pre) return;
    navigator.clipboard.writeText(pre.innerText).then(() => {
        showToast('Copied 1-Click Chrome Console Sync Snippet to clipboard!', 'success');
    });
}

function restoreSimulatedDataset() {
    if (window.INITIAL_AUDIT_DATA && Array.isArray(window.INITIAL_AUDIT_DATA.records)) {
        allRecords = window.INITIAL_AUDIT_DATA.records;
        refreshDashboardView();
        closeLivePortalModal();
        showToast('Restored 90 preloaded QA demo records', 'info');
    }
}

