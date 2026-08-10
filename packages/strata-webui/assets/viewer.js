import RFB from '/novnc/core/rfb.js';

const token = sessionStorage.getItem('strata-token') || '';
const appId = new URLSearchParams(location.search).get('app_id') || '';
let rfb = null;
let selectedAspect = 'auto';
let selectedResolution = 'adaptive';
let selectedQuality = 'balanced';
let resizeTimer = null;
let resizeRetries = [];
let requestedSize = '';

const qualityProfiles = {
  balanced: {quality: 6, compression: 4},
  high: {quality: 8, compression: 3},
  best: {quality: 9, compression: 1},
};

function storedSelectValue(key, fallback, select) {
  const value = localStorage.getItem(key) || fallback;
  return Array.from(select.options).some(option => option.value === value) ? value : fallback;
}

function setStatus(message) {
  document.querySelector('#viewer-status').textContent = message;
}

function even(value) {
  const size = Math.max(2, Math.floor(value));
  return size - (size % 2);
}

function targetRemoteSize() {
  const screen = document.querySelector('#screen');
  const width = even(screen.clientWidth);
  const height = even(screen.clientHeight);
  if (selectedResolution === 'adaptive') return {width, height};

  const [presetWidth, presetHeight] = selectedResolution.split('x').map(Number);
  const [ratioWidth, ratioHeight] = selectedAspect === 'auto' ?
    [presetWidth, presetHeight] : selectedAspect.split('/').map(Number);
  const ratio = ratioWidth / ratioHeight;
  const pixels = presetWidth * presetHeight;
  const targetWidth = even(Math.sqrt(pixels * ratio));
  return {width: targetWidth, height: even(targetWidth / ratio)};
}

function requestResize() {
  clearTimeout(resizeTimer);
  resizeRetries.forEach(clearTimeout);
  resizeRetries = [];
  resizeTimer = setTimeout(() => {
    if (!rfb) return;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const {width, height} = targetRemoteSize();
      const size = `${width}x${height}`;
      if (size === requestedSize) return;
      requestedSize = size;
      const send = () => {
        if (!rfb) return;
        if (typeof rfb.requestRemoteResize === 'function') rfb.requestRemoteResize(width, height);
      };
      send();
      resizeRetries = [setTimeout(send, 300), setTimeout(send, 900)];
    }));
  }, 80);
}

function layoutScreen() {
  const screen = document.querySelector('#screen');
  const bounds = document.querySelector('.viewer-window').getBoundingClientRect();
  const availableWidth = Math.max(320, even(bounds.width - 24));
  const availableHeight = Math.max(240, even(bounds.height - 24));
  if (selectedAspect === 'auto') {
    screen.classList.remove('ratio-fixed');
    screen.style.width = `${availableWidth}px`;
    screen.style.height = `${availableHeight}px`;
  } else {
    const [width, height] = selectedAspect.split('/').map(Number);
    const ratio = width / height;
    let targetWidth = even(Math.min(availableWidth, Math.floor(availableHeight * ratio)));
    let targetHeight = even(targetWidth / ratio);
    screen.style.width = `${targetWidth}px`;
    screen.style.height = `${targetHeight}px`;
    screen.classList.add('ratio-fixed');
  }
  requestResize();
}

function applyQuality() {
  if (!rfb) return;
  const profile = qualityProfiles[selectedQuality];
  rfb.qualityLevel = profile.quality;
  rfb.compressionLevel = profile.compression;
}

function setAspectRatio(value) {
  selectedAspect = value;
  localStorage.setItem('strata-webapp-aspect', value);
  if (value !== 'auto') {
    const [ratioWidth, ratioHeight] = value.split('/').map(Number);
    const headerHeight = document.querySelector('.viewer-window-header').getBoundingClientRect().height;
    const chromeWidth = Math.max(0, window.outerWidth - window.innerWidth);
    const chromeHeight = Math.max(0, window.outerHeight - window.innerHeight);
    const contentWidth = Math.max(640, Math.min(1440, window.innerWidth));
    const contentHeight = Math.round(contentWidth * ratioHeight / ratioWidth);
    window.resizeTo(contentWidth + chromeWidth, contentHeight + headerHeight + chromeHeight);
  }
  layoutScreen();
}

function setResolution(value) {
  selectedResolution = value;
  localStorage.setItem('strata-webapp-resolution', value);
  requestResize();
}

function setQuality(value) {
  selectedQuality = value;
  localStorage.setItem('strata-webapp-quality', value);
  applyQuality();
}

async function connect() {
  if (!token || !/^[A-Za-z0-9._-]+$/.test(appId)) {
    setStatus('Unable to authenticate this viewer. Open it again from Application Center.');
    return;
  }
  const response = await fetch(`/cgi-bin/session?app_id=${encodeURIComponent(appId)}`, {
    headers: {Authorization: `Bearer ${token}`}, cache: 'no-store',
  });
  const session = await response.json();
  if (!response.ok || session.error) throw new Error(session.error || 'Unable to read application session');
  if (session.state !== 'running') {
    setStatus('Application is not running. Start it from Application Center.');
    return;
  }
  if (rfb) rfb.disconnect();
  requestedSize = '';
  document.querySelector('#screen').replaceChildren();
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
  const host = location.hostname.includes(':') ? `[${location.hostname}]` : location.hostname;
  const url = `${scheme}://${host}:${session.websocket_port}/?token=${encodeURIComponent(token)}&session=${encodeURIComponent(appId)}`;
  const connection = new RFB(document.querySelector('#screen'), url, {shared: true});
  rfb = connection;
  connection.scaleViewport = true;
  connection.resizeSession = true;
  connection.dragViewport = false;
  connection.focusOnClick = true;
  applyQuality();
  connection.addEventListener('connect', () => { if (rfb === connection) { setStatus('Connected · closing this window will not stop the application'); requestResize(); } });
  connection.addEventListener('disconnect', event => { if (rfb === connection) setStatus(event.detail.clean ? 'Disconnected' : 'Connection interrupted'); });
}

document.title = `${appId || 'Application'} · StrataOS`;
document.querySelector('#viewer-title').textContent = appId || 'Application Viewer';
const aspect = document.querySelector('#aspect-ratio');
aspect.value = storedSelectValue('strata-webapp-aspect', 'auto', aspect);
const resolution = document.querySelector('#resolution');
resolution.value = storedSelectValue('strata-webapp-resolution', 'adaptive', resolution);
const quality = document.querySelector('#quality');
quality.value = storedSelectValue('strata-webapp-quality', 'balanced', quality);
setAspectRatio(aspect.value);
aspect.addEventListener('change', () => setAspectRatio(aspect.value));
setResolution(resolution.value);
resolution.addEventListener('change', () => setResolution(resolution.value));
setQuality(quality.value);
quality.addEventListener('change', () => setQuality(quality.value));
new ResizeObserver(() => layoutScreen()).observe(document.querySelector('.viewer-window'));
window.addEventListener('resize', layoutScreen);
document.querySelector('#reconnect').addEventListener('click', () => connect().catch(error => setStatus(error.message)));
connect().catch(error => setStatus(error.message));
