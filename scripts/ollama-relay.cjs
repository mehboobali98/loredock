// Offline-check transport: one fixed upstream, no URL or host selection.
// Both request and response are streamed; model prompts stay on this laptop.
const http = require("node:http");
const allowed = new Set([
  "GET /api/version", "GET /api/tags", "GET /api/ps",
  "POST /api/chat", "POST /api/generate", "POST /api/show",
]);

/**
 * Create a streaming HTTP relay with a fixed destination and optional route list.
 * @param {string} hostname Fixed destination, never taken from a request.
 * @param {number} port Destination port.
 * @param {number} listener Container listener; only the UI port is host-published.
 * @param {ReadonlySet<string> | null} routes Allowed method/path pairs, if restricted.
 */
function relay(hostname, port, listener, routes = null) {
  http.createServer((request, response) => {
    if (routes && !routes.has(`${request.method} ${request.url}`)) {
      response.writeHead(403);
      response.end("Only local inference and model inspection are allowed");
      return;
    }
    const upstream = http.request({
      hostname, port, path: request.url, method: request.method,
      headers: { ...request.headers, host: `${hostname}:${port}` },
    }, (result) => {
      response.writeHead(result.statusCode, result.headers);
      result.pipe(response);
    });
    upstream.setTimeout(180_000, () => upstream.destroy());
    upstream.on("error", () => {
      if (!response.headersSent) response.writeHead(502);
      response.end("Local service unavailable");
    });
    request.on("aborted", () => upstream.destroy());
    response.on("close", () => upstream.destroy());
    request.pipe(upstream);
  }).listen(listener, "0.0.0.0");
}

relay("host.docker.internal", 11434, 11434, allowed);
// Docker Desktop also blocks host-published ports on an internal network.
// This fixed application front door is published on host loopback only.
relay("anythingllm", 3001, 3001);
