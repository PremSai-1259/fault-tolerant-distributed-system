import requests
from fastapi import FastAPI, HTTPException

app = FastAPI()

ATTENDANCE_URL = "http://attendance-service:8000"

@app.get("/marks/{student_id}")
def marks(student_id: int):
    student_marks = 85

    try:
        response = requests.get(
            f"{ATTENDANCE_URL}/attendance/{student_id}",
            timeout=3
        )
        response.raise_for_status()
        data = response.json()

        return {
            "student_id": student_id,
            "marks": student_marks,
            "attendance": data["attendance"],
            "eligible": data["eligible"]
        }
    except requests.RequestException:
        raise HTTPException(
            status_code=503,
            detail="Attendance Service unavailable"
        )

@app.get("/health")
def health():
    return {"status": "ok"}