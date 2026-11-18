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
