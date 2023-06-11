# SMS-to-mail for the Portech MV-37X GSM gateway
This simple script tries to load all unread SMS messages from the GSM gateway via Telnet and sends a mail for each unread message to a specified address.

## Configuration
Make sure to adjust the constants at the beginning of the Python file. This script - by default - checks both inserted SIM cards (they're called "modules" in the script) for new messages.

## Known working devices
- Portech MV-372 Dual-SIM GSM VoIP Gateway
