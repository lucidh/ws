from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from CalcEngine import CalcEngine
import json, os
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

@app.get("/", include_in_schema=False)
async def root():
    return PlainTextResponse("Nothing here to see")

@app.api_route("/health", methods=["GET", "HEAD"], include_in_schema=False)
async def health():
    return JSONResponse({"status": "ok"})

@app.post("/solve")
async def solve(request: Request):
    if request.headers.get("content-type") != "application/json":
        return JSONResponse(
            {"error": "METHOD_NOT_FOUND"},
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        )
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
        out[sid] = {
            "id": e["Id"],
            "version": e["Version"],
            "endpoint": normalize(e["Endpoint"], request, version)
        }
    return JSONResponse({"bundle": version, "services": out})

@app.get("/Build/Release/{version}/assets/{path:path}")
async def get_asset(version: str, path: str):
    base = os.path.join("Build", "Release", version, "Streamables")
    full = os.path.join(base, path)
    if not os.path.isfile(full):
        return PlainTextResponse("not found", status_code=404)
    def gen():
        with open(full, "rb") as f:
            while True:
                b = f.read(65536)
                if not b:
                    break
                yield b
    return StreamingResponse(gen(), media_type="application/octet-stream")
