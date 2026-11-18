import argparse, json
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
def main(a):
 df=pd.read_csv(a.input); df['ok']=df.http_status.between(200,299); duration=max(0.001,(pd.to_datetime(df.timestamp).max()-pd.to_datetime(df.timestamp).min()).total_seconds())
 summary={"experiment_id":a.experiment,"total_requests":len(df),"successful_requests":int(df.ok.sum()),"failed_requests":int((~df.ok).sum()),"availability_percent":round(df.ok.mean()*100,2),"successful_request_rate_percent":round(df.ok.mean()*100,2),"mean_latency_ms":round(df.latency_ms.mean(),2),"p50_latency_ms":round(df.latency_ms.quantile(.5),2),"p95_latency_ms":round(df.latency_ms.quantile(.95),2),"throughput_rps":round(len(df)/duration,2),"sla_target_availability_percent":a.sla}
 out=Path(a.output);out.mkdir(parents=True,exist_ok=True); (out/f'{a.experiment}.json').write_text(json.dumps(summary,indent=2)); (out/f'{a.experiment}.md').write_text('# Experiment report\n\n```json\n'+json.dumps(summary,indent=2)+'\n```\n\nAvailability here is request success rate; use detector events for wall-clock outage.\n')
 plt.figure();df.latency_ms.plot(kind='hist',bins=20,title='Latency (ms)');plt.savefig(out/f'{a.experiment}-latency.png');plt.close()
 print(json.dumps(summary,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',default='experiments/results/traffic.csv');p.add_argument('--output',default='experiments/reports');p.add_argument('--experiment',default='normal');p.add_argument('--sla',type=float,default=99.0);main(p.parse_args())
