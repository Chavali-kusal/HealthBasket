"""Atomic demo-only closed-loop discount ledger; callers hold the DB write transaction."""
import json

def spend(c,customer_id,maximum):
 remaining=round(float(maximum),2);used=0
 for row in c.execute("SELECT * FROM ledger_records WHERE customer_id=? AND kind='discountCredits' ORDER BY created_at,id",(customer_id,)).fetchall():
  credit=json.loads(row['data']);available=round(float(credit.get('remaining',0)),2)
  take=min(available,remaining)
  if take<=0:continue
  credit['remaining']=round(available-take,2);credit['status']='Used' if credit['remaining']==0 else 'Available'
  c.execute('UPDATE ledger_records SET data=? WHERE id=?',(json.dumps(credit),row['id']));remaining=round(remaining-take,2);used=round(used+take,2)
  if remaining==0:break
 return used
