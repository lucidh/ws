from fastapi import FastAPI, Request, status, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from CalcEngine import CalcEngine
import json, os, mimetypes
from urllib.parse import urlparse

app = FastAPI()
engine = CalcEngine()

with open("webservice.json", "r", encoding="utf-8") as f:
    WS_SERVICES = json.load(f)["Services"]

SERVICES_BY_ID = {e["Id"]: e for e in WS_SERVICES}

def origin(request: Request) -> str:
    h = f"{request.url.scheme}://{request.url.hostname}"
    if request.url.port and request.url.port not in (80, 443):
        h = f"{h}:{request.url.port}"
    return h

def normalize(ep: str, request: Request, version: str) -> str:
    ep = ep.replace("{version}", version)
    if ep.startswith(("http://", "https://", "ws://", "wss://")):
        u = urlparse(ep)
        sch = "wss" if u.scheme in ("ws", "wss") and request.url.scheme == "https" else ("ws" if u.scheme in ("ws", "wss") else ("https" if request.url.scheme == "https" else "http"))
        return f"{sch}://{request.url.netloc}{u.path}"
    return f"{origin(request)}{ep}"

def find_streamables(version: str) -> str | None:
    candidates = [
        os.path.join("Build", "Release", version, "Streamables"),
        os.path.join("Build", f"Release_{version}", "Streamables"),
        os.path.join("Build", version, "Streamables"),
        os.path.join("Release", version, "Streamables")
    ]
    for b in candidates:
        if os.path.isdir(b):
            return b
    return None

@app.get("/", include_in_schema=False)
async def root():
    return PlainTextResponse("Nothing here to see")

@app.api_route("/health", methods=["GET", "HEAD"], include_in_schema=False)
async def health():
    return JSONResponse({"status": "ok"})

@app.post("/solve")
async def solve(request: Request):
    if request.headers.get("content-type") != "application/json":
        return JSONResponse({"error": "METHOD_NOT_FOUND"}, status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
    body = await request.body()
    return {"signature": engine.solve(body)}

@app.get("/discovery", include_in_schema=False)
async def discovery():
    with open("webservice.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return JSONResponse(data)

@app.get("/Build/Release/{version}/")
async def release_services(version: str, request: Request, services: str | None = None):
    svc_list = None
    if services is not None and services.strip() != "":
        svc_list = [s.strip() for s in services.split(",") if s.strip()]
    out = {}
    for sid, e in SERVICES_BY_ID.items():
        if svc_list and sid not in svc_list:
            continue
        ep = normalize(e["Endpoint"], request, version)
        if sid == "assets":
            if not ep.endswith("/"):
                ep += "/"
            out[sid] = {"id": e["Id"], "version": e["Version"], "endpoint": ep, "prefix": ep}
        else:
            out[sid] = {"id": e["Id"], "version": e["Version"], "endpoint": ep}
    return JSONResponse({"bundle": version, "services": out})

@app.get("/Build/Release/{version}/Streamables/assets/{path:path}")
async def get_asset(version: str, path: str):
    base = find_streamables(version)
    if not base:
        return PlainTextResponse("not found", status_code=404)
    full = os.path.join(base, "assets", path)
    if not os.path.isfile(full):
        return PlainTextResponse("not found", status_code=404)
    if full.endswith(".json") or full.endswith(".js"):
        with open(full, "r", encoding="utf-8") as f:
            text = f.read().replace("{version}", version)
        media_type = "application/json" if full.endswith(".json") else "application/javascript"
        return PlainTextResponse(text, media_type=media_type)
    guessed, _ = mimetypes.guess_type(full)
    media = guessed or "application/octet-stream"
    def gen():
        with open(full, "rb") as f:
            while True:
                b = f.read(65536)
                if not b:
                    break
                yield b
    return StreamingResponse(gen(), media_type=media)

@app.get("/Build/Release/{version}/instance", include_in_schema=False)
async def instance_http_probe(version: str):
    r = PlainTextResponse("Upgrade Required: use WebSocket", status_code=426)
    r.headers["Upgrade"] = "websocket"
    return r

@app.websocket("/Build/Release/{version}/instance")
async def instance_ws(version: str, ws: WebSocket):
    base = find_streamables(version)
    if not base:
        await ws.close()
        return
    ui_file = os.path.join(base, "ui", "index.json")
    await ws.accept()
    try:
        if os.path.isfile(ui_file):
            with open(ui_file, "r", encoding="utf-8") as f:
                spec_text = f.read().replace("{version}", version)
            await ws.send_text(spec_text)
        state = {"payload": ""}
        while True:
            msg = await ws.receive_text()
            try:
                data = json.loads(msg)
            except Exception:
                continue
            ev = data.get("event")
            wid = data.get("id")
            val = data.get("value")
            if ev == "textChanged" and wid == "payload":
                state["payload"] = val or ""
            elif ev == "clicked" and wid == "solveBtn":
                body = (state.get("payload") or "").encode("utf-8")
                try:
                    sig = engine.solve(body)
                    ops = [
                        {"op": "set", "id": "status", "prop": "text", "value": f"signature: {sig}"},
                        {"op": "set", "id": "solveBtn", "prop": "enabled", "value": False}
                    ]
                except Exception:
                    ops = [{"op": "set", "id": "status", "prop": "text", "value": "error"}]
                await ws.send_text(json.dumps({"type": "patch", "ops": ops}))
    except WebSocketDisconnect:
        pass
