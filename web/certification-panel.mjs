import { CertificationHost } from './certification-host.mjs';
import { captureEditConfigV1, createEditConfigApplicator } from './certification-edit-config.mjs';

const TRACE_LABELS = Object.freeze([
  'schema', 'total-ticks', 'room', 'ego-x', 'ego-y', 'ego-direction',
  'on-water', 'hit-special', 'ego-edge', 'ego-view', 'ego-loop', 'ego-cel',
  'ego-priority', 'user-control', 'hold-key', 'game-clock',
]);

const DIGEST_LABELS = Object.freeze([
  'schema',
  'core-state',
  'animated-objects',
  'resources-inventory-script',
  'strings-words-controller-map',
  'random-stream',
  'room',
  'terminal-state',
]);

function hex32(value) {
  return `0x${(Number(value) >>> 0).toString(16).padStart(8, '0')}`;
}

function humanBytes(bytes) {
  const size = Number(bytes) || 0;
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KiB`;
  return `${(size / (1024 * 1024)).toFixed(2)} MiB`;
}

function editConfigIdentity(config) {
  const hash = String(config?.hash ?? 'none');
  const shortHash = hash.startsWith('sha256:') ? `sha256:${hash.slice(7, 19)}` : hash;
  return `${shortHash} · ${config?.rooms?.length ?? 0} room(s) · ${config?.visualPins?.length ?? 0} visual pin(s)`;
}

function formatResultWithEditConfig(result, config) {
  return `${formatCertificationResult(result)}\neditConfig=${editConfigIdentity(config)}`;
}

function monotonicNow() {
  return globalThis.performance?.now?.() ?? Date.now();
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function getGameFilesDirectory(storageRoot) {
  try {
    return await storageRoot.getDirectoryHandle('Game Files', { create: false });
  } catch (error) {
    if (error?.name === 'NotFoundError') return null;
    throw error;
  }
}

export async function discoverImportedGames(storageRoot = null) {
  const root = storageRoot ?? await navigator.storage.getDirectory();
  const gameFilesDir = await getGameFilesDirectory(root);
  if (!gameFilesDir) return [];

  const games = [];
  for await (const [directoryName, handle] of gameFilesDir.entries()) {
    if (!handle || handle.kind !== 'directory') continue;
    try {
      const dataHandle = await handle.getFileHandle('GAMEFILES.DAT', { create: false });
      const file = await dataHandle.getFile();
      if (file.size > 0) games.push({ directoryName, size: file.size });
    } catch (error) {
      if (error?.name !== 'NotFoundError') throw error;
    }
  }
  games.sort((a, b) => a.directoryName.localeCompare(b.directoryName));
  return games;
}

export async function readImportedGame(directoryName, storageRoot = null) {
  if (!directoryName) throw new Error('Choose an imported game first.');
  const root = storageRoot ?? await navigator.storage.getDirectory();
  const gameFilesDir = await getGameFilesDirectory(root);
  if (!gameFilesDir) throw new Error('No AGILE Game Files directory exists in this browser.');
  const gameDir = await gameFilesDir.getDirectoryHandle(directoryName, { create: false });
  const dataHandle = await gameDir.getFileHandle('GAMEFILES.DAT', { create: false });
  const file = await dataHandle.getFile();
  if (!file.size) throw new Error(`Imported game ${directoryName} has an empty GAMEFILES.DAT.`);
  return file.arrayBuffer();
}

export function divergenceCategory(result) {
  if (!result || result.status !== 'DIVERGED') return null;
  if (result.reason === 'trace') return `trace:${TRACE_LABELS[result.index] ?? `slot-${result.index}`}`;
  if (result.reason === 'semantic-digest') return `digest:${DIGEST_LABELS[result.index] ?? `slot-${result.index}`}`;
  if (result.reason === 'random-stream') return 'digest:random-stream';
  if (result.reason === 'external-event') return `external:${result.detail?.type ?? 'event'}`;
  if (result.reason === 'quit-state' || result.reason === 'quit-handshake') return 'terminal-state';
  return result.reason ?? 'unknown';
}

export function formatCertificationResult(result) {
  if (!result) return 'No certification result yet.';
  const head = [
    `status=${result.status}`,
    result.scope ? `scope=${result.scope}` : null,
    Number.isFinite(result.tick) ? `tick=${result.tick}` : null,
    Number.isFinite(result.cycle) ? `cycle=${result.cycle}` : null,
  ].filter(Boolean).join('  ');

  if (result.status === 'MATCH') {
    const digest = Array.isArray(result.digest) ? result.digest.map(hex32).join(' ') : 'n/a';
    return `${head}\nroom=${result.room}  ego=(${result.x},${result.y})  randomDraws=${result.randomDraws}\ndigest=${digest}`;
  }
  if (result.status === 'COMPLETE') {
    return `${head}\nfinal terminal barrier matched.`;
  }
  if (result.status === 'DIVERGED') {
    const category = divergenceCategory(result);
    const values = ('truth' in result || 'edited' in result)
      ? `\ntruth=${String(result.truth)}  edited=${String(result.edited)}`
      : '';
    const detail = result.detail ? `\ndetail=${JSON.stringify(result.detail)}` : '';
    return `${head}\nreason=${result.reason ?? 'unknown'}  category=${category}${values}${detail}`;
  }
  if (result.status === 'BUSY') {
    return `${head}\ntruthIdle=${result.truthIdle}  editedIdle=${result.editedIdle}`;
  }
  return `${head}\nreason=${result.reason ?? 'n/a'}`;
}

export async function runCertificationSession(host, options = {}) {
  const targetBarriers = Math.max(1, Number(options.targetBarriers ?? 60) | 0);
  const maxBusyPulses = Math.max(1, Number(options.maxBusyPulses ?? 900) | 0);
  const pulseIntervalMs = Math.max(0, Number(options.pulseIntervalMs ?? (1000 / 60)) || 0);
  const shouldStop = options.shouldStop ?? (() => false);
  const onUpdate = options.onUpdate ?? (() => {});
  const beforePulse = options.beforePulse ?? (() => {});
  let barriers = 0;
  let busyPulses = 0;
  let pulses = 0;
  let lastResult = null;
  let nextPulseAt = monotonicNow();

  while (!shouldStop()) {
    // CertificationHost.pulse() represents exactly one logical 1/60-second pulse.
    // Do not spin pulses as fast as the browser can schedule them: doing so turns
    // worker CPU scheduling into simulated game time. A missed deadline is not
    // "caught up" with a burst of immediate pulses; the next pulse is re-anchored.
    if (pulses > 0 && pulseIntervalMs > 0) {
      nextPulseAt += pulseIntervalMs;
      const delayMs = nextPulseAt - monotonicNow();
      if (delayMs > 0) {
        await sleep(delayMs);
      } else {
        nextPulseAt = monotonicNow();
      }
    }

    await beforePulse(host);
    const result = await host.pulse();
    lastResult = result;
    pulses += 1;

    if (result.status === 'BUSY') {
      busyPulses += 1;
      onUpdate({ barriers, pulses, busyPulses, result });
      if (busyPulses >= maxBusyPulses) {
        return { status: 'WAITING', barriers, pulses, busyPulses, result };
      }
      continue;
    }

    busyPulses = 0;
    if (result.status === 'MATCH') {
      barriers += 1;
      onUpdate({ barriers, pulses, busyPulses, result });
      if (barriers >= targetBarriers) {
        return { status: 'MATCH_LIMIT', barriers, pulses, busyPulses, result };
      }
      continue;
    }

    onUpdate({ barriers, pulses, busyPulses, result });
    if (result.status === 'DIVERGED') {
      return { status: 'DIVERGED', barriers, pulses, busyPulses, result, firstDivergence: result };
    }
    if (result.status === 'COMPLETE') {
      return { status: 'COMPLETE', barriers, pulses, busyPulses, result };
    }
    return { status: result.status ?? 'STOPPED', barriers, pulses, busyPulses, result };
  }

  return { status: 'STOPPED', barriers, pulses, busyPulses, result: lastResult };
}

function installCertificationPanel() {
  const button = document.getElementById('certify-button');
  const panel = document.getElementById('certify-panel');
  const closeButton = document.getElementById('certify-close-button');
  const refreshButton = document.getElementById('certify-refresh-button');
  const runButton = document.getElementById('certify-run-button');
  const stopButton = document.getElementById('certify-stop-button');
  const gameSelect = document.getElementById('certify-game-select');
  const barrierInput = document.getElementById('certify-barrier-count');
  const status = document.getElementById('certify-status');
  const progress = document.getElementById('certify-progress');
  const detail = document.getElementById('certify-detail');
  if (!button || !panel || !runButton || !gameSelect || !status || !detail) return;

  let host = null;
  let stopRequested = false;
  let running = false;

  const setStatus = (text, state = 'IDLE') => {
    status.textContent = text;
    status.dataset.state = state;
  };

  const setRunning = value => {
    running = value;
    runButton.disabled = value;
    refreshButton.disabled = value;
    gameSelect.disabled = value;
    barrierInput.disabled = value;
    stopButton.disabled = !value;
  };

  const showButtonWhenGameReady = () => {
    if (document.querySelector('#embed-html canvas, canvas')) {
      button.style.display = 'block';
      return true;
    }
    return false;
  };
  if (!showButtonWhenGameReady()) {
    const observer = new MutationObserver(() => {
      if (showButtonWhenGameReady()) observer.disconnect();
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }

  async function refreshGames() {
    refreshButton.disabled = true;
    setStatus('SCANNING LOCAL IMPORTS', 'BUSY');
    try {
      const games = await discoverImportedGames();
      gameSelect.textContent = '';
      for (const game of games) {
        const option = document.createElement('option');
        option.value = game.directoryName;
        option.textContent = `${game.directoryName} (${humanBytes(game.size)})`;
        gameSelect.appendChild(option);
      }
      if (!games.length) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'No imported AGI game found';
        gameSelect.appendChild(option);
        runButton.disabled = true;
        setStatus('NO LOCAL GAME', 'ERROR');
        detail.textContent = 'Import your own King\'s Quest ZIP through normal PLAY first. CERTIFY reads only that same-origin OPFS copy.';
      } else {
        runButton.disabled = false;
        setStatus('READY', 'READY');
        detail.textContent = 'Local GAMEFILES.DAT found. Nothing is uploaded; the buffer is copied directly into the two certification workers.';
      }
    } catch (error) {
      setStatus('OPFS ERROR', 'ERROR');
      detail.textContent = String(error?.stack ?? error);
    } finally {
      refreshButton.disabled = false;
    }
  }

  async function startRun() {
    if (running) return;
    if (!window.crossOriginIsolated) {
      setStatus('NOT ISOLATED', 'ERROR');
      detail.textContent = 'CERTIFY requires the same cross-origin isolation used by the AGILE SharedArrayBuffer runtime.';
      return;
    }
    const directoryName = gameSelect.value;
    if (!directoryName) {
      setStatus('NO LOCAL GAME', 'ERROR');
      return;
    }

    stopRequested = false;
    setRunning(true);
    setStatus('LOADING LOCAL GAME', 'BUSY');
    progress.textContent = '0 certified barriers';
    detail.textContent = 'Reading GAMEFILES.DAT from this origin only…';

    try {
      host?.terminate();
      host = null;
      const gameBuffer = await readImportedGame(directoryName);
      const editConfig = await captureEditConfigV1();
      const truthWorkerUrl = new URL('./truth-worker/worker.nocache.js', import.meta.url).href;
      const editedWorkerUrl = new URL('./edited-worker/worker.nocache.js', import.meta.url).href;
      host = new CertificationHost({ truthWorkerUrl, editedWorkerUrl });
      await host.start(gameBuffer);
      const applyEditConfig = createEditConfigApplicator(editConfig);
      applyEditConfig(host);

      setStatus('CERTIFYING', 'BUSY');
      detail.textContent = `Frozen EditConfig v1: ${editConfigIdentity(editConfig)}\nTruth lane remains pristine; this config is applied only to the edited lane.`;
      const targetBarriers = Math.max(1, Number(barrierInput.value || 60));
      const summary = await runCertificationSession(host, {
        targetBarriers,
        maxBusyPulses: 900,
        pulseIntervalMs: 1000 / 60,
        beforePulse: () => applyEditConfig(host),
        shouldStop: () => stopRequested,
        onUpdate: update => {
          progress.textContent = `${update.barriers}/${targetBarriers} certified barriers · tick ${update.result?.tick ?? host.logicalTick} · ${editConfigIdentity(editConfig)}`;
          if (update.result?.status !== 'BUSY') detail.textContent = formatResultWithEditConfig(update.result, editConfig);
        },
      });

      if (summary.status === 'MATCH_LIMIT') {
        setStatus(`MATCH × ${summary.barriers}`, 'MATCH');
        detail.textContent = `${formatResultWithEditConfig(summary.result, editConfig)}\n\nNo divergence was observed across the requested ${summary.barriers} shared barriers.`;
      } else if (summary.status === 'DIVERGED') {
        setStatus(`DIVERGED @ ${summary.firstDivergence.tick}`, 'DIVERGED');
        detail.textContent = `${formatResultWithEditConfig(summary.firstDivergence, editConfig)}\n\nThis is the first divergent shared barrier observed by this run.`;
      } else if (summary.status === 'COMPLETE') {
        setStatus('COMPLETE / MATCH', 'MATCH');
        detail.textContent = formatResultWithEditConfig(summary.result, editConfig);
      } else if (summary.status === 'WAITING') {
        setStatus('WAITING FOR INPUT', 'WAITING');
        detail.textContent = `${formatResultWithEditConfig(summary.result, editConfig)}\n\nThe no-input Phase -1C smoke run reached a long blocking interpreter wait. Input record/replay is intentionally a later phase.`;
      } else if (summary.status === 'STOPPED') {
        setStatus('STOPPED', 'IDLE');
      } else {
        setStatus(summary.status, 'ERROR');
        detail.textContent = formatResultWithEditConfig(summary.result, editConfig);
      }
    } catch (error) {
      setStatus('CERTIFICATION ERROR', 'ERROR');
      detail.textContent = String(error?.stack ?? error);
    } finally {
      host?.terminate();
      host = null;
      setRunning(false);
    }
  }

  button.addEventListener('click', () => {
    const opening = panel.getAttribute('aria-hidden') !== 'false';
    panel.setAttribute('aria-hidden', opening ? 'false' : 'true');
    if (opening) refreshGames();
  });
  closeButton.addEventListener('click', () => panel.setAttribute('aria-hidden', 'true'));
  refreshButton.addEventListener('click', refreshGames);
  runButton.addEventListener('click', startRun);
  stopButton.addEventListener('click', () => {
    stopRequested = true;
    setStatus('STOPPING…', 'BUSY');
  });
  window.addEventListener('beforeunload', () => host?.terminate());
}

if (typeof document !== 'undefined') installCertificationPanel();
