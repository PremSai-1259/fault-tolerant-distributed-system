import requests
from fastapi import FastAPI, HTTPException

app = FastAPI()

ELIGIBILITY_URL = "http://eligibility-service:8000"

@app.get("/attendance/{student_id}")
def attendance(student_id: int):
    percentage = 90

    try:
        response = requests.get(
            f"{ELIGIBILITY_URL}/eligibility/{student_id}",
            params={"attendance": percentage},
            timeout=2
        )
        response.raise_for_status()
        result = response.json()
        return {
            "student_id": student_id,
            "attendance": percentage,
            "eligible": result["eligible"]
        }
    except requests.RequestException:
        raise HTTPException(
            status_code=503,
            detail="Eligibility Service unavailable"
        )

@app.get("/health")
def health():
    return {"status": "ok"}