import os
import sys
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    # Bind to 0.0.0.0 so Railway and cloud container routers can reach the app
    host = os.environ.get("HOST", "0.0.0.0")
    is_railway = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_SERVICE_ID"))
    is_dev = not is_railway and os.environ.get("ENVIRONMENT", "development").lower() == "development"

    print("==================================================")
    print("  PattuBook - Back Office AI Assistant Server     ")
    print(f"  Serving on: http://{host}:{port}               ")
    print(f"  Mode: {'Railway / Production' if is_railway else 'Local Development'} ")
    print("==================================================")
    uvicorn.run("backend.main:app", host=host, port=port, reload=is_dev)


