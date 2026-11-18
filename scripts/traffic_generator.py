import argparse, asyncio, csv, datetime as dt, time, uuid
import httpx
async def one(client,url,writer,lock,experiment,student):
 rid=str(uuid.uuid4()); started=time.perf_counter(); status=0; category=""; outcome=""
 try:
  r=await client.get(f"{url}/results/{student}",headers={"X-Request-ID":rid}); status=r.status_code; body=r.json(); category=body.get("detail",{}).get("category","") if isinstance(body,dict) else ""; outcome=body.get("outcome","") if isinstance(body,dict) else ""
 except httpx.TimeoutException: category="timeout"
 except httpx.HTTPError: category="connection"
 async with lock: writer.writerow([dt.datetime.now(dt.UTC).isoformat(),experiment,rid,status,round((time.perf_counter()-started)*1000,2),category,outcome])
async def main(a):
 end=time.monotonic()+a.duration; lock=asyncio.Lock()
 with open(a.output,"w",newline="") as f:
  w=csv.writer(f);w.writerow(["timestamp","experiment_id","request_id","http_status","latency_ms","error_category","business_outcome"])
  async with httpx.AsyncClient(timeout=a.timeout) as c:
   while time.monotonic()<end:
    await asyncio.gather(*(one(c,a.url,w,lock,a.experiment,"S001" if i%5 else "BAD") for i in range(a.concurrency))); await asyncio.sleep(max(0,1/a.rate))
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--url",default="http://127.0.0.1:8000");p.add_argument("--duration",type=int,default=60);p.add_argument("--rate",type=float,default=2);p.add_argument("--concurrency",type=int,default=2);p.add_argument("--timeout",type=float,default=3);p.add_argument("--experiment",default="normal");p.add_argument("--output",default="experiments/results/traffic.csv");asyncio.run(main(p.parse_args()))
