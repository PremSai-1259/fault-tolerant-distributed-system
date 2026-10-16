import requests
from fastapi import FastAPI, HTTPException

app = FastAPI()

MARKS_URL = "http://marks-service:8000"

@app.get("/result/{student_id}")
def result(student_id: int):
    try:
        response = requests.get(
            f"{MARKS_URL}/marks/{student_id}",
            timeout=5
        )
        response.raise_for_status()
        data = response.json()

        passed = data["marks"] >= 40 and data["eligible"]

        return {
            "student_id": student_id,
            "marks": data["marks"],
            "attendance": data["attendance"],
            "eligible": data["eligible"],
            "result": "PASS" if passed else "FAIL"
        }
    except requests.RequestException:
        raise HTTPException(
            status_code=503,
            detail="Marks Service unavailable"
        )

@app.get("/health")
def health():
    return {"status": "ok"}