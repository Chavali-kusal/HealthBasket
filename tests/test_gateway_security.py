import sys,hashlib,hmac,base64
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from gateway_security import verify_razorpay,verify_cashfree
body=b'{"payment":{"amount":59900,"status":"captured"}}';secret='synthetic-test-secret';timestamp='1720000000123'
r=hmac.new(secret.encode(),body,hashlib.sha256).hexdigest();c=base64.b64encode(hmac.new(secret.encode(),timestamp.encode()+body,hashlib.sha256).digest()).decode()
assert verify_razorpay(body,r,secret) and verify_cashfree(body,c,timestamp,secret)
for altered in [body+b' ',body.replace(b'59900',b'10000')]:assert not verify_razorpay(altered,r,secret) and not verify_cashfree(altered,c,timestamp,secret)
assert not verify_razorpay(body,r,'') and not verify_cashfree(body,c,'',secret)
assert not verify_cashfree(body,c,'1720000000124',secret)
print('PASS synthetic Razorpay/Cashfree raw-body signatures; tamper/wrong timestamp/missing-secret rejection. No live gateway used.')
