import os
os.environ['SERVICE_NAME']='test'
import pytest
from httpx import ASGITransport, AsyncClient
from services.marks.app import app as marks
from services.eligibility.app import app as eligibility
@pytest.mark.asyncio
async def test_marks_and_correlation():
 async with AsyncClient(transport=ASGITransport(app=marks),base_url='http://test') as c:
  r=await c.get('/marks/S001',headers={'X-Request-ID':'abc'}); assert r.status_code==200 and r.headers['X-Request-ID']=='abc' and r.json()['request_id']=='abc'
@pytest.mark.asyncio
async def test_invalid_student_is_business_404():
 async with AsyncClient(transport=ASGITransport(app=marks),base_url='http://test') as c: assert (await c.get('/marks/NOPE')).status_code==404
@pytest.mark.asyncio
async def test_eligibility_threshold():
 async with AsyncClient(transport=ASGITransport(app=eligibility),base_url='http://test') as c:
  assert (await c.get('/eligibility/75')).json()['eligible']; assert not (await c.get('/eligibility/74.9')).json()['eligible']

from services.result.app import app as result_app

@pytest.mark.asyncio
async def test_result_generates_request_id(monkeypatch):
    async def mock_get_json(service, url, request_id):
        if service == "marks":
            return {"marks": {"math": 88, "science": 91}, "average": 89.5}, None
        return {"attendance_percentage": 92, "eligibility": True}, None

    monkeypatch.setattr("services.result.app.get_json", mock_get_json)

    async with AsyncClient(
        transport=ASGITransport(app=result_app),
        base_url="http://test"
    ) as c:
        r = await c.get("/results/S001")

        assert r.status_code == 200
        assert r.headers.get("X-Request-ID")
        assert r.json()["request_id"] == r.headers["X-Request-ID"]