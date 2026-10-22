/* Predictable service errors, shared by the browser and Node regression tests. */
(function (root) {
  "use strict";
  function serviceError(message, code, status) {
    return Object.assign(new Error(message), {code, status});
  }
  async function responseError(response, fallback) {
    let body;
    try { body = await response.json(); } catch { /* Never show a server HTML page as an error. */ }
    const detail = typeof body?.detail === "string" ? body.detail.trim() : "";
    const defaults = {
      404:"找不到这份内容，请刷新作品列表后重试。", 413:"文件或请求内容过大，请减小后重试。",
      429:"本地服务正在处理其他任务，请稍后重试。",
    };
    return serviceError(detail || defaults[response.status] || fallback ||
      (response.status >= 500 ? "本地服务暂时无法完成操作，请稍后重试。" : "操作失败，请稍后重试。"),
      "HTTP", response.status);
  }
  function friendlyError(error) {
    return error instanceof TypeError ? serviceError("无法连接本地服务，请确认启动窗口仍在运行。", "NETWORK") : error;
  }
  async function request(url, options, settings, format) {
    const controller = new AbortController(), external = options.signal;
    const abort = () => controller.abort();
    if (external?.aborted) abort();
    else external?.addEventListener("abort", abort, {once:true});
    const timeout = setTimeout(abort, settings.timeoutMs ?? 80000);
    try {
      const response = await (settings.fetcher || root.fetch)(url, {...options, signal:controller.signal,
        headers:options.body ? {"Content-Type":"application/json", ...options.headers} : options.headers});
      if (!response.ok) throw await responseError(response);
      try {
        if (format === "text") {
          if (!response.headers.get("Content-Type")?.toLowerCase().startsWith("text/plain"))
            throw new Error("Unexpected text content type");
          return await response.text();
        }
        return await response.json();
      }
      catch (error) {
        if (error.name === "AbortError") throw error;
        throw serviceError("本地服务返回了无法读取的结果，请重试。", "INVALID_RESPONSE", response.status);
      }
    } catch (error) {
      if (controller.signal.aborted && !external?.aborted)
        throw serviceError("请求超时，请稍后重试。已提交的任务可能仍在处理，可在作品库或导出任务中查看。", "TIMEOUT");
      throw friendlyError(error);
    } finally {
      clearTimeout(timeout); external?.removeEventListener("abort", abort);
    }
  }
  function requestJSON(url, options = {}, settings = {}) { return request(url, options, settings, "json"); }
  function requestText(url, options = {}, settings = {}) { return request(url, options, settings, "text"); }
  const api = {requestJSON, requestText, responseError, friendlyError};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.FrameHTTP = api;
})(typeof window !== "undefined" ? window : globalThis);
