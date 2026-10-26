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

                kfItem.innerHTML = `
                    <div class="kf-thumb-wrap">
                        <img src="${kf.image_url}" alt="Keyframe at ${kf.timestamp_sec}s" loading="lazy">
                        <span class="kf-type-tag ${typeClass}">${typeLabel}</span>
                    </div>
                    <div class="kf-details">
                        <span class="kf-time">t=${kf.timestamp_sec.toFixed(2)}s</span>
                        <span class="kf-blur">Blur: ${kf.blur_score}</span>
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

    // Filtering & Search
    shotSearch.addEventListener("input", renderShotCards);
    shotFilter.addEventListener("change", renderShotCards);

    // Prevent auto-scroll while user is actively scrolling the list
    shotList.addEventListener("mouseenter", () => { state.isUserInteracting = true; });
    shotList.addEventListener("mouseleave", () => { state.isUserInteracting = false; });

    // Buttons
    btnPrevShot.addEventListener("click", jumpPrevShot);
    btnNextShot.addEventListener("click", jumpNextShot);
    btnJumpCenter.addEventListener("click", jumpCurrentCenter);
}

// Start app
document.addEventListener("DOMContentLoaded", init);
