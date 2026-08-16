/**
 * OmniMedia Studio - Frontend Application Engine
 * Pure Vanilla JavaScript with secure DOM manipulation and real-time task polling.
 */

// Application State
const state = {
  activeTab: 'tab-upload',
  stagedFiles: [],
  renderedFiles: [],
  activeJobId: null,
  jobPollInterval: null,
  systemInfo: {}
};

// DOM Elements Cache
const DOM = {
  navItems: document.querySelectorAll('.nav-item'),
  tabPanels: document.querySelectorAll('.tab-panel'),
  
  // System Badges
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
  
  // URL Downloader
  ytdlUrl: document.getElementById('ytdlUrl'),
  ytdlPreset: document.getElementById('ytdlPreset'),
  pasteUrlBtn: document.getElementById('pasteUrlBtn'),
  startDownloadBtn: document.getElementById('startDownloadBtn'),
  
  // Merge
  mergeFileList: document.getElementById('mergeFileList'),
  mergeFormat: document.getElementById('mergeFormat'),
  mergeResolution: document.getElementById('mergeResolution'),
  startMergeBtn: document.getElementById('startMergeBtn'),
  
  // Convert
  convertSourceFile: document.getElementById('convertSourceFile'),
  convertOutputFormat: document.getElementById('convertOutputFormat'),
  convertVideoCodec: document.getElementById('convertVideoCodec'),
  convertAudioCodec: document.getElementById('convertAudioCodec'),
  convertCrf: document.getElementById('convertCrf'),
  crfValueDisplay: document.getElementById('crfValueDisplay'),
  convertPreset: document.getElementById('convertPreset'),
  convertAudioBitrate: document.getElementById('convertAudioBitrate'),
  videoCodecGroup: document.getElementById('videoCodecGroup'),
  videoSettingsRow: document.getElementById('videoSettingsRow'),
  audioSettingsRow: document.getElementById('audioSettingsRow'),
  startConvertBtn: document.getElementById('startConvertBtn'),
  
  // Trim
  trimSourceFile: document.getElementById('trimSourceFile'),
  trimPreviewPlayer: document.getElementById('trimPreviewPlayer'),
  trimStartTime: document.getElementById('trimStartTime'),
  trimEndTime: document.getElementById('trimEndTime'),
  setTrimStartBtn: document.getElementById('setTrimStartBtn'),
  setTrimEndBtn: document.getElementById('setTrimEndBtn'),
  startTrimBtn: document.getElementById('startTrimBtn'),
  
  // Compress
  compressSourceFile: document.getElementById('compressSourceFile'),
  compressTargetSize: document.getElementById('compressTargetSize'),
  compressResolution: document.getElementById('compressResolution'),
  startCompressBtn: document.getElementById('startCompressBtn'),
  
  // Audio Studio
  audioVideoFile: document.getElementById('audioVideoFile'),
  audioTrackFile: document.getElementById('audioTrackFile'),
  audioTrackFileGroup: document.getElementById('audioTrackFileGroup'),
  audioExtractFormatRow: document.getElementById('audioExtractFormatRow'),
  audioVolumeControlsRow: document.getElementById('audioVolumeControlsRow'),
  audioOrigVol: document.getElementById('audioOrigVol'),
  audioNewVol: document.getElementById('audioNewVol'),
  audioOrigVolDisplay: document.getElementById('audioOrigVolDisplay'),
  audioNewVolDisplay: document.getElementById('audioNewVolDisplay'),
  audioExtractFormat: document.getElementById('audioExtractFormat'),
  startAudioOpBtn: document.getElementById('startAudioOpBtn'),
  
  // Effects & Speed
  effectSourceFile: document.getElementById('effectSourceFile'),
  effectSpeed: document.getElementById('effectSpeed'),
  speedValueDisplay: document.getElementById('speedValueDisplay'),
  effectRotate: document.getElementById('effectRotate'),
  effectHflip: document.getElementById('effectHflip'),
  effectVflip: document.getElementById('effectVflip'),
  effectReverse: document.getElementById('effectReverse'),
  startEffectBtn: document.getElementById('startEffectBtn'),
  
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
// Initialization & Navigation
// ==============================================================================

document.addEventListener('DOMContentLoaded', () => {
  setupNavigation();
  setupDropZone();
  setupEventHandlers();
  fetchSystemInfo();
  fetchFiles();
  
  // System polling
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
  
  // Trigger tab-specific updates
  if (tabId === 'tab-merge') renderMergeList();
  if (tabId === 'tab-trim') syncTrimSource();
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
    console.error('Failed to fetch system info:', err);
  }
}

async function fetchFiles() {
  try {
    const res = await fetch('/api/files');
    if (!res.ok) return;
    const data = await res.json();
    state.stagedFiles = data.uploads || [];
    state.renderedFiles = data.outputs || [];
    
    // Update badge counts
    DOM.uploadCountBadge.textContent = state.stagedFiles.length;
    DOM.outputCountBadge.textContent = state.renderedFiles.length;
    DOM.stagedFilesCount.textContent = state.stagedFiles.length;
    DOM.renderedFilesCount.textContent = state.renderedFiles.length;
    
    renderMediaGrids();
    populateSelectDropdowns();
  } catch (err) {
    console.error('Failed to fetch files:', err);
  }
}

function populateSelectDropdowns() {
  const selects = [
    DOM.convertSourceFile,
    DOM.trimSourceFile,
    DOM.compressSourceFile,
    DOM.audioVideoFile,
    DOM.audioTrackFile,
    DOM.effectSourceFile
  ];
  
  selects.forEach(select => {
    if (!select) return;
    const currentVal = select.value;
    select.replaceChildren();
    
    if (state.stagedFiles.length === 0) {
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = '-- No staged media files available --';
      select.appendChild(opt);
      return;
    }
    
    state.stagedFiles.forEach(file => {
      const opt = document.createElement('option');
      opt.value = file.filename;
      const meta = file.metadata || {};
      const res = meta.video_streams && meta.video_streams[0] ? ` [${meta.video_streams[0].resolution}]` : '';
      const dur = meta.duration_formatted ? ` (${meta.duration_formatted})` : '';
      opt.textContent = `${file.filename}${res}${dur}`;
      select.appendChild(opt);
    });
    
    if (currentVal && state.stagedFiles.some(f => f.filename === currentVal)) {
      select.value = currentVal;
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
    icon.textContent = category === 'uploads' ? '📂' : '📦';
    
    const p = document.createElement('p');
    p.textContent = category === 'uploads' 
      ? 'No media files uploaded yet. Drag & drop files above or download from URL.'
      : 'No rendered outputs yet. Complete a media operation to see results here.';
      
    empty.appendChild(icon);
    empty.appendChild(p);
    container.appendChild(empty);
    return;
  }
  
  files.forEach(file => {
    const meta = file.metadata || {};
    const card = document.createElement('div');
    card.className = 'media-card';
    
    // Top Row
    const top = document.createElement('div');
    top.className = 'media-card-top';
    
    const icon = document.createElement('div');
    icon.className = 'media-card-icon';
    icon.textContent = meta.has_video ? '🎬' : (meta.has_audio ? '🎵' : '📄');
    
    const titleBox = document.createElement('div');
    titleBox.className = 'media-card-title';
    
    const h4 = document.createElement('h4');
    h4.textContent = file.filename;
    h4.title = file.filename;
    
    const metaBox = document.createElement('div');
    metaBox.className = 'media-card-meta';
    
    const sizeTag = document.createElement('span');
    sizeTag.className = 'tag';
    sizeTag.textContent = file.size_formatted || '0 MB';
    metaBox.appendChild(sizeTag);
    
    if (meta.duration_formatted) {
      const durTag = document.createElement('span');
      durTag.className = 'tag highlight';
      durTag.textContent = `⏱️ ${meta.duration_formatted}`;
      metaBox.appendChild(durTag);
    }
    
    if (meta.video_streams && meta.video_streams.length > 0) {
      const v = meta.video_streams[0];
      const resTag = document.createElement('span');
      resTag.className = 'tag';
      resTag.textContent = `${v.resolution} • ${v.codec_name}`;
      metaBox.appendChild(resTag);
    }
    
    if (meta.audio_streams && meta.audio_streams.length > 0) {
      const a = meta.audio_streams[0];
      const aTag = document.createElement('span');
      aTag.className = 'tag';
      aTag.textContent = `${a.codec_name} • ${a.channel_layout}`;
      metaBox.appendChild(aTag);
    }
    
    titleBox.appendChild(h4);
    titleBox.appendChild(metaBox);
    top.appendChild(icon);
    top.appendChild(titleBox);
    
    // Actions Row
    const actions = document.createElement('div');
    actions.className = 'media-card-actions';
    
    const playBtn = document.createElement('button');
    playBtn.className = 'btn btn-secondary btn-sm';
    playBtn.textContent = '👁️ Inspect';
    playBtn.addEventListener('click', () => openPreviewModal(file, category));
    
    const dlBtn = document.createElement('a');
    dlBtn.className = 'btn btn-secondary btn-sm';
    dlBtn.textContent = '⬇️';
    dlBtn.title = 'Download';
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
// Drag & Drop File Upload
// ==============================================================================

function setupDropZone() {
  const zone = DOM.dropZone;
  
  ['dragenter', 'dragover'].forEach(eventName => {
    zone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      zone.classList.add('dragover');
    });
  });
  
  ['dragleave', 'drop'].forEach(eventName => {
    zone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      zone.classList.remove('dragover');
    });
  });
  
  zone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files && files.length > 0) {
      handleFilesUpload(files);
    }
  });
  
  DOM.fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFilesUpload(e.target.files);
    }
  });
}

function handleFilesUpload(files) {
  const formData = new FormData();
  for (let i = 0; i < files.length; i++) {
    formData.append('files', files[i]);
  }
  
  DOM.uploadProgressBar.style.display = 'flex';
  DOM.uploadProgressFill.style.width = '0%';
  DOM.uploadProgressText.textContent = 'Uploading... 0%';
  
  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/upload', true);
  
  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) {
      const pct = Math.round((e.loaded / e.total) * 100);
      DOM.uploadProgressFill.style.width = `${pct}%`;
      DOM.uploadProgressText.textContent = `Uploading... ${pct}%`;
    }
  };
  
  xhr.onload = () => {
    DOM.uploadProgressBar.style.display = 'none';
    if (xhr.status === 200) {
      fetchFiles();
    } else {
      alert(`Upload failed with status ${xhr.status}`);
    }
  };
  
  xhr.onerror = () => {
    DOM.uploadProgressBar.style.display = 'none';
    alert('Upload network error occurred.');
  };
  
  xhr.send(formData);
}

// ==============================================================================
// File Operations & Deletion
// ==============================================================================

async function deleteFile(category, filename) {
  if (!confirm(`Are you sure you want to delete ${filename}?`)) return;
  try {
    const res = await fetch(`/api/files/${category}/${encodeURIComponent(filename)}`, { method: 'DELETE' });
    if (res.ok) {
      fetchFiles();
    } else {
      const data = await res.json();
      alert(`Delete error: ${data.detail || 'Unknown'}`);
    }
  } catch (err) {
    alert(`Failed to delete: ${err.message}`);
  }
}

async function clearFiles(category) {
  if (!confirm(`Are you sure you want to clear all ${category}?`)) return;
  try {
    const res = await fetch(`/api/files/clear?category=${category}`, { method: 'POST' });
    if (res.ok) {
      fetchFiles();
    }
  } catch (err) {
    console.error(err);
  }
}

// ==============================================================================
// Media Inspector Modal
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
    video.autoplay = false;
    video.src = mediaUrl;
    video.className = 'media-preview-element';
    DOM.modalPlayerBox.appendChild(video);
  } else if (meta.has_audio) {
    const audio = document.createElement('audio');
    audio.controls = true;
    audio.src = mediaUrl;
    audio.style.width = '100%';
    DOM.modalPlayerBox.appendChild(audio);
  } else {
    const img = document.createElement('img');
    img.src = mediaUrl;
    img.style.maxWidth = '100%';
    img.style.maxHeight = '360px';
    DOM.modalPlayerBox.appendChild(img);
  }
  
  // Render Metadata Table
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
  
  addRow('File Size', file.size_formatted || `${file.size_bytes} bytes`);
  addRow('Duration', meta.duration_formatted || `${meta.duration}s`);
  addRow('Format Container', meta.format_name);
  addRow('Total Bitrate', meta.bitrate_kbps ? `${meta.bitrate_kbps} kbps` : null);
  
  if (meta.video_streams && meta.video_streams.length > 0) {
    const v = meta.video_streams[0];
    addRow('Video Codec', `${v.codec_name} (${v.codec_long_name})`);
    addRow('Resolution', v.resolution);
    addRow('Framerate (FPS)', `${v.fps} fps`);
    addRow('Pixel Format', v.pix_fmt);
    addRow('Aspect Ratio', v.aspect_ratio);
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
// Task Polling & Floating Drawer Manager
// ==============================================================================

function startJobTracking(jobId, initialTitle) {
  state.activeJobId = jobId;
  DOM.taskDrawer.style.display = 'block';
  DOM.taskTitle.textContent = initialTitle || 'Processing Task...';
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
      
      DOM.taskTitle.textContent = job.title || 'Processing Media...';
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
        DOM.taskSubtext.textContent = '✅ Completed Successfully!';
        DOM.taskProgressFill.style.width = '100%';
        DOM.taskPercent.textContent = '100%';
        fetchFiles();
        setTimeout(() => {
          DOM.taskDrawer.style.display = 'none';
          switchTab('tab-outputs');
        }, 2200);
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

// ==============================================================================
// Feature Handlers (Merge, Convert, Trim, Compress, Audio, Transform)
// ==============================================================================

function setupEventHandlers() {
  // Modal close handlers
  DOM.closeModalBtn.addEventListener('click', closeModal);
  DOM.modalCloseActionBtn.addEventListener('click', closeModal);
  DOM.previewModal.addEventListener('click', (e) => {
    if (e.target === DOM.previewModal) closeModal();
  });
  
  // Refresh / Clear Buttons
  DOM.refreshFilesBtn.addEventListener('click', fetchFiles);
  DOM.refreshOutputsBtn.addEventListener('click', fetchFiles);
  DOM.clearUploadsBtn.addEventListener('click', () => clearFiles('uploads'));
  DOM.clearOutputsBtn.addEventListener('click', () => clearFiles('outputs'));
  
  // Task Drawer
  DOM.toggleLogsBtn.addEventListener('click', () => {
    const isVisible = DOM.taskLogsTerminal.style.display === 'block';
    DOM.taskLogsTerminal.style.display = isVisible ? 'none' : 'block';
  });
  DOM.cancelTaskBtn.addEventListener('click', cancelCurrentJob);
  
  // URL Downloader Paste
  DOM.pasteUrlBtn.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) DOM.ytdlUrl.value = text.trim();
    } catch {
      const input = prompt('Paste media URL here:');
      if (input) DOM.ytdlUrl.value = input.trim();
    }
  });
  
  // Start URL Download
  DOM.startDownloadBtn.addEventListener('click', async () => {
    const url = DOM.ytdlUrl.value.trim();
    if (!url) {
      alert('Please enter a media URL.');
      return;
    }
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
      alert(`Error starting download: ${err.message}`);
    }
  });
  
  // Convert Controls Form Dynamics
  DOM.convertOutputFormat.addEventListener('change', () => {
    const fmt = DOM.convertOutputFormat.value;
    const isAudio = ['mp3', 'wav', 'aac', 'flac', 'ogg', 'm4a'].includes(fmt);
    const isGif = fmt === 'gif';
    
    if (isAudio) {
      DOM.videoCodecGroup.style.display = 'none';
      DOM.videoSettingsRow.style.display = 'none';
      DOM.audioSettingsRow.style.display = 'grid';
    } else if (isGif) {
      DOM.videoCodecGroup.style.display = 'none';
      DOM.videoSettingsRow.style.display = 'none';
      DOM.audioSettingsRow.style.display = 'none';
    } else {
      DOM.videoCodecGroup.style.display = 'flex';
      DOM.videoSettingsRow.style.display = 'grid';
      DOM.audioSettingsRow.style.display = 'grid';
    }
  });
  
  DOM.convertCrf.addEventListener('input', (e) => {
    DOM.crfValueDisplay.textContent = e.target.value;
  });
  
  // Start Convert
  DOM.startConvertBtn.addEventListener('click', async () => {
    const filename = DOM.convertSourceFile.value;
    if (!filename) return alert('Please select a source file.');
    
    const payload = {
      filename,
      output_format: DOM.convertOutputFormat.value,
      video_codec: DOM.convertVideoCodec.value,
      audio_codec: DOM.convertAudioCodec.value,
      crf: parseInt(DOM.convertCrf.value, 10),
      preset: DOM.convertPreset.value,
      audio_bitrate_kbps: parseInt(DOM.convertAudioBitrate.value, 10)
    };
    
    try {
      const res = await fetch('/api/ops/convert', {
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
  
  // Start Merge
  DOM.startMergeBtn.addEventListener('click', async () => {
    const selected = getSelectedMergeFiles();
    if (selected.length < 2) {
      alert('Please select at least 2 files to merge.');
      return;
    }
    
    const payload = {
      filenames: selected,
      output_format: DOM.mergeFormat.value,
      normalize_resolution: DOM.mergeResolution.value !== 'original',
      target_resolution: DOM.mergeResolution.value
    };
    
    try {
      const res = await fetch('/api/ops/merge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok && data.job_id) {
        startJobTracking(data.job_id, `Merging ${selected.length} files`);
      } else {
        alert(data.detail || 'Merge request failed');
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  });
  
  // Trim & Player Sync
  DOM.trimSourceFile.addEventListener('change', syncTrimSource);
  DOM.setTrimStartBtn.addEventListener('click', () => {
    DOM.trimStartTime.value = formatSecondsToTime(DOM.trimPreviewPlayer.currentTime);
  });
  DOM.setTrimEndBtn.addEventListener('click', () => {
    DOM.trimEndTime.value = formatSecondsToTime(DOM.trimPreviewPlayer.currentTime);
  });
  
  DOM.startTrimBtn.addEventListener('click', async () => {
    const filename = DOM.trimSourceFile.value;
    if (!filename) return alert('Please select a file to trim.');
    
    const mode = document.querySelector('input[name="trimMode"]:checked').value;
    const payload = {
      filename,
      start_time: DOM.trimStartTime.value,
      end_time: DOM.trimEndTime.value,
      mode
    };
    
    try {
      const res = await fetch('/api/ops/trim', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok && data.job_id) {
        startJobTracking(data.job_id, `Trimming ${filename}`);
      } else {
        alert(data.detail || 'Trim request failed');
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  });
  
  // Compress Presets
  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      DOM.compressTargetSize.value = btn.getAttribute('data-size');
    });
  });
  
  DOM.startCompressBtn.addEventListener('click', async () => {
    const filename = DOM.compressSourceFile.value;
    if (!filename) return alert('Please select a video file.');
    
    const sizeVal = parseFloat(DOM.compressTargetSize.value);
    const payload = {
      filename,
      target_size_mb: isNaN(sizeVal) ? null : sizeVal,
      resolution_scale: DOM.compressResolution.value
    };
    
    try {
      const res = await fetch('/api/ops/compress', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok && data.job_id) {
        startJobTracking(data.job_id, `Compressing ${filename}`);
      } else {
        alert(data.detail || 'Compress request failed');
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  });
  
  // Audio Studio Action Radios
  document.querySelectorAll('input[name="audioStudioAction"]').forEach(radio => {
    radio.addEventListener('change', () => {
      const act = radio.value;
      if (act === 'extract') {
        DOM.audioTrackFileGroup.style.display = 'none';
        DOM.audioExtractFormatRow.style.display = 'grid';
        DOM.audioVolumeControlsRow.style.display = 'none';
      } else if (act === 'replace') {
        DOM.audioTrackFileGroup.style.display = 'flex';
        DOM.audioExtractFormatRow.style.display = 'none';
        DOM.audioVolumeControlsRow.style.display = 'none';
      } else { // mix
        DOM.audioTrackFileGroup.style.display = 'flex';
        DOM.audioExtractFormatRow.style.display = 'none';
        DOM.audioVolumeControlsRow.style.display = 'grid';
      }
    });
  });
  
  DOM.audioOrigVol.addEventListener('input', (e) => {
    DOM.audioOrigVolDisplay.textContent = `${Math.round(e.target.value * 100)}%`;
  });
  DOM.audioNewVol.addEventListener('input', (e) => {
    DOM.audioNewVolDisplay.textContent = `${Math.round(e.target.value * 100)}%`;
  });
  
  DOM.startAudioOpBtn.addEventListener('click', async () => {
    const act = document.querySelector('input[name="audioStudioAction"]:checked').value;
    const vFile = DOM.audioVideoFile.value;
    if (!vFile) return alert('Please select a video file.');
    
    if (act === 'extract') {
      const payload = {
        filename: vFile,
        output_format: DOM.audioExtractFormat.value,
        video_codec: 'none',
        audio_codec: DOM.audioExtractFormat.value === 'wav' ? 'pcm_s16le' : (DOM.audioExtractFormat.value === 'mp3' ? 'libmp3lame' : 'aac'),
        audio_bitrate_kbps: 320
      };
      const res = await fetch('/api/ops/convert', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok && data.job_id) startJobTracking(data.job_id, `Extracting audio from ${vFile}`);
    } else {
      const aFile = DOM.audioTrackFile.value;
      if (!aFile) return alert('Please select an audio track file.');
      const payload = {
        video_filename: vFile,
        audio_filename: aFile,
        action: act,
        video_volume: parseFloat(DOM.audioOrigVol.value),
        audio_volume: parseFloat(DOM.audioNewVol.value)
      };
      const res = await fetch('/api/ops/audio-replace', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok && data.job_id) startJobTracking(data.job_id, `${act.toUpperCase()} audio on ${vFile}`);
    }
  });
  
  // Transform & Effects
  DOM.effectSpeed.addEventListener('input', (e) => {
    DOM.speedValueDisplay.textContent = `${e.target.value}x`;
  });
  
  DOM.startEffectBtn.addEventListener('click', async () => {
    const filename = DOM.effectSourceFile.value;
    if (!filename) return alert('Please select a media file.');
    
    const payload = {
      filename,
      speed: parseFloat(DOM.effectSpeed.value),
      rotate: parseInt(DOM.effectRotate.value, 10),
      hflip: DOM.effectHflip.checked,
      vflip: DOM.effectVflip.checked,
      reverse: DOM.effectReverse.checked
    };
    
    try {
      const res = await fetch('/api/ops/transform', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok && data.job_id) {
        startJobTracking(data.job_id, `Transforming ${filename}`);
      } else {
        alert(data.detail || 'Transform request failed');
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  });
}

// ==============================================================================
// Helpers
// ==============================================================================

function syncTrimSource() {
  const fn = DOM.trimSourceFile.value;
  if (!fn) {
    DOM.trimPreviewPlayer.removeAttribute('src');
    return;
  }
  DOM.trimPreviewPlayer.src = `/api/media/uploads/${encodeURIComponent(fn)}`;
}

function formatSecondsToTime(sec) {
  if (isNaN(sec) || sec < 0) return '00:00:00';
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function renderMergeList() {
  DOM.mergeFileList.replaceChildren();
  if (state.stagedFiles.length === 0) {
    const empty = document.createElement('p');
    empty.className = 'helper-text';
    empty.textContent = 'No staged files. Upload files first to enable merging.';
    DOM.mergeFileList.appendChild(empty);
    return;
  }
  
  state.stagedFiles.forEach(file => {
    const item = document.createElement('div');
    item.className = 'merge-item';
    
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = true;
    cb.value = file.filename;
    cb.className = 'merge-checkbox';
    
    const handle = document.createElement('span');
    handle.className = 'merge-item-handle';
    handle.textContent = '☰';
    
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
    
    DOM.mergeFileList.appendChild(item);
  });
}

function getSelectedMergeFiles() {
  const checkboxes = DOM.mergeFileList.querySelectorAll('.merge-checkbox:checked');
  const selected = [];
  checkboxes.forEach(cb => selected.push(cb.value));
  return selected;
}
