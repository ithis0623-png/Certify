'use strict';
const $ = selector => document.querySelector(selector);
const fieldIds = ['recipientName', 'designation', 'identityLine', 'issueDate'];
const state = { template: null, photo: '', photoWidth: 0, photoHeight: 0, crop: { zoom: 1, x: 0, y: 0 }, errors: {}, pending: true, exporting: false, backgroundReady: false };
let revision = 0, photoRevision = 0, debounce, previewController, overlayUrl;
const touched = new Set();

function setSidebarCollapsed(collapsed) {
  $('.app-shell').classList.toggle('sidebar-collapsed', collapsed);
  $('#sidebar-toggle').setAttribute('aria-expanded', String(!collapsed));
  $('#sidebar-toggle').title = collapsed ? 'Expand sidebar' : 'Collapse sidebar';
  $('#sidebar-toggle').setAttribute('aria-label', $('#sidebar-toggle').title);
}
let savedSidebarState = null;
try { savedSidebarState = localStorage.getItem('certify-sidebar-collapsed'); } catch { }
setSidebarCollapsed(savedSidebarState === null ? matchMedia('(max-width:720px)').matches : savedSidebarState === 'true');
$('#sidebar-toggle').addEventListener('click', () => {
  const collapsed = !$('.app-shell').classList.contains('sidebar-collapsed');
  setSidebarCollapsed(collapsed);
  try { localStorage.setItem('certify-sidebar-collapsed', String(collapsed)); } catch { }
});
function values() { return Object.fromEntries(fieldIds.map(id => [id, $(`#${id}`).value.trim()])); }
function message(text, error = false) { $('#editor-message').textContent = text; $('#editor-message').classList.toggle('error', error); }
function updateValidation() {
  const allValues = values();
  const valid = state.backgroundReady && !state.pending && !state.exporting && state.photo && fieldIds.every(id => allValues[id]) && !Object.keys(state.errors).length;
  document.querySelectorAll('[data-export]').forEach(button => { button.disabled = !valid; });
  for (const id of [...fieldIds, 'profileImage']) {
    const error = touched.has(id) ? state.errors[id] || '' : '';
    $(`#error-${id}`).textContent = error;
    $(`#${id}`).setAttribute('aria-invalid', String(Boolean(error)));
  }
}
async function api(path, data, signal) {
  const response = await fetch(path, {
    method: 'POST', signal, credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'X-CSRF-TOKEN': $('meta[name=csrf-token]').content },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    const error = new Error(response.status === 419 ? 'Your session expired. Refresh the page and try again.' : detail.message || 'Unable to render the certificate. Please try again.');
    error.fields = detail.errors;
    throw error;
  }
  return response;
}
function schedulePreview() {
  const current = ++revision;
  clearTimeout(debounce);
  previewController?.abort();
  state.pending = true;
  $('#preview-status').textContent = 'Updating preview…';
  $('#certificate-stage').setAttribute('aria-busy', 'true');
  updateValidation();
  debounce = setTimeout(() => renderText(current), 100);
}
async function renderText(current) {
  if (!state.template) return;
  previewController = new AbortController();
  try {
    const response = await api('/editor/preview', values(), previewController.signal);
    const result = await response.json();
    if (current !== revision) return;
    const nextUrl = URL.createObjectURL(new Blob([result.svg], { type: 'image/svg+xml' }));
    const nextImage = new Image(); nextImage.src = nextUrl; await nextImage.decode();
    if (current !== revision) { URL.revokeObjectURL(nextUrl); return; }
    $('#dynamic-ink').src = nextUrl;
    if (overlayUrl) URL.revokeObjectURL(overlayUrl);
    overlayUrl = nextUrl;
    const photoError = state.errors.profileImage;
    state.errors = { ...result.errors };
    if (!state.photo) state.errors.profileImage = photoError || 'Upload a profile photo.';
    state.pending = false;
    $('#preview-status').textContent = Object.keys(result.errors).length ? 'Complete the fields below' : 'Preview up to date';
    $('#certificate-stage').setAttribute('aria-busy', 'false');
    updateValidation();
  } catch (error) {
    if (error.name === 'AbortError' || current !== revision) return;
    state.pending = false;
    state.errors = { ...state.errors, renderer: error.message };
    $('#preview-status').textContent = 'Preview unavailable';
    message(error.message, true); updateValidation();
  }
}
function setImageGeometry(element, region) {
  if (!state.photo) { element.removeAttribute('href'); return; }
  const side = Math.min(state.photoWidth, state.photoHeight) / state.crop.zoom;
  const left = (state.photoWidth - side) * (state.crop.x + 1) / 2;
  const top = (state.photoHeight - side) * (state.crop.y + 1) / 2;
  const attributes = { href: state.photo, x: region.x - left * region.width / side, y: region.y - top * region.height / side, width: state.photoWidth * region.width / side, height: state.photoHeight * region.height / side };
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
}
function renderPhoto() {
  if (!state.template) return;
  setImageGeometry($('#portrait-image'), state.template.image);
  setImageGeometry($('#crop-image'), { x: 0, y: 0, width: 100, height: 100 });
  $('#crop-controls').disabled = !state.photo;
  $('#zoom-value').value = `${state.crop.zoom.toFixed(1)}×`;
}
function resetCrop() {
  state.crop = { zoom: 1, x: 0, y: 0 };
  $('#photo-zoom').value = 1; $('#photo-x').value = $('#photo-y').value = 0;
  renderPhoto();
}
$('#profileImage').addEventListener('change', async event => {
  const file = event.target.files[0]; if (!file) return;
  const current = ++photoRevision;
  touched.add('profileImage'); state.photo = ''; state.errors.profileImage = 'Loading photo…';
  renderPhoto(); updateValidation();
  let url;
  try {
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) throw new Error('Choose a JPG, PNG or WEBP image.');
    if (file.size > 10_000_000) throw new Error('Choose an image smaller than 10 MB.');
    url = URL.createObjectURL(file);
    const image = new Image(); image.src = url; await image.decode();
    if (current !== photoRevision) return;
    if (image.naturalWidth * image.naturalHeight > 25_000_000) throw new Error('Choose an image under 25 megapixels.');
    // Normalize orientation; 4096px retains ample detail for the small portrait.
    const factor = Math.min(1, 4096 / Math.max(image.naturalWidth, image.naturalHeight));
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(image.naturalWidth * factor); canvas.height = Math.round(image.naturalHeight * factor);
    canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
    state.photo = canvas.toDataURL('image/png');
    if (state.photo.length > 14_000_000) throw new Error('This photo is too large after decoding. Please choose a smaller image.');
    state.photoWidth = canvas.width; state.photoHeight = canvas.height;
    delete state.errors.profileImage;
    resetCrop(); message('Photo ready. Adjust zoom and position to frame the portrait.');
  } catch (error) {
    if (current !== photoRevision) return;
    state.photo = ''; state.errors.profileImage = error.message; renderPhoto();
  } finally { if (url) URL.revokeObjectURL(url); updateValidation(); }
});
for (const [id, key] of [['photo-zoom', 'zoom'], ['photo-x', 'x'], ['photo-y', 'y']]) {
  $(`#${id}`).addEventListener('input', event => { state.crop[key] = Number(event.target.value); renderPhoto(); });
}
$('#center-photo').addEventListener('click', resetCrop);
fieldIds.forEach(id => $(`#${id}`).addEventListener('input', () => { touched.add(id); schedulePreview(); }));
$('#certificate-form').addEventListener('submit', event => event.preventDefault());
$('#reset-editor').addEventListener('click', () => {
  if (!state.template) return;
  photoRevision++; $('#certificate-form').reset();
  fieldIds.forEach(id => { $(`#${id}`).value = state.template.defaults[id] || ''; });
  state.photo = ''; touched.clear(); state.errors = {}; resetCrop();
  message('Complete all five fields to download your certificate.'); schedulePreview();
});
document.querySelectorAll('[data-export]').forEach(button => button.addEventListener('click', async () => {
  if (state.pending || state.exporting || !state.photo || Object.keys(state.errors).length) return;
  const format = button.dataset.export;
  const snapshot = { ...values(), profileImage: state.photo, crop: { ...state.crop }, format };
  state.exporting = true; updateValidation(); message(`Preparing your ${format.toUpperCase()}…`);
  try {
    const response = await api('/editor/export', snapshot);
    const blob = await response.blob(); const url = URL.createObjectURL(blob);
    const link = document.createElement('a'); link.href = url;
    link.download = `Certificate-${snapshot.recipientName.replace(/[^\p{L}\p{N} _-]/gu, '').slice(0, 80) || 'Appreciation'}.${format === 'jpeg' ? 'jpg' : format}`;
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
    message('Your certificate is ready. The download has started.');
  } catch (error) {
    if (error.fields) {
      for (const [key, value] of Object.entries(error.fields)) state.errors[key] = Array.isArray(value) ? value[0] : value;
      [...fieldIds, 'profileImage'].forEach(id => touched.add(id));
    }
    message(error.message, true);
  } finally { state.exporting = false; updateValidation(); }
}));
async function initialize() {
  try {
    if (location.protocol === 'file:') throw new Error('Open this editor through Laravel at http://127.0.0.1:8000.');
    const response = await fetch('/editor/template', { headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error('The certificate template could not be loaded.');
    state.template = await response.json(); const config = state.template;
    $('#certificate-stage').style.aspectRatio = `${config.width} / ${config.height}`;
    $('#portrait-overlay').setAttribute('viewBox', `0 0 ${config.width} ${config.height}`);
    const region = config.image;
    Object.entries({ cx: region.x + region.width / 2, cy: region.y + region.height / 2, rx: region.width / 2, ry: region.height / 2 }).forEach(([key, value]) => $('#portrait-circle').setAttribute(key, value));
    fieldIds.forEach(id => { $(`#${id}`).value = config.defaults[id] || ''; });
    $('#locked-background').src = `/editor/background?v=${config.masterSha256}`;
    await $('#locked-background').decode();
    state.backgroundReady = true; schedulePreview();
  } catch (error) { $('#preview-status').textContent = 'Template unavailable'; message(error.message, true); }
}
initialize();
