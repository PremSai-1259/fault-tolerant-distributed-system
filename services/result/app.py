import asyncio, os
from fastapi import FastAPI, Header, HTTPException, Request
from services.common.observability import install, lifespan
from services.common.client import get_json

app = FastAPI(title="Result Service", lifespan=lifespan)
install(app)

@app.get("/results/{student_id}")
async def result(student_id: str, request: Request):
    x_request_id = request.state.request_id

    marks_url = f"{os.getenv('MARKS_URL','http://marks-service:8000')}/marks/{student_id}"
    attendance_url = f"{os.getenv('ATTENDANCE_URL','http://attendance-service:8000')}/attendance/{student_id}"

    (marks, me), (attendance, ae) = await asyncio.gather(
        get_json("marks", marks_url, x_request_id),
        get_json("attendance", attendance_url, x_request_id)
    )

    if me == "not_found" or ae == "not_found":
        raise HTTPException(
            status_code=404,
            detail={"error": "student_not_found", "category": "business"}
        )

    if me or ae:
        raise HTTPException(503, {
            "error": "downstream_unavailable",
            "category": "infrastructure",
            "details": {"marks": me, "attendance": ae}
        })

    return {
        "student_id": student_id,
        "marks": marks["marks"],
        "average": marks["average"],
        "attendance_percentage": attendance["attendance_percentage"],
        "eligible": attendance["eligibility"],
        "outcome": "eligible" if attendance["eligibility"] else "business_ineligible",
        "request_id": x_request_id
    }