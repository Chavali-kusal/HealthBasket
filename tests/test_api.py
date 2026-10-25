import importlib.util,os,threading,json,urllib.request,urllib.error,concurrent.futures,base64
from pathlib import Path
root=Path(__file__).resolve().parent.parent
import tempfile
_temp=tempfile.TemporaryDirectory(prefix='healthbasket-api-test-')
file=Path(_temp.name)/'test.sqlite3'
os.environ['HEALTHBASKET_DB']=str(file)
spec=importlib.util.spec_from_file_location('suite',root/'server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.initialise()
srv=m.ThreadingHTTPServer(('127.0.0.1',0),m.Handler);threading.Thread(target=srv.serve_forever,daemon=True).start();base='http://127.0.0.1:'+str(srv.server_port)
def req(path,data=None,token=None):
 if data and data.get('action') in ['pay_demo','sample_bill_pay']:data={**data,'termsAccepted':True,'termsVersion':'2026-10-v1'}
 h={'Content-Type':'application/json'}
 if token:h['Authorization']='Bearer '+token
 try:
  r=urllib.request.urlopen(urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,headers=h));body=r.read();return r.status,json.loads(body) if r.headers.get_content_type()=='application/json' else body
 except urllib.error.HTTPError as e:return e.code,json.load(e)
def login(role,user):
 code,s=req('/api/login',{'role':role,'username':user,'password':'1234','name':'Sample '+user});assert code==200,(code,s);return s['token']
c=login('customer','9000000009');other=login('customer','9000000098');h=login('hospital','hospital001');h2=login('hospital','hospital002');doctor=login('doctor','doctor001');d=login('driver','9000000001')
assert req('/api/customer/save',{'orders':[]})[0]==403
order={'id':'ONLINE','type':'online','hospital':'VeloCare Hospital · Demo','patient':'Test Patient','specialty':'General medicine'}
assert req('/api/customer/save',{'orders':[order]},c)[0]==200
assert not req('/api/state',token=other)[1]['customer']['orders']
assert not req('/api/state',token=h2)[1]['customer']['orders']
assert req('/api/action',{'action':'accept','id':'ONLINE','doctor':'Test Doctor','amount':399},h2)[0]==403
assert req('/api/action',{'action':'accept','id':'ONLINE','doctor':'Test Doctor','amount':399},h)[0]==200
assert req('/api/action',{'action':'online','online':True},d)[0]==200
code,s=req('/api/driver/register',{'name':'Second driver','phone':'9000000002','vehicle':'BLS','vehicleNumber':'DEMO AP 002','registeredAddress':'Sample base','lat':14.6819,'lng':77.6006,'optIn':True});assert code==200;s2=s['token'];req('/api/action',{'action':'online','online':True},s2)
ride={'id':'RACE','type':'ambulance','hospital':'VeloCare Hospital · Demo','patient':'Test Rider','vehicle':'BLS','coords':{'lat':14.6819,'lng':77.6006},'pickup':'Sample pickup','shareConsent':True,'km':10,'amount':1}
assert req('/api/customer/save',{'orders':[ride]},c)[0]==200
with concurrent.futures.ThreadPoolExecutor() as pool:results=list(pool.map(lambda t:req('/api/action',{'action':'ride_accept','id':'RACE'},t),[d,s2]))
assert sorted(x[0] for x in results)==[200,403],results
winning= d if results[0][0]==200 else s2
state=req('/api/state',token=c)[1];o=next(x for x in state['customer']['orders'] if x['id']=='RACE');assert o['amount']==1420
assert req('/api/action',{'action':'pay_demo','id':'RACE','context':'ambulance','result':'success'},c)[0]==400
assert req('/api/action',{'action':'claim','id':'RACE'},winning)[0]==400
req('/api/customer/save',{'orders':[{**o,'stage':'completed','paymentStatus':'Paid · simulated','amount':1}]},c)
assert next(x for x in req('/api/state',token=c)[1]['customer']['orders'] if x['id']=='RACE')['stage']=='assigned'
assert req('/api/action',{'action':'arrive','id':'RACE'},winning)[0]==200
assert req('/api/action',{'action':'pickup_otp','id':'RACE','code':'0000'},winning)[0]==400
req('/api/action',{'action':'pickup_otp','id':'RACE','code':o['pickupOTP']},winning)
assert any('selected hospital notified' in e['text'] for e in req('/api/state',token=h)[1]['customer']['events'])
assert not any(x.get('pickupOTP') or x.get('completionOTP') for x in req('/api/state',token=winning)[1]['customer']['orders'])
req('/api/action',{'action':'drop','id':'RACE'},winning);req('/api/action',{'action':'handover_otp','id':'RACE','code':o['completionOTP']},winning)
assert req('/api/action',{'action':'claim','id':'RACE'},winning)[0]==400
assert req('/api/action',{'action':'pay_demo','id':'RACE','context':'ambulance','result':'success'},c)[0]==200
assert req('/api/action',{'action':'pay_demo','id':'RACE','context':'ambulance','result':'success'},c)[0]==400
assert req('/api/action',{'action':'claim','id':'RACE'},winning)[0]==200
assert req('/api/action',{'action':'claim','id':'RACE'},winning)[0]==400
png=base64.b64encode(b'\x89PNG\r\n\x1a\nDEMO').decode()
code,s=req('/api/documents',{'requestId':'ONLINE','filename':'sample.png','mime':'image/png','base64':png},c);assert code==200,s
did=next(x for x in s['customer']['orders'] if x['id']=='ONLINE')['rx']['documentId']
assert req('/api/documents/'+did,token=h)[0]==200
assert req('/api/documents/'+did,token=h2)[0] in [401,403]
assert req('/api/documents/'+did,token=winning)[0] in [401,403]
assert req('/api/documents',{'requestId':'ONLINE','filename':'bad.pdf','mime':'application/pdf','base64':base64.b64encode(b'<html>').decode()},c)[0]==400
assert req('/api/reports?from=2026-10-26&to=2026-10-01',token=h)[0]==400
assert req('/api/reports',token=other)[1]['rows']==[]
assert req('/api/doctor/save',{'referrals':[{'id':'REF1','name':'Care Test','hospitalId':'HOSP-001','problem':'Sample care'}]},doctor)[0]==200
assert req('/api/action',{'action':'follow_up','id':'REF1'},h)[0]==200
assert req('/api/action',{'action':'admit','id':'REF1'},h)[0]==200
with m.connect() as con:
 assert con.execute('PRAGMA foreign_key_check').fetchall()==[]
 assert con.execute('SELECT COUNT(*) FROM payments').fetchone()[0]==1
 assert con.execute('SELECT COUNT(*) FROM driver_claims').fetchone()[0]==1
 assert con.execute('SELECT amount FROM driver_claims').fetchone()[0]==1420
 assert con.execute('SELECT COUNT(*) FROM documents').fetchone()[0]==1
m.initialise()
with m.connect() as con:assert con.execute('SELECT COUNT(*) FROM requests').fetchone()[0]==2
srv.shutdown();srv.server_close();_temp.cleanup();print('PASS API role isolation, SQLite first-driver-wins, server OTP checks, amount tamper prevention, no client-stage/payment spoof, premature/duplicate claim/payment rejection, protected persistent files, file-type signatures, report scope/date validation, Doctor care status, foreign keys and restart-safe persistence.')
