import pytest
from httpx import ASGITransport, AsyncClient
from services.marks.app import app
@pytest.mark.asyncio
async def test_metrics_endpoint():
 async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as c:
  await c.get('/marks/S001'); r=await c.get('/metrics'); assert r.status_code==200 and 'ft_http_requests_total' in r.text
