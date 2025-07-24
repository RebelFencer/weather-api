from fastapi import HTTPException
from database import get_user_by_key, increment_usage, get_plan_limit

async def validate_api_key(api_key: str):
    user = get_user_by_key(api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    max_requests = get_plan_limit(user["plan"])
    if user["requests_today"] >= max_requests:
        raise HTTPException(status_code=429, detail="Daily limit reached")

    increment_usage(api_key)
    return api_key

def get_plan_limits(api_key: str):
    user = get_user_by_key(api_key)
    if user:
        return {"plan": user["plan"], "requests_today": user["requests_today"], "limit": get_plan_limit(user["plan"])}
    return None