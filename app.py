from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse
from CalcEngine import CalcEngine

app = FastAPI()
engine = CalcEngine()

@app.get("/", include_in_schema=False)
async def root():
    return PlainTextResponse("Nothing here to see")

@app.get("/health", include_in_schema=False)
async def health():
    return JSONResponse({"status": "ok"})

@app.post("/solve")
async def solve(request: Request):
    content_type = request.headers.get("content-type")
    if content_type != "application/json":
        return JSONResponse(
            {"error": "<METHOD_NOT_FOUND>"},
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        )

    body = await request.body()
    return {"signature": engine.solve(body)}

@app.middleware("http")
async def block_invalid_methods(request: Request, call_next):
    if request.url.path == "/solve":
        if request.method != "POST":
            return PlainTextResponse("<METHOD_NOT_FOUND>", status_code=405)
        return await call_next(request)
    if request.url.path in ["/", "/health"]:
        return await call_next(request)
    return PlainTextResponse("<METHOD_NOT_FOUND>", status_code=405)
