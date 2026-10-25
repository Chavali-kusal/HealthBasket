"""Reusable verification helpers. No gateway checkout/webhook routes are live in the demo."""
import base64,hashlib,hmac

def verify_razorpay(raw_body,signature,webhook_secret):
 if not isinstance(webhook_secret,str) or not webhook_secret or not isinstance(raw_body,bytes) or not isinstance(signature,str) or not signature.isascii():return False
 expected=hmac.new(webhook_secret.encode(),raw_body,hashlib.sha256).hexdigest()
 return hmac.compare_digest(expected,signature)

def verify_cashfree(raw_body,signature,timestamp,merchant_secret):
 if not isinstance(merchant_secret,str) or not merchant_secret or not isinstance(timestamp,str) or not timestamp or not isinstance(raw_body,bytes) or not isinstance(signature,str) or not signature.isascii():return False
 expected=base64.b64encode(hmac.new(merchant_secret.encode(),timestamp.encode()+raw_body,hashlib.sha256).digest()).decode()
 return hmac.compare_digest(expected,signature)
