from fastapi import FastAPI

app = FastAPI(
    title="AI-Powered IPsec VPN Protocol Analyzer",
    version="1.0.0"
)

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "IPsec VPN Analyzer"
    }
