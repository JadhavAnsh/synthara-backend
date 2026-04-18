import http from "node:http";

import {
  askPaper,
  getPaper,
  isLoggedIn,
  readPaperCode,
  searchPapers,
} from "@companion-ai/alpha-hub/lib";

const port = Number.parseInt(process.env.ALPHAXIV_BRIDGE_PORT ?? "4100", 10);

function sendJson(res, statusCode, payload) {
  res.writeHead(statusCode, { "Content-Type": "application/json" });
  res.end(JSON.stringify(payload));
}

async function readBody(req) {
  const chunks = [];
  for await (const chunk of req) {
    chunks.push(chunk);
  }
  const raw = Buffer.concat(chunks).toString("utf8");
  return raw ? JSON.parse(raw) : {};
}

function notFound(res) {
  sendJson(res, 404, { error: "not_found", message: "route not found" });
}

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === "GET" && req.url === "/health") {
      return sendJson(res, 200, { status: "ok" });
    }

    if (req.method === "GET" && req.url === "/auth/status") {
      return sendJson(res, 200, { loggedIn: isLoggedIn() });
    }

    if (req.method === "POST" && req.url === "/papers/search") {
      const body = await readBody(req);
      const results = await searchPapers(body.query, body.mode ?? "semantic");
      return sendJson(res, 200, { results });
    }

    if (req.method === "POST" && req.url === "/papers/get") {
      const body = await readBody(req);
      const result = await getPaper(body.paper, { fullText: Boolean(body.full_text) });
      return sendJson(res, 200, result);
    }

    if (req.method === "POST" && req.url === "/papers/ask") {
      const body = await readBody(req);
      const result = await askPaper(body.paper, body.question);
      return sendJson(res, 200, result);
    }

    if (req.method === "POST" && req.url === "/repos/read") {
      const body = await readBody(req);
      const result = await readPaperCode(body.githubUrl, body.path ?? "/");
      return sendJson(res, 200, result);
    }

    return notFound(res);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return sendJson(res, 500, { error: "bridge_error", message });
  }
});

server.listen(port, "127.0.0.1", () => {
  process.stdout.write(`alphaXiv bridge listening on http://127.0.0.1:${port}\n`);
});
