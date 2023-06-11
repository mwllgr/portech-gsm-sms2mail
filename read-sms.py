import sys, base64, re, pprint
import telnetlib

# PDU decoding
from io import StringIO
from smspdudecoder.fields import SMSDeliver

# SMTP
from email.utils import formataddr, formatdate, make_msgid
from email.message import EmailMessage
import smtplib

HOST = "192.168.0.10"
PORT = 23
USERNAME = "AzureDiamond"
PASSWORD = "******"

MAIL_HOST = "example.com"
MAIL_TO = "user@example.com"
MAIL_FROM = "sms@example.com"
MAIL_FROM_NAME = "Example-SMS"
MAIL_SUBJ_PREFIX = "[Example-SMS] "
MAIL_PASSWORD = "hunter2"
MAIL_MSGID_DOMAIN = "example.com"
MAIL_MSGID_IDSTRING = "Example-SMS"

# SIM card phone number assignment (module1, module2)
MODULE_NUMBERS = ["+15558675309", "+4915228895456"]

# Group mappings: 1 -> Message ID, 2 -> Type, 3 -> PDU payload length
MESSAGE_START_REGEX = r'^\+CMGL: (\d*),(.*),.*,(\d*)$'

telnet = telnetlib.Telnet(HOST, PORT)

def login(username, password):
        # Send username
        telnet.read_until(b"username: ", 3)
        telnet.write(bytes(username, encoding='ascii') + b"\r")
        print("[LOGIN] Sent username.")

        # Send password
        telnet.read_until(b"password: ", 3)
        telnet.write(bytes(password, encoding='ascii') + b'\r')
        print("[LOGIN] Sent password.")
        telnet.read_until(b"]", 3)

        print("[LOGIN] Success!")

def read_sms_from_module(index):
        # Lock module for reading
        telnet.write(bytes("module" + str(index), encoding='ascii') + b"\r")
        telnet.read_until(b"to release module " + bytes(str(index), encoding='ascii') + b".")
        print("[MODULE] Got module " + str(index) + "!")

        # Set modem to text mode
        print("[MODULE] Setting mode to PDU.")
        telnet.write(b"AT+CMGF=0" + b"\r")
        telnet.read_until(b"0")

        # Read all unread messages
        print("[MESSAGES] Reading stored messages...")
        # 0 -> unread, 1 -> read, 2 -> unsent, 3 -> sent, 4 -> all
        telnet.write(b'AT+CMGL=0' + b"\r")
        messages_raw = telnet.read_until(b"\n0\r")
        messages = messages_raw.decode('utf-8')
        print("[MESSAGES] Read success.")

        # Parse messages
        parsed = parse_messages(messages, index)
        print("[MESSAGES] Parsed " + str(len(parsed)) + " new messages.")
        # pprint.pprint(parsed)

        # Send CTRL+X to release module
        telnet.write(b"\030" + b"\r")
        telnet.read_until(b"]", 3)
        print("[MODULE] Released module " + str(index) + "!")

        return parsed

def parse_messages(messages, module):
        parsed = []
        messages = messages.splitlines()[1:-1]

        for message in messages:
                message_header = re.search(MESSAGE_START_REGEX, message)
                if message_header:
                        parsed.append({
                                "id": int(message_header.group(1)),
                                "module": int(module),
                                "status": int(message_header.group(2)),
                                "length": int(message_header.group(3)),
                                "payload": ""
                        })
                else:
                        if parsed[len(parsed) - 1]['payload'] != "":
                                parsed[len(parsed) - 1]['payload'] += '\r'

                        parsed[len(parsed) - 1]['payload'] += message
                        decoded = SMSDeliver.decode(StringIO(message))
                        parsed[len(parsed) - 1]['decoded'] = decoded

                        # Add plus to number if it's an international phone no.
                        sender_prefix = ""
                        if decoded["sender"]["toa"]["ton"] == "international":
                                sender_prefix = "+"

                        parsed[len(parsed) - 1]['sender'] = sender_prefix + decoded["sender"]["number"]

        return parsed

def send_email(message):
        decoded = message["decoded"]

        email = EmailMessage()
        email["Message-ID"] = make_msgid(MAIL_MSGID_IDSTRING, MAIL_MSGID_DOMAIN)
        email["Subject"] = "{0}Neue Nachricht von {1} für {2}".format(MAIL_SUBJ_PREFIX, message["sender"], MODULE_NUMBERS[message["module"] - 1])

        email["From"] = formataddr((MAIL_FROM_NAME, MAIL_FROM))
        email["To"] = MAIL_TO
        email["Date"] = formatdate(localtime=True)

        # Include base64 version of content in mail headers
        email["X-SMS-Recipient"] = message["sender"]
        email["X-SMS-Content"] = base64.b64encode(bytes(decoded["user_data"]["data"], 'utf-8')).decode('utf-8')

        body_header = "<style>table,td,th{border:1px solid #000;border-collapse:collapse;text-align:left;padding:3px}</style>"
        body_header += "<h1>Neue SMS-Nachricht</h1>"

        body_content = "<blockquote>{0}</blockquote>".format(nl2br(decoded["user_data"]["data"]))
        body_content += "<p><b>Absenderkennung:</b> {0}<br>".format(message["sender"])
        body_content += "<b>Zeitstempel:</b> {0}<br>".format(decoded["scts"])
        body_content += "<b>SMS-Zentrale:</b> {0}</p>".format(decoded["smsc"]["number"])

        body_footer = "<hr><small style='font-weight: bold'>Technische Gesamtzusammenfassung:</small><pre style='font-size: 7pt'>" + pprint.pformat(message) + "</pre>"
        email.set_content(body_header + body_content + body_footer, subtype="html")

        smtp = smtplib.SMTP_SSL(MAIL_HOST)
        smtp.login(MAIL_FROM, MAIL_PASSWORD)
        smtp.sendmail(MAIL_FROM, MAIL_TO, email.as_string())
        smtp.quit()
        print("[EMAIL] Sent e-mail for message no. {0} from module {1}".format(message["id"], message["module"]))

def logout():
        # Send logout command and wait for exit
        telnet.write(b"logout" + b"\r")
        telnet.read_until(b"exit...")

        print("[LOGOUT] Successful.")

def nl2br(s):
    return '<br />\n'.join(s.split('\n'))

login(USERNAME, PASSWORD)
sms_module1 = read_sms_from_module(1)
sms_module2 = read_sms_from_module(2)
sms_combined = sms_module1 + sms_module2

if len(sms_combined) > 0:
        for message in sms_combined:
                send_email(message)

logout()
