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
for rid in ['S1','S2']:
 assert call('/api/customer/save',{'orders':[{'id':rid,'type':'online','hospital':'Sunrise Hospital · Demo','patient':'Schedule sample','specialty':'General medicine','date':date,'slot':'09:00 – 11:00'}]},c)[0]==200
assert not call('/api/state',token=wrong)[1]['customer']['orders']
p={'action':'accept','id':'S1','doctor':'Dr Schedule','amount':499,'date':date,'start':'10:00','end':'10:30'};assert call('/api/action',p,h)[0]==200
assert call('/api/action',{**p,'id':'S2'},h)[0]==400
assert call('/api/action',{'action':'pay_demo','id':'S1','context':'consultation','result':'success'},c)[0]==400
assert call('/api/action',{'action':'accept_schedule','id':'S1','scheduleRevision':1},c)[0]==200
assert call('/api/action',{'action':'pay_demo','id':'S1','context':'consultation','result':'success'},c)[0]==200
assert call('/api/action',{'action':'reschedule','id':'S1','date':date,'start':'13:00','end':'13:30'},h)[0]==200
assert call('/api/action',{'action':'accept_schedule','id':'S1','scheduleRevision':1},c)[0]==400
assert call('/api/action',{'action':'online_complete','id':'S1'},h)[0]==400
assert call('/api/action',{'action':'accept_schedule','id':'S1','scheduleRevision':2},c)[0]==200
assert call('/api/action',{'action':'online_complete','id':'S1'},h)[0]==200
with m.connect() as db:
 assert db.execute('SELECT COUNT(*) FROM payments').fetchone()[0]==1
 o=json.loads(db.execute("SELECT data FROM requests WHERE id='S1'").fetchone()[0]);assert o['amount']==499 and o['requestedSlot']=='09:00 – 11:00' and o['slot']=='13:00 – 13:30'
# Unchanged requested slot must accept directly, even with stale editor values.
assert call('/api/customer/save',{'orders':[{'id':'KEEP','type':'online','hospital':'Sunrise Hospital · Demo','patient':'Keep slot','date':date,'slot':'15:00 – 17:00'}]},c)[0]==200
assert call('/api/action',{'action':'accept','id':'KEEP','doctor':'Dr Available','amount':399,'scheduleMode':'keep','date':'2000-01-01','start':'01:00','end':'02:00'},h)[0]==200
kept=next(o for o in call('/api/state',token=c)[1]['customer']['orders'] if o['id']=='KEEP')
assert kept['date']==date and kept['slot']=='15:00 – 17:00' and kept['scheduleAccepted'] and not kept['scheduleNeedsAcceptance']
assert call('/api/action',{'action':'pay_demo','id':'KEEP','context':'consultation','result':'success'},c)[0]==200
print('PASS unchanged requested slot accepted without editing or additional customer schedule consent.')
server.shutdown();server.server_close();temp.cleanup();print('PASS Sunrise routing, overlapping-doctor-slot rejection, revised schedule consent, stale revision rejection, completion consent gate and no duplicate payment / fee mutation.')
