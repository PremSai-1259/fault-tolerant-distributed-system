from fastapi import FastAPI

app = FastAPI()

@app.get("/eligibility/{student_id}")
def eligibility(student_id: int, attendance: float = 0):
    return {
        "student_id": student_id,
        "attendance": attendance,
        "eligible": attendance >= 75
    }

@app.get("/health")
def health():
    return {"status": "ok"}