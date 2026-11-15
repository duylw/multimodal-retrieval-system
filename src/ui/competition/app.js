/**
 * KIS Competition Workstation Client Application
 * Ergonomic, distraction-free control center for live VBS / AI Challenge submission.
 */

(() => {
  'use strict';

  // =========================================================================
  // State Management
  // =========================================================================
  const state = {
    // Current query & search
    searchMode: 'auto',
    resultsLimit: 300,
    targetVideoOnly: false,
    activeVideoId: null,
    allCandidates: [],
    activeCandidate: null,

    // Task 07B: Similarity Reference & Active Pruning Filters
    referenceKeyframe: null, // { keyframe_id, video_id, timestamp_sec }
    allowedBatches: null,    // initialized in loadAllowedBatches()
    excludedVideos: new Set(),

    // Task 07C: View Mode ('frames' or 'by_video')
    viewMode: 'frames',
    lastSeekSec: 0.0,

    // Target coordinates
    targetStartSec: 0.0,
    targetEndSec: 0.0,

    // Video modal & scrubbing
    isVideoModalOpen: false,
    currentVideoDuration: 0.0,
    markInSec: 0.0,
    markOutSec: 0.0,
    isPlayingRange: false,

    // Competition Stopwatch & Score Decay
    taskTimeLimit: 300, // 300s (Textual KIS) or 240s (Video KIS)
    elapsedSeconds: 0,
    isTimerRunning: false,
    timerIntervalId: null,
    wrongAttempts: 0,

    // Layout Mode ('docked' = Zero-Popup Cockpit by default, or 'popup')
    layoutMode: 'docked',

    // DRES Client Status
    dresStatus: {
      is_authenticated: false,
      session_id: null,
      evaluation_id: 'offline_kis_eval',
      base_url: 'https://eventretrieval.one',
      history: []
    },

    // Task 06D & 07A/07B: Query Translation State
    lastTranslation: {
      original: '',
      translated: '',
      originalScene2: '',
      translatedScene2: '',
      originalNegative: '',
      translatedNegative: ''
    }
  };

  // Official competition batches: L01 through L24
  const DRES_OFFICIAL_BATCHES = new Set([
    'L01', 'L02', 'L03', 'L04', 'L05', 'L06',
    'L07', 'L08', 'L09', 'L10', 'L11', 'L12',
    'L13', 'L14', 'L15', 'L16', 'L17', 'L18',
    'L19', 'L20', 'L21', 'L22', 'L23', 'L24'
  ]);
  const ALL_BATCH_LIST = Array.from(DRES_OFFICIAL_BATCHES);
  const ALLOWED_BATCHES_STORAGE_KEY = 'kis_allowed_batches';
  const VIEW_MODE_STORAGE_KEY = 'kis_canvas_view_mode';

  // =========================================================================
  // DOM Elements Cache
  // =========================================================================
  const dom = {
    // Top Bar
    queryInput: document.getElementById('queryInput'),
    refKeyframePill: document.getElementById('refKeyframePill'),
    refKeyframeLabel: document.getElementById('refKeyframeLabel'),
    clearRefKeyframeBtn: document.getElementById('clearRefKeyframeBtn'),
    ocrQueryInput: document.getElementById('ocrQueryInput'),
    ocrRoleSelect: document.getElementById('ocrRoleSelect'),
    negativeQueryInput: document.getElementById('negativeQueryInput'),
    toggleSequenceBtn: document.getElementById('toggleSequenceBtn'),
    sequenceBuilderRow: document.getElementById('sequenceBuilderRow'),
    scene2Input: document.getElementById('scene2Input'),
    sequenceAnchorSelect: document.getElementById('sequenceAnchorSelect'),
    sequenceGapSelect: document.getElementById('sequenceGapSelect'),
    closeSequenceBtn: document.getElementById('closeSequenceBtn'),
    translateQueryBtn: document.getElementById('translateQueryBtn'),
    clearQueryBtn: document.getElementById('clearQueryBtn'),
    searchBtn: document.getElementById('searchBtn'),
    searchModePills: document.querySelectorAll('.mode-pill'),
    autoTranslateCheck: document.getElementById('autoTranslateCheck'),
    batchScopeWrapper: document.getElementById('batchScopeWrapper'),
    batchScopeBtn: document.getElementById('batchScopeBtn'),
    batchScopeLabel: document.getElementById('batchScopeLabel'),
    batchScopePopover: document.getElementById('batchScopePopover'),
    batchCheckboxGrid: document.getElementById('batchCheckboxGrid'),
    applyBatchScopeBtn: document.getElementById('applyBatchScopeBtn'),
    targetVideoOnly: document.getElementById('targetVideoOnly'),
    targetVideoFilterLabel: document.getElementById('targetVideoFilterLabel'),
    resultsLimitSelect: document.getElementById('resultsLimitSelect'),
    excludedVideosBar: document.getElementById('excludedVideosBar'),
    excludedVideosCountLabel: document.getElementById('excludedVideosCountLabel'),
    resetExcludedVideosBtn: document.getElementById('resetExcludedVideosBtn'),
    simActiveBar: document.getElementById('simActiveBar'),
    simActiveLabel: document.getElementById('simActiveLabel'),
    exitSimModeBtn: document.getElementById('exitSimModeBtn'),
    dresConnectionPill: document.getElementById('dresConnectionPill'),
    dresStatusText: document.getElementById('dresStatusText'),
    toggleDresSettingsBtn: document.getElementById('toggleDresSettingsBtn'),
    toggleDockedLayoutBtn: document.getElementById('toggleDockedLayoutBtn'),
    layoutModeLabel: document.getElementById('layoutModeLabel'),
    unloadVramBtn: document.getElementById('unloadVramBtn'),

    // DRES Config Drawer
    dresSettingsDrawer: document.getElementById('dresSettingsDrawer'),
    closeDresDrawerBtn: document.getElementById('closeDresDrawerBtn'),
    dresBaseUrl: document.getElementById('dresBaseUrl'),
    dresEvalId: document.getElementById('dresEvalId'),
    dresCollectionName: document.getElementById('dresCollectionName'),
    dresSessionId: document.getElementById('dresSessionId'),
    dresUsername: document.getElementById('dresUsername'),
    dresPassword: document.getElementById('dresPassword'),
    saveDresConfigBtn: document.getElementById('saveDresConfigBtn'),
    clearDresCacheBtn: document.getElementById('clearDresCacheBtn'),

    // Header Timer Capsule & Score Breakdown Popover
    headerTimerWrapper: document.getElementById('headerTimerWrapper'),
    timerDetailsBtn: document.getElementById('timerDetailsBtn'),
    timerDetailsPopover: document.getElementById('timerDetailsPopover'),
    taskModeTextual: document.getElementById('taskModeTextual'),
    taskModeVideo: document.getElementById('taskModeVideo'),
    stopwatchClock: document.getElementById('stopwatchClock'),
    clockLimitLabel: document.getElementById('clockLimitLabel'),
    timerStartPauseBtn: document.getElementById('timerStartPauseBtn'),
    timerResetBtn: document.getElementById('timerResetBtn'),
    predictedTotalScore: document.getElementById('predictedTotalScore'),
    predictedAccScore: document.getElementById('predictedAccScore'),
    predictedTimeScore: document.getElementById('predictedTimeScore'),
    wrongAttemptsCounter: document.getElementById('wrongAttemptsCounter'),
    addWrongAttemptBtn: document.getElementById('addWrongAttemptBtn'),
    resetWrongAttemptsBtn: document.getElementById('resetWrongAttemptsBtn'),

    // Left Sidebar: Target Coordinates & Submission
    targetStatusBadge: document.getElementById('targetStatusBadge'),
    targetVideoId: document.getElementById('targetVideoId'),
    targetDurationVal: document.getElementById('targetDurationVal'),
    targetStartSec: document.getElementById('targetStartSec'),
    targetEndSec: document.getElementById('targetEndSec'),
    targetMsBounds: document.getElementById('targetMsBounds'),
    presetTightBtn: document.getElementById('presetTightBtn'),
    presetShotBtn: document.getElementById('presetShotBtn'),
    presetWindowBtn: document.getElementById('presetWindowBtn'),
    subDryRunCheck: document.getElementById('subDryRunCheck'),
    subAllowDuplicateCheck: document.getElementById('subAllowDuplicateCheck'),
    submitTargetRangeBtn: document.getElementById('submitTargetRangeBtn'),
    quickSubmitPlayheadBtn: document.getElementById('quickSubmitPlayheadBtn'),

    // Left Sidebar: Submission Stream
    historyCountBadge: document.getElementById('historyCountBadge'),
    submissionHistoryFeed: document.getElementById('submissionHistoryFeed'),

    // Task 06D: Query Accelerators Bar & History Chips
    queryAcceleratorsBar: document.getElementById('queryAcceleratorsBar'),
    historyChipsContainer: document.getElementById('historyChipsContainer'),
    historyChipsScroll: document.getElementById('historyChipsScroll'),
    clearQueryHistoryBtn: document.getElementById('clearQueryHistoryBtn'),
    translationDiffBanner: document.getElementById('translationDiffBanner'),
    diffOriginalText: document.getElementById('diffOriginalText'),
    diffTranslatedText: document.getElementById('diffTranslatedText'),
    diffRevertBtn: document.getElementById('diffRevertBtn'),
    diffDismissBtn: document.getElementById('diffDismissBtn'),

    // Right Canvas: Candidate Grid
    candidateTotalCount: document.getElementById('candidateTotalCount'),
    candidateQueryEcho: document.getElementById('candidateQueryEcho'),
    viewModeFramesBtn: document.getElementById('viewModeFramesBtn'),
    viewModeVideoBtn: document.getElementById('viewModeVideoBtn'),
    clearAllCandidatesBtn: document.getElementById('clearAllCandidatesBtn'),
    candidateGrid: document.getElementById('candidateGrid'),
    gridLoadingOverlay: document.getElementById('gridLoadingOverlay'),

    // Modal Video Inspector
    videoModal: document.getElementById('videoModal'),
    modalBody: document.getElementById('modalBody'),
    modalVideoIdBadge: document.getElementById('modalVideoIdBadge'),
    modalHeading: document.getElementById('modalHeading'),
    modalTimeIndicator: document.getElementById('modalTimeIndicator'),
    modalDockToggleBtn: document.getElementById('modalDockToggleBtn'),
    modalCloseBtn: document.getElementById('modalCloseBtn'),
    playerWrapper: document.getElementById('playerWrapper'),
    modalVideoPlayer: document.getElementById('modalVideoPlayer'),
    playerBufferingOverlay: document.getElementById('playerBufferingOverlay'),
    playerTransportBar: document.getElementById('playerTransportBar'),
    videoTimelineSlider: document.getElementById('videoTimelineSlider'),
    timelineRangeHighlight: document.getElementById('timelineRangeHighlight'),
    timelineHitMarkers: document.getElementById('timelineHitMarkers'),

    // Steppers & Transport
    stepBack5s: document.getElementById('stepBack5s'),
    stepBack1s: document.getElementById('stepBack1s'),
    stepBackFrame: document.getElementById('stepBackFrame'),
    modalPlayPauseBtn: document.getElementById('modalPlayPauseBtn'),
    stepFwdFrame: document.getElementById('stepFwdFrame'),
    stepFwd1s: document.getElementById('stepFwd1s'),
    stepFwd5s: document.getElementById('stepFwd5s'),
    setMarkInBtn: document.getElementById('setMarkInBtn'),
    setMarkOutBtn: document.getElementById('setMarkOutBtn'),
    markInVal: document.getElementById('markInVal'),
    markOutVal: document.getElementById('markOutVal'),
    playRangePreviewBtn: document.getElementById('playRangePreviewBtn'),
    modalSubmitRangeBtn: document.getElementById('modalSubmitRangeBtn'),
    modalSubmitPlayheadBtn: document.getElementById('modalSubmitPlayheadBtn'),

    // Filmstrip Carousel
    modalFilmstripSection: document.getElementById('modalFilmstripSection'),
    filmstripStatus: document.getElementById('filmstripStatus'),
    filmstripCarousel: document.getElementById('filmstripCarousel'),

    // Docked Cockpit Panel
    dockedPlayerPanel: document.getElementById('dockedPlayerPanel'),
    dockedPlayerTitle: document.getElementById('dockedPlayerTitle'),
    expandPopupBtn: document.getElementById('expandPopupBtn'),
    dockedPlayerContainer: document.getElementById('dockedPlayerContainer'),
    closeDockedPlayerBtn: document.getElementById('closeDockedPlayerBtn')
  };

  // =========================================================================
  // Helper Functions
  // =========================================================================

  function formatTime(seconds) {
    const s = Math.max(0, Number(seconds) || 0);
    const mins = Math.floor(s / 60);
    const secs = (s % 60).toFixed(2);
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(5, '0')}`;
  }

  function secondsToMs(seconds) {
    return Math.round(Math.max(0, Number(seconds) || 0) * 1000);
  }

  function getVideoBatch(videoId) {
    if (!videoId) return '';
    const clean = videoId.replace(/\.mp4$/i, '').trim();
    return clean.split('_')[0] || '';
  }

  function isDresOfficialBatch(videoId) {
    const batch = getVideoBatch(videoId);
    return DRES_OFFICIAL_BATCHES.has(batch);
  }

  // =========================================================================
  // Competition Stopwatch & Live Score Simulator
  // =========================================================================

  function updateStopwatchDisplay() {
    const mins = Math.floor(state.elapsedSeconds / 60);
    const secs = state.elapsedSeconds % 60;
    dom.stopwatchClock.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    calculateScoreDecay();
  }

  function calculateScoreDecay() {
    // S_acc = max(0, 50 - 10 * w_s)
    const accScore = Math.max(0, 50.0 - 10.0 * state.wrongAttempts);
    
    // S_time = 50 * max(0, 1 - t / t_L)
    const timeFraction = Math.min(1.0, state.elapsedSeconds / state.taskTimeLimit);
    const timeScore = Math.max(0.0, 50.0 * (1.0 - timeFraction));

    const totalScore = accScore + timeScore;

    dom.predictedTotalScore.textContent = `${totalScore.toFixed(1)} pts`;
    dom.predictedAccScore.textContent = `${accScore.toFixed(1)} pts`;
    dom.predictedTimeScore.textContent = `${timeScore.toFixed(1)} pts`;
    dom.wrongAttemptsCounter.textContent = String(state.wrongAttempts);

    // Warning color if time is running out
    if (state.elapsedSeconds >= state.taskTimeLimit) {
      dom.stopwatchClock.style.color = '#f87171';
    } else if (state.elapsedSeconds >= state.taskTimeLimit * 0.8) {
      dom.stopwatchClock.style.color = '#fbbf24';
    } else {
      dom.stopwatchClock.style.color = '#38bdf8';
    }
  }

  function startStopwatch() {
    if (state.isTimerRunning) return;
    state.isTimerRunning = true;
    dom.timerStartPauseBtn.textContent = 'Pause';
    dom.timerStartPauseBtn.style.backgroundColor = '#f59e0b';

    state.timerIntervalId = setInterval(() => {
      state.elapsedSeconds += 1;
      updateStopwatchDisplay();
    }, 1000);
  }

  function pauseStopwatch() {
    if (!state.isTimerRunning) return;
    state.isTimerRunning = false;
    clearInterval(state.timerIntervalId);
    state.timerIntervalId = null;
    dom.timerStartPauseBtn.textContent = 'Resume';
    dom.timerStartPauseBtn.style.backgroundColor = '#2563eb';
  }

  function resetStopwatch() {
    pauseStopwatch();
    state.elapsedSeconds = 0;
    dom.timerStartPauseBtn.textContent = 'Start';
    dom.timerStartPauseBtn.style.backgroundColor = '#2563eb';
    updateStopwatchDisplay();
  }

  function setTaskMode(limitSeconds, isTextual) {
    state.taskTimeLimit = limitSeconds;
    dom.clockLimitLabel.textContent = isTextual ? '05:00' : '04:00';
    if (isTextual) {
      dom.taskModeTextual.classList.add('active');
      dom.taskModeVideo.classList.remove('active');
    } else {
      dom.taskModeVideo.classList.add('active');
      dom.taskModeTextual.classList.remove('active');
    }
    updateStopwatchDisplay();
  }

  // =========================================================================
  // DRES Connection & History Management
  // =========================================================================

  async function fetchDresStatus() {
    try {
      const res = await fetch('/api/dres/status');
      if (!res.ok) return;
      const data = await res.json();
      state.dresStatus = data;

      // Update Header Pill
      if (data.is_authenticated) {
        dom.dresConnectionPill.className = 'dres-status-pill live';
        dom.dresStatusText.textContent = `LIVE: ${data.session_id.substring(0, 8)}...`;
        dom.subDryRunCheck.checked = false;
      } else {
        dom.dresConnectionPill.className = 'dres-status-pill dry-run';
        dom.dresStatusText.textContent = 'DRY-RUN';
        dom.subDryRunCheck.checked = true;
      }

      // Populate config form
      if (data.base_url) dom.dresBaseUrl.value = data.base_url;
      if (data.evaluation_id) dom.dresEvalId.value = data.evaluation_id;
      if (dom.dresCollectionName) dom.dresCollectionName.value = data.collection_name || '';
      if (data.session_id) dom.dresSessionId.value = data.session_id;

      renderSubmissionHistory(data.history || []);
    } catch (err) {
      console.warn('[DRES] Could not fetch status:', err);
    }
  }

  async function saveDresConfiguration() {
    const payload = {
      base_url: dom.dresBaseUrl.value.trim(),
      evaluation_id: dom.dresEvalId.value.trim(),
      collection_name: dom.dresCollectionName ? dom.dresCollectionName.value.trim() : '',
      session_id: dom.dresSessionId.value.trim(),
      username: dom.dresUsername.value.trim(),
      password: dom.dresPassword.value.trim()
    };

    dom.saveDresConfigBtn.textContent = 'Connecting...';
    try {
      const res = await fetch('/api/dres/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Connection failed');

      alert('[OK] DRES session updated successfully!');
      dom.dresSettingsDrawer.classList.add('hidden');
      await fetchDresStatus();
    } catch (err) {
      alert(`[ERROR] DRES Configuration failed: ${err.message}`);
    } finally {
      dom.saveDresConfigBtn.textContent = 'Connect / Login';
    }
  }

  async function clearDresCache() {
    if (!confirm('Clear local duplicate cache and submission history for this competition round?')) return;
    try {
      const res = await fetch('/api/dres/clear-cache', { method: 'POST' });
      if (res.ok) {
        state.wrongAttempts = 0;
        calculateScoreDecay();
        await fetchDresStatus();
        alert('[OK] Round cache cleared.');
      }
    } catch (err) {
      console.error(err);
    }
  }

  function renderSubmissionHistory(historyList) {
    dom.historyCountBadge.textContent = `${historyList.length} submissions`;
    if (!historyList || historyList.length === 0) {
      dom.submissionHistoryFeed.innerHTML = '<div class="history-empty-placeholder">No submissions recorded in this session.</div>';
      return;
    }

    dom.submissionHistoryFeed.innerHTML = '';
    historyList.forEach(entry => {
      const item = document.createElement('div');
      item.className = 'history-entry-item';

      const status = (entry.status || 'SUBMITTED').toUpperCase();
      let badgeClass = 'dry-run';
      if (status === 'CORRECT' || status === 'ACCEPTED') badgeClass = 'correct';
      else if (status === 'WRONG' || status === 'REJECTED') badgeClass = 'wrong';
      else if (status.includes('DUPLICATE')) badgeClass = 'duplicate';

      item.innerHTML = `
        <div class="history-details">
          <span class="history-vid">${entry.video_id}</span>
          <span class="history-ms">${entry.start_ms}ms - ${entry.end_ms}ms</span>
        </div>
        <span class="history-badge ${badgeClass}">${status}</span>
      `;
      dom.submissionHistoryFeed.appendChild(item);
    });
  }

  // =========================================================================
  // Target Coordinates & Range Presets
  // =========================================================================

  function setActiveTarget(candidate, autoPreset = 'tight') {
    if (!candidate) return;
    state.activeCandidate = candidate;
    state.activeVideoId = candidate.video_id;

    dom.targetStatusBadge.textContent = 'TARGET ACTIVE';
    dom.targetStatusBadge.className = 'target-status-badge active';
    dom.targetVideoId.value = candidate.video_id;
    dom.targetVideoFilterLabel.textContent = candidate.video_id;

    const start = Number(candidate.start_sec) || 0.0;
    const rawEnd = Number(candidate.end_sec) || (start + 5.0);
    const seq = getSequenceBounds(candidate);

    if (seq) {
      updateTargetInputs(seq.startSec, seq.endSec);
    } else if (autoPreset === 'tight') {
      applyPresetTight(start, rawEnd);
    } else if (autoPreset === 'shot') {
      applyPresetShot(start, rawEnd);
    } else {
      applyPresetWindow(start, rawEnd);
    }

    // Highlight card or strip hit in grid
    document.querySelectorAll('.candidate-card, .video-hit-thumb-card').forEach(card => {
      if (card.dataset.kfid === candidate.keyframe_id) {
        card.classList.add('active-target');
      } else {
        card.classList.remove('active-target');
      }
    });
  }

  function updateTargetInputs(startSec, endSec) {
    const s = Math.max(0, Number(startSec) || 0);
    const e = Math.max(s, Number(endSec) || s);

    state.targetStartSec = s;
    state.targetEndSec = e;

    dom.targetStartSec.value = s.toFixed(2);
    dom.targetEndSec.value = e.toFixed(2);

    const dur = (e - s).toFixed(2);
    dom.targetDurationVal.textContent = `${dur}s`;

    const sMs = secondsToMs(s);
    const eMs = secondsToMs(e);
    dom.targetMsBounds.textContent = `${sMs}ms - ${eMs}ms`;
  }

  function applyPresetTight(centerStart, centerEnd) {
    const center = ((Number(centerStart) || 0) + (Number(centerEnd) || 0)) / 2;
    const s = Math.max(0, center - 0.5);
    const e = center + 0.5;
    updateTargetInputs(s, e);
  }

  function applyPresetShot(shotStart, shotEnd) {
    updateTargetInputs(shotStart, shotEnd);
  }

  function applyPresetWindow(centerStart, centerEnd) {
    const center = ((Number(centerStart) || 0) + (Number(centerEnd) || 0)) / 2;
    const s = Math.max(0, center - 2.5);
    const e = center + 2.5;
    updateTargetInputs(s, e);
  }

  // =========================================================================
  // DRES Submission Core Handler
  // =========================================================================

  async function submitKisPayload(videoId, startSec, endSec) {
    const cleanId = videoId.replace(/\.mp4$/i, '').trim();
    if (!cleanId) {
      alert('[ERROR] Please select or enter a valid Video ID.');
      return;
    }

    const payload = {
      video_id: cleanId,
      start_sec: Number(startSec) || 0.0,
      end_sec: Number(endSec) || 0.0,
      evaluation_id: dom.dresEvalId.value.trim() || state.dresStatus.evaluation_id,
      collection_name: (dom.dresCollectionName ? dom.dresCollectionName.value.trim() : '') || state.dresStatus.collection_name || null,
      dry_run: dom.subDryRunCheck.checked,
      allow_duplicate: dom.subAllowDuplicateCheck.checked
    };

    const sMs = secondsToMs(payload.start_sec);
    const eMs = secondsToMs(payload.end_sec);
    console.log(`[KIS SUBMIT] Sending ${cleanId} [${sMs}ms - ${eMs}ms]...`);

    try {
      const res = await fetch('/api/dres/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Submission request rejected');
      }

      const status = (data.status || 'SUBMITTED').toUpperCase();
      console.log(`[KIS RESPONSE] ${status}:`, data);

      if (status === 'WRONG' || status === 'REJECTED') {
        state.wrongAttempts += 1;
        calculateScoreDecay();
      }

      await fetchDresStatus();
      return data;
    } catch (err) {
      alert(`[SUBMISSION ERROR] ${err.message}`);
      throw err;
    }
  }

  async function submitCurrentTargetRange() {
    const vid = dom.targetVideoId.value.trim();
    const s = parseFloat(dom.targetStartSec.value);
    const e = parseFloat(dom.targetEndSec.value);

    dom.submitTargetRangeBtn.disabled = true;
    try {
      await submitKisPayload(vid, s, e);
    } finally {
      dom.submitTargetRangeBtn.disabled = false;
    }
  }

  async function submitPlayheadInterval() {
    let vid = state.activeVideoId || dom.targetVideoId.value.trim();
    if (!vid && state.activeCandidate) vid = state.activeCandidate.video_id;

    if (!vid) {
      alert('[ERROR] No active video selected to submit playhead.');
      return;
    }

    const currTime = (dom.modalVideoPlayer && dom.modalVideoPlayer.readyState >= 1)
      ? dom.modalVideoPlayer.currentTime
      : (state.lastSeekSec || state.targetStartSec || 0.0);
    const s = Math.max(0, currTime - 0.5);
    const e = currTime + 0.5;

    updateTargetInputs(s, e);
    await submitKisPayload(vid, s, e);
  }

  // =========================================================================
  // Task 06D: Automated Query Translation & Selective Cue Protection
  // =========================================================================

  async function translateCurrentQuery(force = false) {
    const raw = dom.queryInput.value.trim();
    const rawScene2 = dom.scene2Input ? dom.scene2Input.value.trim() : '';
    const rawNegative = dom.negativeQueryInput ? dom.negativeQueryInput.value.trim() : '';
    if (!raw && !rawScene2 && !rawNegative) return raw;

    // Skip if identical to currently displayed translation unless forced
    const s1Same = !raw || (state.lastTranslation.translated && raw === state.lastTranslation.translated);
    const s2Same = !rawScene2 || (state.lastTranslation.translatedScene2 && rawScene2 === state.lastTranslation.translatedScene2);
    const negSame = !rawNegative || (state.lastTranslation.translatedNegative && rawNegative === state.lastTranslation.translatedNegative);
    if (!force && s1Same && s2Same && negSame) {
      return raw;
    }

    if (dom.translateQueryBtn) {
      dom.translateQueryBtn.classList.add('translating');
      dom.translateQueryBtn.textContent = '...';
    }

    try {
      const translateText = async (text) => {
        if (!text) return text;
        const res = await fetch('/api/translate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: text, source_lang: 'auto', target_lang: 'en' })
        });
        if (!res.ok) return text;
        const data = await res.json();
        return (data.translated_query || '').trim() || text;
      };

      const translated = s1Same ? raw : await translateText(raw);
      const translatedScene2 = s2Same ? rawScene2 : await translateText(rawScene2);
      const translatedNegative = negSame ? rawNegative : await translateText(rawNegative);

      const changed = (
        (translated && translated !== raw) ||
        (translatedScene2 && translatedScene2 !== rawScene2) ||
        (translatedNegative && translatedNegative !== rawNegative)
      );
      if (changed) {
        state.lastTranslation = {
          original: raw || state.lastTranslation.original,
          translated: translated || state.lastTranslation.translated,
          originalScene2: rawScene2 || state.lastTranslation.originalScene2,
          translatedScene2: translatedScene2 || state.lastTranslation.translatedScene2,
          originalNegative: rawNegative || state.lastTranslation.originalNegative,
          translatedNegative: translatedNegative || state.lastTranslation.translatedNegative
        };
        if (raw) dom.queryInput.value = translated;
        if (rawScene2 && dom.scene2Input) dom.scene2Input.value = translatedScene2;
        if (rawNegative && dom.negativeQueryInput) dom.negativeQueryInput.value = translatedNegative;

        // Display translation diff banner
        if (dom.translationDiffBanner && dom.diffOriginalText && dom.diffTranslatedText) {
          const origParts = [raw, rawScene2 ? `>> ${rawScene2}` : '', rawNegative ? `(-v: ${rawNegative})` : ''].filter(Boolean);
          const transParts = [translated, translatedScene2 ? `>> ${translatedScene2}` : '', translatedNegative ? `(-v: ${translatedNegative})` : ''].filter(Boolean);
          dom.diffOriginalText.textContent = origParts.join(' ');
          dom.diffTranslatedText.textContent = transParts.join(' ');
          dom.translationDiffBanner.classList.remove('hidden');
        }
      }
      return translated;
    } catch (err) {
      console.warn('[TRANSLATE WARN] Translation request failed:', err);
      return raw;
    } finally {
      if (dom.translateQueryBtn) {
        dom.translateQueryBtn.classList.remove('translating');
        dom.translateQueryBtn.textContent = 'VI➜EN';
      }
    }
  }

  function revertTranslation() {
    const lt = state.lastTranslation;
    if (lt.original || lt.originalScene2 || lt.originalNegative) {
      if (lt.original !== undefined) dom.queryInput.value = lt.original || '';
      if (dom.scene2Input && lt.originalScene2 !== undefined) {
        dom.scene2Input.value = lt.originalScene2 || '';
      }
      if (dom.negativeQueryInput && lt.originalNegative !== undefined) {
        dom.negativeQueryInput.value = lt.originalNegative || '';
      }
      if (dom.translationDiffBanner) {
        dom.translationDiffBanner.classList.add('hidden');
      }
      state.lastTranslation = {
        original: '',
        translated: '',
        originalScene2: '',
        translatedScene2: '',
        originalNegative: '',
        translatedNegative: ''
      };
      executeSearch(true); // skipAutoTranslate = true to prevent re-translation loop
    }
  }

  function dismissTranslationDiff() {
    if (dom.translationDiffBanner) {
      dom.translationDiffBanner.classList.add('hidden');
    }
  }

  // =========================================================================
  // Task 06D: Competition Query History & Iteration Chips
  // =========================================================================

  const QUERY_HISTORY_KEY = 'kis_competition_query_history';
  const MAX_HISTORY_ITEMS = 15;

  function loadQueryHistory() {
    try {
      const saved = localStorage.getItem(QUERY_HISTORY_KEY);
      if (!saved) return [];
      const list = JSON.parse(saved);
      return Array.isArray(list) ? list.slice(0, MAX_HISTORY_ITEMS) : [];
    } catch (e) {
      return [];
    }
  }

  function saveQueryToHistory(queryStr) {
    const q = (queryStr || '').trim();
    if (!q) return;

    try {
      let history = loadQueryHistory();
      history = history.filter(item => item.toLowerCase() !== q.toLowerCase());
      history.unshift(q);
      if (history.length > MAX_HISTORY_ITEMS) {
        history = history.slice(0, MAX_HISTORY_ITEMS);
      }
      localStorage.setItem(QUERY_HISTORY_KEY, JSON.stringify(history));
      renderQueryHistory();
    } catch (e) {
      console.warn('[HISTORY WARN] Failed to save query history to localStorage:', e);
    }
  }

  function renderQueryHistory() {
    if (!dom.historyChipsScroll) return;
    const history = loadQueryHistory();
    dom.historyChipsScroll.innerHTML = '';

    if (history.length === 0) {
      const placeholder = document.createElement('span');
      placeholder.style.color = 'var(--text-dim)';
      placeholder.style.fontSize = '10.5px';
      placeholder.textContent = 'None';
      dom.historyChipsScroll.appendChild(placeholder);
      return;
    }

    history.forEach(item => {
      const chip = document.createElement('button');
      chip.className = 'history-chip';
      chip.title = `Run: ${item}`;
      chip.textContent = item.length > 45 ? `${item.slice(0, 42)}...` : item;

      chip.addEventListener('click', () => {
        clearReferenceKeyframe();
        dom.queryInput.value = item;
        document.querySelectorAll('.history-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        executeSearch();
      });

      dom.historyChipsScroll.appendChild(chip);
    });
  }

  function clearQueryHistory() {
    localStorage.removeItem(QUERY_HISTORY_KEY);
    renderQueryHistory();
  }

  // =========================================================================
  // Task 07B: Similarity Reference, Active Batch Scope & Video Exclusion
  // =========================================================================

  function loadAllowedBatches() {
    try {
      const saved = localStorage.getItem(ALLOWED_BATCHES_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) {
          state.allowedBatches = new Set(parsed.filter(b => DRES_OFFICIAL_BATCHES.has(b)));
          renderBatchScopeUI();
          return;
        }
      }
    } catch (err) {
      console.warn('[BATCH SCOPE] Failed to load saved batches:', err);
    }
    state.allowedBatches = new Set(ALL_BATCH_LIST);
    renderBatchScopeUI();
  }

  function saveAllowedBatches() {
    try {
      localStorage.setItem(ALLOWED_BATCHES_STORAGE_KEY, JSON.stringify(Array.from(state.allowedBatches)));
    } catch (err) {
      console.warn('[BATCH SCOPE] Failed to persist batches:', err);
    }
  }

  function formatBatchScopeSummary() {
    const count = state.allowedBatches ? state.allowedBatches.size : 0;
    if (count === ALL_BATCH_LIST.length) return `All (${count})`;
    if (count === 0) return 'None (0)';
    const sorted = ALL_BATCH_LIST.filter(b => state.allowedBatches.has(b));
    if (count === 12 && sorted[0] === 'L01' && sorted[11] === 'L12') return 'L01-L12 (12)';
    if (count === 12 && sorted[0] === 'L13' && sorted[11] === 'L24') return 'L13-L24 (12)';
    if (count <= 2) return sorted.join(', ');
    return `${sorted.slice(0, 2).join(',')} (+${count - 2})`;
  }

  function renderBatchScopeUI() {
    if (!state.allowedBatches) state.allowedBatches = new Set(ALL_BATCH_LIST);
    if (dom.batchScopeLabel) {
      dom.batchScopeLabel.textContent = formatBatchScopeSummary();
    }
    if (dom.batchScopeBtn) {
      dom.batchScopeBtn.classList.toggle('filtered', state.allowedBatches.size < ALL_BATCH_LIST.length);
    }
    if (!dom.batchCheckboxGrid) return;

    dom.batchCheckboxGrid.innerHTML = '';
    ALL_BATCH_LIST.forEach(batchId => {
      const btn = document.createElement('button');
      btn.type = 'button';
      const isSelected = state.allowedBatches.has(batchId);
      btn.className = `batch-chip-toggle ${isSelected ? 'selected' : ''}`;
      btn.textContent = batchId;
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (state.allowedBatches.has(batchId)) {
          state.allowedBatches.delete(batchId);
        } else {
          state.allowedBatches.add(batchId);
        }
        saveAllowedBatches();
        renderBatchScopeUI();
      });
      dom.batchCheckboxGrid.appendChild(btn);
    });
  }

  function getAllowedBatchesPayload() {
    if (!state.allowedBatches || state.allowedBatches.size === ALL_BATCH_LIST.length) {
      return null;
    }
    return Array.from(state.allowedBatches);
  }

  function updateExcludedVideosUI() {
    if (!dom.excludedVideosBar || !dom.excludedVideosCountLabel) return;
    const count = state.excludedVideos.size;
    if (count === 0) {
      dom.excludedVideosBar.classList.add('hidden');
      return;
    }
    dom.excludedVideosCountLabel.textContent = `Hidden: ${count} video${count > 1 ? 's' : ''}`;
    dom.excludedVideosBar.classList.remove('hidden');
  }

  function hideVideoFromResults(videoId) {
    if (!videoId) return;
    state.excludedVideos.add(videoId);
    if (state.activeVideoId === videoId) {
      state.activeVideoId = null;
      if (dom.targetVideoOnly) dom.targetVideoOnly.checked = false;
      if (dom.targetVideoFilterLabel) dom.targetVideoFilterLabel.textContent = 'This Video';
    }
    updateExcludedVideosUI();
    renderCandidateGrid();
  }

  function resetExcludedVideos() {
    state.excludedVideos.clear();
    updateExcludedVideosUI();
    renderCandidateGrid();
  }

  const DEFAULT_QUERY_PLACEHOLDER = 'Visual query (VI/EN) or steering prompt when Ref active...';

  function setReferenceKeyframe(targetObj) {
    if (!targetObj || !targetObj.keyframe_id) return;
    const ts = targetObj.timestamp_sec !== undefined ? Number(targetObj.timestamp_sec) : Number(targetObj.start_sec || 0);
    state.referenceKeyframe = {
      keyframe_id: targetObj.keyframe_id,
      video_id: targetObj.video_id || '',
      timestamp_sec: ts
    };
    const labelText = `${state.referenceKeyframe.video_id} @ ${formatTime(ts)}`;
    if (dom.refKeyframePill && dom.refKeyframeLabel) {
      dom.refKeyframeLabel.textContent = `Ref: ${labelText}`;
      dom.refKeyframePill.classList.remove('hidden');
    }
    if (dom.simActiveBar && dom.simActiveLabel) {
      dom.simActiveLabel.textContent = `Sim Anchor: ${labelText}`;
      dom.simActiveBar.classList.remove('hidden');
    }
    if (dom.queryInput) {
      dom.queryInput.placeholder = 'Optional steering text for Sim (e.g. night, red car) — click Exit Sim to leave';
    }
    if (state.isVideoModalOpen && state.layoutMode === 'popup') {
      closeVideoModal();
    }
    executeSearch();
  }

  function clearReferenceKeyframe(rerunIfQueryPresent = false) {
    const hadRef = Boolean(state.referenceKeyframe);
    state.referenceKeyframe = null;
    if (dom.refKeyframePill) {
      dom.refKeyframePill.classList.add('hidden');
    }
    if (dom.simActiveBar) {
      dom.simActiveBar.classList.add('hidden');
    }
    if (dom.queryInput) {
      dom.queryInput.placeholder = DEFAULT_QUERY_PLACEHOLDER;
    }
    document.querySelectorAll('.btn-sim-card.active').forEach(btn => {
      btn.classList.remove('active');
      btn.title = 'Find visually similar frames (0ms)';
    });

    if (!hadRef || !rerunIfQueryPresent) return;

    const hasText = Boolean(dom.queryInput && dom.queryInput.value.trim());
    const hasOcr = Boolean(dom.ocrQueryInput && dom.ocrQueryInput.value.trim());
    const hasScene2 = Boolean(dom.scene2Input && dom.scene2Input.value.trim());
    if (hasText || hasOcr || hasScene2) {
      executeSearch();
    } else if (dom.candidateQueryEcho) {
      dom.candidateQueryEcho.textContent = 'Sim exited — ready for query';
    }
  }

  function parseNegativeQueries() {
    const raw = dom.negativeQueryInput ? dom.negativeQueryInput.value.trim() : '';
    if (!raw) return [];
    return raw.split(',').map(s => s.trim()).filter(Boolean);
  }

  // =========================================================================
  // Multimodal Search & High-Density Candidate Grid
  // =========================================================================

  async function executeSearch(skipAutoTranslate = false) {
    let query = dom.queryInput.value.trim();
    const ocrText = dom.ocrQueryInput ? dom.ocrQueryInput.value.trim() : '';
    const ocrMode = dom.ocrRoleSelect ? dom.ocrRoleSelect.value : 'boost';
    let scene2Text = dom.scene2Input ? dom.scene2Input.value.trim() : '';
    const refKf = state.referenceKeyframe;

    if (!query && !ocrText && !scene2Text && !refKf) {
      dom.queryInput.focus();
      return;
    }

    // Auto-translate visual descriptions & negative cues (OCR input stays intact)
    const rawNeg = dom.negativeQueryInput ? dom.negativeQueryInput.value.trim() : '';
    if (!skipAutoTranslate && dom.autoTranslateCheck && dom.autoTranslateCheck.checked && (query || scene2Text || rawNeg)) {
      await translateCurrentQuery(false);
      query = dom.queryInput.value.trim();
      scene2Text = dom.scene2Input ? dom.scene2Input.value.trim() : '';
    }

    const negList = parseNegativeQueries();
    const allowedBatchesPayload = getAllowedBatchesPayload();
    const excludedVideosPayload = state.excludedVideos.size > 0 ? Array.from(state.excludedVideos) : null;

    const gapStr = dom.sequenceGapSelect ? dom.sequenceGapSelect.value : '1-30';
    const [minGapStr, maxGapStr] = gapStr.split('-');
    const minGapSec = parseFloat(minGapStr) || 1.0;
    const maxGapSec = parseFloat(maxGapStr) || 30.0;
    const anchorStage = dom.sequenceAnchorSelect ? (parseInt(dom.sequenceAnchorSelect.value, 10) || 0) : 0;

    const historyDisplay = [
      query,
      scene2Text ? `>> ${scene2Text}` : '',
      ocrText ? `ocr: ${ocrText}` : '',
      negList.length ? `-v: ${negList.join(', ')}` : ''
    ].filter(Boolean).join(' ');
    if (query || scene2Text || ocrText) {
      saveQueryToHistory(historyDisplay);
    }

    dom.gridLoadingOverlay.classList.remove('hidden');
    dom.candidateQueryEcho.textContent = refKf
      ? `Sim: ${refKf.video_id} @ ${formatTime(refKf.timestamp_sec)}${query ? ` + "${query}"` : ''}`
      : `"${historyDisplay}" (${state.searchMode}${ocrText ? ` + ocr:${ocrMode}` : ''})`;

    const vidFilter = (dom.targetVideoOnly.checked && state.activeVideoId) ? state.activeVideoId : null;

    try {
      let res;
      if (refKf) {
        const simPayload = {
          keyframe_id: refKf.keyframe_id,
          steer_text: query || null,
          steer_alpha: 0.3,
          negative_visual_queries: negList,
          top_k: state.resultsLimit,
          video_id: vidFilter,
          allowed_batches: allowedBatchesPayload,
          excluded_videos: excludedVideosPayload
        };
        res = await fetch('/api/search/similar', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(simPayload)
        });
      } else {
        const useStructuredPost = Boolean(
          ocrText || scene2Text || negList.length || query.includes('>>') ||
          allowedBatchesPayload !== null || excludedVideosPayload !== null
        );
        if (useStructuredPost) {
          const bodyPayload = {
            mode: state.searchMode,
            top_k: state.resultsLimit,
            video_id: vidFilter,
            ocr_text: ocrText,
            ocr_mode: ocrMode,
            negative_visual_queries: negList,
            anchor_stage: anchorStage,
            min_gap_sec: minGapSec,
            max_gap_sec: maxGapSec,
            allowed_batches: allowedBatchesPayload,
            excluded_videos: excludedVideosPayload
          };

          if (scene2Text) {
            bodyPayload.scenes = [
              { visual: query, ocr: ocrText },
              { visual: scene2Text }
            ];
          } else {
            bodyPayload.query = query;
          }

          res = await fetch('/api/search/multimodal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(bodyPayload)
          });
        } else {
          const params = new URLSearchParams({
            query: query,
            mode: state.searchMode,
            top_k: String(state.resultsLimit)
          });
          if (vidFilter) params.append('video_id', vidFilter);
          res = await fetch(`/api/search/multimodal?${params.toString()}`);
        }
      }

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Search query failed');
      }

      const data = await res.json();
      state.allCandidates = data.candidates || [];
      renderCandidateGrid();
    } catch (err) {
      alert(`[SEARCH ERROR] ${err.message}`);
    } finally {
      dom.gridLoadingOverlay.classList.add('hidden');
    }
  }

  function getSequenceBounds(candidate) {
    if (!candidate || !Array.isArray(candidate.stage_hits) || candidate.stage_hits.length < 2) {
      return null;
    }
    const s0 = candidate.stage_hits[0];
    const s1 = candidate.stage_hits[1];
    const t0 = Number(s0.timestamp_sec || 0);
    const t1 = Number(s1.timestamp_sec || 0);
    const startSec = Math.max(0, Math.min(t0, t1));
    const maxSec = Math.max(t0, t1);
    // Cap default KIS range at 20s max span while keeping at least 1s width
    const endSec = Math.max(startSec + 1.0, Math.min(maxSec, startSec + 20.0));
    const deltaSec = (t1 - t0).toFixed(1);
    return { isSeq: true, s0, s1, t0, t1, startSec, endSec, deltaSec };
  }

  function toggleOnlyVideoFilter(videoId) {
    if (!videoId) return;
    if (dom.targetVideoOnly.checked && state.activeVideoId === videoId) {
      dom.targetVideoOnly.checked = false;
      dom.targetVideoFilterLabel.textContent = 'This Video';
    } else {
      state.activeVideoId = videoId;
      dom.targetVideoOnly.checked = true;
      dom.targetVideoFilterLabel.textContent = videoId;
    }
    executeSearch();
  }

  function toggleSimCandidate(candidate) {
    if (!candidate || !candidate.keyframe_id) return;
    if (state.referenceKeyframe && state.referenceKeyframe.keyframe_id === candidate.keyframe_id) {
      clearReferenceKeyframe(true);
    } else {
      setReferenceKeyframe(candidate);
    }
  }

  function setViewMode(mode, rerender = true) {
    const cleanMode = mode === 'by_video' ? 'by_video' : 'frames';
    state.viewMode = cleanMode;
    try {
      localStorage.setItem(VIEW_MODE_STORAGE_KEY, cleanMode);
    } catch (e) {
      console.warn('[VIEW] Failed saving view mode preference:', e);
    }
    if (dom.viewModeFramesBtn) {
      dom.viewModeFramesBtn.classList.toggle('active', cleanMode === 'frames');
    }
    if (dom.viewModeVideoBtn) {
      dom.viewModeVideoBtn.classList.toggle('active', cleanMode === 'by_video');
    }
    if (dom.candidateGrid) {
      dom.candidateGrid.classList.toggle('by-video-mode', cleanMode === 'by_video');
    }
    if (rerender && state.allCandidates.length > 0) {
      renderCandidateGrid();
    }
  }

  function loadViewMode() {
    let saved = 'frames';
    try {
      const raw = localStorage.getItem(VIEW_MODE_STORAGE_KEY);
      if (raw === 'by_video' || raw === 'frames') saved = raw;
    } catch (e) {
      saved = 'frames';
    }
    setViewMode(saved, false);
  }

  function groupCandidatesByVideo(candidates, maxHitsPerVideo = 7) {
    const buckets = new Map();
    candidates.forEach(item => {
      if (!item || !item.video_id) return;
      if (!buckets.has(item.video_id)) buckets.set(item.video_id, []);
      buckets.get(item.video_id).push(item);
    });

    const groups = Array.from(buckets.entries()).map(([videoId, hits]) => {
      let topScore = 0;
      hits.forEach(h => {
        const s = Number(h.score || 0);
        if (s > topScore) topScore = s;
      });
      const topHits = hits
        .slice()
        .sort((a, b) => Number(b.score || 0) - Number(a.score || 0))
        .slice(0, maxHitsPerVideo)
        .sort((a, b) => Number(a.start_sec || 0) - Number(b.start_sec || 0));
      return {
        video_id: videoId,
        top_score: topScore,
        total_hits: hits.length,
        hits: topHits
      };
    });

    groups.sort((a, b) => b.top_score - a.top_score);
    return groups.map((g, idx) => ({ ...g, rank: idx + 1 }));
  }

  function createVideoStripCard(group) {
    const card = document.createElement('div');
    card.className = 'video-strip-card';
    card.dataset.vid = group.video_id;

    let rankClass = '';
    if (group.rank === 1) rankClass = 'gold';
    else if (group.rank === 2) rankClass = 'silver';
    else if (group.rank === 3) rankClass = 'bronze';

    const batch = getVideoBatch(group.video_id);
    const isLockedThis = Boolean(dom.targetVideoOnly && dom.targetVideoOnly.checked && state.activeVideoId === group.video_id);

    card.innerHTML = `
      <div class="video-strip-meta">
        <div class="video-strip-top">
          <div class="video-strip-rank-row">
            <span class="strip-rank-badge ${rankClass}">#${group.rank}</span>
            <span class="strip-batch-tag">${batch}</span>
          </div>
          <div class="video-strip-id">${group.video_id}</div>
          <div class="video-strip-score-line">
            <span>Top: ${Number(group.top_score || 0).toFixed(4)}</span>
            <span>${group.hits.length}/${group.total_hits} hits</span>
          </div>
        </div>
        <div class="video-strip-actions">
          <button type="button" class="btn-card-aux btn-only-video ${isLockedThis ? 'active' : ''}" title="Toggle search lock inside ${group.video_id}">Only</button>
          <button type="button" class="btn-card-aux btn-hide-video" title="Hide all results from ${group.video_id}">Hide</button>
        </div>
      </div>
      <div class="video-strip-hits-row"></div>
    `;

    card.querySelector('.btn-only-video').addEventListener('click', (e) => {
      e.stopPropagation();
      toggleOnlyVideoFilter(group.video_id);
    });
    card.querySelector('.btn-hide-video').addEventListener('click', (e) => {
      e.stopPropagation();
      hideVideoFromResults(group.video_id);
    });

    const hitsRow = card.querySelector('.video-strip-hits-row');
    group.hits.forEach(hit => {
      const seq = getSequenceBounds(hit);
      const isSimThis = Boolean(state.referenceKeyframe && state.referenceKeyframe.keyframe_id === hit.keyframe_id);
      const thumbEl = document.createElement('div');
      thumbEl.className = 'video-hit-thumb-card';
      thumbEl.dataset.kfid = hit.keyframe_id || '';

      let mediaInner = '';
      if (seq) {
        mediaInner = `
          <div class="video-hit-media dual-frame-wrapper" title="Click Stage 1 (${formatTime(seq.t0)}) or Stage 2 (${formatTime(seq.t1)})">
            <div class="dual-stage-pane" data-stage="0">
              <img src="${seq.s0.thumbnail_url || hit.thumbnail_url || ''}" alt="${hit.video_id} S1" loading="lazy" />
              <span class="dual-stage-badge s1">S1 ${formatTime(seq.t0)}</span>
            </div>
            <div class="dual-stage-pane" data-stage="1">
              <img src="${seq.s1.thumbnail_url || hit.thumbnail_url || ''}" alt="${hit.video_id} S2" loading="lazy" />
              <span class="dual-stage-badge s2">S2 ${formatTime(seq.t1)}</span>
            </div>
            <span class="dual-delta-badge">+${seq.deltaSec}s</span>
            <span class="video-hit-score">${Number(hit.score || 0).toFixed(4)}</span>
          </div>
        `;
      } else {
        mediaInner = `
          <div class="video-hit-media" title="Inspect ${hit.video_id} @ ${formatTime(hit.start_sec)}">
            <img src="${hit.thumbnail_url || ''}" alt="${hit.video_id}" loading="lazy" onerror="this.style.display='none'" />
            <span class="video-hit-time">${formatTime(hit.start_sec)}</span>
            <span class="video-hit-score">${Number(hit.score || 0).toFixed(4)}</span>
          </div>
        `;
      }

      thumbEl.innerHTML = `
        ${mediaInner}
        <div class="video-hit-footer">
          <button type="button" class="btn-hit-sim ${isSimThis ? 'active' : ''}" title="Find visually similar frames (0ms)">Sim</button>
          <button type="button" class="btn-hit-submit" title="1-Click KIS Submit">⚡ Submit</button>
        </div>
      `;

      const mediaBox = thumbEl.querySelector('.video-hit-media');
      if (seq) {
        const p0 = thumbEl.querySelector('.dual-stage-pane[data-stage="0"]');
        const p1 = thumbEl.querySelector('.dual-stage-pane[data-stage="1"]');
        if (p0) p0.addEventListener('click', () => { setActiveTarget(hit, 'shot'); openVideoModal(hit, false, seq.t0); });
        if (p1) p1.addEventListener('click', () => { setActiveTarget(hit, 'shot'); openVideoModal(hit, false, seq.t1); });
      } else if (mediaBox) {
        mediaBox.addEventListener('click', () => {
          setActiveTarget(hit, 'tight');
          openVideoModal(hit);
        });
      }

      thumbEl.querySelector('.btn-hit-sim').addEventListener('click', (e) => {
        e.stopPropagation();
        toggleSimCandidate(hit);
      });

      const subBtn = thumbEl.querySelector('.btn-hit-submit');
      subBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        setActiveTarget(hit, seq ? 'shot' : 'tight');
        subBtn.disabled = true;
        subBtn.textContent = '...';
        try {
          await submitKisPayload(hit.video_id, state.targetStartSec, state.targetEndSec);
        } finally {
          subBtn.disabled = false;
          subBtn.textContent = '⚡ Submit';
        }
      });

      hitsRow.appendChild(thumbEl);
    });

    return card;
  }

  function renderCandidateGrid() {
    let candidates = state.allCandidates;

    if (state.excludedVideos.size > 0) {
      candidates = candidates.filter(c => !state.excludedVideos.has(c.video_id));
    }
    if (state.allowedBatches && state.allowedBatches.size < ALL_BATCH_LIST.length) {
      candidates = candidates.filter(c => state.allowedBatches.has(getVideoBatch(c.video_id)));
    }

    const isByVideo = state.viewMode === 'by_video';
    if (dom.candidateGrid) {
      dom.candidateGrid.classList.toggle('by-video-mode', isByVideo);
    }

    if (candidates.length === 0) {
      dom.candidateTotalCount.textContent = '0';
      dom.candidateGrid.innerHTML = `
        <div class="grid-empty-state">
          <div class="empty-icon">⚠️</div>
          <h3>No Matching Candidates Found</h3>
          <p>Try broadening your query keywords, expanding Batch Scope, or resetting hidden videos.</p>
        </div>
      `;
      return;
    }

    dom.candidateGrid.innerHTML = '';
    if (isByVideo) {
      const groups = groupCandidatesByVideo(candidates, 7);
      dom.candidateTotalCount.textContent = `${groups.length} videos (${candidates.length} hits)`;
      groups.forEach(g => dom.candidateGrid.appendChild(createVideoStripCard(g)));
    } else {
      dom.candidateTotalCount.textContent = String(candidates.length);
      candidates.forEach((c, idx) => {
        const card = createCandidateCard(c, idx + 1);
        dom.candidateGrid.appendChild(card);
      });
    }

    // Auto-select #1 candidate coordinates as default target
    if (candidates.length > 0 && !state.activeCandidate) {
      setActiveTarget(candidates[0], getSequenceBounds(candidates[0]) ? 'shot' : 'tight');
    }
    if (state.activeVideoId) {
      renderTimelineHitMarkers(state.activeVideoId);
    }
  }

  function createCandidateCard(candidate, rankNum) {
    const card = document.createElement('div');
    card.className = 'candidate-card';
    card.dataset.kfid = candidate.keyframe_id || '';
    card.dataset.vid = candidate.video_id;

    // Rank styling
    let rankBadgeClass = '';
    if (rankNum === 1) rankBadgeClass = 'gold';
    else if (rankNum === 2) rankBadgeClass = 'silver';
    else if (rankNum === 3) rankBadgeClass = 'bronze';

    // Overlaid Consensus badge
    const matchedCues = Array.isArray(candidate.matched_cues)
      ? candidate.matched_cues.length
      : (candidate.matched_cues || 1);
    const consensusHtml = matchedCues > 1
      ? `<span class="badge-consensus-overlay" title="Matched ${matchedCues} independent cues">Consensus: ${matchedCues}</span>`
      : '';

    // Sequence Timeline Pill & Dual-Frame Preview (Task 07A + 07C)
    const seq = getSequenceBounds(candidate);
    let seqPillHtml = '';
    if (seq) {
      seqPillHtml = `<div class="card-sequence-pill" title="Chronological sequence match">S1 ${formatTime(seq.t0)} ➜ +${seq.deltaSec}s ➜ S2 ${formatTime(seq.t1)}</div>`;
    }

    // DRES Batch Badge
    const batch = getVideoBatch(candidate.video_id);
    const dresBadgeHtml = `<span class="badge-dres-batch-overlay">${batch}</span>`;

    // OCR snippet preview
    const ocrSnippet = candidate.text_detected ? candidate.text_detected.trim() : '';
    const ocrHtml = ocrSnippet 
      ? `<div class="card-ocr-snippet" title="${ocrSnippet}">OCR: ${ocrSnippet}</div>` 
      : '';

    const dur = ((candidate.end_sec || 0) - (candidate.start_sec || 0)).toFixed(1);
    const isLockedThis = Boolean(dom.targetVideoOnly && dom.targetVideoOnly.checked && state.activeVideoId === candidate.video_id);
    const isSimThis = Boolean(state.referenceKeyframe && state.referenceKeyframe.keyframe_id === candidate.keyframe_id);

    const mediaWrapperHtml = seq
      ? `
      <div class="card-media-wrapper dual-frame-wrapper" title="Click Stage 1 (${formatTime(seq.t0)}) or Stage 2 (${formatTime(seq.t1)}) to inspect">
        <span class="badge-rank-overlay ${rankBadgeClass}">#${rankNum}</span>
        ${consensusHtml}
        ${dresBadgeHtml}
        <div class="dual-stage-pane" data-stage="0" title="Open player @ Stage 1 (${formatTime(seq.t0)})">
          <img
            src="${seq.s0.thumbnail_url || candidate.thumbnail_url || ''}"
            alt="${candidate.video_id} S1"
            class="dual-stage-thumb"
            loading="lazy"
            onerror="this.style.display='none'"
          />
          <span class="dual-stage-badge s1">S1 ${formatTime(seq.t0)}</span>
        </div>
        <div class="dual-stage-pane" data-stage="1" title="Open player @ Stage 2 (${formatTime(seq.t1)})">
          <img
            src="${seq.s1.thumbnail_url || candidate.thumbnail_url || ''}"
            alt="${candidate.video_id} S2"
            class="dual-stage-thumb"
            loading="lazy"
            onerror="this.style.display='none'"
          />
          <span class="dual-stage-badge s2">S2 ${formatTime(seq.t1)}</span>
        </div>
        <span class="dual-delta-badge">+${seq.deltaSec}s</span>
      </div>
      `
      : `
      <div class="card-media-wrapper" title="Click to open video modal inspector">
        <span class="badge-rank-overlay ${rankBadgeClass}">#${rankNum}</span>
        ${consensusHtml}
        ${dresBadgeHtml}
        <img 
          src="${candidate.thumbnail_url || ''}" 
          alt="${candidate.video_id}" 
          class="card-thumbnail-img" 
          loading="lazy"
          onerror="this.style.display='none'"
        />
      </div>
      `;

    card.innerHTML = `
      ${mediaWrapperHtml}

      <div class="card-body">
        <div class="card-meta-row">
          <span class="card-vid">${candidate.video_id}</span>
          <span class="card-score-pill">${(candidate.score || 0).toFixed(4)}</span>
        </div>

        <div class="card-time-row">
          <span>${formatTime(candidate.start_sec)} - ${formatTime(candidate.end_sec)}</span>
          <span class="card-duration">(${dur}s)</span>
        </div>

        ${seqPillHtml}
        ${ocrHtml}

        <div class="card-actions-row">
          <button class="btn-card-aux btn-open-modal" title="Open modal player">Play</button>
          <button class="btn-card-aux btn-view-strip" title="View +-15s filmstrip">Strip</button>
          <button class="btn-card-aux btn-sim-card ${isSimThis ? 'active' : ''}" title="${isSimThis ? 'Click to exit similarity mode' : 'Find visually similar frames (0ms)'}">Sim</button>
          <button class="btn-card-aux btn-only-video ${isLockedThis ? 'active' : ''}" title="Toggle search lock inside ${candidate.video_id}">Only</button>
          <button class="btn-card-aux btn-hide-video" title="Hide all results from ${candidate.video_id}">Hide</button>
        </div>

        <button class="btn-card-submit-kis" title="1-Click Instant KIS Submit to DRES">
          <span>⚡ SUBMIT KIS</span>
        </button>
      </div>
    `;

    // Event Listeners on Card
    const mediaWrap = card.querySelector('.card-media-wrapper');
    const playBtn = card.querySelector('.btn-open-modal');
    const stripBtn = card.querySelector('.btn-view-strip');
    const simBtn = card.querySelector('.btn-sim-card');
    const onlyBtn = card.querySelector('.btn-only-video');
    const hideBtn = card.querySelector('.btn-hide-video');
    const submitBtn = card.querySelector('.btn-card-submit-kis');

    const handleOpenPlayer = (focusSecOverride = null) => {
      setActiveTarget(candidate, seq ? 'shot' : 'tight');
      openVideoModal(candidate, false, focusSecOverride);
    };

    if (seq) {
      const stage0Pane = card.querySelector('.dual-stage-pane[data-stage="0"]');
      const stage1Pane = card.querySelector('.dual-stage-pane[data-stage="1"]');
      if (stage0Pane) stage0Pane.addEventListener('click', () => handleOpenPlayer(seq.t0));
      if (stage1Pane) stage1Pane.addEventListener('click', () => handleOpenPlayer(seq.t1));
    } else if (mediaWrap) {
      mediaWrap.addEventListener('click', () => handleOpenPlayer(null));
    }

    playBtn.addEventListener('click', () => handleOpenPlayer(null));

    stripBtn.addEventListener('click', () => {
      setActiveTarget(candidate, seq ? 'shot' : 'tight');
      openVideoModal(candidate, true);
    });

    if (simBtn) {
      simBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleSimCandidate(candidate);
      });
    }

    onlyBtn.addEventListener('click', () => toggleOnlyVideoFilter(candidate.video_id));

    if (hideBtn) {
      hideBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        hideVideoFromResults(candidate.video_id);
      });
    }

    submitBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      setActiveTarget(candidate, seq ? 'shot' : 'tight');
      submitBtn.disabled = true;
      submitBtn.textContent = 'SUBMITTING...';
      try {
        await submitKisPayload(candidate.video_id, state.targetStartSec, state.targetEndSec);
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span>⚡ SUBMIT KIS</span>';
      }
    });

    return card;
  }

  // =========================================================================
  // Interactive Modal Video Inspector & Pop-up Player
  // =========================================================================

  function attachPlayerToModal() {
    if (dom.modalBody && dom.playerWrapper && dom.playerTransportBar) {
      if (dom.playerWrapper.parentElement !== dom.modalBody) {
        dom.modalBody.appendChild(dom.playerWrapper);
      }
      if (dom.playerTransportBar.parentElement !== dom.modalBody) {
        dom.modalBody.appendChild(dom.playerTransportBar);
      }
      if (dom.modalFilmstripSection && dom.modalFilmstripSection.parentElement !== dom.modalBody) {
        dom.modalBody.appendChild(dom.modalFilmstripSection);
      }
    }
  }

  function attachPlayerToDocked() {
    if (dom.dockedPlayerContainer && dom.playerWrapper && dom.playerTransportBar) {
      if (dom.playerWrapper.parentElement !== dom.dockedPlayerContainer) {
        dom.dockedPlayerContainer.appendChild(dom.playerWrapper);
      }
      if (dom.playerTransportBar.parentElement !== dom.dockedPlayerContainer) {
        dom.dockedPlayerContainer.appendChild(dom.playerTransportBar);
      }
      if (dom.modalFilmstripSection && dom.modalFilmstripSection.parentElement !== dom.dockedPlayerContainer) {
        dom.dockedPlayerContainer.appendChild(dom.modalFilmstripSection);
      }
    }
  }

  function openVideoModal(candidate, jumpToFilmstrip = false, focusSecOverride = null) {
    state.activeCandidate = candidate;
    state.activeVideoId = candidate.video_id;

    const targetSec = focusSecOverride !== null && focusSecOverride !== undefined
      ? Math.max(0, Number(focusSecOverride) || 0.0)
      : Math.max(0, Number(candidate.start_sec) || 0.0);
    state.lastSeekSec = targetSec;

    dom.modalVideoIdBadge.textContent = candidate.video_id;
    dom.modalHeading.textContent = `${candidate.video_id} @ ${formatTime(targetSec)}`;
    if (dom.dockedPlayerTitle) {
      dom.dockedPlayerTitle.textContent = `Inspector: ${candidate.video_id} @ ${formatTime(targetSec)}`;
    }

    const seq = getSequenceBounds(candidate);
    // Reset Mark In / Out cleanly (preserving [t1, t2] for sequential candidates)
    if (seq) {
      state.markInSec = seq.startSec;
      state.markOutSec = seq.endSec;
    } else {
      state.markInSec = targetSec;
      state.markOutSec = Number(candidate.end_sec) || (targetSec + 5.0);
    }
    updateMarkDisplay();

    // Zero-Popup Docked Cockpit vs Pop-up Modal
    if (state.layoutMode === 'docked') {
      state.isVideoModalOpen = false;
      attachPlayerToDocked();
      dom.dockedPlayerPanel.classList.remove('hidden');
      dom.videoModal.classList.add('hidden');
    } else {
      state.isVideoModalOpen = true;
      attachPlayerToModal();
      dom.videoModal.classList.remove('hidden');
      dom.dockedPlayerPanel.classList.add('hidden');
    }

    // Unfocus search bar or active inputs so single-hand hotkeys work cleanly
    if (document.activeElement && typeof document.activeElement.blur === 'function') {
      document.activeElement.blur();
    }

    // Set video source and smoothly seek after metadata is available
    const streamUrl = `/api/videos/${candidate.video_id}/stream`;
    const fullStreamUrl = window.location.origin + streamUrl;
    const player = dom.modalVideoPlayer;

    const applySeekAndPlay = () => {
      try {
        player.currentTime = targetSec;
        dom.videoTimelineSlider.value = targetSec;
        dom.modalTimeIndicator.textContent = `${formatTime(targetSec)} / ${formatTime(player.duration || 0)}`;
        renderTimelineHitMarkers(candidate.video_id);
        const p = player.play();
        if (p !== undefined) {
          p.catch(err => {
            console.warn('[PLAYER] Autoplay notice (click Play or press Space):', err.name);
          });
        }
      } catch (err) {
        console.warn('[PLAYER] Seek error:', err);
      }
    };

    if (player.src !== fullStreamUrl) {
      player.pause();
      player.src = streamUrl;
      player.addEventListener('loadedmetadata', applySeekAndPlay, { once: true });
    } else {
      applySeekAndPlay();
    }

    // Load Inline Neighbor Filmstrip (+-10s)
    loadTemporalFilmstrip(candidate.video_id, targetSec);
  }

  function closeVideoModal() {
    state.isVideoModalOpen = false;
    dom.videoModal.classList.add('hidden');
    if (state.layoutMode === 'docked') {
      attachPlayerToDocked();
      dom.dockedPlayerPanel.classList.remove('hidden');
    } else {
      dom.modalVideoPlayer.pause();
      dom.dockedPlayerPanel.classList.add('hidden');
      attachPlayerToModal();
    }
    if (dom.candidateGrid) {
      dom.candidateGrid.focus();
    }
  }

  function expandDockedToPopup() {
    state.isVideoModalOpen = true;
    attachPlayerToModal();
    dom.videoModal.classList.remove('hidden');
  }

  function toggleDockedLayout() {
    if (state.layoutMode === 'popup') {
      state.layoutMode = 'docked';
      state.isVideoModalOpen = false;
      dom.layoutModeLabel.textContent = 'Cockpit';
      attachPlayerToDocked();
      dom.videoModal.classList.add('hidden');
      dom.dockedPlayerPanel.classList.remove('hidden');
    } else {
      state.layoutMode = 'popup';
      dom.layoutModeLabel.textContent = 'Popup';
      dom.dockedPlayerPanel.classList.add('hidden');
      attachPlayerToModal();
      if (state.activeVideoId) {
        state.isVideoModalOpen = true;
        dom.videoModal.classList.remove('hidden');
      }
    }
  }

  function renderTimelineHitMarkers(videoId) {
    if (!dom.timelineHitMarkers) return;
    dom.timelineHitMarkers.innerHTML = '';

    const dur = dom.modalVideoPlayer ? (dom.modalVideoPlayer.duration || state.currentVideoDuration || 0) : 0;
    if (!videoId || !dur || dur <= 0) return;

    const rawPoints = [];
    state.allCandidates.forEach((c, idx) => {
      if (!c || c.video_id !== videoId) return;
      const rank = idx + 1;
      const score = Number(c.score || 0);
      if (Array.isArray(c.stage_hits) && c.stage_hits.length >= 2) {
        c.stage_hits.forEach(sh => {
          rawPoints.push({
            ts: Math.max(0, Math.min(dur, Number(sh.timestamp_sec || 0))),
            score,
            rank
          });
        });
      } else {
        rawPoints.push({
          ts: Math.max(0, Math.min(dur, Number(c.start_sec || 0))),
          score,
          rank
        });
      }
    });

    // Keep highest-scoring tick per 0.5s bucket to keep scrubber clean
    rawPoints.sort((a, b) => b.score - a.score);
    const deduped = [];
    rawPoints.forEach(pt => {
      if (!deduped.some(existing => Math.abs(existing.ts - pt.ts) < 0.5)) {
        deduped.push(pt);
      }
    });

    deduped.sort((a, b) => a.ts - b.ts);
    deduped.forEach(pt => {
      const pct = Math.max(0.5, Math.min(99.5, (pt.ts / dur) * 100));
      const tick = document.createElement('button');
      tick.type = 'button';
      tick.className = 'timeline-hit-marker';
      tick.style.left = `${pct.toFixed(2)}%`;
      tick.title = `Hit #${pt.rank} @ ${formatTime(pt.ts)} (score: ${pt.score.toFixed(4)})`;
      tick.addEventListener('click', (e) => {
        e.stopPropagation();
        if (dom.modalVideoPlayer) {
          dom.modalVideoPlayer.currentTime = pt.ts;
        }
        state.lastSeekSec = pt.ts;
        if (dom.videoTimelineSlider) {
          dom.videoTimelineSlider.value = pt.ts;
        }
        if (dom.modalTimeIndicator) {
          dom.modalTimeIndicator.textContent = `${formatTime(pt.ts)} / ${formatTime(dur)}`;
        }
        if (dom.dockedPlayerTitle) {
          dom.dockedPlayerTitle.textContent = `Inspector: ${videoId} @ ${formatTime(pt.ts)}`;
        }
        dom.modalHeading.textContent = `${videoId} @ ${formatTime(pt.ts)}`;
      });
      dom.timelineHitMarkers.appendChild(tick);
    });
  }

  function updateMarkDisplay() {
    dom.markInVal.textContent = `${state.markInSec.toFixed(2)}s`;
    dom.markOutVal.textContent = `${state.markOutSec.toFixed(2)}s`;
    updateTimelineHighlight();
  }

  function updateTimelineHighlight() {
    const dur = dom.modalVideoPlayer.duration;
    if (!dur || dur <= 0) return;

    const leftPct = (state.markInSec / dur) * 100;
    const widthPct = Math.max(0, ((state.markOutSec - state.markInSec) / dur) * 100);

    dom.timelineRangeHighlight.style.left = `${leftPct}%`;
    dom.timelineRangeHighlight.style.width = `${widthPct}%`;
  }

  // Stepper controls
  function stepTime(deltaSeconds) {
    const p = dom.modalVideoPlayer;
    if (!p) return;
    const dur = p.duration || state.currentVideoDuration || 0;
    const newTime = Math.max(0, Math.min(dur, (p.currentTime || 0) + deltaSeconds));
    p.currentTime = newTime;

    // Immediately update digital indicators and slider for instant UI responsiveness
    if (dom.modalTimeIndicator) {
      dom.modalTimeIndicator.textContent = `${formatTime(newTime)} / ${formatTime(dur)}`;
    }
    if (dom.videoTimelineSlider) {
      dom.videoTimelineSlider.value = newTime;
    }
    updateTimelineHighlight();
  }

  function togglePlayPause() {
    const p = dom.modalVideoPlayer;
    if (p.paused) {
      p.play();
      dom.modalPlayPauseBtn.textContent = '❚❚ Pause';
    } else {
      p.pause();
      dom.modalPlayPauseBtn.textContent = '▶ Play';
    }
  }

  // Range preview player
  function playSelectedRange() {
    const p = dom.modalVideoPlayer;
    p.currentTime = state.markInSec;
    p.play();
    state.isPlayingRange = true;

    const checkRangeEnd = () => {
      if (!state.isPlayingRange) {
        p.removeEventListener('timeupdate', checkRangeEnd);
        return;
      }
      if (p.currentTime >= state.markOutSec) {
        p.pause();
        state.isPlayingRange = false;
        p.removeEventListener('timeupdate', checkRangeEnd);
      }
    };
    p.addEventListener('timeupdate', checkRangeEnd);
  }

  // =========================================================================
  // Temporal Context Filmstrip
  // =========================================================================

  async function loadTemporalFilmstrip(videoId, centerSec) {
    dom.filmstripStatus.textContent = 'Loading neighbor keyframes...';
    dom.filmstripCarousel.innerHTML = '';

    try {
      const res = await fetch(`/api/videos/${videoId}/context?timestamp_sec=${centerSec}&window_sec=10.0`);
      if (!res.ok) throw new Error('Filmstrip not available');

      const data = await res.json();
      const frames = data.frames || [];
      dom.filmstripStatus.textContent = `${frames.length} keyframes in +-10s horizon`;

      frames.forEach(f => {
        const card = document.createElement('div');
        const isCenter = Math.abs(f.delta_sec) < 0.5;
        card.className = `filmstrip-card ${isCenter ? 'center-frame' : ''}`;
        card.title = `Seek to ${formatTime(f.timestamp_sec)} (delta: ${f.delta_sec}s)`;

        card.innerHTML = `
          <img src="${f.image_url}" alt="KF" class="filmstrip-thumb" loading="lazy" />
          <button type="button" class="btn-filmstrip-similar" title="Find visually similar frames (0ms)">Sim</button>
          <div class="filmstrip-info">
            <span class="filmstrip-time">${formatTime(f.timestamp_sec)}</span>
            <span class="filmstrip-delta">${f.delta_sec >= 0 ? '+' : ''}${f.delta_sec}s</span>
          </div>
        `;

        const simBtn = card.querySelector('.btn-filmstrip-similar');
        if (simBtn && f.keyframe_id) {
          simBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            setReferenceKeyframe({
              keyframe_id: f.keyframe_id,
              video_id: videoId,
              timestamp_sec: f.timestamp_sec
            });
          });
        }

        card.addEventListener('click', () => {
          dom.modalVideoPlayer.currentTime = f.timestamp_sec;
        });

        dom.filmstripCarousel.appendChild(card);
      });
    } catch (err) {
      dom.filmstripStatus.textContent = 'No context filmstrip keyframes';
    }
  }

  // =========================================================================
  // Keyboard Accelerators & Global Hotkeys
  // =========================================================================

  function handleGlobalKeydown(e) {
    const isEditableInput =
      (e.target.tagName === 'INPUT' && e.target.type !== 'range') ||
      e.target.tagName === 'TEXTAREA' ||
      e.target.tagName === 'SELECT';

    if (e.key === 'Escape') {
      if (dom.timerDetailsPopover && !dom.timerDetailsPopover.classList.contains('hidden')) {
        dom.timerDetailsPopover.classList.add('hidden');
        e.preventDefault();
        return;
      }
      if (state.isVideoModalOpen) {
        closeVideoModal();
        e.preventDefault();
        return;
      }
      if (isEditableInput) {
        e.target.blur();
      }
      return;
    }

    if (isEditableInput) {
      if (e.key === 'Enter' && e.target === dom.queryInput) {
        executeSearch();
      }
      return;
    }

    if (e.key === '/') {
      e.preventDefault();
      dom.queryInput.focus();
      dom.queryInput.select();
      return;
    }

    const playerActive = state.isVideoModalOpen || (state.layoutMode === 'docked' && Boolean(state.activeVideoId));
    if (playerActive) {
      const k = e.key;
      if (k === ' ') {
        togglePlayPause();
        e.preventDefault();
      } else if (k === 'j' || k === 'J') {
        stepTime(-1.0);
        e.preventDefault();
      } else if (k === 'l' || k === 'L') {
        stepTime(1.0);
        e.preventDefault();
      } else if (k === 'ArrowLeft' || e.code === 'ArrowLeft') {
        stepTime(e.shiftKey ? -5.0 : -0.04);
        e.preventDefault();
      } else if (k === 'ArrowRight' || e.code === 'ArrowRight') {
        stepTime(e.shiftKey ? 5.0 : 0.04);
        e.preventDefault();
      } else if (k === 'i' || k === 'I') {
        state.markInSec = dom.modalVideoPlayer.currentTime;
        updateMarkDisplay();
        updateTargetInputs(state.markInSec, state.markOutSec);
        e.preventDefault();
      } else if (k === 'o' || k === 'O') {
        state.markOutSec = dom.modalVideoPlayer.currentTime;
        updateMarkDisplay();
        updateTargetInputs(state.markInSec, state.markOutSec);
        e.preventDefault();
      } else if (k === 's' || k === 'S') {
        submitPlayheadInterval();
        e.preventDefault();
      }
      return;
    }

    if (e.key === 's' || e.key === 'S') {
      submitCurrentTargetRange();
      e.preventDefault();
    }
  }

  // =========================================================================
  // Event Listeners Binding
  // =========================================================================

  function initEventListeners() {
    // Search Trigger & Query Translation
    dom.searchBtn.addEventListener('click', executeSearch);
    if (dom.translateQueryBtn) {
      dom.translateQueryBtn.addEventListener('click', () => translateCurrentQuery(true));
    }
    if (dom.clearQueryHistoryBtn) {
      dom.clearQueryHistoryBtn.addEventListener('click', clearQueryHistory);
    }
    if (dom.diffRevertBtn) {
      dom.diffRevertBtn.addEventListener('click', revertTranslation);
    }
    if (dom.diffDismissBtn) {
      dom.diffDismissBtn.addEventListener('click', dismissTranslationDiff);
    }
    dom.clearQueryBtn.addEventListener('click', () => {
      dom.queryInput.value = '';
      if (dom.ocrQueryInput) dom.ocrQueryInput.value = '';
      if (dom.negativeQueryInput) dom.negativeQueryInput.value = '';
      if (dom.scene2Input) dom.scene2Input.value = '';
      clearReferenceKeyframe();
      dom.queryInput.focus();
    });

    if (dom.clearRefKeyframeBtn) {
      dom.clearRefKeyframeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        clearReferenceKeyframe(true);
      });
    }

    if (dom.exitSimModeBtn) {
      dom.exitSimModeBtn.addEventListener('click', () => {
        clearReferenceKeyframe(true);
      });
    }

    if (dom.queryInput) {
      dom.queryInput.addEventListener('keydown', (e) => {
        if (e.key === 'Backspace' && dom.queryInput.value === '' && state.referenceKeyframe) {
          e.preventDefault();
          clearReferenceKeyframe(false);
        }
      });
    }

    // Task 07A: Sequence Builder Toggle & Enter key support
    if (dom.toggleSequenceBtn && dom.sequenceBuilderRow) {
      dom.toggleSequenceBtn.addEventListener('click', () => {
        const isHidden = dom.sequenceBuilderRow.classList.toggle('hidden');
        dom.toggleSequenceBtn.classList.toggle('active', !isHidden);
        if (!isHidden) {
          if (state.referenceKeyframe) {
            clearReferenceKeyframe(false);
          }
          if (dom.scene2Input) dom.scene2Input.focus();
        }
      });
    }
    if (dom.closeSequenceBtn && dom.sequenceBuilderRow) {
      dom.closeSequenceBtn.addEventListener('click', () => {
        dom.sequenceBuilderRow.classList.add('hidden');
        if (dom.toggleSequenceBtn) dom.toggleSequenceBtn.classList.remove('active');
        if (dom.scene2Input) dom.scene2Input.value = '';
      });
    }
    if (dom.ocrQueryInput) {
      dom.ocrQueryInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          executeSearch();
        }
      });
    }
    if (dom.negativeQueryInput) {
      dom.negativeQueryInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          executeSearch();
        }
      });
    }
    if (dom.scene2Input) {
      dom.scene2Input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          executeSearch();
        }
      });
    }

    // Modality Selector Pills
    dom.searchModePills.forEach(pill => {
      pill.addEventListener('click', () => {
        dom.searchModePills.forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        const radio = pill.querySelector('input');
        radio.checked = true;
        state.searchMode = radio.value;
        if (state.searchMode === 'ocr' && state.referenceKeyframe) {
          clearReferenceKeyframe(false);
        }
      });
    });

    // Task 07B: Batch Scope Popover & Active Video Exclusion Filters
    if (dom.batchScopeBtn && dom.batchScopePopover) {
      dom.batchScopeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        dom.batchScopePopover.classList.toggle('hidden');
      });

      document.addEventListener('click', (e) => {
        if (dom.batchScopeWrapper && !dom.batchScopeWrapper.contains(e.target)) {
          dom.batchScopePopover.classList.add('hidden');
        }
      });

      dom.batchScopePopover.querySelectorAll('.btn-batch-preset').forEach(presetBtn => {
        presetBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          const p = presetBtn.dataset.preset;
          if (p === 'all') state.allowedBatches = new Set(ALL_BATCH_LIST);
          else if (p === 'b1') state.allowedBatches = new Set(ALL_BATCH_LIST.slice(0, 12));
          else if (p === 'b2') state.allowedBatches = new Set(ALL_BATCH_LIST.slice(12));
          else if (p === 'none') state.allowedBatches = new Set();
          saveAllowedBatches();
          renderBatchScopeUI();
          renderCandidateGrid();
        });
      });
    }

    if (dom.applyBatchScopeBtn && dom.batchScopePopover) {
      dom.applyBatchScopeBtn.addEventListener('click', () => {
        dom.batchScopePopover.classList.add('hidden');
        executeSearch();
      });
    }

    if (dom.resetExcludedVideosBtn) {
      dom.resetExcludedVideosBtn.addEventListener('click', resetExcludedVideos);
    }

    if (dom.targetVideoOnly) {
      dom.targetVideoOnly.addEventListener('change', () => {
        if (!dom.targetVideoOnly.checked) {
          dom.targetVideoFilterLabel.textContent = 'This Video';
        } else if (state.activeVideoId) {
          dom.targetVideoFilterLabel.textContent = state.activeVideoId;
        }
        if (dom.queryInput.value.trim() || state.referenceKeyframe || (dom.ocrQueryInput && dom.ocrQueryInput.value.trim())) {
          executeSearch();
        }
      });
    }

    dom.resultsLimitSelect.addEventListener('change', (e) => {
      state.resultsLimit = parseInt(e.target.value, 10);
      executeSearch();
    });

    if (dom.viewModeFramesBtn) {
      dom.viewModeFramesBtn.addEventListener('click', () => setViewMode('frames', true));
    }
    if (dom.viewModeVideoBtn) {
      dom.viewModeVideoBtn.addEventListener('click', () => setViewMode('by_video', true));
    }

    dom.clearAllCandidatesBtn.addEventListener('click', () => {
      state.allCandidates = [];
      renderCandidateGrid();
    });

    // DRES Drawer & Config
    dom.toggleDresSettingsBtn.addEventListener('click', () => {
      dom.dresSettingsDrawer.classList.toggle('hidden');
    });
    dom.closeDresDrawerBtn.addEventListener('click', () => {
      dom.dresSettingsDrawer.classList.add('hidden');
    });
    dom.saveDresConfigBtn.addEventListener('click', saveDresConfiguration);
    dom.clearDresCacheBtn.addEventListener('click', clearDresCache);

    // Layout Toggle & Docked Inspector Controls
    dom.toggleDockedLayoutBtn.addEventListener('click', toggleDockedLayout);
    dom.modalDockToggleBtn.addEventListener('click', toggleDockedLayout);
    if (dom.expandPopupBtn) {
      dom.expandPopupBtn.addEventListener('click', expandDockedToPopup);
    }
    dom.closeDockedPlayerBtn.addEventListener('click', () => {
      dom.modalVideoPlayer.pause();
      dom.dockedPlayerPanel.classList.add('hidden');
    });

    // Header Timer Popover Toggle
    if (dom.timerDetailsBtn && dom.timerDetailsPopover) {
      dom.timerDetailsBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        dom.timerDetailsPopover.classList.toggle('hidden');
      });
      document.addEventListener('click', (e) => {
        if (dom.headerTimerWrapper && !dom.headerTimerWrapper.contains(e.target)) {
          dom.timerDetailsPopover.classList.add('hidden');
        }
      });
    }

    // VRAM Unload
    dom.unloadVramBtn.addEventListener('click', async () => {
      try {
        const res = await fetch('/api/search/unload', { method: 'POST' });
        const data = await res.json();
        alert(`[OK] ${data.message}`);
      } catch (err) {
        console.error(err);
      }
    });

    // Stopwatch & Simulator
    dom.timerStartPauseBtn.addEventListener('click', () => {
      if (state.isTimerRunning) pauseStopwatch();
      else startStopwatch();
    });
    dom.timerResetBtn.addEventListener('click', resetStopwatch);
    dom.taskModeTextual.addEventListener('click', () => setTaskMode(300, true));
    dom.taskModeVideo.addEventListener('click', () => setTaskMode(240, false));
    dom.addWrongAttemptBtn.addEventListener('click', () => {
      state.wrongAttempts += 1;
      calculateScoreDecay();
    });
    dom.resetWrongAttemptsBtn.addEventListener('click', () => {
      state.wrongAttempts = 0;
      calculateScoreDecay();
    });

    // Presets
    dom.presetTightBtn.addEventListener('click', () => {
      applyPresetTight(state.targetStartSec, state.targetEndSec);
    });
    dom.presetShotBtn.addEventListener('click', () => {
      if (state.activeCandidate) {
        applyPresetShot(state.activeCandidate.start_sec, state.activeCandidate.end_sec);
      }
    });
    dom.presetWindowBtn.addEventListener('click', () => {
      applyPresetWindow(state.targetStartSec, state.targetEndSec);
    });

    // Numerical Target Inputs sync
    dom.targetStartSec.addEventListener('input', () => {
      updateTargetInputs(dom.targetStartSec.value, dom.targetEndSec.value);
    });
    dom.targetEndSec.addEventListener('input', () => {
      updateTargetInputs(dom.targetStartSec.value, dom.targetEndSec.value);
    });

    // Sidebar Submit Buttons
    dom.submitTargetRangeBtn.addEventListener('click', submitCurrentTargetRange);
    dom.quickSubmitPlayheadBtn.addEventListener('click', submitPlayheadInterval);

    // Modal Video Player Controls
    dom.modalCloseBtn.addEventListener('click', closeVideoModal);
    dom.modalPlayPauseBtn.addEventListener('click', togglePlayPause);
    dom.stepBack5s.addEventListener('click', () => stepTime(-5.0));
    dom.stepBack1s.addEventListener('click', () => stepTime(-1.0));
    dom.stepBackFrame.addEventListener('click', () => stepTime(-0.04));
    dom.stepFwdFrame.addEventListener('click', () => stepTime(0.04));
    dom.stepFwd1s.addEventListener('click', () => stepTime(1.0));
    dom.stepFwd5s.addEventListener('click', () => stepTime(5.0));

    dom.setMarkInBtn.addEventListener('click', () => {
      state.markInSec = dom.modalVideoPlayer.currentTime;
      updateMarkDisplay();
      updateTargetInputs(state.markInSec, state.markOutSec);
    });
    dom.setMarkOutBtn.addEventListener('click', () => {
      state.markOutSec = dom.modalVideoPlayer.currentTime;
      updateMarkDisplay();
      updateTargetInputs(state.markInSec, state.markOutSec);
    });
    dom.playRangePreviewBtn.addEventListener('click', playSelectedRange);

    dom.modalSubmitRangeBtn.addEventListener('click', () => {
      submitKisPayload(state.activeVideoId, state.markInSec, state.markOutSec);
    });
    dom.modalSubmitPlayheadBtn.addEventListener('click', submitPlayheadInterval);

    // Video Element Events
    const player = dom.modalVideoPlayer;
    player.addEventListener('timeupdate', () => {
      dom.modalTimeIndicator.textContent = `${formatTime(player.currentTime)} / ${formatTime(player.duration)}`;
      dom.videoTimelineSlider.value = player.currentTime;
      updateTimelineHighlight();
    });

    player.addEventListener('loadedmetadata', () => {
      state.currentVideoDuration = player.duration;
      dom.videoTimelineSlider.max = player.duration;
      dom.modalTimeIndicator.textContent = `${formatTime(player.currentTime)} / ${formatTime(player.duration)}`;
      updateTimelineHighlight();
      renderTimelineHitMarkers(state.activeVideoId);
    });

    player.addEventListener('waiting', () => {
      dom.playerBufferingOverlay.classList.remove('hidden');
    });
    player.addEventListener('playing', () => {
      dom.playerBufferingOverlay.classList.add('hidden');
      dom.modalPlayPauseBtn.textContent = '❚❚ Pause';
    });
    player.addEventListener('pause', () => {
      dom.modalPlayPauseBtn.textContent = '▶ Play';
    });

    dom.videoTimelineSlider.addEventListener('input', (e) => {
      player.currentTime = parseFloat(e.target.value);
    });

    // Global Keydown
    window.addEventListener('keydown', handleGlobalKeydown);
  }

  // =========================================================================
  // App Initialization
  // =========================================================================

  async function init() {
    console.log('[KIS Workstation] Initializing application...');
    if (state.layoutMode === 'docked') {
      attachPlayerToDocked();
      if (dom.layoutModeLabel) dom.layoutModeLabel.textContent = 'Cockpit';
      if (dom.dockedPlayerPanel) dom.dockedPlayerPanel.classList.remove('hidden');
    } else {
      if (dom.layoutModeLabel) dom.layoutModeLabel.textContent = 'Popup';
      if (dom.dockedPlayerPanel) dom.dockedPlayerPanel.classList.add('hidden');
    }
    loadViewMode();
    loadAllowedBatches();
    updateExcludedVideosUI();
    initEventListeners();
    renderQueryHistory();
    updateStopwatchDisplay();
    await fetchDresStatus();
    console.log('[KIS Workstation] Ready.');
  }

  document.addEventListener('DOMContentLoaded', init);
})();
