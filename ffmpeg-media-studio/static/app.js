/**
 * OmniAudio Studio - Frontend Application Engine
 * Pure Vanilla JavaScript with 5MB Chunked Slicing (100% Cloudflare 100MB Limit Proof)
 * and full Audio & MP3 processing capabilities.
 */

// Application State
const state = {
  activeTab: 'tab-upload',
  stagedFiles: [],
  renderedFiles: [],
  activeJobId: null,
  jobPollInterval: null,
  systemInfo: {},
  selectedEqPreset: 'bass_boost'
};

const CHUNK_SIZE = 5 * 1024 * 1024; // 5 MB per slice (Under Cloudflare 100MB limit)

// DOM Elements Cache
const DOM = {
  navItems: document.querySelectorAll('.nav-item'),
  tabPanels: document.querySelectorAll('.tab-panel'),
  
  // Badges & Metrics
  sysFfmpeg: document.getElementById('sysFfmpeg'),
  sysYtdlp: document.getElementById('sysYtdlp'),
  sysDisk: document.getElementById('sysDisk'),
  activeJobsBadge: document.getElementById('activeJobsBadge'),
  uploadCountBadge: document.getElementById('uploadCountBadge'),
  outputCountBadge: document.getElementById('outputCountBadge'),
  stagedFilesCount: document.getElementById('stagedFilesCount'),
  renderedFilesCount: document.getElementById('renderedFilesCount'),
  
  // Drop Zone
  dropZone: document.getElementById('dropZone'),
  fileInput: document.getElementById('fileInput'),
  uploadProgressBar: document.getElementById('uploadProgressBar'),
  uploadProgressFill: document.getElementById('uploadProgressFill'),
  uploadProgressText: document.getElementById('uploadProgressText'),
  stagedMediaGrid: document.getElementById('stagedMediaGrid'),
  renderedMediaGrid: document.getElementById('renderedMediaGrid'),
  refreshFilesBtn: document.getElementById('refreshFilesBtn'),
  clearUploadsBtn: document.getElementById('clearUploadsBtn'),
  refreshOutputsBtn: document.getElementById('refreshOutputsBtn'),
  clearOutputsBtn: document.getElementById('clearOutputsBtn'),
  
  // Music / URL Downloader
  ytdlUrl: document.getElementById('ytdlUrl'),
  ytdlPreset: document.getElementById('ytdlPreset'),
  pasteUrlBtn: document.getElementById('pasteUrlBtn'),
  startDownloadBtn: document.getElementById('startDownloadBtn'),
  
  // Multi-Track Joiner
  joinFileList: document.getElementById('joinFileList'),
  joinFormat: document.getElementById('joinFormat'),
  joinCrossfade: document.getElementById('joinCrossfade'),
  startJoinBtn: document.getElementById('startJoinBtn'),
  
  // Format Converter
  convertSourceFile: document.getElementById('convertSourceFile'),
  convertOutputFormat: document.getElementById('convertOutputFormat'),
  convertAudioBitrate: document.getElementById('convertAudioBitrate'),
  convertSampleRate: document.getElementById('convertSampleRate'),
  convertChannels: document.getElementById('convertChannels'),
  startConvertBtn: document.getElementById('startConvertBtn'),
  
  // Trimmer & Ringtone
  trimSourceFile: document.getElementById('trimSourceFile'),
  trimAudioPlayer: document.getElementById('trimAudioPlayer'),
  trimStartTime: document.getElementById('trimStartTime'),
  trimEndTime: document.getElementById('trimEndTime'),
  setTrimStartBtn: document.getElementById('setTrimStartBtn'),
  setTrimEndBtn: document.getElementById('setTrimEndBtn'),
  trimFadeIn: document.getElementById('trimFadeIn'),
  trimFadeOut: document.getElementById('trimFadeOut'),
  trimFormat: document.getElementById('trimFormat'),
  startTrimBtn: document.getElementById('startTrimBtn'),
  
  // Volume & Loudness
  loudnessSourceFile: document.getElementById('loudnessSourceFile'),
  targetLufs: document.getElementById('targetLufs'),
  volumeMultiplier: document.getElementById('volumeMultiplier'),
  volumeMultiplierDisplay: document.getElementById('volumeMultiplierDisplay'),
  ebur128SettingsRow: document.getElementById('ebur128SettingsRow'),
  boostSettingsRow: document.getElementById('boostSettingsRow'),
  startLoudnessBtn: document.getElementById('startLoudnessBtn'),
  
  // Pitch & Tempo
  pitchSourceFile: document.getElementById('pitchSourceFile'),
  audioTempoSlider: document.getElementById('audioTempoSlider'),
  audioTempoDisplay: document.getElementById('audioTempoDisplay'),
  pitchSemitones: document.getElementById('pitchSemitones'),
  pitchSemitonesDisplay: document.getElementById('pitchSemitonesDisplay'),
  reverseAudio: document.getElementById('reverseAudio'),
  startPitchBtn: document.getElementById('startPitchBtn'),
  
  // Equalizer
  eqSourceFile: document.getElementById('eqSourceFile'),
  eqCards: document.querySelectorAll('.eq-card'),
  startEqBtn: document.getElementById('startEqBtn'),
  
  // ID3 Tag Editor
  tagSourceFile: document.getElementById('tagSourceFile'),
  tagTitle: document.getElementById('tagTitle'),
  tagArtist: document.getElementById('tagArtist'),
  tagAlbum: document.getElementById('tagAlbum'),
  tagGenre: document.getElementById('tagGenre'),
  tagYear: document.getElementById('tagYear'),
  startTagBtn: document.getElementById('startTagBtn'),
  
  // Task Drawer
  taskDrawer: document.getElementById('taskDrawer'),
  taskTitle: document.getElementById('taskTitle'),
  taskSubtext: document.getElementById('taskSubtext'),
  taskProgressFill: document.getElementById('taskProgressFill'),
  taskPercent: document.getElementById('taskPercent'),
  taskSpeed: document.getElementById('taskSpeed'),
  toggleLogsBtn: document.getElementById('toggleLogsBtn'),
  cancelTaskBtn: document.getElementById('cancelTaskBtn'),
  taskLogsTerminal: document.getElementById('taskLogsTerminal'),
  taskLogsContent: document.getElementById('taskLogsContent'),
  
  // Modal
  previewModal: document.getElementById('previewModal'),
  modalMediaTitle: document.getElementById('modalMediaTitle'),
  modalPlayerBox: document.getElementById('modalPlayerBox'),
  modalMetadataBox: document.getElementById('modalMetadataBox'),
  modalDownloadBtn: document.getElementById('modalDownloadBtn'),
  closeModalBtn: document.getElementById('closeModalBtn'),
  modalCloseActionBtn: document.getElementById('modalCloseActionBtn')
};

// ==============================================================================
// App Initialization
// ==============================================================================

document.addEventListener('DOMContentLoaded', () => {
  setupNavigation();
  setupChunkedDropZone();
  setupEventHandlers();
  fetchSystemInfo();
  fetchFiles();
  
  setInterval(fetchSystemInfo, 5000);
});

function setupNavigation() {
  DOM.navItems.forEach(item => {
    item.addEventListener('click', () => {
      const tabId = item.getAttribute('data-tab');
      switchTab(tabId);
    });
  });
}

function switchTab(tabId) {
  state.activeTab = tabId;
  DOM.navItems.forEach(btn => {
    if (btn.getAttribute('data-tab') === tabId) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
  
  DOM.tabPanels.forEach(panel => {
    if (panel.id === tabId) {
      panel.classList.add('active');
    } else {
      panel.classList.remove('active');
    }
  });
  
  if (tabId === 'tab-join') renderJoinList();
  if (tabId === 'tab-trim') syncTrimSource();
}

// ==============================================================================
// 5MB Chunked Slicing Upload Handler (Cloudflare 100MB Limit Proof)
// ==============================================================================

function setupChunkedDropZone() {
  const zone = DOM.dropZone;
  
  ['dragenter', 'dragover'].forEach(name => {
    zone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      zone.classList.add('dragover');
    });
  });
  
  ['dragleave', 'drop'].forEach(name => {
    zone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      zone.classList.remove('dragover');
    });
  });
  
  zone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    if (dt.files && dt.files.length > 0) {
      processFilesQueue(dt.files);
    }
  });
  
  DOM.fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      processFilesQueue(e.target.files);
    }
  });
}

async function processFilesQueue(filesList) {
  DOM.uploadProgressBar.style.display = 'flex';
  const totalFiles = filesList.length;
  
  for (let fileIdx = 0; fileIdx < totalFiles; fileIdx++) {
    const file = filesList[fileIdx];
    await uploadSingleFileInChunks(file, fileIdx + 1, totalFiles);
  }
  
  DOM.uploadProgressBar.style.display = 'none';
  fetchFiles();
}

async function uploadSingleFileInChunks(file, fileNum, totalFiles) {
  const fileSize = file.size;
  const totalChunks = Math.ceil(fileSize / CHUNK_SIZE) || 1;
  
  // 1. Initialize upload session
  let initRes;
  try {
    initRes = await fetch('/api/upload/init', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filename: file.name,
        total_chunks: totalChunks,
        total_size: fileSize
      })
    });
    if (!initRes.ok) throw new Error(`Init failed (${initRes.status})`);
  } catch (err) {
    alert(`Upload init error for ${file.name}: ${err.message}`);
    return;
  }
  
  const { upload_id } = await initRes.json();
  
  // 2. Slices upload loop
  for (let chunkIdx = 0; chunkIdx < totalChunks; chunkIdx++) {
    const start = chunkIdx * CHUNK_SIZE;
    const end = Math.min(fileSize, start + CHUNK_SIZE);
    const chunkBlob = file.slice(start, end);
    
    const formData = new FormData();
    formData.append('upload_id', upload_id);
    formData.append('chunk_index', chunkIdx);
    formData.append('chunk', chunkBlob, `chunk_${chunkIdx}.part`);
    
    // Update progress UI
    const overallPct = Math.round(((chunkIdx + 1) / totalChunks) * 100);
    DOM.uploadProgressFill.style.width = `${overallPct}%`;
    DOM.uploadProgressText.textContent = `[${fileNum}/${totalFiles}] ${file.name} - Chunk ${chunkIdx + 1}/${totalChunks} (${overallPct}%)`;
    
    let uploaded = false;
    let attempts = 0;
    while (!uploaded && attempts < 3) {
      try {
        attempts++;
        const chunkRes = await fetch('/api/upload/chunk', {
          method: 'POST',
          body: formData
        });
        if (chunkRes.ok) {
          uploaded = true;
        } else {
          console.warn(`Retry chunk ${chunkIdx} attempt ${attempts}`);
          await new Promise(r => setTimeout(r, 800));
        }
      } catch (err) {
        console.warn(`Chunk network error: ${err.message}`);
        await new Promise(r => setTimeout(r, 1000));
      }
    }
    
    if (!uploaded) {
      alert(`Failed to upload chunk ${chunkIdx} of ${file.name} after 3 attempts.`);
      return;
    }
  }
  
  // 3. Assemble and complete upload
  DOM.uploadProgressText.textContent = `Assembling ${file.name}...`;
  try {
    const completeRes = await fetch('/api/upload/complete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ upload_id })
    });
    if (!completeRes.ok) throw new Error('Stitching failed');
  } catch (err) {
    alert(`File assembly error: ${err.message}`);
  }
}

// ==============================================================================
// System Info & File Management
// ==============================================================================

async function fetchSystemInfo() {
  try {
    const res = await fetch('/api/system-info');
    if (!res.ok) return;
    const data = await res.json();
    state.systemInfo = data;
    
    DOM.sysFfmpeg.textContent = data.ffmpeg_version || 'Ready';
    DOM.sysYtdlp.textContent = data.ytdlp_version || 'Ready';
    DOM.sysDisk.textContent = `${data.disk_free_gb} GB`;
    DOM.activeJobsBadge.textContent = `⚡ ${data.active_jobs} Active Tasks`;
  } catch (err) {
    console.error('System info fetch error:', err);
  }
}

async function fetchFiles() {
  try {
    const res = await fetch('/api/files');
    if (!res.ok) return;
    const data = await res.json();
    state.stagedFiles = data.uploads || [];
    state.renderedFiles = data.outputs || [];
    
    DOM.uploadCountBadge.textContent = state.stagedFiles.length;
    DOM.outputCountBadge.textContent = state.renderedFiles.length;
    DOM.stagedFilesCount.textContent = state.stagedFiles.length;
    DOM.renderedFilesCount.textContent = state.renderedFiles.length;
    
    renderMediaGrids();
    populateSelectDropdowns();
  } catch (err) {
    console.error('Files fetch error:', err);
  }
}

function populateSelectDropdowns() {
  const selects = [
    DOM.convertSourceFile,
    DOM.trimSourceFile,
    DOM.loudnessSourceFile,
    DOM.pitchSourceFile,
    DOM.eqSourceFile,
    DOM.tagSourceFile
  ];
  
  selects.forEach(select => {
    if (!select) return;
    const curr = select.value;
    select.replaceChildren();
    
    if (state.stagedFiles.length === 0) {
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = '-- No staged audio files available --';
      select.appendChild(opt);
      return;
    }
    
    state.stagedFiles.forEach(file => {
      const opt = document.createElement('option');
      opt.value = file.filename;
      const meta = file.metadata || {};
      const dur = meta.duration_formatted ? ` (${meta.duration_formatted})` : '';
      const sr = meta.audio_streams && meta.audio_streams[0] ? ` [${meta.audio_streams[0].sample_rate}Hz]` : '';
      opt.textContent = `${file.filename}${dur}${sr}`;
      select.appendChild(opt);
    });
    
    if (curr && state.stagedFiles.some(f => f.filename === curr)) {
      select.value = curr;
    }
  });
}

// ==============================================================================
// Safe DOM Rendering for Media Grids
// ==============================================================================

function renderMediaGrids() {
  renderGrid(DOM.stagedMediaGrid, state.stagedFiles, 'uploads');
  renderGrid(DOM.renderedMediaGrid, state.renderedFiles, 'outputs');
}

function renderGrid(container, files, category) {
  container.replaceChildren();
  
  if (!files || files.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    
    const icon = document.createElement('div');
    icon.className = 'empty-icon';
    icon.textContent = category === 'uploads' ? '🎵' : '🎧';
    
    const p = document.createElement('p');
    p.textContent = category === 'uploads' 
      ? 'No audio files uploaded yet. Drag & drop files above or download from URL.'
      : 'No master tracks rendered yet. Process a track to see results here.';
      
    empty.appendChild(icon);
    empty.appendChild(p);
    container.appendChild(empty);
    return;
  }
  
  files.forEach(file => {
    const meta = file.metadata || {};
    const card = document.createElement('div');
    card.className = 'media-card';
    
    const top = document.createElement('div');
    top.className = 'media-card-top';
    
    const icon = document.createElement('div');
    icon.className = 'media-card-icon';
    icon.textContent = meta.has_video ? '🎬' : '🎵';
    
    const titleBox = document.createElement('div');
    titleBox.className = 'media-card-title';
    
    const h4 = document.createElement('h4');
    h4.textContent = file.filename;
    h4.title = file.filename;
    
    const metaBox = document.createElement('div');
    metaBox.className = 'media-card-meta';
    
    const sizeTag = document.createElement('span');
    sizeTag.className = 'tag';
    sizeTag.textContent = file.size_formatted || '0 KB';
    metaBox.appendChild(sizeTag);
    
    if (meta.duration_formatted) {
      const durTag = document.createElement('span');
      durTag.className = 'tag highlight';
      durTag.textContent = `⏱️ ${meta.duration_formatted}`;
      metaBox.appendChild(durTag);
    }
    
    if (meta.audio_streams && meta.audio_streams.length > 0) {
      const a = meta.audio_streams[0];
      const aTag = document.createElement('span');
      aTag.className = 'tag';
      aTag.textContent = `${a.codec_name} • ${a.sample_rate}Hz • ${a.channel_layout}`;
      metaBox.appendChild(aTag);
    }
    
    titleBox.appendChild(h4);
    titleBox.appendChild(metaBox);
    top.appendChild(icon);
    top.appendChild(titleBox);
    
    const actions = document.createElement('div');
    actions.className = 'media-card-actions';
    
    const playBtn = document.createElement('button');
    playBtn.className = 'btn btn-secondary btn-sm';
    playBtn.textContent = '👁️ Inspect & Play';
    playBtn.addEventListener('click', () => openPreviewModal(file, category));
    
    const dlBtn = document.createElement('a');
    dlBtn.className = 'btn btn-secondary btn-sm';
    dlBtn.textContent = '⬇️';
    dlBtn.title = 'Download Track';
    dlBtn.href = `/api/download/${category}/${encodeURIComponent(file.filename)}`;
    
    const delBtn = document.createElement('button');
    delBtn.className = 'btn btn-danger-outline btn-sm';
    delBtn.textContent = '🗑️';
    delBtn.title = 'Delete';
    delBtn.addEventListener('click', () => deleteFile(category, file.filename));
    
    actions.appendChild(playBtn);
    actions.appendChild(dlBtn);
    actions.appendChild(delBtn);
    
    card.appendChild(top);
    card.appendChild(actions);
    container.appendChild(card);
  });
}

// ==============================================================================
// Modal & Audio Inspector
// ==============================================================================

function openPreviewModal(file, category) {
  DOM.modalMediaTitle.textContent = file.filename;
  DOM.modalPlayerBox.replaceChildren();
  DOM.modalMetadataBox.replaceChildren();
  
  const mediaUrl = `/api/media/${category}/${encodeURIComponent(file.filename)}`;
  DOM.modalDownloadBtn.href = `/api/download/${category}/${encodeURIComponent(file.filename)}`;
  
  const meta = file.metadata || {};
  
  if (meta.has_video) {
    const video = document.createElement('video');
    video.controls = true;
    video.src = mediaUrl;
    video.className = 'media-preview-element';
    DOM.modalPlayerBox.appendChild(video);
  } else {
    const audio = document.createElement('audio');
    audio.controls = true;
    audio.src = mediaUrl;
    audio.style.width = '100%';
    DOM.modalPlayerBox.appendChild(audio);
  }
  
  const table = document.createElement('table');
  table.className = 'metadata-table';
  
  const addRow = (label, val) => {
    if (val === undefined || val === null || val === '') return;
    const tr = document.createElement('tr');
    const td1 = document.createElement('td');
    td1.textContent = label;
    const td2 = document.createElement('td');
    td2.textContent = val;
    tr.appendChild(td1);
    tr.appendChild(td2);
    table.appendChild(tr);
  };
  
  addRow('File Size', file.size_formatted);
  addRow('Duration', meta.duration_formatted);
  addRow('Format', meta.format_name);
  addRow('Bitrate', meta.bitrate_kbps ? `${meta.bitrate_kbps} kbps` : null);
  
  if (meta.tags) {
    if (meta.tags.title) addRow('Title', meta.tags.title);
    if (meta.tags.artist) addRow('Artist', meta.tags.artist);
    if (meta.tags.album) addRow('Album', meta.tags.album);
    if (meta.tags.genre) addRow('Genre', meta.tags.genre);
    if (meta.tags.date) addRow('Year / Date', meta.tags.date);
  }
  
  if (meta.audio_streams && meta.audio_streams.length > 0) {
    const a = meta.audio_streams[0];
    addRow('Audio Codec', `${a.codec_name} (${a.codec_long_name})`);
    addRow('Sample Rate', `${a.sample_rate} Hz`);
    addRow('Channels', `${a.channels} (${a.channel_layout})`);
  }
  
  DOM.modalMetadataBox.appendChild(table);
  DOM.previewModal.style.display = 'flex';
}

function closeModal() {
  DOM.modalPlayerBox.replaceChildren();
  DOM.previewModal.style.display = 'none';
}

// ==============================================================================
// Task Tracking & Real-time Progress Engine
// ==============================================================================

function startJobTracking(jobId, initialTitle) {
  state.activeJobId = jobId;
  DOM.taskDrawer.style.display = 'block';
  DOM.taskTitle.textContent = initialTitle || 'Processing Audio Task...';
  DOM.taskSubtext.textContent = 'Executing FFmpeg pipeline...';
  DOM.taskProgressFill.style.width = '0%';
  DOM.taskPercent.textContent = '0%';
  DOM.taskSpeed.textContent = 'Speed: --';
  DOM.taskLogsContent.textContent = 'Starting process logs...';
  
  if (state.jobPollInterval) clearInterval(state.jobPollInterval);
  
  state.jobPollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/jobs/${jobId}`);
      if (!res.ok) return;
      const job = await res.json();
      
      DOM.taskTitle.textContent = job.title || 'Processing Audio...';
      DOM.taskSubtext.textContent = `Status: ${job.status.toUpperCase()}`;
      
      const pct = job.progress || 0;
      DOM.taskProgressFill.style.width = `${pct}%`;
      DOM.taskPercent.textContent = `${pct}%`;
      DOM.taskSpeed.textContent = `Speed: ${job.speed || '--'}`;
      
      if (job.logs && job.logs.length > 0) {
        DOM.taskLogsContent.textContent = job.logs.slice(-30).join('\n');
        DOM.taskLogsTerminal.scrollTop = DOM.taskLogsTerminal.scrollHeight;
      }
      
      if (job.status === 'completed') {
        clearInterval(state.jobPollInterval);
        state.jobPollInterval = null;
        DOM.taskSubtext.textContent = '✅ Audio Processed Successfully!';
        DOM.taskProgressFill.style.width = '100%';
        DOM.taskPercent.textContent = '100%';
        fetchFiles();
        setTimeout(() => {
          DOM.taskDrawer.style.display = 'none';
          switchTab('tab-outputs');
        }, 2000);
      } else if (job.status === 'failed' || job.status === 'cancelled') {
        clearInterval(state.jobPollInterval);
        state.jobPollInterval = null;
        DOM.taskSubtext.textContent = `❌ ${job.status === 'cancelled' ? 'Cancelled' : 'Failed'}: ${job.error || 'Check logs'}`;
        DOM.taskLogsTerminal.style.display = 'block';
      }
    } catch (err) {
      console.error('Job polling error:', err);
    }
  }, 750);
}

async function cancelCurrentJob() {
  if (!state.activeJobId) return;
  try {
    await fetch(`/api/jobs/${state.activeJobId}/cancel`, { method: 'POST' });
  } catch (err) {
    console.error(err);
  }
}

async function deleteFile(category, filename) {
  if (!confirm(`Delete ${filename}?`)) return;
  try {
    const res = await fetch(`/api/files/${category}/${encodeURIComponent(filename)}`, { method: 'DELETE' });
    if (res.ok) fetchFiles();
  } catch (err) {
    alert(`Failed to delete: ${err.message}`);
  }
}

async function clearFiles(category) {
  if (!confirm(`Clear all ${category}?`)) return;
  try {
    const res = await fetch(`/api/files/clear?category=${category}`, { method: 'POST' });
    if (res.ok) fetchFiles();
  } catch (err) {
    console.error(err);
  }
}

// ==============================================================================
// Feature Operations (Join, Convert, Trim, Loudness, Pitch, EQ, ID3 Tags)
// ==============================================================================

function setupEventHandlers() {
  DOM.closeModalBtn.addEventListener('click', closeModal);
  DOM.modalCloseActionBtn.addEventListener('click', closeModal);
  DOM.previewModal.addEventListener('click', (e) => {
    if (e.target === DOM.previewModal) closeModal();
  });
  
  DOM.refreshFilesBtn.addEventListener('click', fetchFiles);
  DOM.refreshOutputsBtn.addEventListener('click', fetchFiles);
  DOM.clearUploadsBtn.addEventListener('click', () => clearFiles('uploads'));
  DOM.clearOutputsBtn.addEventListener('click', () => clearFiles('outputs'));
  
  DOM.toggleLogsBtn.addEventListener('click', () => {
    const isVis = DOM.taskLogsTerminal.style.display === 'block';
    DOM.taskLogsTerminal.style.display = isVis ? 'none' : 'block';
  });
  DOM.cancelTaskBtn.addEventListener('click', cancelCurrentJob);
  
  // URL Downloader Paste
  DOM.pasteUrlBtn.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) DOM.ytdlUrl.value = text.trim();
    } catch {
      const input = prompt('Paste audio/media URL here:');
      if (input) DOM.ytdlUrl.value = input.trim();
    }
  });
  
  // Start URL Download
  DOM.startDownloadBtn.addEventListener('click', async () => {
    const url = DOM.ytdlUrl.value.trim();
    if (!url) return alert('Please enter a media URL.');
    const preset = DOM.ytdlPreset.value;
    
    try {
      const res = await fetch('/api/download-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, preset })
      });
      const data = await res.json();
      if (res.ok && data.job_id) {
        startJobTracking(data.job_id, `Downloading: ${url.substring(0, 30)}...`);
        DOM.ytdlUrl.value = '';
      } else {
        alert(data.detail || 'Download request failed');
      }
    } catch (err) {
      alert(`Download error: ${err.message}`);
    }
  });
  
  // Start Multi-Track Join
  DOM.startJoinBtn.addEventListener('click', async () => {
    const selected = getSelectedJoinFiles();
    if (selected.length < 2) return alert('Please select at least 2 audio tracks to join.');
    
    const payload = {
      filenames: selected,
      output_format: DOM.joinFormat.value,
      bitrate_kbps: 320,
      crossfade_sec: parseFloat(DOM.joinCrossfade.value)
    };
    
    try {
      const res = await fetch('/api/ops/audio-join', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok && data.job_id) {
        startJobTracking(data.job_id, `Joining ${selected.length} audio tracks`);
      } else {
        alert(data.detail || 'Join failed');
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  });
  
  // Start Audio Convert
  DOM.startConvertBtn.addEventListener('click', async () => {
    const filename = DOM.convertSourceFile.value;
    if (!filename) return alert('Please select an audio file.');
    
    const payload = {
      filename,
      output_format: DOM.convertOutputFormat.value,
      bitrate_kbps: parseInt(DOM.convertAudioBitrate.value, 10),
      sample_rate: DOM.convertSampleRate.value,
      channels: DOM.convertChannels.value
    };
    
    try {
      const res = await fetch('/api/ops/audio-convert', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok && data.job_id) {
        startJobTracking(data.job_id, `Converting ${filename} to ${payload.output_format.toUpperCase()}`);
      } else {
        alert(data.detail || 'Conversion failed');
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  });
  
  // Trimmer Sync & Player
  DOM.trimSourceFile.addEventListener('change', syncTrimSource);
  DOM.setTrimStartBtn.addEventListener('click', () => {
    DOM.trimStartTime.value = formatSecondsToTime(DOM.trimAudioPlayer.currentTime);
  });
  DOM.setTrimEndBtn.addEventListener('click', () => {
    DOM.trimEndTime.value = formatSecondsToTime(DOM.trimAudioPlayer.currentTime);
  });
  
  DOM.startTrimBtn.addEventListener('click', async () => {
    const filename = DOM.trimSourceFile.value;
    if (!filename) return alert('Please select an audio file to trim.');
    
    const payload = {
      filename,
      start_time: DOM.trimStartTime.value,
      end_time: DOM.trimEndTime.value,
      fade_in_sec: parseFloat(DOM.trimFadeIn.value) || 0.0,
      fade_out_sec: parseFloat(DOM.trimFadeOut.value) || 0.0,
      output_format: DOM.trimFormat.value
    };
    
    try {
      const res = await fetch('/api/ops/audio-trim', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok && data.job_id) {
        startJobTracking(data.job_id, `Trimming ${filename}`);
      } else {
        alert(data.detail || 'Trim failed');
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  });
  
  // Volume / Loudness Radios
  document.querySelectorAll('input[name="loudnessMode"]').forEach(r => {
    r.addEventListener('change', () => {
      const isEbu = r.value === 'ebur128';
      DOM.ebur128SettingsRow.style.display = isEbu ? 'grid' : 'none';
      DOM.boostSettingsRow.style.display = isEbu ? 'none' : 'grid';
    });
  });
  
  DOM.volumeMultiplier.addEventListener('input', (e) => {
    DOM.volumeMultiplierDisplay.textContent = `${Math.round(e.target.value * 100)}%`;
  });
  
  DOM.startLoudnessBtn.addEventListener('click', async () => {
    const filename = DOM.loudnessSourceFile.value;
    if (!filename) return alert('Please select an audio file.');
    
    const mode = document.querySelector('input[name="loudnessMode"]:checked').value;
    const payload = {
      filename,
      mode,
      volume_multiplier: parseFloat(DOM.volumeMultiplier.value),
      target_lufs: parseFloat(DOM.targetLufs.value)
    };
    
    try {
      const res = await fetch('/api/ops/audio-loudness', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok && data.job_id) {
        startJobTracking(data.job_id, `Normalizing loudness on ${filename}`);
      } else {
        alert(data.detail || 'Loudness failed');
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  });
  
  // Pitch & Tempo Sliders
  DOM.audioTempoSlider.addEventListener('input', (e) => {
    DOM.audioTempoDisplay.textContent = `${parseFloat(e.target.value).toFixed(2)}x`;
  });
  DOM.pitchSemitones.addEventListener('input', (e) => {
    const v = parseInt(e.target.value, 10);
    DOM.pitchSemitonesDisplay.textContent = `${v > 0 ? '+' : ''}${v} Semitones`;
  });
  
  DOM.startPitchBtn.addEventListener('click', async () => {
    const filename = DOM.pitchSourceFile.value;
    if (!filename) return alert('Please select an audio file.');
    
    const payload = {
      filename,
      tempo: parseFloat(DOM.audioTempoSlider.value),
      pitch_semitones: parseInt(DOM.pitchSemitones.value, 10),
      reverse: DOM.reverseAudio.checked
    };
    
    try {
      const res = await fetch('/api/ops/audio-pitch-tempo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok && data.job_id) {
        startJobTracking(data.job_id, `Applying Pitch/Tempo shift on ${filename}`);
      } else {
        alert(data.detail || 'Shift failed');
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  });
  
  // Equalizer Cards Selection
  DOM.eqCards.forEach(card => {
    card.addEventListener('click', () => {
      DOM.eqCards.forEach(c => c.classList.remove('active'));
      card.classList.add('active');
      state.selectedEqPreset = card.getAttribute('data-preset');
    });
  });
  
  DOM.startEqBtn.addEventListener('click', async () => {
    const filename = DOM.eqSourceFile.value;
    if (!filename) return alert('Please select an audio file.');
    
    const payload = {
      filename,
      preset: state.selectedEqPreset
    };
    
    try {
      const res = await fetch('/api/ops/audio-eq', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok && data.job_id) {
        startJobTracking(data.job_id, `Applying EQ Preset on ${filename}`);
      } else {
        alert(data.detail || 'EQ failed');
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  });
  
  // ID3 Tag Editor
  DOM.startTagBtn.addEventListener('click', async () => {
    const filename = DOM.tagSourceFile.value;
    if (!filename) return alert('Please select an audio file.');
    
    const payload = {
      filename,
      title: DOM.tagTitle.value.trim() || null,
      artist: DOM.tagArtist.value.trim() || null,
      album: DOM.tagAlbum.value.trim() || null,
      genre: DOM.tagGenre.value.trim() || null,
      year: DOM.tagYear.value.trim() || null
    };
    
    try {
      const res = await fetch('/api/ops/audio-tag', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok) {
        alert(`ID3 Tags saved successfully to ${data.output_filename}!`);
        fetchFiles();
        switchTab('tab-outputs');
      } else {
        alert(data.detail || 'Tagging failed');
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  });
}

function syncTrimSource() {
  const fn = DOM.trimSourceFile.value;
  if (!fn) {
    DOM.trimAudioPlayer.removeAttribute('src');
    return;
  }
  DOM.trimAudioPlayer.src = `/api/media/uploads/${encodeURIComponent(fn)}`;
}

function formatSecondsToTime(sec) {
  if (isNaN(sec) || sec < 0) return '00:00:00';
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function renderJoinList() {
  DOM.joinFileList.replaceChildren();
  if (state.stagedFiles.length === 0) {
    const empty = document.createElement('p');
    empty.className = 'helper-text';
    empty.textContent = 'No staged tracks. Upload audio files first to enable joining.';
    DOM.joinFileList.appendChild(empty);
    return;
  }
  
  state.stagedFiles.forEach(file => {
    const item = document.createElement('div');
    item.className = 'merge-item';
    
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = true;
    cb.value = file.filename;
    cb.className = 'join-checkbox';
    
    const handle = document.createElement('span');
    handle.className = 'merge-item-handle';
    handle.textContent = '🎵';
    
    const title = document.createElement('span');
    title.className = 'merge-item-title';
    title.textContent = file.filename;
    
    const dur = document.createElement('span');
    dur.className = 'tag';
    dur.textContent = file.metadata?.duration_formatted || file.size_formatted;
    
    item.appendChild(cb);
    item.appendChild(handle);
    item.appendChild(title);
    item.appendChild(dur);
    
    DOM.joinFileList.appendChild(item);
  });
}

function getSelectedJoinFiles() {
  const checkboxes = DOM.joinFileList.querySelectorAll('.join-checkbox:checked');
  const selected = [];
  checkboxes.forEach(cb => selected.push(cb.value));
  return selected;
}
