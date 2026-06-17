const state = { sessionId: null, replacements: null };
const baseUrl = window.location.origin;
const elements = {
  status: document.querySelector('#status'), dropZone: document.querySelector('#dropZone'),
  fileInput: document.querySelector('#fileInput'), documentInfo: document.querySelector('#documentInfo'),
  messages: document.querySelector('#messages'), prompt: document.querySelector('#prompt'),
  askButton: document.querySelector('#askButton'), previewButton: document.querySelector('#previewButton'),
  preview: document.querySelector('#preview'), applyButton: document.querySelector('#applyButton'),
  cancelButton: document.querySelector('#cancelButton'), downloadLink: document.querySelector('#downloadLink'),
  folderButton: document.querySelector('#folderButton'), outputStatus: document.querySelector('#outputStatus')
};

function localPath(path) { return new URL(path, baseUrl).toString(); }
function setBusy(message) { elements.outputStatus.textContent = message; }
function addMessage(role, text) {
  const item = document.createElement('p');
  item.className = 'message';
  item.textContent = `${role}: ${text}`;
  elements.messages.append(item);
}
function setPreview(replacements) {
  state.replacements = replacements;
  elements.preview.textContent = JSON.stringify(replacements, null, 2);
  elements.applyButton.disabled = !replacements;
}
function renderDocumentInfo(data) {
  elements.documentInfo.innerHTML = `<dt>File</dt><dd>${data.filename}</dd><dt>Session</dt><dd>${data.session_id}</dd><dt>Characters</dt><dd>${data.text_length}</dd><dt>Preview</dt><dd>${data.text_preview || 'No text preview'}</dd>`;
}
async function requestJson(path, options = {}) {
  const response = await fetch(localPath(path), options);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}
async function checkStatus() {
  const health = await requestJson('/health');
  elements.status.textContent = health.offline_ready ? 'Offline ready' : 'Setup needed';
  elements.status.className = `status ${health.offline_ready ? 'ready' : 'warn'}`;
}
async function uploadFile(file) {
  const formData = new FormData();
  formData.append('file', file);
  const data = await requestJson('/documents', { method: 'POST', body: formData });
  state.sessionId = data.session_id;
  renderDocumentInfo(data);
  setPreview(null);
}
async function askQuestion() {
  if (!state.sessionId) return setBusy('Upload a document first.');
  const question = elements.prompt.value.trim();
  if (!question) return;
  addMessage('You', question);
  const data = await requestJson(`/sessions/${state.sessionId}/questions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }) });
  addMessage('Agent', data.answer);
}
async function previewOperation() {
  if (!state.sessionId) return setBusy('Upload a document first.');
  const instruction = elements.prompt.value.trim();
  if (!instruction) return;
  const data = await requestJson(`/sessions/${state.sessionId}/plan`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ instruction }) });
  setPreview(data.replacements);
}
async function applyOperation() {
  const data = await requestJson(`/sessions/${state.sessionId}/apply`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ replacements: state.replacements }) });
  elements.downloadLink.href = localPath(data.download_url);
  elements.downloadLink.hidden = false;
  setBusy(`Applied ${data.changed_count} changes.`);
}
async function openOutputFolder() {
  const data = await requestJson('/output-folder', { method: 'POST' });
  setBusy(data.supported ? `Opened ${data.path}` : data.message);
}
elements.fileInput.addEventListener('change', event => uploadFile(event.target.files[0]));
elements.dropZone.addEventListener('dragover', event => { event.preventDefault(); elements.dropZone.classList.add('dragging'); });
elements.dropZone.addEventListener('dragleave', () => elements.dropZone.classList.remove('dragging'));
elements.dropZone.addEventListener('drop', event => { event.preventDefault(); elements.dropZone.classList.remove('dragging'); uploadFile(event.dataTransfer.files[0]); });
elements.askButton.addEventListener('click', askQuestion);
elements.previewButton.addEventListener('click', previewOperation);
elements.applyButton.addEventListener('click', applyOperation);
elements.cancelButton.addEventListener('click', () => setPreview(null));
elements.folderButton.addEventListener('click', openOutputFolder);
checkStatus().catch(error => { elements.status.textContent = error.message; elements.status.className = 'status warn'; });
