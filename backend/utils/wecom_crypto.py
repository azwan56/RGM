import base64
import struct
import hashlib
import string
import random
from Crypto.Cipher import AES

class WXBizMsgCrypt:
    def __init__(self, token, encoding_aes_key, corp_id):
        self.token = token
        self.corp_id = corp_id
        self.key = base64.b64decode(encoding_aes_key + "=")

    def verify_signature(self, msg_signature, timestamp, nonce, echostr):
        sort_list = [self.token, timestamp, nonce, echostr]
        sort_list.sort()
        sha = hashlib.sha1()
        sha.update("".join(sort_list).encode('utf-8'))
        return sha.hexdigest() == msg_signature

    def decrypt(self, text):
        """Decrypts AES-CBC encrypted text, removes PKCS#7 padding and extracts msg."""
        cryptor = AES.new(self.key, AES.MODE_CBC, self.key[:16])
        plain_text = cryptor.decrypt(base64.b64decode(text))
        
        # Unpad PKCS#7
        pad = plain_text[-1]
        plain_text = plain_text[:-pad]
        
        # Extract msg
        # Format: 16 bytes random | 4 bytes msg_len | msg | corp_id
        content = plain_text[16:]
        xml_len = struct.unpack("!I", content[:4])[0]
        xml_content = content[4:4 + xml_len].decode('utf-8')
        from_corpid = content[4 + xml_len:].decode('utf-8')
        
        if from_corpid != self.corp_id:
            raise ValueError("CorpID mismatch during decryption")
            
        return xml_content

    def encrypt(self, text):
        """Encrypts a string (e.g. reply xml) and wraps it with signature."""
        random_str = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(16))
        text_bytes = text.encode('utf-8')
        corp_bytes = self.corp_id.encode('utf-8')
        msg_len = struct.pack("!I", len(text_bytes))
        
        unencrypted = random_str.encode('utf-8') + msg_len + text_bytes + corp_bytes
        
        # Pad PKCS#7
        amount_to_pad = 32 - (len(unencrypted) % 32)
        if amount_to_pad == 0:
            amount_to_pad = 32
        pad_chr = bytes([amount_to_pad])
        unencrypted += pad_chr * amount_to_pad
        
        cryptor = AES.new(self.key, AES.MODE_CBC, self.key[:16])
        ciphertext = cryptor.encrypt(unencrypted)
        return base64.b64encode(ciphertext).decode('utf-8')
        
    def verify_url(self, msg_signature, timestamp, nonce, echostr):
        if not self.verify_signature(msg_signature, timestamp, nonce, echostr):
            raise ValueError("Signature verification failed")
        return self.decrypt(echostr)
        
    def decrypt_msg(self, msg_signature, timestamp, nonce, encrypt_msg):
        if not self.verify_signature(msg_signature, timestamp, nonce, encrypt_msg):
            raise ValueError("Signature verification failed")
        return self.decrypt(encrypt_msg)
        
    def generate_reply_xml(self, reply_msg, timestamp, nonce):
        encrypt_msg = self.encrypt(reply_msg)
        sort_list = [self.token, timestamp, nonce, encrypt_msg]
        sort_list.sort()
        sha = hashlib.sha1()
        sha.update("".join(sort_list).encode('utf-8'))
        signature = sha.hexdigest()
        
        return f"""<xml>
<Encrypt><![CDATA[{encrypt_msg}]]></Encrypt>
<MsgSignature><![CDATA[{signature}]]></MsgSignature>
<TimeStamp>{timestamp}</TimeStamp>
<Nonce><![CDATA[{nonce}]]></Nonce>
</xml>"""
