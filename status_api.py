from fastapi import FastAPI, Depends, HTTPException, Query
from auth import get_plan_limits

app = FastAPI()

@app.get("/status")
def get_status(api_key: str = Query(...)):
    status = get_plan_limits(api_key)
    if not status:
        raise HTTPException(status_code=404, detail="API Key not found")
    return status