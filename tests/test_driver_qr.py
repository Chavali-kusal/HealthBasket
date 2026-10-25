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

driver=login('driver','9000000001')
assert call('/api/state',token=driver)[1]['partner']['drivers'][0]['online']
assert call('/api/action',{'action':'online','online':False},driver)[0]==200
ride={'id':'PRESENCE-RIDE','type':'ambulance','hospitalId':'HOSP-003','patient':'Sample rider','km':10,'coords':{'lat':14.6819,'lng':77.6006},'pickup':'Sample location','vehicle':'BLS','shareConsent':True}
assert call('/api/customer/save',{'orders':[ride]},c)[0]==200
assert not call('/api/state',token=driver)[1]['customer']['orders']
assert not call('/api/state',token=driver)[1]['partner']['drivers'][0]['online']
driver2=login('driver','9000000001')
assert any(o['id']=='PRESENCE-RIDE' for o in call('/api/state',token=driver2)[1]['customer']['orders'])
assert call('/api/logout',{},driver2)[0]==200
assert call('/api/state',token=driver)[0]==401 and call('/api/state',token=driver2)[0]==401
assert not call('/api/state',token=c)[1]['partner']['drivers']
doc=login('doctor','doctor001')
assert call('/api/intake-link',{'hospitalId':'HOSP-003'},c)[0]==403
link=call('/api/intake-link',{'hospitalId':'HOSP-003'},doc)[1]['url'];token=link.split('token=')[1]
assert call('/api/intake/'+token)[1]['hospitalId']=='HOSP-003'
payload={'submissionId':'qa-intake-unique-12345','name':'QR Sample','phone':'9000000091','problem':'General care','consent':False,'age':100,'note':'manual number'}
assert call('/api/intake/'+token,payload)[0]==400
code,created=call('/api/intake/'+token,{**payload,'consent':True});assert code==200
assert call('/api/intake/'+token,{**payload,'consent':True})[1]['referenceNumber']==created['referenceNumber']
refs=call('/api/state',token=doc)[1]['doctor']['referrals'];assert len(refs)==1 and refs[0]['note']==created['referenceNumber'] and 'age' not in refs[0]
assert len(call('/api/state',token=h)[1]['doctor']['referrals'])==1
assert not call('/api/state',token=wrong)[1]['doctor']['referrals']
assert call('/api/intake/invalid-token')[0]==400
server.shutdown();server.server_close();temp.cleanup();print('PASS driver auto-online, manual-off matching suppression/persistence, logout offline/all-session invalidation, Doctor-only QR links, token-scoped consent intake, automatic IDs/no Age or manual note, duplicate submission protection and hospital/doctor mapping.')
