# Usefull scripts for Zimbra

## compare_users.py
### Description:
 - Compare current Zimbra users with LDAP(AD) group
 - Add users to Zimbra if they exist in LDAP
 - Disable and Remove users from Zimbra if they missing in LDAP

### Requires
 - python-ldap

### Settings
For settings see same section inside script

### Changelog
**19.05.2016**  
Add new features:
  - Mailboxes will be disabled and deleted after N days
