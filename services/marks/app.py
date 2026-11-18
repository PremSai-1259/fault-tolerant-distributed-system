from fastapi import FastAPI, Header, HTTPException
from services.common.observability import install, lifespan
DATA={"S001":{"math":88,"science":91},"S002":{"math":74,"science":69},"S003":{"math":55,"science":62}}
app=FastAPI(title="Marks Service", lifespan=lifespan); install(app)
@app.get("/marks/{student_id}")
async def marks(student_id:str, x_request_id:str=Header("")):
    if student_id not in DATA: raise HTTPException(404,"student_not_found")
    values=DATA[student_id]; return {"student_id":student_id,"marks":values,"average":sum(values.values())/len(values),"request_id":x_request_id}
