// Run with a temporary Chromium/Edge instance exposing CDP on localhost:9234.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

(async () => {
  const targets = await (await fetch('http://127.0.0.1:9234/json/list')).json();
  const target = targets.find(item => item.type === 'page' && item.url.includes(':8000'));
  assert(target, 'Editor tab must be open');
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  let id = 0;
  const pending = new Map(), exceptions = [];
  ws.onmessage = event => {
    const data = JSON.parse(event.data);
    if (data.method === 'Runtime.exceptionThrown') exceptions.push(data.params);
    if (pending.has(data.id)) { pending.get(data.id)(data); pending.delete(data.id); }
  };
  const call = (method, params = {}) => new Promise(resolve => { const n = ++id; pending.set(n, resolve); ws.send(JSON.stringify({ id: n, method, params })); });
  async function evaluate(expression) {
    const result = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    assert(!result.error && !result.result.exceptionDetails, JSON.stringify(result));
    return result.result.result.value;
  }
  async function waitFor(expression) {
    for (let attempt = 0; attempt < 80; attempt++) {
      if (await evaluate(expression)) return;
      await sleep(250);
    }
    throw new Error('Timed out: ' + expression + '\n' + await evaluate('document.querySelector("#editor-message").textContent'));
  }
  await call('Runtime.enable');
  await call('Page.enable');
  await call('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1200, deviceScaleFactor: 1, mobile: false });
  await call('Page.reload', { ignoreCache: true });
  await waitFor('typeof state !== "undefined" && state.backgroundReady && !state.pending');
  assert.equal(await evaluate('document.querySelectorAll("[contenteditable],.drag-handle").length'), 0);
  assert.equal(await evaluate('document.querySelectorAll("input:not([type=range])").length'), 5);
  assert(await evaluate('document.querySelector("[data-export=pdf]").disabled'));
  await evaluate(`for (const [id, value] of Object.entries({recipientName:'Hernán Simó',designation:'Digital Artist',identityLine:'Hernán Simó Digital Art',issueDate:'2026-05-05'})) { const field=document.getElementById(id);field.value=value;field.dispatchEvent(new Event('input',{bubbles:true})); }`);
  const documentNode = await call('DOM.getDocument');
  const input = await call('DOM.querySelector', { nodeId: documentNode.result.root.nodeId, selector: '#profileImage' });
  await call('DOM.setFileInputFiles', { nodeId: input.result.nodeId, files: [path.resolve('artifacts/reference-photo.png')] });
  await waitFor('!document.querySelector("[data-export=pdf]").disabled');
  const outputDirectory = path.resolve('artifacts/browser-downloads');
  fs.mkdirSync(outputDirectory, { recursive: true });
  await call('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: outputDirectory });
  await evaluate('document.querySelector("[data-export=pdf]").click()');
  await waitFor('document.querySelector("#editor-message").textContent.includes("download has started")');
  await sleep(500);
  const downloads = fs.readdirSync(outputDirectory).filter(name => name.endsWith('.pdf'));
  assert(downloads.length > 0, 'PDF button must download a document');
  assert.equal(fs.readFileSync(path.join(outputDirectory, downloads[0])).subarray(0, 4).toString(), '%PDF');
  const certificate = await evaluate('JSON.stringify((()=>{const r=document.querySelector("#certificate-stage").getBoundingClientRect();return {x:r.x,y:r.y+scrollY,width:r.width,height:r.height,scale:1}})())');
  const screenshot = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip: JSON.parse(certificate) });
  fs.writeFileSync('artifacts/browser-certificate.png', Buffer.from(screenshot.result.data, 'base64'));
  await evaluate('document.querySelector("#photo-zoom").value=2;document.querySelector("#photo-zoom").dispatchEvent(new Event("input"));');
  assert.equal(await evaluate('state.crop.zoom'), 2);
  await evaluate('document.querySelector("#center-photo").click()');
  assert.equal(await evaluate('state.crop.zoom'), 1);
  await evaluate('document.querySelector("#recipientName").value="W".repeat(100);document.querySelector("#recipientName").dispatchEvent(new Event("input"));');
  await waitFor('!state.pending');
  assert(await evaluate('document.querySelector("[data-export=pdf]").disabled'));
  assert((await evaluate('document.querySelector("#error-recipientName").textContent')).includes('too long'));
  await call('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  await sleep(300);
  assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile page must not overflow horizontally');
  const ratio = await evaluate('(()=>{const r=document.querySelector("#certificate-stage").getBoundingClientRect();return r.width/r.height})()');
  assert(Math.abs(ratio - 595.276 / 841.89) < .001);
  await evaluate('document.querySelector("#sidebar-toggle").click()');
  await sleep(250);
  assert.equal(await evaluate('document.querySelector(".sidebar").getBoundingClientRect().width'), 72);
  await evaluate('document.querySelector("#reset-editor").click()');
  await waitFor('!state.pending');
  assert.equal(await evaluate('document.querySelector("#recipientName").value'), '');
  assert.equal(await evaluate('state.photo'), '');
  assert(await evaluate('document.querySelector("[data-export=pdf]").disabled'));
  assert.deepEqual(exceptions, []);
  console.log('PASS: five locked fields, live updates, real photo upload, crop, PDF button download, overflow blocking, responsive proportions, sidebar and reset.');
  await call('Browser.close');
  ws.close();
})().catch(error => { console.error(error); process.exit(1); });
