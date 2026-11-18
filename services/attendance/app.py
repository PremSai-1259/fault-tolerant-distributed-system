import os
from fastapi import FastAPI, Header, HTTPException
from services.common.observability import install, lifespan
from services.common.client import get_json
DATA={"S001":92,"S002":78,"S003":63}
app=FastAPI(title="Attendance Service", lifespan=lifespan); install(app)
@app.get("/attendance/{student_id}")
async def attendance(student_id:str, x_request_id:str=Header("")):
    if student_id not in DATA: raise HTTPException(404,"student_not_found")
    pct=DATA[student_id]; result,err=await get_json("eligibility",f"{os.getenv('ELIGIBILITY_URL','http://eligibility-service:8000')}/eligibility/{pct}",x_request_id)
    if err: raise HTTPException(503,{"error":"eligibility_unavailable","category":"infrastructure"})
    return {"student_id":student_id,"attendance_percentage":pct,"eligibility":result["eligible"],"request_id":x_request_id}
