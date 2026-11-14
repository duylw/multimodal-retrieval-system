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
    dresBatchesOnly: true,
    targetVideoOnly: false,
    activeVideoId: null,
    allCandidates: [],
    activeCandidate: null,

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

    // Layout Mode ('popup' or 'docked')
    layoutMode: 'popup',

    // DRES Client Status
    dresStatus: {
      is_authenticated: false,
      session_id: null,
      evaluation_id: 'offline_kis_eval',
      base_url: 'https://eventretrieval.one',
      history: []
    },

    // Task 06D: Query Translation State
    lastTranslation: {
      original: '',
      translated: ''
    }
  };

  // Official competition batches: L01 through L24
  const DRES_OFFICIAL_BATCHES = new Set([
    'L01', 'L02', 'L03', 'L04', 'L05', 'L06',
    'L07', 'L08', 'L09', 'L10', 'L11', 'L12',
    'L13', 'L14', 'L15', 'L16', 'L17', 'L18',
    'L19', 'L20', 'L21', 'L22', 'L23', 'L24'
  ]);

  // =========================================================================
  // DOM Elements Cache
  // =========================================================================
  const dom = {
    // Top Bar
    queryInput: document.getElementById('queryInput'),
    translateQueryBtn: document.getElementById('translateQueryBtn'),
    clearQueryBtn: document.getElementById('clearQueryBtn'),
    searchBtn: document.getElementById('searchBtn'),
    searchModePills: document.querySelectorAll('.mode-pill'),
    autoTranslateCheck: document.getElementById('autoTranslateCheck'),
    dresBatchesOnly: document.getElementById('dresBatchesOnly'),
    targetVideoOnly: document.getElementById('targetVideoOnly'),
    targetVideoFilterLabel: document.getElementById('targetVideoFilterLabel'),
    resultsLimitSelect: document.getElementById('resultsLimitSelect'),
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
    dresSessionId: document.getElementById('dresSessionId'),
    dresUsername: document.getElementById('dresUsername'),
    dresPassword: document.getElementById('dresPassword'),
    saveDresConfigBtn: document.getElementById('saveDresConfigBtn'),
    clearDresCacheBtn: document.getElementById('clearDresCacheBtn'),

    // Left Sidebar: Stopwatch & Score Decay
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

    // Docked Panel
    dockedPlayerPanel: document.getElementById('dockedPlayerPanel'),
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
    dom.timerStartPauseBtn.textContent = 'Pause Timer';
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
    dom.timerStartPauseBtn.textContent = 'Resume Timer';
    dom.timerStartPauseBtn.style.backgroundColor = '#2563eb';
  }

  function resetStopwatch() {
    pauseStopwatch();
    state.elapsedSeconds = 0;
    dom.timerStartPauseBtn.textContent = 'Start Timer';
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
    const end = Number(candidate.end_sec) || (start + 5.0);

    if (autoPreset === 'tight') {
      applyPresetTight(start, end);
    } else if (autoPreset === 'shot') {
      applyPresetShot(start, end);
    } else {
      applyPresetWindow(start, end);
    }

    // Highlight card in grid
    document.querySelectorAll('.candidate-card').forEach(card => {
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

    const currTime = dom.modalVideoPlayer.currentTime || state.targetStartSec || 0.0;
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
    if (!raw) return raw;

    // Skip if identical to currently displayed translation unless forced
    if (!force && state.lastTranslation.translated && raw === state.lastTranslation.translated) {
      return raw;
    }

    if (dom.translateQueryBtn) {
      dom.translateQueryBtn.classList.add('translating');
      dom.translateQueryBtn.textContent = '...';
    }

    try {
      const res = await fetch('/api/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: raw,
          source_lang: 'auto',
          target_lang: 'en'
        })
      });

      if (!res.ok) {
        return raw;
      }

      const data = await res.json();
      const translated = (data.translated_query || '').trim();

      if (translated && translated !== raw) {
        state.lastTranslation = {
          original: raw,
          translated: translated
        };
        dom.queryInput.value = translated;

        // Display translation diff banner
        if (dom.translationDiffBanner && dom.diffOriginalText && dom.diffTranslatedText) {
          dom.diffOriginalText.textContent = raw;
          dom.diffTranslatedText.textContent = translated;
          dom.translationDiffBanner.classList.remove('hidden');
        }

        return translated;
      } else {
        return raw;
      }
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
    if (state.lastTranslation.original) {
      const orig = state.lastTranslation.original;
      dom.queryInput.value = orig;
      if (dom.translationDiffBanner) {
        dom.translationDiffBanner.classList.add('hidden');
      }
      state.lastTranslation = { original: '', translated: '' };
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
  // Multimodal Search & High-Density Candidate Grid
  // =========================================================================

  async function executeSearch(skipAutoTranslate = false) {
    let query = dom.queryInput.value.trim();
    if (!query) {
      dom.queryInput.focus();
      return;
    }

    // Auto-translate if enabled, not explicitly skipped (e.g. on Revert), and query differs from last translation
    if (!skipAutoTranslate && dom.autoTranslateCheck && dom.autoTranslateCheck.checked) {
      if (query !== state.lastTranslation.translated) {
        query = await translateCurrentQuery(false);
      }
    }

    // Save query to competition history
    saveQueryToHistory(query);

    dom.gridLoadingOverlay.classList.remove('hidden');
    dom.candidateQueryEcho.textContent = `"${query}" (${state.searchMode})`;

    const params = new URLSearchParams({
      query: query,
      mode: state.searchMode,
      top_k: String(state.resultsLimit)
    });

    if (dom.targetVideoOnly.checked && state.activeVideoId) {
      params.append('video_id', state.activeVideoId);
    }

    try {
      const res = await fetch(`/api/search/multimodal?${params.toString()}`);
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

  function renderCandidateGrid() {
    let candidates = state.allCandidates;

    // Filter by DRES official batches if toggled
    if (dom.dresBatchesOnly.checked) {
      candidates = candidates.filter(c => isDresOfficialBatch(c.video_id));
    }

    dom.candidateTotalCount.textContent = String(candidates.length);

    if (candidates.length === 0) {
      dom.candidateGrid.innerHTML = `
        <div class="grid-empty-state">
          <div class="empty-icon">⚠️</div>
          <h3>No Matching Candidates Found</h3>
          <p>Try broadening your query keywords or unchecking "DRES Batches Only".</p>
        </div>
      `;
      return;
    }

    dom.candidateGrid.innerHTML = '';
    candidates.forEach((c, idx) => {
      const card = createCandidateCard(c, idx + 1);
      dom.candidateGrid.appendChild(card);
    });

    // Auto-select #1 candidate coordinates as default target
    if (candidates.length > 0 && !state.activeCandidate) {
      setActiveTarget(candidates[0], 'tight');
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
    const matchedCues = candidate.matched_cues || 1;
    const consensusHtml = matchedCues > 1 
      ? `<span class="badge-consensus-overlay" title="Matched ${matchedCues} independent cues">Consensus: ${matchedCues}</span>` 
      : '';

    // DRES Batch Badge
    const batch = getVideoBatch(candidate.video_id);
    const dresBadgeHtml = `<span class="badge-dres-batch-overlay">${batch}</span>`;

    // OCR snippet preview
    const ocrSnippet = candidate.text_detected ? candidate.text_detected.trim() : '';
    const ocrHtml = ocrSnippet 
      ? `<div class="card-ocr-snippet" title="${ocrSnippet}">OCR: ${ocrSnippet}</div>` 
      : '';

    const dur = ((candidate.end_sec || 0) - (candidate.start_sec || 0)).toFixed(1);

    card.innerHTML = `
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

      <div class="card-body">
        <div class="card-meta-row">
          <span class="card-vid">${candidate.video_id}</span>
          <span class="card-score-pill">${(candidate.score || 0).toFixed(4)}</span>
        </div>

        <div class="card-time-row">
          <span>${formatTime(candidate.start_sec)} - ${formatTime(candidate.end_sec)}</span>
          <span class="card-duration">(${dur}s)</span>
        </div>

        ${ocrHtml}

        <div class="card-actions-row">
          <button class="btn-card-aux btn-open-modal" title="Open modal player">Play</button>
          <button class="btn-card-aux btn-view-strip" title="View +-15s filmstrip">Strip</button>
          <button class="btn-card-aux btn-only-video" title="Search only inside ${candidate.video_id}">Only</button>
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
    const onlyBtn = card.querySelector('.btn-only-video');
    const submitBtn = card.querySelector('.btn-card-submit-kis');

    const handleOpenPlayer = () => {
      setActiveTarget(candidate, 'tight');
      openVideoModal(candidate);
    };

    mediaWrap.addEventListener('click', handleOpenPlayer);
    playBtn.addEventListener('click', handleOpenPlayer);

    stripBtn.addEventListener('click', () => {
      setActiveTarget(candidate, 'tight');
      openVideoModal(candidate, true);
    });

    onlyBtn.addEventListener('click', () => {
      state.activeVideoId = candidate.video_id;
      dom.targetVideoOnly.checked = true;
      dom.targetVideoFilterLabel.textContent = candidate.video_id;
      executeSearch();
    });

    submitBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      setActiveTarget(candidate, 'tight');
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
        dom.modalBody.insertBefore(dom.playerWrapper, dom.modalBody.firstChild);
      }
      if (dom.playerTransportBar.parentElement !== dom.modalBody) {
        if (dom.modalFilmstripSection && dom.modalFilmstripSection.parentElement === dom.modalBody) {
          dom.modalBody.insertBefore(dom.playerTransportBar, dom.modalFilmstripSection);
        } else {
          dom.modalBody.appendChild(dom.playerTransportBar);
        }
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
    }
  }

  function openVideoModal(candidate, jumpToFilmstrip = false) {
    state.isVideoModalOpen = true;
    state.activeCandidate = candidate;
    state.activeVideoId = candidate.video_id;

    dom.modalVideoIdBadge.textContent = candidate.video_id;
    dom.modalHeading.textContent = `${candidate.video_id} @ ${formatTime(candidate.start_sec)}`;

    const targetSec = Math.max(0, Number(candidate.start_sec) || 0.0);

    // Reset Mark In / Out to candidate boundary
    state.markInSec = targetSec;
    state.markOutSec = Number(candidate.end_sec) || (targetSec + 5.0);
    updateMarkDisplay();

    // Show modal or docked
    if (state.layoutMode === 'docked') {
      attachPlayerToDocked();
      dom.dockedPlayerPanel.classList.remove('hidden');
      dom.videoModal.classList.add('hidden');
    } else {
      attachPlayerToModal();
      dom.videoModal.classList.remove('hidden');
      dom.dockedPlayerPanel.classList.add('hidden');
    }

    // Unfocus search bar or active inputs so hotkeys immediately work on modal
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

    // Load Temporal Filmstrip
    loadTemporalFilmstrip(candidate.video_id, targetSec);
  }

  function closeVideoModal() {
    state.isVideoModalOpen = false;
    dom.modalVideoPlayer.pause();
    dom.videoModal.classList.add('hidden');
    dom.dockedPlayerPanel.classList.add('hidden');
    attachPlayerToModal();
    if (dom.candidateGrid) {
      dom.candidateGrid.focus();
    }
  }

  function toggleDockedLayout() {
    if (state.layoutMode === 'popup') {
      state.layoutMode = 'docked';
      dom.layoutModeLabel.textContent = 'Docked';
      if (state.isVideoModalOpen) {
        attachPlayerToDocked();
        dom.videoModal.classList.add('hidden');
        dom.dockedPlayerPanel.classList.remove('hidden');
      }
    } else {
      state.layoutMode = 'popup';
      dom.layoutModeLabel.textContent = 'Popup';
      dom.dockedPlayerPanel.classList.add('hidden');
      attachPlayerToModal();
      if (state.isVideoModalOpen) {
        dom.videoModal.classList.remove('hidden');
      }
    }
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
      const res = await fetch(`/api/videos/${videoId}/context?timestamp_sec=${centerSec}&window_sec=15.0`);
      if (!res.ok) throw new Error('Filmstrip not available');

      const data = await res.json();
      const frames = data.frames || [];
      dom.filmstripStatus.textContent = `${frames.length} keyframes in +-15s horizon`;

      frames.forEach(f => {
        const card = document.createElement('div');
        const isCenter = Math.abs(f.delta_sec) < 0.5;
        card.className = `filmstrip-card ${isCenter ? 'center-frame' : ''}`;
        card.title = `Seek to ${formatTime(f.timestamp_sec)} (delta: ${f.delta_sec}s)`;

        card.innerHTML = `
          <img src="${f.image_url}" alt="KF" class="filmstrip-thumb" loading="lazy" />
          <div class="filmstrip-info">
            <span class="filmstrip-time">${formatTime(f.timestamp_sec)}</span>
            <span class="filmstrip-delta">${f.delta_sec >= 0 ? '+' : ''}${f.delta_sec}s</span>
          </div>
        `;

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
    // Modal is open hotkeys take top priority
    if (state.isVideoModalOpen) {
      if (e.key === 'Escape') {
        closeVideoModal();
        e.preventDefault();
        return;
      }

      // Ignore text typing ONLY for actual editable text boxes, never range slider
      const isEditableText = (e.target.tagName === 'INPUT' && e.target.type !== 'range') || e.target.tagName === 'TEXTAREA';
      if (isEditableText) {
        return;
      }

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

    // Outside Modal Hotkeys
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
      if (e.key === 'Escape') {
        e.target.blur();
      }
      if (e.key === 'Enter' && e.target === dom.queryInput) {
        executeSearch();
      }
      return;
    }

    if (e.key === '/') {
      e.preventDefault();
      dom.queryInput.focus();
      dom.queryInput.select();
    } else if (e.key === 's' || e.key === 'S') {
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
      dom.queryInput.focus();
    });

    // Modality Selector Pills
    dom.searchModePills.forEach(pill => {
      pill.addEventListener('click', () => {
        dom.searchModePills.forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        const radio = pill.querySelector('input');
        radio.checked = true;
        state.searchMode = radio.value;
      });
    });

    // Filters
    dom.dresBatchesOnly.addEventListener('change', renderCandidateGrid);
    dom.resultsLimitSelect.addEventListener('change', (e) => {
      state.resultsLimit = parseInt(e.target.value, 10);
      executeSearch();
    });

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

    // Layout Toggle
    dom.toggleDockedLayoutBtn.addEventListener('click', toggleDockedLayout);
    dom.modalDockToggleBtn.addEventListener('click', toggleDockedLayout);
    dom.closeDockedPlayerBtn.addEventListener('click', closeVideoModal);

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
    initEventListeners();
    renderQueryHistory();
    updateStopwatchDisplay();
    await fetchDresStatus();
    console.log('[KIS Workstation] Ready.');
  }

  document.addEventListener('DOMContentLoaded', init);
})();
