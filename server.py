"""Four separate demo clients, one SQLite database and role-scoped HTTP API. Python stdlib only."""
import base64, datetime as dt, hashlib, hmac, json, math, os, re, secrets, sqlite3, threading, time, webbrowser
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from credit_ops import spend
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
ROOT=Path(__file__).resolve().parent
DB=Path(os.environ.get('HEALTHBASKET_DB',str(ROOT/'data'/'healthbasket.sqlite3')))
HOSP=[('HOSP-001','VeloCare Hospital · Demo'),('HOSP-002','City Health Hospital · Demo'),('HOSP-003','Sunrise Hospital · Demo')]
SESSION_TTL=8*3600
REFUND_TERMS_VERSION='2026-10-v1'
LOCK=threading.RLock()
LOGIN_ATTEMPTS={}
INTAKE_ATTEMPTS={}
def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def ident(prefix): return prefix+'-'+secrets.token_hex(6).upper()
def dump(v): return json.dumps(v,ensure_ascii=False,separators=(',',':'))
def hashed(p,salt=None):
 salt=salt or secrets.token_hex(16)
 return salt+':'+hashlib.pbkdf2_hmac('sha256',p.encode(),salt.encode(),120000).hex()
def verify(p,h): return hmac.compare_digest(hashed(p,h.split(':')[0]),h)
def connect():
 c=sqlite3.connect(DB,timeout=15);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c
def initialise():
 DB.parent.mkdir(parents=True,exist_ok=True)
 with connect() as c:
  c.execute('PRAGMA journal_mode=WAL')
  c.executescript((ROOT/'schema.sql').read_text())
  for i,n in HOSP:c.execute('INSERT OR IGNORE INTO hospitals VALUES(?,?)',(i,n))
  for code,label in [('online','Online consultation'),('pharmacy','Pharmacy'),('labs','Home lab'),('doctor','Physician'),('packages','Health packages'),('offers','Camps'),('ambulance','Ambulance'),('billpay','Hospital QR bill')]:
   c.execute('INSERT OR IGNORE INTO services VALUES(?,?)',(code,label))
   for hospital,_ in HOSP:c.execute('INSERT OR IGNORE INTO hospital_services VALUES(?,?,1)',(hospital,code))
  rows=[('DOC-001','doctor001','doctor','Demo Doctor',None)]+[('STAFF-'+str(i),'hospital00'+str(i),'hospital','Hospital '+str(i)+' team',h[0]) for i,h in enumerate(HOSP,1)]+[('DRV-001','9000000001','driver','Ravi · demo',None)]
  for r in rows:c.execute('INSERT OR IGNORE INTO users VALUES(?,?,?,?,?,?)',(*r,hashed('1234')))
  d={'id':'DRV-001','name':'Ravi · demo','phone':'9000000001','vehicle':'BLS','vehicleNumber':'DEMO AP 001','registeredAddress':'Sample Anantapur station','lat':14.6819,'lng':77.6006,'online':True,'optIn':True,'verification':'Demo registration · not verified'}
  c.execute('INSERT OR IGNORE INTO driver_profiles VALUES(?,?,?,?,?,?)',(d['id'],d['vehicle'],0,d['lat'],d['lng'],dump(d)))
  for row in c.execute("SELECT * FROM requests WHERE service IN ('pharmacy','labs','doctor','packages') AND stage IN ('ready','completed')").fetchall():
   o=json.loads(row['data'])
   if not o.get('billRef'):put_request(c,o,row['customer_id'])
def num(v,minimum=0,maximum=1000000):
 try:n=float(v)
 except (ValueError,TypeError):raise ValueError('Enter a valid amount or coordinate.')
 if not math.isfinite(n) or not minimum<=n<=maximum:raise ValueError('Value is outside the permitted demo range.')
 return round(n,6)
def hospital_id(o):
 h=o.get('hospitalId')
 if h in dict(HOSP):return h
 return next((i for i,n in HOSP if n==o.get('hospital')),None)
def distance(a,b):
 x,y=map(math.radians,[float(a['lat']),float(b['lat'])]);dx=y-x;dy=math.radians(float(b['lng'])-float(a['lng']));v=math.sin(dx/2)**2+math.cos(x)*math.cos(y)*math.sin(dy/2)**2
 return 6371*2*math.atan2(math.sqrt(v),math.sqrt(max(0,1-v)))
def driver(c,i):
 r=c.execute('SELECT * FROM driver_profiles WHERE id=?',(i,)).fetchone()
 if not r:return None
 d=json.loads(r['data']);d.update(online=bool(r['online']),lat=r['lat'],lng=r['lng']);return d
def eligible(o,d):
 return bool(d and d.get('online') and d.get('optIn') and o.get('type')=='ambulance' and o.get('stage')=='dispatching' and not o.get('driver') and o.get('vehicle')==d.get('vehicle') and o.get('coords') and distance(d,o['coords'])<=10 and d['id'] not in o.get('declines',[]))
def read_request(c,i):
 r=c.execute('SELECT * FROM requests WHERE id=?',(i,)).fetchone()
 if not r:raise ValueError('Request not found.')
 o=json.loads(r['data']);o['_rev']=r['revision'];return r,o
def put_request(c,o,owner):
 if o.get('type') in ['pharmacy','labs','doctor','packages'] and o.get('stage') in ['ready','completed'] and not o.get('billRef'):o['billRef']=o['id']
 h=hospital_id(o)
 if not h:raise ValueError('Unknown hospital.')
 o['hospitalId']=h;o['hospital']=dict(HOSP)[h];o['customer_id']=owner
 old=c.execute('SELECT revision FROM requests WHERE id=?',(o['id'],)).fetchone();rev=old[0]+1 if old else 1;o['_rev']=rev;o['updatedAt']=now()
 c.execute('INSERT INTO requests VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET driver_id=excluded.driver_id,stage=excluded.stage,revision=excluded.revision,data=excluded.data',(o['id'],owner,h,(o.get('driver')or{}).get('id'),o['type'],o['stage'],o['createdAt'],rev,dump(o)))
def emit(c,u,o,text):
 t=now();o.setdefault('history',[]).append({'at':t,'text':text,'actor':u['role']+' · '+u['name']})
 c.execute('INSERT INTO events(request_id,actor_id,hospital_id,customer_id,text,created_at)VALUES(?,?,?,?,?,?)',(o['id'],u['id'],hospital_id(o),o.get('customer_id'),text,t))
def allowed(r,o,u,c):
 return u['role']=='customer' and r['customer_id']==u['id'] or u['role']=='hospital' and r['hospital_id']==u['hospital_id'] or u['role']=='driver' and (r['driver_id']==u['id'] or eligible(o,driver(c,u['id'])))
def public_order(o,role):
 o=json.loads(dump(o))
 if role!='customer':
  o.pop('pickupOTP',None);o.pop('completionOTP',None);o.pop('refundBankPreference',None)
 if role=='driver':
  for k in ['rx','reason','description','doctor','specialty']:o.pop(k,None)
 return o
def state(c,u):
 orders=[]
 query,args=('SELECT * FROM requests WHERE customer_id=? ORDER BY created_at DESC',(u['id'],)) if u['role']=='customer' else ('SELECT * FROM requests WHERE hospital_id=? ORDER BY created_at DESC',(u['hospital_id'],)) if u['role']=='hospital' else ("SELECT * FROM requests WHERE service='ambulance' AND (driver_id=? OR stage='dispatching') ORDER BY created_at DESC",(u['id'],))
 for r in c.execute(query,args):
  o=json.loads(r['data']);o['_rev']=r['revision']
  if allowed(r,o,u,c):orders.append(public_order(o,u['role']))
 refs=[]
 for r in c.execute('SELECT * FROM referrals WHERE doctor_id=? OR hospital_id=? ORDER BY created_at DESC',(u['id'] if u['role']=='doctor' else '',u['hospital_id'] if u['role']=='hospital' else '')):
  if u['role']=='doctor' and r['doctor_id']==u['id'] or u['role']=='hospital' and r['hospital_id']==u['hospital_id']:refs.append(json.loads(r['data']))
 claims=[]
 for r in c.execute('SELECT driver_claims.* FROM driver_claims JOIN requests ON requests.id=driver_claims.trip_id WHERE driver_claims.driver_id=? OR requests.customer_id=?',(u['id'] if u['role']=='driver' else '',u['id'] if u['role']=='customer' else '')):
  if u['role']=='driver' and r['driver_id']==u['id'] or u['role']=='customer' and any(o['id']==r['trip_id'] for o in orders):claims.append(json.loads(r['data']))
 records={k:[] for k in ['directClaims','benefits','billPayments','discountCredits']}
 for r in c.execute("SELECT * FROM ledger_records WHERE customer_id=? OR (hospital_id=? AND kind='directClaims') ORDER BY created_at DESC",(u['id'] if u['role']=='customer' else '',u['hospital_id'] if u['role']=='hospital' else '')):
  if u['role']=='customer' and r['customer_id']==u['id'] or u['role']=='hospital' and r['hospital_id']==u['hospital_id'] and r['kind']=='directClaims':records.setdefault(r['kind'],[]).append(json.loads(r['data']))
 ev=[];ev_revision=0
 for r in c.execute('SELECT * FROM events WHERE customer_id=? OR hospital_id=? OR request_id IN (SELECT id FROM requests WHERE driver_id=?) ORDER BY id DESC LIMIT 500',(u['id'] if u['role']=='customer' else '',u['hospital_id'] if u['role']=='hospital' else '',u['id'] if u['role']=='driver' else '')):
  ev_revision=max(ev_revision,r['id'])
  if u['role']=='customer' and r['customer_id']==u['id'] or u['role']=='hospital' and r['hospital_id']==u['hospital_id'] or any(o['id']==r['request_id'] for o in orders):ev.append({'id':r['request_id'],'text':r['text'],'at':r['created_at']})
 visits=[{'doctorId':o.get('doctorId'),'name':o.get('doctor'),'hospital':o['hospital'],'specialty':o.get('specialty'),'completed':True,'at':o.get('completedAt',o['createdAt'])} for o in orders if o['type']=='online' and o['stage']=='completed']
 ds=[driver(c,r['id']) for r in c.execute('SELECT id FROM driver_profiles')]
 if u['role']=='driver':ds=[d for d in ds if d['id']==u['id']]
 elif u['role']=='customer':ds=[{k:v for k,v in d.items() if k not in ['phone']} for d in ds if d['online']]
 else:ds=[]
 return {'user':{'id':u['id'],'name':u['name'],'phone':u['username'] if u['role']=='customer' else '', 'role':u['role'],'hospitalId':u['hospital_id']},'hospitals':[{'id':i,'name':n} for i,n in HOSP], 'customer':{'user':{'id':u['id'],'name':u['name'],'phone':u['username']},'loggedIn':True,'orders':orders,'events':ev,'driverClaims':claims,'visits':visits,**records},'partner':{'drivers':ds,'audit':[]},'doctor':{'referrals':refs,'profile':json.loads(pr['data']) if (pr:=c.execute('SELECT data FROM user_profiles WHERE user_id=?',(u['id'],)).fetchone()) else {}},'revision':ev_revision}
def apply_customer(c,u,payload):
 if u['role']!='customer':raise PermissionError('Customer account required.')
 for incoming in payload.get('orders',[]):
  if not isinstance(incoming,dict) or not incoming.get('id'):continue
  old=c.execute('SELECT * FROM requests WHERE id=?',(incoming['id'],)).fetchone()
  if not old:
   if incoming.get('type') not in ['online','pharmacy','labs','doctor','packages','offers','ambulance']:continue
   h=hospital_id(incoming)
   if not h:raise ValueError('Select a valid hospital.')
   typ=incoming['type']
   if not c.execute('SELECT 1 FROM hospital_services WHERE hospital_id=? AND service_id=? AND enabled=1',(h,typ)).fetchone():raise ValueError('Service is unavailable at the selected hospital.')
   o={k:v for k,v in incoming.items() if k in ['id','type','patient','hospital','hospitalId','specialty','doctor','doctorId','date','slot','reason','description','address','coords','rx','title','packageId','km','vehicle','pickup','shareConsent']}
   o.update(createdAt=now(),stage='interest' if typ=='offers' else 'dispatching' if typ=='ambulance' else 'requested',history=[],paymentStatus='No advance payment' if typ in ['pharmacy','labs','doctor'] else 'Not requested',amount=None,customer_id=u['id'],hospitalId=h)
   if typ=='packages':
    prices={'cardio':1499,'senior':2499,'diabetes':999,'kidney':1199,'liver':1099,'eye':599,'dental':499}
    if o.get('packageId') not in prices:raise ValueError('Unknown package.')
    o['amount']=prices[o['packageId']];o['paymentStatus']='Pay after service'
   if typ=='ambulance':
    km=num(o.get('km'),.1,1000);coord=o.get('coords')or{};num(coord.get('lat'),-85,85);num(coord.get('lng'),-180,180)
    if not o.get('shareConsent') or o.get('vehicle') not in ['BLS','ALS','ICU']:raise ValueError('Confirm dispatch consent and vehicle class.')
    amount=round(1200+km*12+100,2);o.update(amount=amount,km=km,fare={'base':1200,'perKm':12,'km':km,'extras':100,'total':amount},paymentStatus='Due after trip',pickupOTP=str(secrets.randbelow(9000)+1000),completionOTP=str(secrets.randbelow(9000)+1000))
   if typ=='ambulance':
    candidates=[driver(c,d['id']) for d in c.execute('SELECT id FROM driver_profiles')]
    o['candidates']=[d for d in candidates if eligible(o,d)]
    o['dispatchPreview']=[{'driverId':d['id'],'to':d['name'],'status':'Preview only · not sent','message':'Ambulance request '+o['id']+' | Pickup '+str(o.get('pickup'))+' | '+str(o.get('coords'))+' | '+o['hospital']+' | INR '+str(o['amount'])} for d in o['candidates']]
   emit(c,u,o,'Customer request received by selected hospital'+('; ambulance dispatch queued' if typ=='ambulance' else ''));put_request(c,o,u['id'])
  elif old['customer_id']==u['id'] and incoming.get('stage')=='cancelled' and json.loads(old['data'])['stage']!='cancelled':
   action(c,u,{'action':'cancel','id':incoming['id'],'reason':incoming.get('cancelReason','Customer cancellation')})
 for rec in payload.get('directClaims',[]):
  if not rec.get('id') or c.execute('SELECT 1 FROM ledger_records WHERE id=?',(rec['id'],)).fetchone():continue
  h=hospital_id(rec)
  if not h:raise ValueError('Receipt hospital is not recognised.')
  o={k:rec.get(k) for k in ['id','billId','invoice','receiptRef','proof']};o.update(hospitalId=h,hospital=dict(HOSP)[h],amount=num(rec.get('amount'),.01),status='Awaiting hospital confirmation',at=now())
  duplicate=c.execute("SELECT data FROM ledger_records WHERE customer_id=? AND kind IN ('directClaims','billPayments')",(u['id'],)).fetchall()
  if any(json.loads(r[0]).get('billId')==o['billId'] for r in duplicate):continue
  c.execute('INSERT INTO ledger_records VALUES(?,?,?,?,?,?)',(o['id'],u['id'],h,'directClaims',now(),dump(o)))
 for rec in payload.get('benefits',[]):
  if not rec.get('id'):continue
  old=c.execute("SELECT * FROM ledger_records WHERE id=? AND customer_id=? AND kind='benefits'",(rec['id'],u['id'])).fetchone()
  src=c.execute('SELECT * FROM ledger_records WHERE id=? AND customer_id=?',(rec.get('sourceId'),u['id'])).fetchone()
  if not old:
   if not src:continue
   existing=c.execute("SELECT data FROM ledger_records WHERE customer_id=? AND kind='benefits'",(u['id'],)).fetchall()
   if any(json.loads(x[0]).get('billId')==rec.get('billId') for x in existing):continue
   o={'id':rec['id'],'billId':rec.get('billId'),'sourceId':src['id'],'source':'hospital_direct' if src['kind']=='directClaims' else 'app','amount':50,'status':'Pending verification','at':now()}
   c.execute('INSERT INTO ledger_records VALUES(?,?,?,?,?,?)',(o['id'],u['id'],src['hospital_id'],'benefits',now(),dump(o)))
  else:
   o=json.loads(old['data']);source=c.execute('SELECT * FROM ledger_records WHERE id=?',(o['sourceId'],)).fetchone();data=json.loads(source['data']) if source else {}
   if rec.get('status')=='Verified · demo credit' and o['status']=='Pending verification' and data.get('status') in ['Paid · simulated','Hospital confirmed · demo']:o.update(status='Verified · demo credit',verifiedAt=now())
   elif rec.get('status')=='Claimed · simulated' and o['status']=='Verified · demo credit':o.update(status='Claimed · simulated',claimRef=ident('BENEFIT-DEMO'),claimedAt=now())
   c.execute('UPDATE ledger_records SET data=? WHERE id=?',(dump(o),o['id']))
def slot_parts(slot):
 parts=re.findall(r'\b(?:[01]\d|2[0-3]):[0-5]\d\b',str(slot or ''))
 return (parts[0],parts[1]) if len(parts)>=2 else ('09:00','11:00')
def confirm_schedule(c,o,p,reschedule=False):
 if not reschedule and p.get('scheduleMode')=='keep':p={}
 today=dt.datetime.now(dt.timezone(dt.timedelta(hours=5,minutes=30))).date()
 date=str(p.get('date')or o.get('confirmedDate')or o.get('date')or today.isoformat())
 try:chosen=dt.date.fromisoformat(date)
 except ValueError:raise ValueError('Choose a valid consultation date.')
 date=chosen.isoformat()
 if chosen<today:raise ValueError('Confirmed consultation date cannot be in the past.')
 old_start,old_end=slot_parts(o.get('slot'));start=str(p.get('start')or old_start);end=str(p.get('end')or old_end)
 try:
  st=dt.datetime.strptime(start,'%H:%M').time();en=dt.datetime.strptime(end,'%H:%M').time()
 except ValueError:raise ValueError('Choose valid start/end times.')
 if en<=st:raise ValueError('End time must be after start time.')
 start=st.strftime('%H:%M');end=en.strftime('%H:%M')
 for r in c.execute("SELECT data FROM requests WHERE hospital_id=? AND service='online' AND stage IN ('priced','completed')",(hospital_id(o),)):
  other=json.loads(r[0])
  if other['id']==o['id'] or other.get('doctorId')!=o.get('doctorId') or (other.get('confirmedDate')or other.get('date'))!=date:continue
  a,b=slot_parts(other.get('slot'))
  if start<b and end>a:raise ValueError('This doctor already has an overlapping confirmed slot. Choose another time.')
 old_date=o.get('confirmedDate')or o.get('date');changed=old_date!=date or old_start!=start or old_end!=end
 if reschedule and not changed:raise ValueError('Choose a different date or time to reschedule.')
 o.setdefault('requestedDate',o.get('date')or date);o.setdefault('requestedSlot',o.get('slot')or (start+' – '+end))
 revision=o.get('scheduleRevision',0)+1;needs=reschedule or changed
 o.update(date=date,slot=start+' – '+end,confirmedDate=date,confirmedStart=start,confirmedEnd=end,scheduleRevision=revision,scheduleNeedsAcceptance=needs,scheduleAccepted=not needs,scheduleAcceptedRevision=revision if not needs else None)
 return needs

def action(c,u,p):
 a=p.get('action');rid=p.get('id')
 if a=='online':
  if u['role']!='driver':raise PermissionError('Driver account required.')
  d=driver(c,u['id']);d['online']=bool(p.get('online'));c.execute('UPDATE driver_profiles SET online=?,data=? WHERE id=?',(int(d['online']),dump(d),u['id']));return
 if a=='receipt_confirm':
  r=c.execute("SELECT * FROM ledger_records WHERE id=? AND kind='directClaims'",(rid,)).fetchone()
  if not r or u['role']!='hospital' or r['hospital_id']!=u['hospital_id']:raise PermissionError('Hospital receipt access denied.')
  o=json.loads(r['data']);o.update(status='Hospital confirmed · demo',confirmedAmount=o['amount'],confirmedAt=now(),confirmedBy=u['name']);c.execute('UPDATE ledger_records SET data=? WHERE id=?',(dump(o),rid));return
 if a in ['follow_up','admit']:
  r=c.execute('SELECT * FROM referrals WHERE id=?',(rid,)).fetchone()
  if not r or u['role']!='hospital' or r['hospital_id']!=u['hospital_id']:raise PermissionError('Referral access denied.')
  o=json.loads(r['data']);target='follow_up' if a=='follow_up' else 'admitted'
  if {'submitted':'follow_up','follow_up':'admitted'}.get(o['status'])!=target:raise ValueError('Care record state changed.')
  o['status']=target;t=now();o.setdefault('timeline',[]).append({'title':'Hospital follow-up started' if a=='follow_up' else 'Admission confirmed','actor':'Hospital team · '+u['name'],'at':t,'note':'Explicit care event; no service fee inferred.'});c.execute('UPDATE referrals SET status=?,data=? WHERE id=?',(target,dump(o),rid));return
 if a=='sample_bill_pay':
  if u['role']!='customer':raise PermissionError('Customer account required.')
  if p.get('termsVersion')!=REFUND_TERMS_VERSION or p.get('termsAccepted') is not True:raise ValueError('Accept the cancellation/refund terms before payment.')
  known={'HBILL-001':('HOSP-001',900,'General consultation · sample bill','VC-DEMO-1001'),'HBILL-002':('HOSP-002',450,'CBC · sample bill','CH-DEMO-2001')}
  if rid not in known:raise ValueError('Unknown demo bill.')
  for r in c.execute("SELECT * FROM ledger_records WHERE customer_id=? AND kind IN ('billPayments','directClaims')",(u['id'],)):
   if json.loads(r['data']).get('billId')==rid:raise ValueError('This bill already has a payment or direct receipt.')
  h,amount,title,inv=known[rid];payid=ident('BILLPAY-DEMO');ref=ident('PAY-DEMO');o={'id':ident('HB'),'type':'billpay','billId':rid,'hospitalId':h,'hospital':dict(HOSP)[h],'title':title,'patient':u['name'],'createdAt':now(),'amount':amount,'stage':'completed','paymentStatus':'Paid · simulated','paymentRef':ref,'companyCollected':amount,'customer_id':u['id'],'history':[]};o.update(paymentTermsVersion=REFUND_TERMS_VERSION,paymentTermsAcceptedAt=now());emit(c,u,o,'Demo bill payment recorded; not a bank transaction');put_request(c,o,u['id']);c.execute('INSERT INTO payments VALUES(?,?,?,?,?,?,?)',(ref,o['id'],u['id'],amount,'Sample QR','Paid · simulated',now()))
  pay={'id':payid,'billId':rid,'invoice':inv,'hospitalId':h,'serviceId':'Sample bill','amount':amount,'status':'Paid · simulated','paymentRef':ref,'at':now()};c.execute('INSERT INTO ledger_records VALUES(?,?,?,?,?,?)',(payid,u['id'],h,'billPayments',now(),dump(pay)));bid=ident('BENEFIT-DEMO');benefit={'id':bid,'billId':rid,'sourceId':payid,'source':'app','amount':50,'status':'Pending verification','at':now()};c.execute('INSERT INTO ledger_records VALUES(?,?,?,?,?,?)',(bid,u['id'],h,'benefits',now(),dump(benefit)));return
 r,o=read_request(c,rid)
 if not allowed(r,o,u,c):raise PermissionError('Request belongs to another account.')
 role=u['role'];stage=o['stage'];paid=o.get('paymentStatus') in ['Paid · simulated','Cash received · simulated']
 if o.get('cancellationStatus')=='Pending approval' and a not in ['cancel_approve','cancel_reject','cancel','cancel_request'] and not (role=='driver' and o['type']=='ambulance' and a in ['gps','arrive','pickup_otp','drop','handover_otp']):raise ValueError('Cancellation review pending. Hospital must decide before service/payment actions continue.')
 if a=='accept' and role=='hospital':
  if stage not in ['requested','interest'] or o['type']=='ambulance':raise ValueError('Request is no longer new.')
  if stage=='interest':
   if o.get('hospitalAcknowledged'):raise ValueError('Interest already acknowledged.')
   o['hospitalAcknowledged']=True
  elif o['type']=='online':
   name=str(p.get('doctor','')).strip()
   if not name:raise ValueError('Enter confirmed doctor name.')
   o.update(stage='priced',doctor=name[:80],doctorId=u['hospital_id']+'-'+hashlib.sha256(name.lower().encode()).hexdigest()[:10],amount=round(num(p.get('amount'),1),2),paymentStatus='Company payment due')
   confirm_schedule(c,o,p)
  else:o['stage']='accepted'
  text=('Hospital confirmed '+o['doctor']+' · '+o['date']+' '+o['slot']+' · INR '+str(o['amount'])+(' · customer schedule approval required' if o.get('scheduleNeedsAcceptance') else '') if o['type']=='online' else 'Hospital accepted request')
 elif a=='reschedule' and role=='hospital':
  if o['type']!='online' or stage!='priced':raise ValueError('Only a confirmed, unfinished consultation can be rescheduled.')
  confirm_schedule(c,o,p,reschedule=True);text='Hospital proposed revised consultation slot '+o['date']+' '+o['slot']+'; customer approval required'
 elif a=='accept_schedule' and role=='customer':
  if o['type']!='online' or stage!='priced' or not o.get('scheduleNeedsAcceptance'):raise ValueError('No revised consultation slot is awaiting acceptance.')
  if p.get('scheduleRevision')!=o.get('scheduleRevision'):raise ValueError('The hospital changed this slot again. Review the latest schedule.')
  o.update(scheduleAccepted=True,scheduleAcceptedRevision=o['scheduleRevision']);text='Customer accepted hospital-confirmed consultation slot '+o['date']+' '+o['slot']
 elif a=='ready' and role=='hospital':
  if stage!='accepted' or o['type'] in ['online','ambulance']:raise ValueError('Accept this service first.')
  o.update(stage='ready',serviceDoneAt=now(),completionOTP=str(secrets.randbelow(9000)+1000));text='Hospital recorded service/delivery; awaiting customer completion OTP'
 elif a=='bill' and role=='hospital':
  if stage not in ['ready','completed'] or paid or o['type'] in ['online','ambulance','billpay']:raise ValueError('Bill cannot be changed now.')
  ref=o.get('billRef') or o['id']
  o.update(amount=round(num(p.get('amount'),.01),2),billRef=ref[:80],paymentLink=None,paymentStatus='Bill issued · due after service');text='Hospital issued after-service bill'
 elif a=='link' and role=='hospital':
  if stage not in ['ready','completed'] or not o.get('amount') or paid:raise ValueError('A payable after-service bill is required.')
  if o.get('paymentLink') and o['paymentLink']['expiresAt']>time.time()*1000:raise ValueError('Existing link is still active.')
  o['paymentLink']={'id':ident('LINK-DEMO'),'amount':o['amount'],'createdAt':now(),'expiresAt':int(time.time()*1000)+1800000,'status':'issued'};text='Hospital issued local demo payment link'
 elif a=='cash' and role=='hospital':
  if stage not in ['ready','completed'] or not o.get('amount') or paid or o['type']=='ambulance':raise ValueError('Cash cannot be recorded now.')
  o.update(paymentStatus='Cash received · simulated',paymentMethod='Cash',paymentRef=ident('CASH-DEMO'));text='Hospital acknowledged cash in demo; no bank transaction'
 elif a=='service_otp' and role=='hospital':
  if stage!='ready' or str(p.get('code'))!=o.get('completionOTP'):raise ValueError('Completion OTP does not match or service is not ready.')
  o.update(stage='completed',completionVerified=True,completedAt=now());text='Hospital verified customer completion OTP'
 elif a=='online_complete' and role=='hospital':
  if o['type']!='online' or stage!='priced' or o.get('paymentStatus')!='Paid · simulated':raise ValueError('Consultation requires confirmed fee and demo collection.')
  if o.get('scheduleNeedsAcceptance') and not o.get('scheduleAccepted'):raise ValueError('Customer must accept the revised consultation schedule first.')
  o.update(stage='completed',completedAt=now());text='Hospital recorded consultation completion'
 elif a=='ride_accept' and role=='driver':
  if not eligible(o,driver(c,u['id'])):raise ValueError('This trip is no longer available.')
  active=c.execute("SELECT 1 FROM requests WHERE driver_id=? AND stage IN ('assigned','arrived','in_trip','dropped')",(u['id'],)).fetchone()
  if active:raise ValueError('Finish your active trip first.')
  o.update(driver=driver(c,u['id']),stage='assigned',assignedAt=now());text='Registered driver accepted ambulance request'
 elif a=='ride_pass' and role=='driver':
  if not eligible(o,driver(c,u['id'])):raise ValueError('Request is no longer available.')
  o['declines']=list(set(o.get('declines',[])+[u['id']]));text='Driver passed the request'
 elif a=='arrive' and role=='driver':
  if r['driver_id']!=u['id'] or stage!='assigned':raise ValueError('Trip is not assigned / active.')
  o['stage']='arrived';text='Ambulance arrived at pickup; selected hospital notified'
 elif a=='pickup_otp' and role=='driver':
  if r['driver_id']!=u['id'] or stage!='arrived' or str(p.get('code'))!=o.get('pickupOTP'):raise ValueError('Pickup OTP does not match or trip is not at pickup.')
  o.update(stage='in_trip',pickupVerified=True);text='Driver verified pickup OTP; patient en route; selected hospital notified'
 elif a=='drop' and role=='driver':
  if r['driver_id']!=u['id'] or stage!='in_trip':raise ValueError('Trip is not in progress.')
  o.update(stage='dropped',serviceDoneAt=now());text='Driver recorded hospital arrival/drop'
 elif a=='handover_otp' and role=='driver':
  if r['driver_id']!=u['id'] or stage!='dropped' or str(p.get('code'))!=o.get('completionOTP'):raise ValueError('Handover OTP does not match or trip is not dropped.')
  o.update(stage='completed',completionVerified=True,completedAt=now());text='Driver verified customer handover OTP; selected hospital notified'
 elif a=='gps' and role=='driver':
  if r['driver_id']!=u['id'] or stage not in ['assigned','arrived','in_trip']:raise ValueError('No active assigned trip.')
  o['driverLocation']={'lat':num(p.get('lat'),-85,85),'lng':num(p.get('lng'),-180,180),'accuracy':num(p.get('accuracy'),0,100000),'at':now(),'source':'Browser GPS point · demo'};text='Driver shared a current GPS point'
 elif a=='claim' and role=='driver':
  if r['driver_id']!=u['id'] or stage!='completed' or not o.get('completionVerified') or o.get('paymentStatus')!='Paid · simulated':raise ValueError('Completion OTP and customer collection are required.')
  if c.execute('SELECT 1 FROM driver_claims WHERE trip_id=?',(rid,)).fetchone():raise ValueError('Trip already claimed.')
  claim={'id':ident('CLAIM-DEMO'),'orderId':rid,'driverId':u['id'],'amount':o['amount'],'status':'Claimed','createdAt':now()};c.execute('INSERT INTO driver_claims VALUES(?,?,?,?,?,?,?)',(claim['id'],rid,u['id'],claim['amount'],claim['status'],claim['createdAt'],dump(claim)));text='Driver claimed full fare; company finance pending'
 elif a=='pay_demo' and role=='customer':
  if p.get('termsVersion')!=REFUND_TERMS_VERSION or p.get('termsAccepted') is not True:raise ValueError('Accept the cancellation/refund terms before payment.')
  if o['type']=='online' and o.get('scheduleNeedsAcceptance') and not o.get('scheduleAccepted'):raise ValueError('Accept the hospital-confirmed date/time before payment.')
  context=p.get('context');valid=o['type']=='online' and stage=='priced' or o['type']=='ambulance' and stage in ['dropped','completed'] or context=='service_link' and stage in ['ready','completed'] and o.get('paymentLink')
  if not valid or not o.get('amount') or paid:raise ValueError('Payment not available or already collected.')
  if context=='service_link' and o['paymentLink']['expiresAt']<time.time()*1000:raise ValueError('Payment link expired.')
  result=p.get('result','success')
  if result=='success':
   o.update(paymentTermsVersion=REFUND_TERMS_VERSION,paymentTermsAcceptedAt=now())
   used=spend(c,u['id'],o['amount']) if p.get('useDiscount') is True else 0;cash=round(o['amount']-used,2)
   ref=ident('PAY-DEMO');o.update(paymentStatus='Paid · simulated',paymentRef=ref,paymentMethod=str(p.get('method','Demo')),companyCollected=cash,discountApplied=used,paidAt=now());c.execute('INSERT INTO payments VALUES(?,?,?,?,?,?,?)',(ref,rid,u['id'],cash,o['paymentMethod'],'Paid · simulated',now()))
   if o.get('paymentLink'):o['paymentLink']['status']='paid'
   text='Company payment simulated; no real funds moved'
  else:o['paymentStatus']='Payment failed · retry available' if result=='failed' else 'Payment pending · unverified';text=o['paymentStatus']
 elif a=='link_request' and role=='customer':
  if stage not in ['ready','completed'] or paid or o['type'] not in ['pharmacy','labs','doctor','packages']:raise ValueError('Payment link request is unavailable for this service/state.')
  o['paymentLinkRequested']=True;text='Customer requested an after-service payment link'
 elif a in ['cancel','cancel_request'] and role in ['customer','hospital']:
  if stage in ['completed','cancelled'] or o.get('clinicalRecords'):raise ValueError('Completed services / issued reports cannot be cancelled.')
  if o.get('cancellationStatus')=='Pending approval':raise ValueError('Cancellation is already awaiting approval.')
  reason=str(p.get('reason','')).strip()
  if not reason:raise ValueError('Cancellation reason is required.')
  o.update(cancellationStatus='Pending approval',cancellationReason=reason[:300],cancellationRequestedAt=now(),cancellationRequestId=ident('CANCEL-DEMO'))
  text='Cancellation requested; hospital/company verification pending (review target 48 hours). No refund claim available before approval.'
 elif a in ['cancel_approve','cancel_reject'] and role=='hospital':
  if o.get('cancellationStatus')!='Pending approval' or stage in ['completed','cancelled'] or o.get('clinicalRecords'):raise ValueError('No eligible cancellation awaiting approval.')
  note=str(p.get('note','')).strip()
  if not note:raise ValueError('Record hospital verification / decision reason.')
  o.update(cancellationDecisionAt=now(),cancellationDecisionNote=note[:400],cancellationDecidedBy=u['name'])
  if a=='cancel_reject':o['cancellationStatus']='Rejected';text='Hospital rejected cancellation: '+note[:300]
  else:
   o.update(stage='cancelled',cancellationStatus='Approved',cancelReason=o['cancellationReason'])
   if o.get('discountApplied',0):
    credit={'id':'RESTORE-'+rid,'amount':o['discountApplied'],'remaining':o['discountApplied'],'sourceId':rid,'status':'Available','createdAt':now()}
    c.execute('INSERT OR IGNORE INTO ledger_records VALUES(?,?,?,?,?,?)',(credit['id'],r['customer_id'],r['hospital_id'],'discountCredits',now(),dump(credit)))
   refundable=o.get('companyCollected',o.get('amount',0)) if paid else 0
   if refundable:o.update(refundStatus='Eligible to claim',refundAmount=refundable,refundId=ident('REFUND-DEMO'),refundEligibleAt=now(),paymentStatus='Refund eligible · simulated')
   text='Cancellation approved after hospital verification; '+('customer may now claim refund' if refundable else 'no cash refund due')
 elif a=='refund_claim' and role=='customer':
  if stage!='cancelled' or o.get('cancellationStatus')!='Approved' or o.get('refundStatus')!='Eligible to claim':raise ValueError('Refund claim requires approved cancellation and refundable payment.')
  if any(k in p for k in ['accountNumber','bankAccount','cvv','pin','otp']):raise ValueError('Do not send full bank/card credentials to this demo.')
  method=p.get('method')
  if method not in ['original','discount','bank']:raise ValueError('Choose a refund method.')
  if p.get('consent') is not True:raise ValueError('Accept the selected refund method and processing terms.')
  o.update(refundMethod=method,refundRequestedAt=now(),refundReason=o.get('cancelReason'),refundClaimConsentAt=now(),refundStatus='Claimed · company finance review')
  if method=='bank':
   holder=str(p.get('holder','')).strip();ifsc=str(p.get('ifsc','')).upper().strip();last4=str(p.get('last4','')).strip()
   if not holder or not re.fullmatch(r'[A-Z]{4}0[A-Z0-9]{6}',ifsc) or not re.fullmatch(r'\d{4}',last4):raise ValueError('Enter sample holder, valid IFSC and last 4 digits only.')
   o['refundBankPreference']={'holder':holder[:80],'ifsc':ifsc,'last4':last4,'status':'Secure beneficiary collection/verification pending'}
  text='Customer claimed '+method+' refund; company finance verification pending. No real bank funds moved.'
 else:raise PermissionError('This action is not permitted for your role or state.')
 if o['stage']=='completed' and o.get('cancellationStatus')=='Pending approval':o.update(cancellationStatus='Rejected',cancellationDecisionAt=now(),cancellationDecisionNote='Actual service completed before cancellation approval; refund cancellation is unavailable.')
 emit(c,u,o,text);put_request(c,o,r['customer_id'])
def report_rows(c,u,query):
 s=state(c,u);rows=[]
 for o in s['customer']['orders']:
  if u['role']=='driver' and (o.get('driver')or{}).get('id')!=u['id']:continue
  rows.append({'id':o['id'],'created':o['createdAt'],'service':o['type'],'title':o.get('title')or o['type'],'hospital':o['hospital'],'patient':o.get('patient',''),'status':o['stage'],'payment':o.get('paymentStatus',''),'amount':o.get('amount'),'kind':'Request'})
  if o.get('refundStatus') and u['role']!='driver':rows.append({'id':o.get('refundId')or o['id']+'-REFUND','created':o.get('refundRequestedAt')or o['createdAt'],'service':o['type'],'title':'Refund request · '+o['id'],'hospital':o['hospital'],'patient':o.get('patient',''),'status':o['refundStatus'],'payment':'Discount credit issued; no bank transfer' if o.get('refundStatus','').startswith('Discount credit issued') else 'Finance / original-source reconciliation; no live bank refund','amount':o.get('refundAmount',o.get('amount')),'kind':'Refund request'})
 for r in s['doctor']['referrals']:rows.append({'id':r['id'],'created':r['created'],'service':'care','title':'Doctor care submission','hospital':dict(HOSP).get(r['hospitalId'],''),'patient':r['name'],'status':r['status'],'payment':'No referral fee generated','amount':None,'kind':'Care record'})
 for cl in s['customer']['driverClaims']:rows.append({'id':cl['id'],'created':cl['createdAt'],'service':'driver_claim','title':'Driver claim','hospital':'','patient':'','status':cl['status'],'payment':'Company finance pending','amount':cl['amount'],'kind':'Claim'})
 for kind in ['directClaims','benefits','billPayments','discountCredits']:
  for r in s['customer'][kind]:rows.append({'id':r['id'],'created':r.get('at')or r.get('createdAt')or now(),'service':kind,'title':kind,'hospital':r.get('hospital',''),'patient':'','status':r.get('status',''),'payment':r.get('collection','Demo ledger'),'amount':r.get('amount'),'kind':kind})
 frm=query.get('from',[''])[0];to=query.get('to',[''])[0];svc=query.get('service',['all'])[0]
 for v in [frm,to]:
  if v:dt.date.fromisoformat(v)
 if frm and to and frm>to:raise ValueError('From date must be on or before To date.')
 for r in rows:
  try:r['date']=dt.datetime.fromisoformat(r['created'].replace('Z','+00:00')).astimezone(dt.timezone(dt.timedelta(hours=5,minutes=30))).date().isoformat()
  except ValueError:r['date']=''
 return [r for r in sorted(rows,key=lambda x:x['created'],reverse=True) if (not frm or r['date']>=frm) and (not to or r['date']<=to) and (svc=='all' or r['service']==svc)]
class Handler(BaseHTTPRequestHandler):
 def log_message(self,fmt,*args): pass
 def respond(self,status,data,mime='application/json; charset=utf-8'):
  body=dump(data).encode() if isinstance(data,(dict,list)) else data.encode() if isinstance(data,str) else data
  self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','SAMEORIGIN');self.send_header('Permissions-Policy','camera=(self), geolocation=(self), microphone=()');self.send_header('Referrer-Policy','strict-origin-when-cross-origin');self.end_headers();self.wfile.write(body)
 def auth(self,c):
  h=self.headers.get('Authorization','');token=h[7:] if h.startswith('Bearer ') else ''
  u=c.execute('SELECT users.* FROM sessions JOIN users ON sessions.user_id=users.id WHERE token=? AND expires>?',(token,time.time())).fetchone()
  if not u:raise PermissionError('Sign in to this app first.')
  return dict(u)
 def do_GET(self):
  path=urlparse(self.path).path
  try:
   if path.startswith('/api/'):
    with connect() as c:
     if path.startswith('/api/intake/'):
      link=c.execute('SELECT intake_links.*,users.name AS doctor FROM intake_links JOIN users ON users.id=doctor_id WHERE token=? AND expires>?',(path.rsplit('/',1)[1],time.time())).fetchone()
      if not link:raise ValueError('Intake link expired or invalid. Ask the doctor for a new QR.')
      return self.respond(200,{'doctor':link['doctor'],'hospitalId':link['hospital_id'],'hospital':dict(HOSP)[link['hospital_id']]})
     u=self.auth(c)
     if path=='/api/privacy':return self.respond(200,{'requests':[dict(r) for r in c.execute('SELECT id,kind,status,created_at FROM privacy_requests WHERE user_id=? ORDER BY created_at DESC',(u['id'],))]})
     if path=='/api/state':return self.respond(200,state(c,u))
     if path=='/api/reports':return self.respond(200,{'rows':report_rows(c,u,parse_qs(urlparse(self.path).query)),'timezone':'Asia/Kolkata','generated':now()})
     if path.startswith('/api/documents/'):
      d=c.execute('SELECT * FROM documents WHERE id=?',(path.rsplit('/',1)[1],)).fetchone()
      if not d:raise ValueError('Document not found.')
      r,o=read_request(c,d['request_id'])
      if not (u['role']=='customer' and r['customer_id']==u['id'] or u['role']=='hospital' and r['hospital_id']==u['hospital_id']):raise PermissionError('Document access denied.')
      return self.respond(200,d['content'],d['mime'])
    return self.respond(404,{'error':'Unknown API route.'})
   allowed={'/':'hospital.html','/customer':'customer.html','/customer/':'customer.html','/doctor':'doctor.html','/doctor/':'doctor.html','/hospital':'hospital.html','/hospital/':'hospital.html','/driver':'driver.html','/driver/':'driver.html','/sdk.js':'sdk.js','/privacy.js':'privacy.js','/qr-local.js':'qr-local.js','/intake':'intake.html','/intake/':'intake.html','/reports.js':'reports.js','/reports.css':'reports.css','/app-polish.css':'app-polish.css','/version.json':'version.json','/doctor/version.json':'version.json'}
   name=allowed.get(path)
   if not name or not (ROOT/'web'/name).is_file():return self.respond(404,'Not found','text/plain')
   mime='application/javascript' if name.endswith('.js') else 'text/css' if name.endswith('.css') else 'application/json' if name.endswith('.json') else 'text/html; charset=utf-8'
   return self.respond(200,(ROOT/'web'/name).read_bytes(),mime)
  except PermissionError as e:self.respond(401,{'error':str(e)})
  except ValueError as e:self.respond(400,{'error':str(e)})
 def do_POST(self):
  try:
   origin=self.headers.get('Origin')
   if origin and urlparse(origin).netloc!=self.headers.get('Host'):return self.respond(403,{'error':'Cross-origin write rejected.'})
   length=int(self.headers.get('Content-Length',0))
   if length>15*1024*1024:return self.respond(413,{'error':'Upload is too large.'})
   p=json.loads(self.rfile.read(length)or'{}');path=urlparse(self.path).path
   if not isinstance(p,dict):raise ValueError('JSON object required.')
   with LOCK,connect() as c:
    c.execute('BEGIN IMMEDIATE')
    if path=='/api/login':
     role=p.get('role');username=str(p.get('username','')).strip();password=str(p.get('password',''))
     if role not in ['customer','doctor','hospital','driver']:raise PermissionError('Unsupported app role.')
     key=(self.client_address[0],username);attempts=[t for t in LOGIN_ATTEMPTS.get(key,[]) if t>time.time()-300]
     if len(attempts)>=15:return self.respond(429,{'error':'Too many login attempts. Try after five minutes.'})
     LOGIN_ATTEMPTS[key]=attempts+[time.time()]
     if role=='customer':
      name=str(p.get('name','')).strip()
      if password!='1234' or len(username)!=10 or not username.isdigit() or username[0] not in '6789' or not name:raise ValueError('Use valid sample name/mobile and demo OTP 1234.')
      old=c.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
      if old and old['role']!='customer':raise ValueError('This mobile belongs to a different demo role. Use another sample number.')
      if not old:c.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',(ident('CUS'),username,'customer',name[:60],None,hashed('1234')))
     u=c.execute('SELECT * FROM users WHERE username=? AND role=?',(username,role)).fetchone()
     if not u or not verify(password,u['password_hash']):raise PermissionError('Incorrect account / demo password.')
     if role=='driver':
      d=driver(c,u['id']);d['online']=True;c.execute('UPDATE driver_profiles SET online=1,data=? WHERE id=?',(dump(d),u['id']))
     token=secrets.token_urlsafe(32);c.execute('INSERT INTO sessions VALUES(?,?,?)',(token,u['id'],time.time()+SESSION_TTL));result={'token':token,**state(c,dict(u))};c.commit();return self.respond(200,result)
    if path=='/api/driver/register':
     phone=str(p.get('phone',''));name=str(p.get('name','')).strip();vehicle=p.get('vehicle');vno=str(p.get('vehicleNumber','')).strip();addr=str(p.get('registeredAddress','')).strip()
     if len(phone)!=10 or not phone.isdigit() or phone[0] not in '6789' or not name or not addr or not vno or vehicle not in ['BLS','ALS','ICU'] or not p.get('optIn'):raise ValueError('Complete driver and vehicle details with demo dispatch consent.')
     if c.execute('SELECT 1 FROM users WHERE username=?',(phone,)).fetchone():raise ValueError('Mobile is already registered. Sign in instead.')
     if any(json.loads(r[0]).get('vehicleNumber','').casefold()==vno.casefold() for r in c.execute('SELECT data FROM driver_profiles')):raise ValueError('Vehicle number is already registered in this demo.')
     did=ident('DRV');lat=num(p.get('lat'),-85,85);lng=num(p.get('lng'),-180,180);d={'id':did,'name':name[:60],'phone':phone,'vehicle':vehicle,'vehicleNumber':vno[:30],'registeredAddress':addr[:200],'lat':lat,'lng':lng,'online':True,'optIn':True,'verification':'Demo registration · not verified'}
     c.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',(did,phone,'driver',name[:60],None,hashed('1234')));c.execute('INSERT INTO driver_profiles VALUES(?,?,?,?,?,?)',(did,vehicle,1,lat,lng,dump(d)));u=dict(c.execute('SELECT * FROM users WHERE id=?',(did,)).fetchone());token=secrets.token_urlsafe(32);c.execute('INSERT INTO sessions VALUES(?,?,?)',(token,did,time.time()+SESSION_TTL));c.commit();return self.respond(200,{'token':token,**state(c,u)})
    if path.startswith('/api/intake/'):
     token=path.rsplit('/',1)[1];link=c.execute('SELECT * FROM intake_links WHERE token=? AND expires>?',(token,time.time())).fetchone()
     if not link:raise ValueError('Intake link expired or invalid.')
     submission=str(p.get('submissionId',''))
     if not re.fullmatch(r'[A-Za-z0-9-]{12,80}',submission):raise ValueError('Valid submission key required.')
     old=c.execute('SELECT referral_id FROM intake_submissions WHERE submission_id=? AND token=?',(submission,token)).fetchone()
     if old:return self.respond(200,{'submitted':True,'referenceNumber':old['referral_id']})
     name=str(p.get('name','')).strip();phone=str(p.get('phone','')).strip();problem=str(p.get('problem','')).strip()
     if not name or len(name)>80 or not re.fullmatch(r'[6-9][0-9]{9}',phone) or not problem or len(problem)>120 or p.get('consent') is not True:raise ValueError('Enter name, valid mobile, reason and consent.')
     key=(self.client_address[0],token);attempts=[t for t in INTAKE_ATTEMPTS.get(key,[]) if t>time.time()-600]
     if len(attempts)>=12:return self.respond(429,{'error':'Too many submissions. Try later.'})
     INTAKE_ATTEMPTS[key]=attempts+[time.time()];rid=ident('REF');r={'id':rid,'referenceNumber':rid,'name':name,'phone':phone,'problem':problem,'gender':str(p.get('gender',''))[:30],'note':rid,'source':'Patient QR intake','doctorId':link['doctor_id'],'hospitalId':link['hospital_id'],'created':now(),'status':'submitted','confirmed':0,'claimed':0,'approved':0,'paid':0,'payments':[],'claimId':None,'timeline':[{'title':'Patient submitted by QR','actor':'Patient intake','at':now(),'note':'Consent recorded; hospital coordination pending.'}]}
     c.execute('INSERT INTO referrals VALUES(?,?,?,?,?,?)',(rid,link['doctor_id'],link['hospital_id'],'submitted',r['created'],dump(r)));c.execute('INSERT INTO intake_submissions VALUES(?,?,?)',(submission,token,rid));c.commit();return self.respond(200,{'submitted':True,'referenceNumber':rid})
    u=self.auth(c)
    if path=='/api/intake-link':
     if u['role']!='doctor':raise PermissionError('Doctor account required.')
     h=p.get('hospitalId')
     if h not in dict(HOSP):raise ValueError('Select a hospital.')
     link=c.execute('SELECT * FROM intake_links WHERE doctor_id=? AND hospital_id=?',(u['id'],h)).fetchone()
     token=link['token'] if link else secrets.token_urlsafe(24)
     c.execute('INSERT INTO intake_links VALUES(?,?,?,?) ON CONFLICT(doctor_id,hospital_id) DO UPDATE SET token=excluded.token,expires=excluded.expires',(token,u['id'],h,time.time()+30*86400))
     base=os.environ.get('HEALTHBASKET_PUBLIC_BASE_URL','').rstrip('/') or ('http://'+self.headers.get('Host','localhost:8765'))
     if urlparse(base).scheme not in ['http','https']:raise ValueError('Configure valid HTTP(S) public base URL.')
     c.commit();return self.respond(200,{'url':base+'/intake/?token='+token,'hospital':dict(HOSP)[h],'hospitalId':h})
    if path=='/api/logout':
     if u['role']=='driver':
      d=driver(c,u['id']);d['online']=False;c.execute('UPDATE driver_profiles SET online=0,data=? WHERE id=?',(dump(d),u['id']));c.execute('DELETE FROM sessions WHERE user_id=?',(u['id'],))
     else:c.execute('DELETE FROM sessions WHERE token=?',(self.headers.get('Authorization','')[7:],))
     c.commit();return self.respond(200,{'ok':True})
    if path=='/api/privacy/request':
     if p.get('confirm') is not True:raise ValueError('Explicit account deletion request confirmation required.')
     if not c.execute("SELECT 1 FROM privacy_requests WHERE user_id=? AND status='Pending company review'",(u['id'],)).fetchone():c.execute('INSERT INTO privacy_requests VALUES(?,?,?,?,?)',(ident('PRIVACY'),u['id'],'Account deletion','Pending company review',now()))
    elif path=='/api/customer/save':apply_customer(c,u,p)
    elif path=='/api/action':action(c,u,p)
    elif path=='/api/doctor/save':
     if u['role']!='doctor':raise PermissionError('Doctor account required.')
     profile={k:str(v)[:160] for k,v in (p.get('profile')or{}).items() if k in ['name','phone','email','specialty','city','upi']}
     if profile:
      c.execute('INSERT INTO user_profiles VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET data=excluded.data',(u['id'],dump(profile)))
      if profile.get('name','').strip():c.execute('UPDATE users SET name=? WHERE id=?',(profile['name'].strip(),u['id']));u['name']=profile['name'].strip()
     for rec in p.get('referrals',[]):
      if not rec.get('id') or c.execute('SELECT 1 FROM referrals WHERE id=?',(rec['id'],)).fetchone():continue
      h=rec.get('hospitalId')
      if h not in dict(HOSP):raise ValueError('Unknown hospital.')
      r={k:rec.get(k) for k in ['id','name','phone','age','gender','problem','note','source']};r.pop('age',None);r.update(referenceNumber=ident('REF'),note='',doctorId=u['id'],hospitalId=h,created=now(),status='submitted',confirmed=0,claimed=0,approved=0,paid=0,payments=[],claimId=None,timeline=[{'title':'Patient submitted','actor':'Doctor · '+u['name'],'at':now(),'note':'Hospital notification recorded by shared API. No clinical fee inferred.'}]);r['note']=r['referenceNumber'];c.execute('INSERT INTO referrals VALUES(?,?,?,?,?,?)',(r['id'],u['id'],h,r['status'],r['created'],dump(r)))
    elif path=='/api/documents':
     if u['role'] not in ['customer','hospital']:raise PermissionError('Customer or selected hospital upload required.')
     r,o=read_request(c,p.get('requestId'))
     if not (u['role']=='customer' and r['customer_id']==u['id'] or u['role']=='hospital' and r['hospital_id']==u['hospital_id']):raise PermissionError('Document access denied.')
     if u['role']=='hospital' and o['stage']!='completed':raise ValueError('Clinical reports can be published only after actual service completion.')
     try:content=base64.b64decode(p.get('base64',''),validate=True)
     except Exception:raise ValueError('Invalid file encoding.')
     mime=p.get('mime');allowed=['image/png','image/jpeg','image/webp','application/pdf']
     if mime not in allowed or not content or len(content)>10*1024*1024:raise ValueError('Supported photo/PDF up to 10 MB required.')
     valid_magic=(mime=='application/pdf' and content.startswith(b'%PDF-')) or (mime=='image/png' and content.startswith(b'\x89PNG\r\n\x1a\n')) or (mime=='image/jpeg' and content.startswith(b'\xff\xd8\xff')) or (mime=='image/webp' and content.startswith(b'RIFF') and content[8:12]==b'WEBP')
     if not valid_magic:raise ValueError('File content does not match its photo/PDF type.')
     did=ident('DOCFILE');filename=str(p.get('filename','document'))[:180];c.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?)',(did,r['id'],u['id'],filename,mime,content,now()))
     meta={'documentId':did,'name':filename,'type':mime,'size':len(content),'createdAt':now(),'issuer':u['name']}
     if u['role']=='hospital':
      kind=p.get('kind','report')
      if kind not in ['report','prescription','discharge']:raise ValueError('Choose a report, prescription or discharge summary.')
      meta['kind']=kind;o.setdefault('clinicalRecords',[]).append(meta);emit(c,u,o,'Hospital published '+kind+': '+filename)
     else:o['rx']=meta
     put_request(c,o,r['customer_id'])
    else:return self.respond(404,{'error':'Unknown API route.'})
    c.commit();return self.respond(200,state(c,u))
  except PermissionError as e:self.respond(403,{'error':str(e)})
  except (ValueError,TypeError,KeyError,json.JSONDecodeError) as e:self.respond(400,{'error':str(e)})
  except sqlite3.IntegrityError:self.respond(409,{'error':'Duplicate operation or state changed. Refresh and try again.'})
  except Exception as e:
   print('API error:',type(e).__name__,str(e));self.respond(500,{'error':'Server could not finish this action.'})
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--host',default='127.0.0.1');parser.add_argument('--port',type=int,default=8765);parser.add_argument('--open',action='store_true');args=parser.parse_args();initialise();url=f'http://localhost:{args.port}'
 print('HealthBasket Four Apps — one SQLite database:',DB);print('\n'.join(url+'/'+r+'/' for r in ['customer','doctor','hospital','driver']));print('DEMO ONLY: OTP/password 1234; no real payments/WhatsApp. Ctrl+C to stop.')
 try:httpd=ThreadingHTTPServer((args.host,args.port),Handler)
 except OSError:raise SystemExit('Port is already in use. Stop the previous preview server or choose another --port.')
 if args.open:threading.Timer(.7,lambda:webbrowser.open(url+'/hospital/')).start()
 try:httpd.serve_forever()
 except KeyboardInterrupt:print('Server stopped. Shared database is preserved.')
 finally:httpd.server_close()
