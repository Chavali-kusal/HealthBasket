"""Trusted local demo finance operator. Not an internet-facing admin API; no money transfers."""
import argparse,json,secrets
import server as s

def operate(command,request_id,reference):
 if not reference.strip():raise ValueError('Independent verification/reference is required.')
 s.initialise()
 with s.LOCK,s.connect() as c:
  c.execute('BEGIN IMMEDIATE');r,o=s.read_request(c,request_id)
  if o.get('cancellationStatus')!='Approved' or o.get('refundStatus')!='Claimed · company finance review':raise ValueError('Customer must claim an approved cancellation first; each claim settles once.')
  method=o.get('refundMethod');amount=o.get('refundAmount',0)
  if command=='issue-credit':
   if method!='discount':raise ValueError('Customer did not consent to discount credit.')
   credit={'id':'CREDIT-'+o['refundId'],'sourceId':request_id,'amount':amount,'remaining':amount,'status':'Available','createdAt':s.now(),'consentAt':o['refundClaimConsentAt']}
   c.execute('INSERT INTO ledger_records VALUES(?,?,?,?,?,?)',(credit['id'],r['customer_id'],r['hospital_id'],'discountCredits',s.now(),s.dump(credit)))
   o.update(refundStatus='Discount credit issued · simulated',refundSettledAt=s.now(),refundFinanceRef=reference)
  elif command=='queue-refund':
   if method not in ['original','bank']:raise ValueError('Claim must use original source or verified bank route.')
   o.update(refundStatus='Queued · demo finance; no bank refund',refundFinanceRef=reference,refundFinanceReviewedAt=s.now())
  else:raise ValueError('Unknown command.')
  # A separate non-login company actor produces an auditable event.
  actor='COMPANY-FINANCE';c.execute('INSERT OR IGNORE INTO users VALUES(?,?,?,?,?,?)',(actor,'local-finance-operator','company','Company finance · local demo',None,s.hashed(secrets.token_urlsafe(32))))
  s.emit(c,{'id':actor,'role':'company','name':'Finance operator'},o,o['refundStatus']+' · independent reference '+reference[:100]);s.put_request(c,o,r['customer_id']);c.commit()
 return o['refundStatus']
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['list','issue-credit','queue-refund']);p.add_argument('request_id',nargs='?');p.add_argument('--reference',default='');a=p.parse_args()
 try:
  if a.command=='list':
   s.initialise()
   with s.connect() as c:
    for row in c.execute('SELECT id,hospital_id,data FROM requests ORDER BY created_at'):
     o=json.loads(row['data'])
     if o.get('cancellationStatus') or o.get('refundStatus'):print(json.dumps({k:o.get(k) for k in ['id','hospitalId','cancellationStatus','refundId','refundStatus','refundAmount','refundMethod']},ensure_ascii=False))
  else:print(operate(a.command,a.request_id,a.reference))
 except ValueError as e:raise SystemExit(str(e))
