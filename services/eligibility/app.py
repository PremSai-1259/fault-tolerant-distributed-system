from fastapi import FastAPI
from services.common.observability import install, lifespan
app=FastAPI(title="Eligibility Service", lifespan=lifespan); install(app)
@app.get("/eligibility/{percentage}")
async def eligibility(percentage:float): return {"attendance_percentage":percentage,"threshold":75,"eligible":percentage>=75}
