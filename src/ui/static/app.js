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
    activeTab: "shots",
    activeCandidateRank: null,
    searchMode: "visual",
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
const timelineHoverTime = document.getElementById("timelineHoverTime");
const timelineTooltip = document.getElementById("timelineTooltip");
const shotList = document.getElementById("shotList");
const shotSearch = document.getElementById("shotSearch");
const shotFilter = document.getElementById("shotFilter");
const chkAutoScroll = document.getElementById("chkAutoScroll");
const btnPrevShot = document.getElementById("btnPrevShot");
const btnNextShot = document.getElementById("btnNextShot");
const btnJumpCenter = document.getElementById("btnJumpCenter");

// Visual Search DOM Elements
const searchForm = document.getElementById("searchForm");
const queryInput = document.getElementById("queryInput");
const btnClearQuery = document.getElementById("btnClearQuery");
const btnSearch = document.getElementById("btnSearch");
const btnModeVisual = document.getElementById("btnModeVisual");
const btnModeOcr = document.getElementById("btnModeOcr");
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

    } catch (err) {
        console.error("Error loading video details:", err);
        shotList.innerHTML = `<div class="loading-state">Error loading details: ${err.message}</div>`;
    }
}

/**
 * Renders the proportional shot segments on the timeline.
 */
function renderTimeline() {
    // Preserve the cursor element
    shotTimeline.innerHTML = "";
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

        // Click to seek
        segment.addEventListener("click", () => {
            seekVideoTo(shot.start_sec);
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
 * Executes search via SigLIP2 + FAISS (Visual) or SQLite FTS5 (OCR).
 */
async function executeSearch() {
    const query = queryInput.value.trim();
    if (!query) return;

    btnSearch.disabled = true;
    btnSearch.textContent = "Searching...";
    btnClearQuery.style.display = "block";
    switchTab("results");

    const isOcr = state.searchMode === "ocr";
    const modeLabel = isOcr ? "Searching on-screen text with SQLite FTS5..." : "Encoding query & searching FAISS index...";

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
        const endpoint = isOcr ? `/api/search/ocr?query=${encodeURIComponent(query)}${vidParam}&top_k=25`
                              : `/api/search/visual?query=${encodeURIComponent(query)}${vidParam}&top_k=25`;
        const res = await fetch(endpoint);
        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || "Search request failed");
        }

        const data = await res.json();
        state.searchResults = data.candidates || [];
        tabResultCount.textContent = state.searchResults.length;
        renderCandidateCards();

    } catch (err) {
        console.error("Search error:", err);
        candidateList.innerHTML = `<div class="empty-candidate-state" style="color: var(--color-short);">Error during search: ${err.message}</div>`;
    } finally {
        btnSearch.disabled = false;
        btnSearch.textContent = "Search";
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

        // Rank badge styling
        let rankClass = "";
        if (c.rank === 1) rankClass = "top-1";
        else if (c.rank === 2) rankClass = "top-2";
        else if (c.rank === 3) rankClass = "top-3";

        // Thumbnail element
        let thumbHtml = "";
        if (c.thumbnail_url) {
            thumbHtml = `<img src="${c.thumbnail_url}" alt="Rank ${c.rank}" loading="lazy">`;
        } else {
            thumbHtml = `<span class="candidate-thumb-placeholder">Shot #${c.shot_id}</span>`;
        }

        // Type & Score badges
        let typeClass = "keyframe";
        let typeLabel = "Keyframe";
        let scoreLabel = `Score: ${c.score.toFixed(4)}`;

        if (c.is_ocr) {
            typeClass = "ocr";
            typeLabel = "OCR Text";
            scoreLabel = `BM25: ${c.score.toFixed(2)}`;
        } else if (c.is_shot_pooled) {
            typeClass = "pooled";
            typeLabel = "Shot Pooled";
        }

        let snippetHtml = "";
        if (c.text_detected) {
            snippetHtml = `<div class="candidate-text-snippet"><strong>[Detected Text]</strong> "${c.text_detected}"</div>`;
        }

        card.innerHTML = `
            <div class="candidate-thumb-box">
                <span class="candidate-rank-pill ${rankClass}">#${c.rank}</span>
                ${thumbHtml}
            </div>
            <div class="candidate-content">
                <div class="candidate-row-top">
                    <div class="candidate-title">
                        <span class="candidate-vid-badge">${c.video_id}</span>
                        Shot #${String(c.shot_id).padStart(3, "0")}
                    </div>
                    <div class="candidate-score-pill">${scoreLabel}</div>
                </div>
                <div class="candidate-row-bottom">
                    <div class="candidate-time">${c.formatted_time} <span style="color: var(--text-dim); font-size: 11px;">[${c.start_sec.toFixed(1)}s - ${c.end_sec.toFixed(1)}s]</span></div>
                    <span class="candidate-type-badge ${typeClass}">${typeLabel}</span>
                </div>
                ${snippetHtml}
            </div>
        `;

        card.addEventListener("click", async () => {
            if (c.video_id && c.video_id !== state.currentVideoId) {
                videoSelect.value = c.video_id;
                await loadVideo(c.video_id);
            }
            seekVideoTo(c.timestamp_sec);
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
    state.activeCandidateRank = null;
    tabResultCount.textContent = "0";
    switchTab("shots");
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

    // Modality toggle handlers
    if (btnModeVisual && btnModeOcr) {
        btnModeVisual.addEventListener("click", () => {
            state.searchMode = "visual";
            btnModeVisual.classList.add("active");
            btnModeOcr.classList.remove("active");
            queryInput.placeholder = "Search visual scenes (e.g. 'cận cảnh đĩa thức ăn', 'cooking food')...";
            queryInput.focus();
        });

        btnModeOcr.addEventListener("click", () => {
            state.searchMode = "ocr";
            btnModeOcr.classList.add("active");
            btnModeVisual.classList.remove("active");
            queryInput.placeholder = "Search on-screen text (e.g. 'hồ tiêu', 'tây nguyên', 'HTV', 'giá')...";
            queryInput.focus();
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
