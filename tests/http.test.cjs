const test = require('node:test');
const assert = require('node:assert/strict');
const H = require('../web/http.js');

test('JSON requests preserve upload content type and useful server errors', async () => {
  let captured;
  const result = await H.requestJSON('/upload', {method:'POST', body:'binary', headers:{'Content-Type':'image/png'}}, {
    fetcher:async (url, options) => { captured = options; return Response.json({id:'photo'}); }
  });
  assert.deepEqual(result, {id:'photo'});
  assert.equal(captured.headers['Content-Type'], 'image/png');
  await assert.rejects(H.requestJSON('/save', {}, {fetcher:async () => Response.json({detail:'作品已在其他窗口更新'}, {status:409})}),
    {message:'作品已在其他窗口更新', code:'HTTP', status:409});
});

test('HTML server errors and structured details never leak parsing errors or markup', async () => {
  await assert.rejects(H.requestJSON('/save', {}, {fetcher:async () => new Response('<html>internal traceback</html>', {status:500})}),
    {message:'本地服务暂时无法完成操作，请稍后重试。', code:'HTTP', status:500});
  const error = await H.responseError(Response.json({detail:[{message:'raw'}]}, {status:429}));
  assert.equal(error.message, '本地服务正在处理其他任务，请稍后重试。');
});

test('a successful response with invalid JSON has an actionable message', async () => {
  await assert.rejects(H.requestJSON('/projects', {}, {fetcher:async () => new Response('not json')}), {code:'INVALID_RESPONSE'});
});

test('offline fetch failures explain how to restart the local server', async () => {
  await assert.rejects(H.requestJSON('/projects', {}, {fetcher:async () => {throw new TypeError('Failed to fetch');}}),
    {code:'NETWORK', message:'无法连接本地服务，请确认启动窗口仍在运行。'});
});

test('timeouts abort the request and warn against assuming the submitted task failed', async () => {
  const fetcher = async (url, {signal}) => new Promise((resolve, reject) => {
    signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')), {once:true});
  });
  await assert.rejects(H.requestJSON('/render', {}, {fetcher, timeoutMs:5}), error =>
    error.code === 'TIMEOUT' && error.message.includes('仍在处理'));
});

test('caller cancellation remains an AbortError rather than becoming a timeout', async () => {
  const controller = new AbortController(); controller.abort();
  const fetcher = async (url, {signal}) => { signal.throwIfAborted(); };
  await assert.rejects(H.requestJSON('/preview', {signal:controller.signal}, {fetcher}), {name:'AbortError'});
});
