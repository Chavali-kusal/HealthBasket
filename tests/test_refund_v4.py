import os,sys,tempfile,importlib.util,threading,urllib.request,urllib.error,json,datetime as dt
from pathlib import Path
root=Path(__file__).resolve().parent.parent;temp=tempfile.TemporaryDirectory();os.environ['HEALTHBASKET_DB']=str(Path(temp.name)/'test.sqlite3');spec=importlib.util.spec_from_file_location('schedule_test',root/'server.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.initialise();server=m.ThreadingHTTPServer(('127.0.0.1',0),m.Handler);threading.Thread(target=server.serve_forever,daemon=True).start();base='http://127.0.0.1:'+str(server.server_port)
def call(path,data=None,token=None):
 headers={'Content-Type':'application/json'}
 if token:headers['Authorization']='Bearer '+token
 try:
  r=urllib.request.urlopen(urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers));return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
def login(role,user):return call('/api/login',{'role':role,'username':user,'password':'1234','name':'Schedule test'})[1]['token']
c=login('customer','9000000088');h=login('hospital','hospital003');wrong=login('hospital','hospital001');date=(dt.datetime.now(dt.timezone(dt.timedelta(hours=5,minutes=30))).date()+dt.timedelta(days=1)).isoformat()

import base64
sys.path.insert(0,str(root));import company_finance as fin
# Finance and server import must use the same ephemeral database.
fin.s=m
terms={'termsAccepted':True,'termsVersion':m.REFUND_TERMS_VERSION}
def create(rid,doctor='Dr Refund'):
 assert call('/api/customer/save',{'orders':[{'id':rid,'type':'online','hospitalId':'HOSP-003','patient':'Refund sample','date':date,'slot':'09:00 – 11:00'}]},c)[0]==200
 assert call('/api/action',{'action':'accept','id':rid,'doctor':doctor+rid,'amount':599,'scheduleMode':'keep'},h)[0]==200
def act(a,rid,token=c,**kw):return call('/api/action',{'action':a,'id':rid,**kw},token)
def order(rid):return next(o for o in call('/api/state',token=c)[1]['customer']['orders'] if o['id']==rid)
create('A')
assert act('pay_demo','A',context='consultation',result='success')[0]==400
assert act('pay_demo','A',context='consultation',result='success',**terms)[0]==200
assert act('refund_claim','A',method='discount',consent=True)[0]==400
assert act('cancel_request','A',reason='Unavailable')[0]==200
assert order('A')['stage']=='priced' and 'refundStatus' not in order('A')
assert act('refund_claim','A',method='discount',consent=True)[0]==400
assert act('online_complete','A',h)[0]==400
assert act('cancel_approve','A',wrong,note='Other hospital')[0]==403
assert act('cancel_approve','A',note='Self approval')[0]==403
assert act('cancel_approve','A',h,note='Hospital verified no consultation performed')[0]==200
assert order('A')['refundStatus']=='Eligible to claim'
assert act('refund_claim','A',method='discount',consent=False)[0]==400
assert act('refund_claim','A',method='discount',consent=True)[0]==200
assert act('refund_claim','A',method='original',consent=True)[0]==400
assert fin.operate('issue-credit','A','FIN-QA-A').startswith('Discount credit')
try:fin.operate('issue-credit','A','DUP');raise AssertionError('Duplicate credit issued')
except ValueError:pass
credits=call('/api/state',token=c)[1]['customer']['discountCredits'];assert sum(x['remaining'] for x in credits)==599
create('B');assert act('pay_demo','B',context='consultation',result='success',useDiscount=True,**terms)[0]==200
assert order('B')['discountApplied']==599 and order('B')['companyCollected']==0
assert act('cancel_request','B',reason='Reschedule later')[0]==200
assert act('cancel_reject','B',h,note='Service was provided')[0]==200
assert act('online_complete','B',h)[0]==200
assert act('cancel_request','B',reason='Too late')[0]==400
assert act('refund_claim','B',method='original',consent=True)[0]==400
# Provider report only after completion, customer can download; unrelated hospital denied.
blob=base64.b64encode(b'%PDF-1.4\n%QA sample document').decode()
payload={'requestId':'B','kind':'report','filename':'sample.pdf','mime':'application/pdf','base64':blob}
assert call('/api/documents',payload,h)[0]==200
record=order('B')['clinicalRecords'][0]
assert call('/api/documents/'+record['documentId'],token=wrong)[0]==401
create('C');assert call('/api/documents',{**payload,'requestId':'C'},h)[0]==400
assert act('pay_demo','C',context='consultation',result='success',**terms)[0]==200
assert act('cancel_request','C',reason='Bank option')[0]==200
assert act('cancel_approve','C',h,note='Verified unused')[0]==200
assert act('refund_claim','C',method='bank',consent=True,holder='Sample',ifsc='SBIN0001234',last4='1234',accountNumber='123456789')[0]==400
assert act('refund_claim','C',method='bank',consent=True,holder='Sample',ifsc='SBIN0001234',last4='1234')[0]==200
assert 'refundBankPreference' not in next(o for o in call('/api/state',token=h)[1]['customer']['orders'] if o['id']=='C')
assert fin.operate('queue-refund','C','SECURE-BENEFICIARY-PENDING').startswith('Queued')
# Credit-only cancellation restores the original credit once; no extra bank refund.
create('D');assert act('pay_demo','D',context='consultation',result='success',**terms)[0]==200
assert act('cancel_request','D',reason='Original method')[0]==200
assert act('cancel_approve','D',h,note='No service')[0]==200
assert act('refund_claim','D',method='original',consent=True)[0]==200
try:fin.operate('issue-credit','D','NO-CONSENT');raise AssertionError('forced credit')
except ValueError:pass
# Restore credit on an approved cancellation without inventing a bank refund.
create('E');assert act('pay_demo','E',context='consultation',result='success',**terms)[0]==200
assert act('cancel_request','E',reason='Credit route')[0]==200
assert act('cancel_approve','E',h,note='No service')[0]==200
assert act('refund_claim','E',method='discount',consent=True)[0]==200
fin.operate('issue-credit','E','FIN-E')
create('F');assert act('pay_demo','F',context='consultation',result='success',useDiscount=True,**terms)[0]==200
assert act('cancel_request','F',reason='Restore unused credit')[0]==200
assert act('cancel_approve','F',h,note='Verified no service')[0]==200
assert 'refundStatus' not in order('F') and order('F')['companyCollected']==0
assert sum(x['remaining'] for x in call('/api/state',token=c)[1]['customer']['discountCredits'])==599
assert act('cancel_approve','F',h,note='Duplicate')[0]==400
assert call('/api/privacy/request',{'confirm':False},c)[0]==400
assert call('/api/privacy/request',{'confirm':True},c)[0]==200
assert call('/api/privacy/request',{'confirm':True},c)[0]==200
assert len(call('/api/privacy',token=c)[1]['requests'])==1
assert call('/api/privacy',token=h)[1]['requests']==[]
request=urllib.request.Request(base+'/api/documents/'+record['documentId'],headers={'Authorization':'Bearer '+c})
assert urllib.request.urlopen(request).read().startswith(b'%PDF-1.4')
server.shutdown();server.server_close();temp.cleanup();print('PASS terms enforced, approval-gated cancellation/refund, completion blocks, rejection/resume, explicit credit consent, one-time finance credit, atomic redemption, protected provider records, bank masking/no full-account storage and original-source preference.')
