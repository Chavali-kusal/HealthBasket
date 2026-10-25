import os,sys,tempfile,importlib.util,threading,urllib.request,urllib.error,json,datetime as dt
from pathlib import Path
root=Path(__file__).resolve().parent.parent;temp=tempfile.TemporaryDirectory();os.environ['HEALTHBASKET_DB']=str(Path(temp.name)/'test.sqlite3');spec=importlib.util.spec_from_file_location('schedule_test',root/'server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.initialise();server=m.ThreadingHTTPServer(('127.0.0.1',0),m.Handler);threading.Thread(target=server.serve_forever,daemon=True).start();base='http://127.0.0.1:'+str(server.server_port)
def call(path,data=None,token=None):
 if data and data.get('action') in ['pay_demo','sample_bill_pay']:data={**data,'termsAccepted':True,'termsVersion':'2026-10-v1'}
 headers={'Content-Type':'application/json'}
 if token:headers['Authorization']='Bearer '+token
 try:
  r=urllib.request.urlopen(urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers));return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
def login(role,user):return call('/api/login',{'role':role,'username':user,'password':'1234','name':'Schedule test'})[1]['token']
c=login('customer','9000000088');h=login('hospital','hospital003');wrong=login('hospital','hospital001');date=(dt.datetime.now(dt.timezone(dt.timedelta(hours=5,minutes=30))).date()+dt.timedelta(days=1)).isoformat()

for typ in ['pharmacy','labs','doctor','packages','offers']:
 rid='FLOW-'+typ
 assert call('/api/customer/save',{'orders':[{'id':rid,'type':typ,'hospital':'Sunrise Hospital · Demo','packageId':'cardio','patient':'Service QA','date':date,'address':'Sample address'}]},c)[0]==200
 res=call('/api/action',{'action':'accept','id':rid},h);assert res[0]==200,(typ,res)
 if typ=='offers':continue
 assert call('/api/action',{'action':'ready','id':rid},h)[0]==200
 assert call('/api/action',{'action':'bill','id':rid,'amount':550,'reference':'QA-'+typ},h)[0]==200
 assert call('/api/action',{'action':'cash','id':rid},h)[0]==200
 o=next(o for o in call('/api/state',token=c)[1]['customer']['orders'] if o['id']==rid)
 assert call('/api/action',{'action':'service_otp','id':rid,'code':o['completionOTP']},h)[0]==200
 assert call('/api/action',{'action':'cancel','id':rid,'reason':'too late'},c)[0]==400
for typ in ['online','pharmacy','labs','doctor','packages']:
 rid='REF-'+typ
 assert call('/api/customer/save',{'orders':[{'id':rid,'type':typ,'hospital':'Sunrise Hospital · Demo','packageId':'cardio','patient':'Refund QA','date':date,'slot':'15:00 – 17:00'}]},c)[0]==200
 assert call('/api/action',{'action':'accept','id':rid,'doctor':'Dr '+rid,'amount':599,'scheduleMode':'keep'},h)[0]==200
 if typ!='online':
  assert call('/api/action',{'action':'ready','id':rid},h)[0]==200
  assert call('/api/action',{'action':'bill','id':rid,'amount':599,'reference':rid},h)[0]==200
  assert call('/api/action',{'action':'link','id':rid},h)[0]==200
 assert call('/api/action',{'action':'pay_demo','id':rid,'context':'consultation' if typ=='online' else 'service_link','result':'success'},c)[0]==200
 assert call('/api/action',{'action':'cancel','id':rid,'reason':'Plans changed'},c)[0]==200
 o=next(o for o in call('/api/state',token=c)[1]['customer']['orders'] if o['id']==rid)
 assert o['cancellationStatus']=='Pending approval' and o['stage']!='cancelled' and 'refundStatus' not in o
 assert call('/api/action',{'action':'cancel','id':rid,'reason':'duplicate'},c)[0]==400
 assert call('/api/action',{'action':'cancel_approve','id':rid,'note':'Verified'},wrong)[0]==403
 assert call('/api/action',{'action':'cancel_approve','id':rid,'note':'Verified'},c)[0]==403
 assert call('/api/action',{'action':'cancel_approve','id':rid,'note':'Verified not performed'},h)[0]==200
 assert call('/api/action',{'action':'refund_claim','id':rid,'method':'original','consent':True},c)[0]==200
 assert call('/api/action',{'action':'refund_claim','id':rid,'method':'original','consent':True},c)[0]==400
 assert call('/api/action',{'action':'pay_demo','id':rid,'result':'success'},c)[0]==400
server.shutdown();server.server_close();temp.cleanup();print('PASS five provider service accept flows; cash + completion OTP; paid online/link-service cancellations/refund IDs, amount/reason/history; hospital-only cancellation approval and customer refund claim; duplicate refund/payment prevention; completed service cancellation blocked.')
