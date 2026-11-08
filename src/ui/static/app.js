/**
 * Shot & Keyframe Debug Inspector Client Application.
 * Handles interactive video playback, timeline synchronization, and shot/keyframe inspection.
 */

let state = {
    currentVideoId: null,
    videoMetadata: null,
    shots: [],
    activeShotId: null,
    totalDuration: 0,
    isUserInteracting: false,
    searchResults: [],
    searchTrace: null,
    activeTraceCueIdx: 0,
    activeTab: "shots",
    activeCandidateRank: null,
    searchMode: "auto",
    feedbackPositives: new Set(),
    feedbackNegatives: new Set(),
    markInSec: 0.0,
    markOutSec: 5.0,
    isPlayingRange: false,
    kisElapsedSec: 0,
    kisTimerRunning: false,
    kisTimerInterval: null,
    kisWrongAttempts: 0,
    kisTaskLimitSec: 300,
};

// DOM Elements
const videoPlayer = document.getElementById("videoPlayer");
const videoSelect = document.getElementById("videoSelect");
const statDuration = document.getElementById("statDuration");
const statFps = document.getElementById("statFps");
const statShots = document.getElementById("statShots");
const statKeyframes = document.getElementById("statKeyframes");
const timeDisplay = document.getElementById("timeDisplay");
const currentShotBadge = document.getElementById("currentShotBadge");
const shotTimeline = document.getElementById("shotTimeline");
const timelineCursor = document.getElementById("timelineCursor");
const timelineRangeOverlay = document.getElementById("timelineRangeOverlay");
const timelineHoverTime = document.getElementById("timelineHoverTime");
const timelineTooltip = document.getElementById("timelineTooltip");
const shotList = document.getElementById("shotList");
const shotSearch = document.getElementById("shotSearch");
const shotFilter = document.getElementById("shotFilter");
const chkAutoScroll = document.getElementById("chkAutoScroll");
const btnPrevShot = document.getElementById("btnPrevShot");
const btnNextShot = document.getElementById("btnNextShot");
const btnJumpCenter = document.getElementById("btnJumpCenter");

// Task 06B Scrubber & KIS Console DOM Elements
const btnStepBack5s = document.getElementById("btnStepBack5s");
const btnStepBack1s = document.getElementById("btnStepBack1s");
const btnStepBackFrame = document.getElementById("btnStepBackFrame");
const btnTogglePlay = document.getElementById("btnTogglePlay");
const btnStepFwdFrame = document.getElementById("btnStepFwdFrame");
const btnStepFwd1s = document.getElementById("btnStepFwd1s");
const btnStepFwd5s = document.getElementById("btnStepFwd5s");

const kisTargetLabel = document.getElementById("kisTargetLabel");
const kisMarkInInput = document.getElementById("kisMarkInInput");
const kisMarkOutInput = document.getElementById("kisMarkOutInput");
const btnMarkIn = document.getElementById("btnMarkIn");
const btnMarkOut = document.getElementById("btnMarkOut");
const btnPresetShot = document.getElementById("btnPresetShot");
const btnPresetTight = document.getElementById("btnPresetTight");
const btnPresetWindow = document.getElementById("btnPresetWindow");
const btnPlayRange = document.getElementById("btnPlayRange");
const btnQuickSubmitPlayhead = document.getElementById("btnQuickSubmitPlayhead");
const btnSubmitRange = document.getElementById("btnSubmitRange");
const kisSubmitToast = document.getElementById("kisSubmitToast");

const btnToggleFilmstrip = document.getElementById("btnToggleFilmstrip");
const playerFilmstripDrawer = document.getElementById("playerFilmstripDrawer");
const playerFilmstripList = document.getElementById("playerFilmstripList");
const btnRefreshFilmstrip = document.getElementById("btnRefreshFilmstrip");

const btnToggleDresConfig = document.getElementById("btnToggleDresConfig");
const kisDresConfigDrawer = document.getElementById("kisDresConfigDrawer");
const chkDresDryRun = document.getElementById("chkDresDryRun");
const inputDresUrl = document.getElementById("inputDresUrl");
const inputDresEvalId = document.getElementById("inputDresEvalId");
const inputDresSession = document.getElementById("inputDresSession");
const btnSaveDresConfig = document.getElementById("btnSaveDresConfig");
const btnClearDresCache = document.getElementById("btnClearDresCache");
const dresHistoryList = document.getElementById("dresHistoryList");

const kisTaskTypeSelect = document.getElementById("kisTaskTypeSelect");
const kisTimerDisplay = document.getElementById("kisTimerDisplay");
const btnTimerToggle = document.getElementById("btnTimerToggle");
const btnTimerReset = document.getElementById("btnTimerReset");
const kisWrongCount = document.getElementById("kisWrongCount");
const btnAddWrong = document.getElementById("btnAddWrong");
const btnSubWrong = document.getElementById("btnSubWrong");
const kisEstScoreBadge = document.getElementById("kisEstScoreBadge");

// Search & Multimodal DOM Elements
const searchForm = document.getElementById("searchForm");
const queryInput = document.getElementById("queryInput");
const btnClearQuery = document.getElementById("btnClearQuery");
const btnSearch = document.getElementById("btnSearch");
const btnModeMultimodal = document.getElementById("btnModeMultimodal");
const btnModeVisual = document.getElementById("btnModeVisual");
const btnModeOcr = document.getElementById("btnModeOcr");
const btnAddVisualCue = document.getElementById("btnAddVisualCue");
const btnAddNegVisualCue = document.getElementById("btnAddNegVisualCue");
const btnAddOcrCue = document.getElementById("btnAddOcrCue");
const btnAddSeqStage = document.getElementById("btnAddSeqStage");
const btnClearPills = document.getElementById("btnClearPills");
const pipelineTracePanel = document.getElementById("pipelineTracePanel");
const traceSummaryText = document.getElementById("traceSummaryText");
const btnToggleTrace = document.getElementById("btnToggleTrace");
const traceContent = document.getElementById("traceContent");
const traceStageSummary = document.getElementById("traceStageSummary");
const traceCuesNav = document.getElementById("traceCuesNav");
const traceCueBody = document.getElementById("traceCueBody");

const tabShots = document.getElementById("tabShots");
const tabResults = document.getElementById("tabResults");
const tabCheckpoints = document.getElementById("tabCheckpoints");
const tabShotCount = document.getElementById("tabShotCount");
const tabResultCount = document.getElementById("tabResultCount");
const shotControls = document.getElementById("shotControls");
const candidateList = document.getElementById("candidateList");
const checkpointPane = document.getElementById("checkpointPane");
const btnRefreshDb = document.getElementById("btnRefreshDb");

/**
 * Formats seconds into MM:SS.ss string.
 */
function formatTime(seconds) {
    if (isNaN(seconds) || seconds < 0) return "00:00.00";
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    const minStr = String(mins).padStart(2, "0");
    const secStr = secs.toFixed(2).padStart(5, "0");
    return `${minStr}:${secStr}`;
}

/**
 * Initializes app on page load.
 */
async function init() {
    setupEventListeners();
    await fetchVideos();
}

/**
 * Fetches list of processed videos and fills dropdown.
 */
async function fetchVideos() {
    try {
        const res = await fetch("/api/videos");
        if (!res.ok) throw new Error("Failed to fetch videos.");
        const videos = await res.json();

        videoSelect.innerHTML = "";
        if (videos.length === 0) {
            videoSelect.innerHTML = '<option value="" disabled>No videos found</option>';
            return;
        }

        videos.forEach(v => {
            const opt = document.createElement("option");
            opt.value = v.video_id;
            opt.textContent = `${v.video_id} (${v.shot_count} shots, ${v.keyframe_count} frames)`;
            videoSelect.appendChild(opt);
        });

        // Default to first video
        loadVideo(videos[0].video_id);
    } catch (err) {
        console.error("Error loading videos:", err);
        shotList.innerHTML = `<div class="loading-state">Error loading video catalog: ${err.message}</div>`;
    }
}

/**
 * Loads and renders details for a given video ID.
 */
async function loadVideo(videoId) {
    if (!videoId) return;
    state.currentVideoId = videoId;
    shotList.innerHTML = '<div class="loading-state">Loading shots and keyframes...</div>';

    try {
        const res = await fetch(`/api/videos/${videoId}`);
        if (!res.ok) throw new Error("Failed to fetch video details.");
        const data = await res.json();

        state.videoMetadata = data.video;
        state.shots = data.shots;
        state.totalDuration = data.video.duration_sec;

        // Update Header Stats
        statDuration.textContent = formatTime(state.totalDuration);
        statFps.textContent = data.video.fps.toFixed(1);
        statShots.textContent = data.total_shots;
        statKeyframes.textContent = data.total_keyframes;
        if (tabShotCount) tabShotCount.textContent = data.total_shots;

        // Update Video Player Source
        videoPlayer.src = `/api/stream/${videoId}`;
        videoPlayer.load();

        // Render UI
        renderTimeline();
        renderShotCards();

        // Initialize default KIS range to first shot or [0.0, 5.0]
        if (state.shots && state.shots.length > 0) {
            setKisRange(state.shots[0].start_sec, state.shots[0].end_sec);
        } else {
            setKisRange(0.0, Math.min(5.0, state.totalDuration || 5.0));
        }

    } catch (err) {
        console.error("Error loading video details:", err);
        shotList.innerHTML = `<div class="loading-state">Error loading details: ${err.message}</div>`;
    }
}

/**
 * Renders the proportional shot segments on the timeline.
 */
function renderTimeline() {
    // Preserve range overlay and cursor elements
    shotTimeline.innerHTML = "";
    if (timelineRangeOverlay) shotTimeline.appendChild(timelineRangeOverlay);
    shotTimeline.appendChild(timelineCursor);

    if (state.totalDuration <= 0 || state.shots.length === 0) return;

    state.shots.forEach((shot, idx) => {
        const segment = document.createElement("div");
        segment.className = "timeline-segment";
        segment.dataset.shotId = shot.shot_id;

        // Width percentage
        const widthPct = (shot.duration_sec / state.totalDuration) * 100;
        segment.style.width = `${Math.max(widthPct, 0.15)}%`;

        // Classification color class
        if (shot.duration_sec < 3.0) {
            segment.classList.add("short");
        } else if (shot.duration_sec <= 8.0) {
            segment.classList.add("med");
        } else {
            segment.classList.add("long");
        }

        // Click to seek and set shot bounds
        segment.addEventListener("click", () => {
            seekVideoTo(shot.start_sec);
            setKisRange(shot.start_sec, shot.end_sec);
        });

        // Hover Tooltip
        segment.addEventListener("mouseenter", (e) => {
            showTimelineTooltip(e, shot);
        });
        segment.addEventListener("mouseleave", () => {
            hideTimelineTooltip();
        });

        shotTimeline.appendChild(segment);
    });

    renderTimelineRangeOverlay();
}

/**
 * Displays tooltip when hovering a timeline segment.
 */
function showTimelineTooltip(event, shot) {
    timelineTooltip.innerHTML = `
        <strong>Shot #${shot.shot_id}</strong>: ${formatTime(shot.start_sec)} &rarr; ${formatTime(shot.end_sec)}<br>
        Duration: <strong>${shot.duration_sec.toFixed(2)}s</strong> | <strong>${shot.keyframes.length} Keyframe(s)</strong>
    `;
    timelineTooltip.style.opacity = "1";
    positionTooltip(event);
}

function positionTooltip(event) {
    timelineTooltip.style.left = `${event.clientX + 12}px`;
    timelineTooltip.style.top = `${event.clientY - 45}px`;
}

function hideTimelineTooltip() {
    timelineTooltip.style.opacity = "0";
}

/**
 * Renders all shot cards and keyframe thumbnails.
 */
function renderShotCards() {
    shotList.innerHTML = "";

    const query = shotSearch.value.trim().toLowerCase();
    const filterType = shotFilter.value;

    const filteredShots = state.shots.filter(shot => {
        // Search filter
        if (query && !String(shot.shot_id).includes(query)) {
            return false;
        }
        // Duration/category filter
        if (filterType === "short" && shot.duration_sec >= 3.0) return false;
        if (filterType === "medium" && (shot.duration_sec < 3.0 || shot.duration_sec > 8.0)) return false;
        if (filterType === "long" && shot.duration_sec <= 8.0) return false;
        if (filterType === "multi-kf" && shot.keyframes.length <= 1) return false;

        return true;
    });

    if (filteredShots.length === 0) {
        shotList.innerHTML = '<div class="loading-state">No matching shots found.</div>';
        return;
    }

    filteredShots.forEach(shot => {
        const card = document.createElement("div");
        card.className = "shot-card";
        card.id = `shot-card-${shot.shot_id}`;
        card.dataset.shotId = shot.shot_id;

        // Card Header
        const header = document.createElement("div");
        header.className = "shot-card-header";
        header.innerHTML = `
            <div class="shot-id-tag">
                <span class="shot-badge">SHOT #${String(shot.shot_id).padStart(3, "0")}</span>
                <span class="shot-time">${formatTime(shot.start_sec)} &rarr; ${formatTime(shot.end_sec)}</span>
            </div>
            <div class="shot-duration">${shot.duration_sec.toFixed(2)}s (${shot.keyframes.length} frames)</div>
        `;

        header.addEventListener("click", () => {
            seekVideoTo(shot.start_sec);
        });

        card.appendChild(header);

        // Keyframes Grid
        if (shot.keyframes.length > 0) {
            const grid = document.createElement("div");
            grid.className = "keyframes-grid";

            shot.keyframes.forEach(kf => {
                const kfItem = document.createElement("div");
                kfItem.className = "keyframe-item";
                kfItem.title = `Jump to t=${kf.timestamp_sec}s (Blur: ${kf.blur_score})`;

                const typeClass = kf.is_shot_center ? "center" : "dynamic";
                const typeLabel = kf.is_shot_center ? "CENTER" : "DYNAMIC";

                let ocrHtml = "";
                if (kf.ocr_texts && kf.ocr_texts.length > 0) {
                    const textSample = kf.ocr_texts.slice(0, 3).join(" • ");
                    ocrHtml = `<div class="kf-ocr-snippets" title="${kf.ocr_texts.join(' | ')}"><span class="ocr-tag">[OCR]</span>${textSample}</div>`;
                }

                kfItem.innerHTML = `
                    <div class="kf-thumb-wrap">
                        <img src="${kf.image_url}" alt="Keyframe at ${kf.timestamp_sec}s" loading="lazy">
                        <span class="kf-type-tag ${typeClass}">${typeLabel}</span>
                    </div>
                    <div class="kf-details">
                        <span class="kf-time">t=${kf.timestamp_sec.toFixed(2)}s</span>
                        <span class="kf-blur">Blur: ${kf.blur_score}</span>
                        ${ocrHtml}
                    </div>
                `;

                kfItem.addEventListener("click", (e) => {
                    e.stopPropagation();
                    seekVideoTo(kf.timestamp_sec);
                });

                grid.appendChild(kfItem);
            });

            card.appendChild(grid);
        }

        shotList.appendChild(card);
    });
}

/**
 * Seeks the video player to a timestamp.
 */
function seekVideoTo(seconds) {
    if (isNaN(seconds)) return;
    videoPlayer.currentTime = seconds;
    videoPlayer.play();
}

/**
 * Syncs video time with timeline and shot list.
 */
function onVideoTimeUpdate() {
    const curTime = videoPlayer.currentTime;
    const dur = state.totalDuration || videoPlayer.duration || 1;

    // Auto-pause if playing selected KIS range and reached Mark Out
    if (state.isPlayingRange && curTime >= state.markOutSec) {
        videoPlayer.pause();
        videoPlayer.currentTime = state.markOutSec;
        state.isPlayingRange = false;
        if (btnPlayRange) btnPlayRange.textContent = "[Play Range]";
    }

    // 1. Update text display
    timeDisplay.textContent = `${formatTime(curTime)} / ${formatTime(dur)}`;

    // 2. Move timeline cursor
    const curPct = Math.min((curTime / dur) * 100, 100);
    timelineCursor.style.left = `${curPct}%`;

    // 3. Find active shot
    const activeShot = state.shots.find(s => s.start_sec <= curTime && curTime <= s.end_sec);

    if (activeShot && activeShot.shot_id !== state.activeShotId) {
        setActiveShot(activeShot.shot_id);
    }
}

/**
 * Sets active shot highlight across timeline and card list.
 */
function setActiveShot(shotId) {
    state.activeShotId = shotId;
    currentShotBadge.textContent = `Current: Shot #${String(shotId).padStart(3, "0")}`;

    // Update timeline segment active state
    document.querySelectorAll(".timeline-segment").forEach(seg => {
        if (seg.dataset.shotId === String(shotId)) {
            seg.classList.add("active");
        } else {
            seg.classList.remove("active");
        }
    });

    // Update shot cards active state
    document.querySelectorAll(".shot-card").forEach(card => {
        if (card.dataset.shotId === String(shotId)) {
            card.classList.add("active");
            if (chkAutoScroll.checked && !state.isUserInteracting) {
                scrollCardIntoContainer(card);
            }
        } else {
            card.classList.remove("active");
        }
    });
}

/**
 * Scrolls a card into view strictly inside shotList container without moving outer window.
 */
function scrollCardIntoContainer(card) {
    if (!card || !shotList) return;

    const containerTop = shotList.scrollTop;
    const containerHeight = shotList.clientHeight;
    const cardTop = card.offsetTop - shotList.offsetTop;
    const cardBottom = cardTop + card.offsetHeight;

    if (cardTop < containerTop) {
        shotList.scrollTo({
            top: Math.max(0, cardTop - 12),
            behavior: "smooth"
        });
    } else if (cardBottom > containerTop + containerHeight) {
        shotList.scrollTo({
            top: cardBottom - containerHeight + 12,
            behavior: "smooth"
        });
    }
}

/**
 * Quick navigation: Jump to previous shot.
 */
function jumpPrevShot() {
    if (state.shots.length === 0) return;
    const curTime = videoPlayer.currentTime;
    const currentIdx = state.shots.findIndex(s => s.start_sec <= curTime && curTime <= s.end_sec);
    if (currentIdx > 0) {
        seekVideoTo(state.shots[currentIdx - 1].start_sec);
    } else {
        seekVideoTo(state.shots[0].start_sec);
    }
}

/**
 * Quick navigation: Jump to next shot.
 */
function jumpNextShot() {
    if (state.shots.length === 0) return;
    const curTime = videoPlayer.currentTime;
    const currentIdx = state.shots.findIndex(s => s.start_sec <= curTime && curTime <= s.end_sec);
    if (currentIdx >= 0 && currentIdx < state.shots.length - 1) {
        seekVideoTo(state.shots[currentIdx + 1].start_sec);
    }
}

/**
 * Quick navigation: Jump to the center keyframe of current shot.
 */
function jumpCurrentCenter() {
    const curTime = videoPlayer.currentTime;
    const activeShot = state.shots.find(s => s.start_sec <= curTime && curTime <= s.end_sec);
    if (!activeShot || activeShot.keyframes.length === 0) return;

    // Look for center keyframe
    const centerKf = activeShot.keyframes.find(k => k.is_shot_center) || activeShot.keyframes[0];
    seekVideoTo(centerKf.timestamp_sec);
}

/**
 * Switches right pane view between 'shots', 'results', and 'checkpoints'.
 */
function switchTab(tabName) {
    state.activeTab = tabName;
    tabShots.classList.toggle("active", tabName === "shots");
    tabResults.classList.toggle("active", tabName === "results");
    if (tabCheckpoints) tabCheckpoints.classList.toggle("active", tabName === "checkpoints");

    shotControls.style.display = tabName === "shots" ? "flex" : "none";
    shotList.style.display = tabName === "shots" ? "flex" : "none";
    candidateList.style.display = tabName === "results" ? "flex" : "none";
    if (pipelineTracePanel) pipelineTracePanel.style.display = (tabName === "results" && state.searchTrace) ? "block" : "none";
    if (checkpointPane) checkpointPane.style.display = tabName === "checkpoints" ? "flex" : "none";

    if (tabName === "checkpoints") {
        loadCheckpoints();
    }
}

let allCheckpointsMatrix = [];

/**
 * Loads database statistics and pipeline checkpoints matrix from backend.
 */
async function loadCheckpoints() {
    try {
        const res = await fetch("/api/db/summary");
        if (!res.ok) throw new Error("Failed to load DB summary");
        const data = await res.json();

        const elVid = document.getElementById("dbTotalVideos");
        const elShots = document.getElementById("dbTotalShots");
        const elKfs = document.getElementById("dbTotalKeyframes");

        if (elVid) elVid.textContent = data.total_videos;
        if (elShots) elShots.textContent = data.total_shots;
        if (elKfs) elKfs.textContent = data.total_keyframes;

        allCheckpointsMatrix = data.matrix || [];
        renderCheckpointTable();
    } catch (err) {
        console.error("Error loading checkpoints:", err);
    }
}

/**
 * Renders filtered checkpoint rows into the table body.
 */
function renderCheckpointTable() {
    const tbody = document.getElementById("checkpointTableBody");
    if (!tbody) return;
    tbody.innerHTML = "";

    const searchTxt = (document.getElementById("cpSearchInput")?.value || "").trim().toLowerCase();
    const filterMode = document.getElementById("cpFilterSelect")?.value || "completed";

    let filtered = allCheckpointsMatrix.filter(row => {
        if (searchTxt && !row.video_id.toLowerCase().includes(searchTxt)) {
            return false;
        }
        const hasCompleted = Object.values(row.stages).some(st => st.status === "COMPLETED");
        if (filterMode === "completed" && !hasCompleted) return false;
        if (filterMode === "pending" && hasCompleted) return false;
        return true;
    });

    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-dim); padding: 24px;">No matching video checkpoints found.</td></tr>`;
        return;
    }

    const stages = ["shots", "keyframes", "visual", "ocr"];

    filtered.forEach(row => {
        const tr = document.createElement("tr");
        let tdHtml = `<td><strong>${row.video_id}</strong></td>`;

        stages.forEach(st => {
            const sObj = row.stages[st] || { status: "PENDING", count: 0 };
            const stLower = (sObj.status || "PENDING").toLowerCase();
            let countStr = sObj.count > 0 ? ` (${sObj.count})` : "";
            tdHtml += `<td><span class="cp-badge ${stLower}">${sObj.status}${countStr}</span></td>`;
        });

        tr.innerHTML = tdHtml;
        tbody.appendChild(tr);
    });
}

/**
 * Executes search via Unified Multimodal Fusion (/api/search/multimodal).
 */
async function executeSearch() {
    const query = queryInput.value.trim();
    if (!query) return;

    btnSearch.disabled = true;
    btnSearch.textContent = "Searching...";
    btnClearQuery.style.display = "block";
    switchTab("results");

    const mode = state.searchMode; // 'auto', 'visual', or 'ocr'
    let modeLabel = "Executing multimodal fusion across 726 videos...";
    if (mode === "visual") modeLabel = "Encoding visual query & searching SigLIP2 index...";
    if (mode === "ocr") modeLabel = "Searching on-screen text with SQLite FTS5...";

    candidateList.innerHTML = `
        <div class="loading-state">
            <div style="font-size: 16px; font-weight: 600; margin-bottom: 8px; color: var(--text-main);">
                ${modeLabel}
            </div>
            <div style="color: var(--accent); font-family: var(--font-mono); font-size: 13px;">
                "${query}"
            </div>
        </div>
    `;

    try {
        const scopeCurrent = document.getElementById("chkCurrentVideoOnly")?.checked;
        const vidParam = (scopeCurrent && state.currentVideoId) ? `&video_id=${encodeURIComponent(state.currentVideoId)}` : "";
        const endpoint = `/api/search/multimodal?query=${encodeURIComponent(query)}&mode=${encodeURIComponent(mode)}${vidParam}&top_k=25`;
        const res = await fetch(endpoint);
        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || "Search request failed");
        }

        const data = await res.json();
        state.searchResults = data.candidates || [];
        state.searchTrace = data.trace || null;
        state.activeTraceCueIdx = 0;
        tabResultCount.textContent = state.searchResults.length;

        renderPipelineTrace();
        renderCandidateCards();

    } catch (err) {
        console.error("Search error:", err);
        candidateList.innerHTML = `<div class="empty-candidate-state" style="color: var(--color-short);">Error during search: ${err.message}</div>`;
        if (pipelineTracePanel) pipelineTracePanel.style.display = "none";
    } finally {
        btnSearch.disabled = false;
        btnSearch.textContent = "Search";
    }
}

/**
 * Renders Explainable Pipeline Execution Trace.
 */
function renderPipelineTrace() {
    if (!pipelineTracePanel) return;

    if (!state.searchTrace) {
        pipelineTracePanel.style.display = "none";
        return;
    }

    const trace = state.searchTrace;
    pipelineTracePanel.style.display = "block";

    const cues = trace.cues || [];
    if (traceSummaryText) {
        traceSummaryText.textContent = `Decomposed ${cues.length} Cue(s) in ${trace.total_time_ms} ms | Found ${trace.consensus_moments_count} Consensus Moments`;
    }

    if (traceStageSummary) {
        let stagesHtml = `<div style="font-size: 11px; color: var(--text-dim); margin-bottom: 4px;"><strong>Stage Breakdown:</strong></div>`;
        (trace.parsed_stages || []).forEach(st => {
            const vStr = st.visual_queries.map(q => `<span class="candidate-type-badge visual" style="margin-right: 4px;">[Visual: "${q}"]</span>`).join(" ");
            const oStr = st.ocr_queries.map(q => `<span class="candidate-type-badge ocr" style="margin-right: 4px;">[OCR: "${q}"]</span>`).join(" ");
            stagesHtml += `<div style="margin-bottom: 2px;">Stage #${st.stage_index}: ${vStr || '<span style="color: var(--text-dim); font-size: 11px;">none</span>'} ${oStr ? '+ ' + oStr : ''}</div>`;
        });
        traceStageSummary.innerHTML = stagesHtml;
    }

    if (traceCuesNav) {
        traceCuesNav.innerHTML = "";
        cues.forEach((c, idx) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = `trace-cue-tab ${idx === state.activeTraceCueIdx ? "active" : ""}`;
            btn.innerHTML = `<strong>Cue #${idx + 1} [${c.modality.toUpperCase()}]:</strong> "${c.query_text.slice(0, 20)}" (${c.hits_count} hits, ${c.latency_ms}ms)`;
            btn.addEventListener("click", () => {
                state.activeTraceCueIdx = idx;
                renderPipelineTrace();
            });
            traceCuesNav.appendChild(btn);
        });
    }

    renderPipelineTraceCueBody();
}

/**
 * Renders Top Hits for the selected cue inside the trace panel.
 */
function renderPipelineTraceCueBody() {
    if (!traceCueBody || !state.searchTrace) return;

    const cues = state.searchTrace.cues || [];
    if (cues.length === 0) {
        traceCueBody.innerHTML = `<div style="color: var(--text-dim); font-size: 11px;">No individual cue breakdown available.</div>`;
        return;
    }

    const activeCue = cues[state.activeTraceCueIdx] || cues[0];
    const topHits = activeCue.top_hits || [];

    let hitsHtml = `
        <div style="font-size: 11px; color: var(--text-dim); margin-bottom: 4px;">
            Top independent hits retrieved exclusively for <strong>${activeCue.modality.toUpperCase()} Cue</strong>: <em>"${activeCue.query_text}"</em>:
        </div>
        <div class="trace-hits-grid">
    `;

    topHits.forEach(h => {
        const textTag = h.text_detected ? `<div class="trace-hit-text" title="${h.text_detected}">"${h.text_detected}"</div>` : "";
        hitsHtml += `
            <div class="trace-hit-card" onclick="seekToVideoMoment('${h.video_id}', ${h.timestamp_sec});">
                <img src="${h.thumbnail_url}" class="trace-hit-thumb" loading="lazy" alt="Hit #${h.rank}">
                <div class="trace-hit-header">
                    <span class="trace-hit-rank">#${h.rank}</span>
                    <span class="trace-hit-score">${Number(h.score).toFixed(4)}</span>
                </div>
                <div class="trace-hit-time"><strong>${h.video_id}</strong> @ ${Number(h.timestamp_sec).toFixed(1)}s</div>
                ${textTag}
            </div>
        `;
    });

    hitsHtml += `</div>`;
    traceCueBody.innerHTML = hitsHtml;
}

/**
 * Helper: Seeks video player to moment, switches video if needed, and updates KIS range.
 */
async function seekToVideoMoment(videoId, timestampSec, endSec = null) {
    if (videoId && videoId !== state.currentVideoId) {
        videoSelect.value = videoId;
        await loadVideo(videoId);
    }
    seekVideoTo(timestampSec);
    if (endSec !== null && endSec >= timestampSec) {
        setKisRange(timestampSec, endSec);
    } else {
        setKisRange(Math.max(0, timestampSec - 0.5), timestampSec + 0.5);
    }
}

/**
 * Helper: Toggles cue evidence accordion for a candidate card.
 */
function toggleEvidenceBox(rank) {
    const box = document.getElementById(`evidence-box-${rank}`);
    if (box) {
        const isHidden = box.style.display === "none";
        box.style.display = isHidden ? "grid" : "none";
    }
}

/**
 * Helper: Toggles and fetches +-15s Temporal Context Filmstrip for a candidate card.
 */
async function toggleCandidateFilmstrip(rank, videoId, centerSec) {
    const box = document.getElementById(`filmstrip-box-${rank}`);
    if (!box) return;

    const isHidden = box.style.display === "none";
    if (!isHidden) {
        box.style.display = "none";
        return;
    }

    box.style.display = "block";
    box.innerHTML = `<div style="font-size: 11px; color: var(--text-dim); padding: 6px;">Loading +-15s neighbor keyframes for ${videoId}...</div>`;

    try {
        const res = await fetch(`/api/videos/${encodeURIComponent(videoId)}/context?timestamp_sec=${centerSec}&window_sec=15.0`);
        if (!res.ok) throw new Error("Failed to load temporal context");
        const data = await res.json();
        const frames = data.frames || [];
        if (frames.length === 0) {
            box.innerHTML = `<div style="font-size: 11px; color: var(--text-dim); padding: 6px;">No neighbor keyframes found.</div>`;
            return;
        }

        let html = `<div class="filmstrip-strip">`;
        frames.forEach(f => {
            const isCenter = Math.abs(f.delta_sec) < 0.8;
            const deltaStr = f.delta_sec >= 0 ? `+${f.delta_sec.toFixed(1)}s` : `${f.delta_sec.toFixed(1)}s`;
            const ocrTag = (f.ocr_texts && f.ocr_texts.length > 0) ? `<div class="trace-hit-text" title="${f.ocr_texts.join(' ')}">${f.ocr_texts[0]}</div>` : "";
            html += `
                <div class="filmstrip-item ${isCenter ? 'center-hit' : ''}" onclick="event.stopPropagation(); seekToVideoMoment('${videoId}', ${f.timestamp_sec});">
                    <img src="${f.image_url}" class="filmstrip-thumb" loading="lazy" alt="${f.keyframe_id}">
                    <div class="filmstrip-meta">
                        <span class="filmstrip-time">${f.timestamp_sec.toFixed(1)}s</span>
                        <span class="filmstrip-delta">(${deltaStr})</span>
                    </div>
                    ${ocrTag}
                </div>
            `;
        });
        html += `</div>`;
        box.innerHTML = html;
    } catch (err) {
        box.innerHTML = `<div style="font-size: 11px; color: #f87171; padding: 6px;">Error: ${err.message}</div>`;
    }
}

/**
 * Helper: Filters search scope directly to a specific video ID and re-runs search.
 */
function filterSearchToVideo(videoId) {
    if (!videoId) return;
    if (videoId !== state.currentVideoId) {
        videoSelect.value = videoId;
        loadVideo(videoId);
    }
    const chk = document.getElementById("chkCurrentVideoOnly");
    if (chk) {
        chk.checked = true;
    }
    if (queryInput.value.trim()) {
        executeSearch();
    }
}

/**
 * Executes Interactive Relevance Feedback via Rocchio.
 */
async function sendRelevanceFeedback(keyframeId, isPositive) {
    if (!keyframeId) return;

    if (isPositive) {
        state.feedbackPositives.add(keyframeId);
        state.feedbackNegatives.delete(keyframeId);
    } else {
        state.feedbackNegatives.add(keyframeId);
        state.feedbackPositives.delete(keyframeId);
    }

    try {
        const scopeCurrent = document.getElementById("chkCurrentVideoOnly")?.checked;
        const res = await fetch("/api/search/feedback", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                positive_keyframe_ids: Array.from(state.feedbackPositives),
                negative_keyframe_ids: Array.from(state.feedbackNegatives),
                original_query: queryInput.value.trim(),
                top_k: 25,
                video_id: scopeCurrent ? state.currentVideoId : null
            })
        });

        if (!res.ok) throw new Error("Feedback re-ranking failed");
        const data = await res.json();
        state.searchResults = data.candidates || [];
        tabResultCount.textContent = state.searchResults.length;
        renderCandidateCards();
    } catch (err) {
        console.error("Feedback error:", err);
    }
}

/**
 * Renders ranked candidate cards in the right pane.
 */
function renderCandidateCards() {
    if (state.searchResults.length === 0) {
        candidateList.innerHTML = '<div class="empty-candidate-state">No matching moments found for this query.</div>';
        return;
    }

    candidateList.innerHTML = "";

    state.searchResults.forEach(c => {
        const card = document.createElement("div");
        card.className = "candidate-card";
        card.id = `candidate-${c.rank}`;
        if (state.activeCandidateRank === c.rank) {
            card.classList.add("active");
        }

        let rankClass = "";
        if (c.rank === 1) rankClass = "top-1";
        else if (c.rank === 2) rankClass = "top-2";
        else if (c.rank === 3) rankClass = "top-3";

        let thumbHtml = "";
        if (c.thumbnail_url) {
            thumbHtml = `<img src="${c.thumbnail_url}" alt="Rank ${c.rank}" loading="lazy">`;
        } else {
            thumbHtml = `<span class="candidate-thumb-placeholder">Shot #${c.shot_id || '0'}</span>`;
        }

        const isConsensus = (c.matched_cues && c.matched_cues.length > 1);
        const consensusBadge = isConsensus ? `<span class="candidate-consensus-badge">[Consensus: ${c.matched_cues.length} Cues]</span>` : "";

        let cuesBadgeHtml = "";
        if (c.matched_cues && c.matched_cues.length > 0) {
            cuesBadgeHtml = c.matched_cues.map(cueId => {
                const isOcr = cueId.includes("ocr");
                const cls = isOcr ? "ocr" : "visual";
                const label = isOcr ? "OCR" : "VISUAL";
                return `<span class="candidate-type-badge ${cls}">${label}</span>`;
            }).join(" ");
        } else {
            cuesBadgeHtml = `<span class="candidate-type-badge keyframe">Moment</span>`;
        }

        let snippetHtml = "";
        if (c.text_detected) {
            snippetHtml = `<div class="candidate-text-snippet"><strong>[Detected Text]</strong> "${c.text_detected}"</div>`;
        }

        const evidenceEntries = Object.entries(c.cue_evidence || {});
        let evidenceToggleBtn = "";
        let evidenceBoxHtml = "";

        if (evidenceEntries.length > 0) {
            evidenceToggleBtn = `
                <button type="button" class="btn-evidence-toggle" onclick="event.stopPropagation(); toggleEvidenceBox(${c.rank});">
                    [v] Trigger Keyframes (${evidenceEntries.length})
                </button>
            `;

            evidenceBoxHtml = `<div class="candidate-evidence-box" id="evidence-box-${c.rank}" style="display: none;">`;
            evidenceEntries.forEach(([cueId, hit]) => {
                const isOcr = cueId.includes("ocr");
                const cueLabel = isOcr ? "OCR Cue" : "Visual Cue";
                const textDetail = hit.text_detected ? `<div class="trace-hit-text" title="${hit.text_detected}">"${hit.text_detected}"</div>` : "";
                evidenceBoxHtml += `
                    <div class="evidence-item" onclick="event.stopPropagation(); seekToVideoMoment('${hit.video_id || c.video_id}', ${hit.timestamp_sec});">
                        <img src="${hit.thumbnail_url || ''}" class="evidence-thumb" loading="lazy" alt="${hit.keyframe_id}">
                        <div class="evidence-label">[${cueLabel}]: ${cueId}</div>
                        <div class="evidence-time">${hit.keyframe_id} @ ${Number(hit.timestamp_sec).toFixed(1)}s (Score: ${Number(hit.score).toFixed(4)})</div>
                        ${textDetail}
                    </div>
                `;
            });
            evidenceBoxHtml += `</div>`;
        }

        const centerSec = ((Number(c.start_sec) + Number(c.end_sec)) / 2.0).toFixed(2);

        card.innerHTML = `
            <div class="candidate-thumb-box">
                <span class="candidate-rank-pill ${rankClass}">#${c.rank}</span>
                ${thumbHtml}
            </div>
            <div class="candidate-content">
                <div class="candidate-row-top">
                    <div class="candidate-title">
                        <span class="candidate-vid-badge">${c.video_id}</span>
                        ${consensusBadge}
                    </div>
                    <div class="candidate-score-pill">Score: ${Number(c.score).toFixed(4)}</div>
                </div>
                <div class="candidate-row-bottom">
                    <div class="candidate-time">${c.formatted_time} <span style="color: var(--text-dim); font-size: 11px;">[${Number(c.start_sec).toFixed(1)}s - ${Number(c.end_sec).toFixed(1)}s]</span></div>
                    <div style="display: flex; gap: 4px;">${cuesBadgeHtml}</div>
                </div>
                ${snippetHtml}
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 4px; margin-top: 4px;">
                    <div style="display: flex; gap: 4px; align-items: center;">
                        ${evidenceToggleBtn}
                        <button type="button" class="btn-evidence-toggle" onclick="event.stopPropagation(); toggleCandidateFilmstrip(${c.rank}, '${c.video_id}', ${centerSec});" title="Inspect +-15s neighbor keyframes without loading video">
                            [Filmstrip +-15s]
                        </button>
                        <button type="button" class="btn-evidence-toggle" onclick="event.stopPropagation(); filterSearchToVideo('${c.video_id}');" title="Restrict search to this video">
                            [Only ${c.video_id}]
                        </button>
                    </div>
                    <div class="candidate-feedback-actions" onclick="event.stopPropagation();">
                        <button type="button" class="btn-feedback positive" onclick="sendRelevanceFeedback('${c.keyframe_id}', true)" title="Find visually similar frames with Rocchio">[+ Similar]</button>
                        <button type="button" class="btn-feedback negative" onclick="sendRelevanceFeedback('${c.keyframe_id}', false)" title="Suppress similar frames with Rocchio">[- Exclude]</button>
                        <button type="button" class="btn-card-quick-submit" onclick="submitKisMoment('${c.video_id}', ${Number(c.start_sec)}, ${Number(c.end_sec)});" title="Immediately submit this candidate interval to DRES">
                            [Submit KIS]
                        </button>
                    </div>
                </div>
                ${evidenceBoxHtml}
                <div class="candidate-filmstrip-box" id="filmstrip-box-${c.rank}" style="display: none;" onclick="event.stopPropagation();"></div>
            </div>
        `;

        card.addEventListener("click", () => {
            seekToVideoMoment(c.video_id, c.start_sec, c.end_sec);
            highlightCandidateCard(c.rank);
        });

        candidateList.appendChild(card);
    });
}

/**
 * Highlights a candidate card by rank.
 */
function highlightCandidateCard(rank) {
    state.activeCandidateRank = rank;
    document.querySelectorAll(".candidate-card").forEach(el => el.classList.remove("active"));
    const activeCard = document.getElementById(`candidate-${rank}`);
    if (activeCard) {
        activeCard.classList.add("active");
        activeCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
}

/**
 * Clears search and restores Shot Inspector view.
 */
function clearVisualSearch() {
    queryInput.value = "";
    btnClearQuery.style.display = "none";
    state.searchResults = [];
    state.searchTrace = null;
    state.activeCandidateRank = null;
    tabResultCount.textContent = "0";
    if (pipelineTracePanel) pipelineTracePanel.style.display = "none";
    switchTab("shots");
}

// =========================================================================
// Task 06B: KIS Interactive Scrubber, Range Controls & DRES Live Submission
// =========================================================================

/**
 * Steps video player relative to current playhead by deltaSec.
 */
function stepVideoBy(deltaSec) {
    if (!videoPlayer) return;
    const dur = state.totalDuration || videoPlayer.duration || 3600;
    const target = Math.max(0.0, Math.min(dur, (videoPlayer.currentTime || 0.0) + deltaSec));
    videoPlayer.pause();
    state.isPlayingRange = false;
    videoPlayer.currentTime = target;
}

/**
 * Toggles video playback play/pause.
 */
function toggleVideoPlayPause() {
    if (!videoPlayer) return;
    if (videoPlayer.paused) {
        videoPlayer.play();
    } else {
        videoPlayer.pause();
        state.isPlayingRange = false;
    }
}

/**
 * Sets KIS Mark In and Mark Out boundaries and updates UI.
 */
function setKisRange(startSec, endSec) {
    const dur = state.totalDuration || videoPlayer.duration || 3600;
    const s = Math.max(0.0, Math.min(dur, Number(startSec) || 0.0));
    const e = Math.max(s, Math.min(dur, Number(endSec) || s));
    state.markInSec = Number(s.toFixed(2));
    state.markOutSec = Number(e.toFixed(2));

    if (kisMarkInInput) kisMarkInInput.value = state.markInSec.toFixed(2);
    if (kisMarkOutInput) kisMarkOutInput.value = state.markOutSec.toFixed(2);
    updateKisRangeDisplay();
    renderTimelineRangeOverlay();
}

/**
 * Updates KIS target header label with millisecond bounds.
 */
function updateKisRangeDisplay() {
    if (!kisTargetLabel) return;
    const vid = state.currentVideoId || "--";
    const sMs = Math.round(state.markInSec * 1000);
    const eMs = Math.round(state.markOutSec * 1000);
    const dur = Math.max(0.0, state.markOutSec - state.markInSec).toFixed(2);
    kisTargetLabel.textContent = `Target: ${vid} | Range: ${sMs}ms - ${eMs}ms (${dur}s)`;
}

/**
 * Renders the visual range highlight overlay on the shot timeline.
 */
function renderTimelineRangeOverlay() {
    if (!timelineRangeOverlay) return;
    const dur = state.totalDuration || videoPlayer.duration || 0;
    if (dur <= 0 || state.markOutSec < state.markInSec) {
        timelineRangeOverlay.style.display = "none";
        return;
    }
    const leftPct = Math.max(0, Math.min(100, (state.markInSec / dur) * 100));
    const widthPct = Math.max(0.4, Math.min(100 - leftPct, ((state.markOutSec - state.markInSec) / dur) * 100));
    timelineRangeOverlay.style.display = "block";
    timelineRangeOverlay.style.left = `${leftPct}%`;
    timelineRangeOverlay.style.width = `${widthPct}%`;
}

/**
 * Plays exclusively within [markInSec, markOutSec] and auto-pauses at markOutSec.
 */
function playSelectedKisRange() {
    if (!videoPlayer) return;
    if (state.markOutSec <= state.markInSec) {
        showKisToast("[WARNING] Mark Out must be greater than Mark In to preview range.", "warn");
        return;
    }
    state.isPlayingRange = true;
    videoPlayer.currentTime = state.markInSec;
    videoPlayer.play();
    if (btnPlayRange) btnPlayRange.textContent = "[Playing...]";
}

/**
 * Loads +-15s neighbor keyframes around current playhead into Player Filmstrip Drawer.
 */
async function loadPlayerFilmstrip() {
    if (!playerFilmstripList || !state.currentVideoId) return;
    const centerSec = Number((videoPlayer.currentTime || 0.0).toFixed(2));
    const titleEl = document.getElementById("playerFilmstripTitle");
    if (titleEl) {
        titleEl.textContent = `Temporal Context Filmstrip for ${state.currentVideoId} @ ${centerSec}s (+-15s)`;
    }
    playerFilmstripList.innerHTML = `<div style="font-size: 11px; color: var(--text-dim); padding: 6px;">Loading neighbor frames...</div>`;

    try {
        const res = await fetch(`/api/videos/${encodeURIComponent(state.currentVideoId)}/context?timestamp_sec=${centerSec}&window_sec=15.0`);
        if (!res.ok) throw new Error("Failed to load filmstrip");
        const data = await res.json();
        const frames = data.frames || [];
        if (frames.length === 0) {
            playerFilmstripList.innerHTML = `<div style="font-size: 11px; color: var(--text-dim); padding: 6px;">No neighbor keyframes found.</div>`;
            return;
        }

        let html = "";
        frames.forEach(f => {
            const isCenter = Math.abs(f.delta_sec) < 0.8;
            const deltaStr = f.delta_sec >= 0 ? `+${f.delta_sec.toFixed(1)}s` : `${f.delta_sec.toFixed(1)}s`;
            const ocrTag = (f.ocr_texts && f.ocr_texts.length > 0) ? `<div class="trace-hit-text" title="${f.ocr_texts.join(' ')}">${f.ocr_texts[0]}</div>` : "";
            html += `
                <div class="filmstrip-item ${isCenter ? 'center-hit' : ''}" onclick="seekVideoTo(${f.timestamp_sec}); setKisRange(${Math.max(0, f.timestamp_sec - 0.5)}, ${f.timestamp_sec + 0.5});">
                    <img src="${f.image_url}" class="filmstrip-thumb" loading="lazy" alt="${f.keyframe_id}">
                    <div class="filmstrip-meta">
                        <span class="filmstrip-time">${f.timestamp_sec.toFixed(1)}s</span>
                        <span class="filmstrip-delta">(${deltaStr})</span>
                    </div>
                    ${ocrTag}
                </div>
            `;
        });
        playerFilmstripList.innerHTML = html;
    } catch (err) {
        playerFilmstripList.innerHTML = `<div style="font-size: 11px; color: #f87171; padding: 6px;">Error: ${err.message}</div>`;
    }
}

/**
 * Displays a status banner inside KIS Console.
 */
function showKisToast(message, level = "ok") {
    if (!kisSubmitToast) return;
    kisSubmitToast.style.display = "block";
    kisSubmitToast.className = `kis-submit-toast ${level}`;
    kisSubmitToast.textContent = message;
}

/**
 * Submits a KIS interval [startSec, endSec] for videoId to backend DRES endpoint.
 */
async function submitKisMoment(videoId, startSec, endSec) {
    if (!videoId) {
        showKisToast("[ERROR] No active video selected for submission.", "err");
        return;
    }
    if (endSec < startSec) {
        showKisToast(`[ERROR] Invalid interval: End (${endSec}s) < Start (${startSec}s).`, "err");
        return;
    }

    const dryRun = chkDresDryRun ? chkDresDryRun.checked : true;
    const evalId = inputDresEvalId ? inputDresEvalId.value.trim() : "offline_kis_eval";

    try {
        const res = await fetch("/api/dres/submit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                video_id: videoId,
                start_sec: startSec,
                end_sec: endSec,
                evaluation_id: evalId,
                dry_run: dryRun
            })
        });

        const data = await res.json();
        if (!res.ok) {
            showKisToast(`[ERROR] Submission rejected: ${data.detail || "Server error"}`, "err");
            return;
        }

        if (data.status === "DUPLICATE_PREVENTED") {
            showKisToast(data.message, "warn");
        } else {
            const est = computeCurrentKisScore();
            showKisToast(`${data.message} | Est. Score: ${est.toFixed(1)} pts`, "ok");
        }

        refreshDresStatus();
    } catch (err) {
        showKisToast(`[ERROR] Network error submitting to DRES: ${err.message}`, "err");
    }
}

/**
 * 1-Click Quick Submit at current video playhead [currentTime - 0.5s, currentTime + 0.5s].
 */
function quickSubmitAtPlayhead() {
    if (!state.currentVideoId) return;
    const cur = videoPlayer ? (videoPlayer.currentTime || 0.0) : 0.0;
    const dur = state.totalDuration || videoPlayer.duration || 3600;
    const s = Number(Math.max(0.0, cur - 0.5).toFixed(2));
    const e = Number(Math.min(dur, cur + 0.5).toFixed(2));
    setKisRange(s, e);
    submitKisMoment(state.currentVideoId, s, e);
}

/**
 * Refreshes DRES session status and submission history log.
 */
async function refreshDresStatus() {
    if (!dresHistoryList) return;
    try {
        const res = await fetch("/api/dres/status");
        if (!res.ok) return;
        const data = await res.json();
        const hist = data.history || [];
        if (hist.length === 0) {
            dresHistoryList.textContent = "No submissions yet.";
            return;
        }
        dresHistoryList.innerHTML = hist.map((h, i) =>
            `<div class="dres-hist-item">#${hist.length - i} [${h.mode}] <strong>${h.video_id}</strong>: ${h.start_ms}ms - ${h.end_ms}ms (${h.status})</div>`
        ).join("");
    } catch (err) {
        console.error("Failed to load DRES status:", err);
    }
}

/**
 * Computes real-time KIS competition score based on elapsed stopwatch and wrong attempts.
 */
function computeCurrentKisScore() {
    const tL = state.kisTaskLimitSec || 300;
    const t = Math.min(state.kisElapsedSec, tL);
    const sAcc = Math.max(0.0, 50.0 - 10.0 * state.kisWrongAttempts);
    const sTime = 50.0 * (1.0 - t / tL);
    return Math.max(0.0, sAcc + sTime);
}

/**
 * Updates the stopwatch and estimated KIS score badge.
 */
function updateKisScoreWidget() {
    if (kisTimerDisplay) {
        const mins = String(Math.floor(state.kisElapsedSec / 60)).padStart(2, "0");
        const secs = String(state.kisElapsedSec % 60).padStart(2, "0");
        kisTimerDisplay.textContent = `${mins}:${secs}`;
    }
    if (kisWrongCount) {
        kisWrongCount.textContent = String(state.kisWrongAttempts);
    }
    if (kisEstScoreBadge) {
        const total = computeCurrentKisScore();
        kisEstScoreBadge.textContent = `Est: ${total.toFixed(1)} pts`;
    }
}

/**
 * Sets up all UI event handlers.
 */
function setupEventListeners() {
    videoSelect.addEventListener("change", (e) => {
        loadVideo(e.target.value);
    });

    videoPlayer.addEventListener("timeupdate", onVideoTimeUpdate);

    // Timeline hover time indicator
    shotTimeline.addEventListener("mousemove", (e) => {
        const rect = shotTimeline.getBoundingClientRect();
        const offsetX = e.clientX - rect.left;
        const pct = Math.max(0, Math.min(offsetX / rect.width, 1));
        const hoverSecs = pct * state.totalDuration;
        timelineHoverTime.textContent = formatTime(hoverSecs);
        if (timelineTooltip.style.opacity === "1") {
            positionTooltip(e);
        }
    });

    // Filtering & Search for shots
    shotSearch.addEventListener("input", renderShotCards);
    shotFilter.addEventListener("change", renderShotCards);

    // Prevent auto-scroll while user is actively scrolling the list
    shotList.addEventListener("mouseenter", () => { state.isUserInteracting = true; });
    shotList.addEventListener("mouseleave", () => { state.isUserInteracting = false; });

    // Buttons
    btnPrevShot.addEventListener("click", jumpPrevShot);
    btnNextShot.addEventListener("click", jumpNextShot);
    btnJumpCenter.addEventListener("click", jumpCurrentCenter);

    // Task 06B Fine Stepper Controls
    if (btnStepBack5s) btnStepBack5s.addEventListener("click", () => stepVideoBy(-5.0));
    if (btnStepBack1s) btnStepBack1s.addEventListener("click", () => stepVideoBy(-1.0));
    if (btnStepBackFrame) btnStepBackFrame.addEventListener("click", () => stepVideoBy(-0.04));
    if (btnTogglePlay) btnTogglePlay.addEventListener("click", toggleVideoPlayPause);
    if (btnStepFwdFrame) btnStepFwdFrame.addEventListener("click", () => stepVideoBy(0.04));
    if (btnStepFwd1s) btnStepFwd1s.addEventListener("click", () => stepVideoBy(1.0));
    if (btnStepFwd5s) btnStepFwd5s.addEventListener("click", () => stepVideoBy(5.0));

    // Task 06B Mark In / Out & Presets
    if (btnMarkIn) {
        btnMarkIn.addEventListener("click", () => {
            const cur = videoPlayer.currentTime || 0.0;
            const out = Math.max(cur, state.markOutSec);
            setKisRange(cur, out);
        });
    }
    if (btnMarkOut) {
        btnMarkOut.addEventListener("click", () => {
            const cur = videoPlayer.currentTime || 0.0;
            const inn = Math.min(cur, state.markInSec);
            setKisRange(inn, cur);
        });
    }
    if (kisMarkInInput) {
        kisMarkInInput.addEventListener("change", () => {
            setKisRange(parseFloat(kisMarkInInput.value) || 0.0, state.markOutSec);
        });
    }
    if (kisMarkOutInput) {
        kisMarkOutInput.addEventListener("change", () => {
            setKisRange(state.markInSec, parseFloat(kisMarkOutInput.value) || state.markInSec);
        });
    }
    if (btnPresetShot) {
        btnPresetShot.addEventListener("click", () => {
            const cur = videoPlayer.currentTime || 0.0;
            const activeShot = state.shots.find(s => s.start_sec <= cur && cur <= s.end_sec) || state.shots[0];
            if (activeShot) {
                setKisRange(activeShot.start_sec, activeShot.end_sec);
            }
        });
    }
    if (btnPresetTight) {
        btnPresetTight.addEventListener("click", () => {
            const cur = videoPlayer.currentTime || 0.0;
            setKisRange(Math.max(0.0, cur - 0.5), cur + 0.5);
        });
    }
    if (btnPresetWindow) {
        btnPresetWindow.addEventListener("click", () => {
            const cur = videoPlayer.currentTime || 0.0;
            setKisRange(Math.max(0.0, cur - 2.5), cur + 2.5);
        });
    }
    if (btnPlayRange) {
        btnPlayRange.addEventListener("click", playSelectedKisRange);
    }

    // Task 06B Submission Buttons
    if (btnQuickSubmitPlayhead) {
        btnQuickSubmitPlayhead.addEventListener("click", quickSubmitAtPlayhead);
    }
    if (btnSubmitRange) {
        btnSubmitRange.addEventListener("click", () => {
            submitKisMoment(state.currentVideoId, state.markInSec, state.markOutSec);
        });
    }

    // Task 06B Player Filmstrip Drawer
    if (btnToggleFilmstrip && playerFilmstripDrawer) {
        btnToggleFilmstrip.addEventListener("click", () => {
            const isHidden = playerFilmstripDrawer.style.display === "none";
            playerFilmstripDrawer.style.display = isHidden ? "block" : "none";
            if (isHidden) loadPlayerFilmstrip();
        });
    }
    if (btnRefreshFilmstrip) {
        btnRefreshFilmstrip.addEventListener("click", loadPlayerFilmstrip);
    }

    // Task 06B DRES Config & History Drawer
    if (btnToggleDresConfig && kisDresConfigDrawer) {
        btnToggleDresConfig.addEventListener("click", () => {
            const isHidden = kisDresConfigDrawer.style.display === "none";
            kisDresConfigDrawer.style.display = isHidden ? "block" : "none";
            if (isHidden) refreshDresStatus();
        });
    }
    if (btnSaveDresConfig) {
        btnSaveDresConfig.addEventListener("click", async () => {
            try {
                const res = await fetch("/api/dres/session", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        base_url: inputDresUrl?.value || "",
                        evaluation_id: inputDresEvalId?.value || "",
                        session_id: inputDresSession?.value || ""
                    })
                });
                if (res.ok) {
                    showKisToast("[OK] Saved DRES configuration.", "ok");
                    refreshDresStatus();
                }
            } catch (err) {
                showKisToast(`[ERROR] Failed to save DRES config: ${err.message}`, "err");
            }
        });
    }
    if (btnClearDresCache) {
        btnClearDresCache.addEventListener("click", async () => {
            await fetch("/api/dres/clear-cache", { method: "POST" });
            showKisToast("[OK] Cleared duplicate submission cache for new query.", "ok");
            refreshDresStatus();
        });
    }

    // Task 06B Competition Stopwatch & Score Simulator
    if (kisTaskTypeSelect) {
        kisTaskTypeSelect.addEventListener("change", () => {
            state.kisTaskLimitSec = parseInt(kisTaskTypeSelect.value, 10) || 300;
            updateKisScoreWidget();
        });
    }
    if (btnTimerToggle) {
        btnTimerToggle.addEventListener("click", () => {
            if (state.kisTimerRunning) {
                clearInterval(state.kisTimerInterval);
                state.kisTimerRunning = false;
                btnTimerToggle.textContent = "[Start]";
            } else {
                state.kisTimerRunning = true;
                btnTimerToggle.textContent = "[Pause]";
                state.kisTimerInterval = setInterval(() => {
                    state.kisElapsedSec += 1;
                    updateKisScoreWidget();
                }, 1000);
            }
        });
    }
    if (btnTimerReset) {
        btnTimerReset.addEventListener("click", async () => {
            if (state.kisTimerInterval) clearInterval(state.kisTimerInterval);
            state.kisTimerRunning = false;
            state.kisElapsedSec = 0;
            state.kisWrongAttempts = 0;
            if (btnTimerToggle) btnTimerToggle.textContent = "[Start]";
            updateKisScoreWidget();
            await fetch("/api/dres/clear-cache", { method: "POST" });
            showKisToast("[OK] Reset timer and cleared duplicate cache for new query.", "ok");
            refreshDresStatus();
        });
    }
    if (btnAddWrong) {
        btnAddWrong.addEventListener("click", () => {
            state.kisWrongAttempts += 1;
            updateKisScoreWidget();
        });
    }
    if (btnSubWrong) {
        btnSubWrong.addEventListener("click", () => {
            state.kisWrongAttempts = Math.max(0, state.kisWrongAttempts - 1);
            updateKisScoreWidget();
        });
    }

    // Global Keyboard Hotkeys (J, L, ArrowLeft, ArrowRight, Space, I, O, S)
    document.addEventListener("keydown", (e) => {
        const tag = (e.target && e.target.tagName) ? e.target.tagName.toUpperCase() : "";
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

        const key = e.key.toLowerCase();
        if (key === "j") {
            e.preventDefault();
            stepVideoBy(-1.0);
        } else if (key === "l") {
            e.preventDefault();
            stepVideoBy(1.0);
        } else if (e.key === "ArrowLeft") {
            e.preventDefault();
            stepVideoBy(-0.04);
        } else if (e.key === "ArrowRight") {
            e.preventDefault();
            stepVideoBy(0.04);
        } else if (e.key === " ") {
            e.preventDefault();
            toggleVideoPlayPause();
        } else if (key === "i") {
            e.preventDefault();
            const cur = videoPlayer.currentTime || 0.0;
            setKisRange(cur, Math.max(cur, state.markOutSec));
        } else if (key === "o") {
            e.preventDefault();
            const cur = videoPlayer.currentTime || 0.0;
            setKisRange(Math.min(cur, state.markInSec), cur);
        } else if (key === "s" && !e.ctrlKey && !e.metaKey) {
            e.preventDefault();
            quickSubmitAtPlayhead();
        }
    });

    // Modality toggle handlers
    if (btnModeMultimodal) {
        btnModeMultimodal.addEventListener("click", () => {
            state.searchMode = "auto";
            btnModeMultimodal.classList.add("active");
            if (btnModeVisual) btnModeVisual.classList.remove("active");
            if (btnModeOcr) btnModeOcr.classList.remove("active");
            queryInput.placeholder = "Enter multi-cue query (e.g. 'v: news anchor | -v: studio | ocr: thoi su')...";
            queryInput.focus();
        });
    }

    if (btnModeVisual) {
        btnModeVisual.addEventListener("click", () => {
            state.searchMode = "visual";
            btnModeVisual.classList.add("active");
            if (btnModeMultimodal) btnModeMultimodal.classList.remove("active");
            if (btnModeOcr) btnModeOcr.classList.remove("active");
            queryInput.placeholder = "Search visual scenes in English (e.g. 'close up of food dish', 'blue truck')...";
            queryInput.focus();
        });
    }

    if (btnModeOcr) {
        btnModeOcr.addEventListener("click", () => {
            state.searchMode = "ocr";
            btnModeOcr.classList.add("active");
            if (btnModeMultimodal) btnModeMultimodal.classList.remove("active");
            if (btnModeVisual) btnModeVisual.classList.remove("active");
            queryInput.placeholder = "Search on-screen text (e.g. 'trùng biển số', 'tây nguyên', 'HTV')...";
            queryInput.focus();
        });
    }

    // Multi-Cue Builder Pills Handlers
    if (btnAddVisualCue) {
        btnAddVisualCue.addEventListener("click", () => {
            const cur = queryInput.value.trim();
            queryInput.value = cur ? `${cur} | v: ` : "v: ";
            queryInput.focus();
            btnClearQuery.style.display = "block";
        });
    }

    if (btnAddNegVisualCue) {
        btnAddNegVisualCue.addEventListener("click", () => {
            const cur = queryInput.value.trim();
            queryInput.value = cur ? `${cur} | -v: ` : "-v: ";
            queryInput.focus();
            btnClearQuery.style.display = "block";
        });
    }

    if (btnAddOcrCue) {
        btnAddOcrCue.addEventListener("click", () => {
            const cur = queryInput.value.trim();
            queryInput.value = cur ? `${cur} | ocr: ` : "ocr: ";
            queryInput.focus();
            btnClearQuery.style.display = "block";
        });
    }

    if (btnAddSeqStage) {
        btnAddSeqStage.addEventListener("click", () => {
            const cur = queryInput.value.trim();
            if (cur) {
                queryInput.value = `${cur} >> `;
                queryInput.focus();
                btnClearQuery.style.display = "block";
            }
        });
    }

    if (btnClearPills) {
        btnClearPills.addEventListener("click", () => {
            queryInput.value = "";
            btnClearQuery.style.display = "none";
            queryInput.focus();
        });
    }

    // Toggle Explainable Pipeline Trace Handler
    if (btnToggleTrace && traceContent) {
        btnToggleTrace.addEventListener("click", () => {
            const isHidden = traceContent.style.display === "none";
            traceContent.style.display = isHidden ? "flex" : "none";
            btnToggleTrace.innerHTML = isHidden ? "[^] Hide Trace Details" : "[v] Inspect Per-Cue Hits &amp; Fusion";
        });
    }

    // Search handlers
    searchForm.addEventListener("submit", (e) => {
        e.preventDefault();
        executeSearch();
    });

    queryInput.addEventListener("input", () => {
        btnClearQuery.style.display = queryInput.value.trim() ? "block" : "none";
    });

    btnClearQuery.addEventListener("click", clearVisualSearch);
    tabShots.addEventListener("click", () => switchTab("shots"));
    tabResults.addEventListener("click", () => switchTab("results"));
    if (tabCheckpoints) tabCheckpoints.addEventListener("click", () => switchTab("checkpoints"));
    if (btnRefreshDb) btnRefreshDb.addEventListener("click", loadCheckpoints);

    const cpSearch = document.getElementById("cpSearchInput");
    if (cpSearch) cpSearch.addEventListener("input", renderCheckpointTable);

    const cpFilter = document.getElementById("cpFilterSelect");
    if (cpFilter) cpFilter.addEventListener("change", renderCheckpointTable);
}

// Start app
document.addEventListener("DOMContentLoaded", init);
