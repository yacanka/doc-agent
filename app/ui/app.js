const state = { sessionId: null, replacements: null, busy: false };
const baseUrl = window.location.origin;
const elements = {
  status: document.querySelector('#status'), dropZone: document.querySelector('#dropZone'),
  fileInput: document.querySelector('#fileInput'), documentInfo: document.querySelector('#documentInfo'),
  messages: document.querySelector('#messages'), prompt: document.querySelector('#prompt'),
  askButton: document.querySelector('#askButton'), previewButton: document.querySelector('#previewButton'),
  preview: document.querySelector('#preview'), applyButton: document.querySelector('#applyButton'),
  cancelButton: document.querySelector('#cancelButton'), downloadLink: document.querySelector('#downloadLink'),
  folderButton: document.querySelector('#folderButton'), outputStatus: document.querySelector('#outputStatus'),
  loading: document.querySelector('#loading'), developerStream: document.querySelector('#developerStream')
};

function localPath(path) { return new URL(path, baseUrl).toString(); }
function setBusy(message) { elements.outputStatus.textContent = message; }
function setControlsDisabled(disabled) {
  state.busy = disabled;
  elements.askButton.disabled = disabled;
  elements.previewButton.disabled = disabled;
  elements.folderButton.disabled = disabled;
  elements.fileInput.disabled = disabled;
  elements.applyButton.disabled = disabled || !state.replacements;
}
function setLoading(active, message = 'Working…') {
  elements.loading.hidden = !active;
  elements.loading.querySelector('.loading-text').textContent = message;
}
function addMessage(role, text = '') {
  const item = document.createElement('p');
  item.className = 'message';
  item.textContent = `${role}: ${text}`;
  elements.messages.append(item);
  return item;
}
function appendDeveloperChunk(text) {
  elements.developerStream.textContent += text;
  elements.developerStream.scrollTop = elements.developerStream.scrollHeight;
}
function setPreview(replacements) {
  state.replacements = replacements;
  elements.preview.textContent = replacements ? JSON.stringify(replacements, null, 2) : 'No operation planned.';
  elements.applyButton.disabled = state.busy || !replacements;
}
function renderDocumentInfo(data) {
  elements.documentInfo.innerHTML = `<dt>File</dt><dd>${data.filename}</dd><dt>Session</dt><dd>${data.session_id}</dd><dt>Characters</dt><dd>${data.text_length}</dd><dt>Preview</dt><dd>${data.text_preview || 'No text preview'}</dd>`;
}
async function parseResponse(response) {
  const text = await response.text();
  try { return text ? JSON.parse(text) : {}; } catch { return { detail: text || response.statusText }; }
}
async function requestJson(path, options = {}) {
  const response = await fetch(localPath(path), options);
  const payload = await parseResponse(response);
  if (!response.ok) throw new Error(payload.detail || 'Request failed');
  return payload;
}
async function checkStatus() {
  const health = await requestJson('/health');
  elements.status.textContent = health.offline_ready ? 'Offline ready' : 'Setup needed';
  elements.status.className = `status ${health.offline_ready ? 'ready' : 'warn'}`;
}
async function uploadFile(file) {
  if (!file) return;
  if (!isSupportedDocument(file)) return setBusy('Please choose a DOCX or XLSX document.');
  const formData = new FormData();
  formData.append('file', file);
  await withLoading('Uploading document…', async () => {
    const data = await requestJson('/documents', { method: 'POST', body: formData });
    state.sessionId = data.session_id;
    renderDocumentInfo(data);
    setPreview(null);
    setBusy('Document loaded. Ask a question or preview an operation.');
  });
}
async function askQuestion() {
  if (!state.sessionId) return setBusy('Upload a document first.');
  const question = elements.prompt.value.trim();
  if (!question) return;
  addMessage('You', question);
  await streamAnswer(question, addMessage('Agent'));
}
async function streamAnswer(question, message) {
  elements.developerStream.textContent = '';
  await withLoading('Model is answering…', async () => {
    const response = await fetchEventStream(`/sessions/${state.sessionId}/questions/stream`, { question });
    await readEventStream(response.body, event => handleAnswerEvent(event, message));
  });
}
async function fetchEventStream(path, payload) {
  const response = await fetch(localPath(path), streamRequest(payload));
  if (!response.ok || !response.body) throw new Error((await parseResponse(response)).detail || 'Stream failed');
  return response;
}
function streamRequest(payload) {
  return { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) };
}
async function readEventStream(body, onEvent) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    buffer = drainEvents(buffer, onEvent);
    if (done) break;
  }
}
function drainEvents(buffer, onEvent) {
  const frames = buffer.split('\n\n');
  frames.slice(0, -1).forEach(frame => onEvent(parseEvent(frame)));
  return frames.at(-1) || '';
}
function parseEvent(frame) {
  const event = frame.match(/^event: (.+)$/m)?.[1] || 'message';
  const data = frame.match(/^data: (.+)$/m)?.[1] || '{}';
  return { event, data: JSON.parse(data) };
}
function handleAnswerEvent({ event, data }, message) {
  if (event === 'error') throw new Error(data.message || 'Model stream failed');
  if (event !== 'token') return;
  message.textContent += data.text;
  appendDeveloperChunk(data.text);
}
function handlePlanEvent({ event, data }) {
  if (event === 'error') throw new Error(data.message || 'Plan stream failed');
  if (event === 'token') appendDeveloperChunk(data.text);
  if (event === 'replacements') setPreview(data.items);
}
async function previewOperation() {
  if (!state.sessionId) return setBusy('Upload a document first.');
  const instruction = elements.prompt.value.trim();
  if (!instruction) return;
  elements.developerStream.textContent = '';
  setPreview(null);
  await withLoading('Planning operation…', async () => {
    const response = await fetchEventStream(`/sessions/${state.sessionId}/plan/stream`, { instruction });
    await readEventStream(response.body, handlePlanEvent);
  });
}
async function applyOperation() {
  await withLoading('Applying operation…', async () => {
    const data = await requestJson(`/sessions/${state.sessionId}/apply`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ replacements: state.replacements }) });
    elements.downloadLink.href = localPath(data.download_url);
    elements.downloadLink.hidden = false;
    setBusy(`Applied ${data.changed_count} changes.`);
  });
}
async function openOutputFolder() {
  const data = await requestJson('/output-folder', { method: 'POST' });
  setBusy(data.supported ? `Opened ${data.path}` : data.message);
}
function isSupportedDocument(file) {
  const name = file.name.toLowerCase();
  return name.endsWith('.docx') || name.endsWith('.xlsx');
}
async function withLoading(message, work) {
  try { setControlsDisabled(true); setLoading(true, message); await work(); }
  catch (error) { setBusy(error.message); }
  finally { setLoading(false); setControlsDisabled(false); }
}
elements.fileInput.addEventListener('change', event => uploadFile(event.target.files[0]));
elements.dropZone.addEventListener('dragover', event => { event.preventDefault(); elements.dropZone.classList.add('dragging'); });
elements.dropZone.addEventListener('dragleave', () => elements.dropZone.classList.remove('dragging'));
elements.dropZone.addEventListener('drop', event => { event.preventDefault(); elements.dropZone.classList.remove('dragging'); uploadFile(event.dataTransfer.files[0]); });
elements.askButton.addEventListener('click', askQuestion);
elements.previewButton.addEventListener('click', previewOperation);
elements.applyButton.addEventListener('click', applyOperation);
elements.cancelButton.addEventListener('click', () => setPreview(null));
elements.prompt.addEventListener('keydown', event => {
  if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') askQuestion();
});
elements.folderButton.addEventListener('click', openOutputFolder);
checkStatus().catch(error => { elements.status.textContent = error.message; elements.status.className = 'status warn'; });
