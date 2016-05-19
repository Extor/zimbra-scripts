#!/usr/bin/python
# coding=UTF-8
'''
The script will compare the users from LDAP group list with the members of local Zimbra users.
If the user is not in LDAP and present in the Zimbra, it will remove it from Zimbra.
Tested on Zimbra FOSS 8.
'''

# Config section
defaultDomain = "@domain.local"
ldapserver = "10.29.1.1"
ldapport = "389"
ldapbinduser = "svc-zimbra"+defaultDomain
ldappassword = "P@ssw0rd!"
ldapDefaultScope = "OU=Employees,OU=myOrg,DC=domain,DC=local"
ldapSearchGroup = "CN=g_zimbra,OU=Groups,OU=myOrg,DC=domain,DC=local"
ldapFields = ['sAMAccountName','sn','title','givenName','displayName','company']
reExcludeUsers = "^spam.*|^ham.*|^galsync.*|^admin$|^virus-quarantine.*"
emailExpireDay = 365
pathtozmprov="/opt/zimbra/bin/zmprov"
logfile='/var/log/zimbra-compare.log'
pidfile='/var/run/zimbra-compare.pid'
# end Config section

import ldap, os, string, random, time, sys, datetime, subprocess, re

def getLdapSearchResult(ldapconnect,scope,fields):
    res = ldapconnect.search_s(scope,ldap.SCOPE_SUBTREE,"(&(objectClass=user)(memberOf="+ldapSearchGroup+"))",fields)
    return res

def getADUsers(data):
    usersList = []
    for (dn, vals) in data:
        usersList.append(vals['sAMAccountName'][0].lower())
    return usersList

def filterADUsers(data,userList):
    filteredUsers = []
    for (dn, vals) in data:
        if vals['sAMAccountName'][0].lower() in userList:
            filteredUsers.append(vals)
    return filteredUsers

def getDetailedZimbraUsers(fFilter=['zimbraLastLogonTimestamp','zimbraAccountStatus']):
    userFieldsByKeys = {}
    users = subprocess.Popen([pathtozmprov,"-l","gaa","-v","-e"],stdout=subprocess.PIPE)
    for user in users.stdout.read().split("# name "):
        if user != "":
            userFields = user.split("\n")
            userFieldsByKeys[userFields[0][:userFields[0].find('@')]] = {}
            for uf in userFields:
                 if uf.split(": ")[0] in fFilter:
                     userFieldsByKeys[userFields[0][:userFields[0].find('@')]][uf.split(": ")[0]] = uf.split(": ")[1]
    return userFieldsByKeys

# get differents from to lists
def diffLists (list1,list2):
    output = []
    for i in list1:
        if i not in list2:
            output.append("+"+i)
    for i in list2:
        if i not in list1:
            output.append("-"+i)
    return output

# MAIN

pid = str(os.getpid())
log = open(logfile,'a')
if os.path.isfile(pidfile):
  log.write("%s already exists, exiting\n" % pidfile)
  sys.exit()

pf = open(pidfile, 'w')
pf.write(pid)
pf.close
l=ldap.initialize("ldap://"+ldapserver+":"+ldapport)
l.simple_bind_s(ldapbinduser,ldappassword)

result = getLdapSearchResult(l,ldapDefaultScope,ldapFields)
ADUsers = getADUsers(result)

zimbraUsers = getDetailedZimbraUsers()


needToAdd = []
needToClose = []
needToDel = []
for i in diffLists(ADUsers,zimbraUsers.keys()):
    action = i[:1]
    user = i[1:]
    if action == '+':
        needToAdd.append(user)
    elif action == "-":
        if not re.search(reExcludeUsers,user) and zimbraUsers[user]['zimbraAccountStatus'] != 'closed':
            needToClose.append(user)
    else:
        print "Error: first symbol username in diff result must be '+' or '-'"

presentTime = datetime.datetime.now()
for i in zimbraUsers:
        if "zimbraLastLogonTimestamp" not in zimbraUsers[i]:
            zimbraUsers[i]["zimbraLastLogonTimestamp"] = "19700101000000Z"
        userLastLogon = datetime.datetime.strptime(zimbraUsers[i]["zimbraLastLogonTimestamp"][:-1], "%Y%m%d%H%M%S")
        if presentTime > userLastLogon + datetime.timedelta(days=emailExpireDay) and zimbraUsers[i]["zimbraAccountStatus"] == "closed":
            needToDel.append(i)

# Add users
for user in filterADUsers(result,needToAdd):
    strFill = " "
    for f in ldapFields:
        if f in user:
            if f != "sAMAccountName":
                strFill += f+" '"+user[f][0].replace('"','')+"' "
    pwd = ''.join([random.choice(string.ascii_letters + string.digits) for n in xrange(32)])
    command = "export LC_ALL='ru_RU.UTF-8';zmprov ca "+user['sAMAccountName'][0].lower()+defaultDomain+" "+pwd+" "+strFill
    os.system("su - zimbra -c \""+command+"\"")
    log.write(time.strftime("%d.%m.%Y %H:%M:%S")+" Create user: "+user['sAMAccountName'][0].lower()+defaultDomain+"\n")

# Disable users
for user in needToClose:
    os.system("su - zimbra -c \"zmprov ma "+user+defaultDomain+" zimbraAccountStatus closed\"")
    log.write(time.strftime("%d.%m.%Y %H:%M:%S")+" Disable user: "+user+defaultDomain+"\n")

# Delete users
for user in needToDel:
    os.system("su - zimbra -c \"zmprov da "+user+defaultDomain+"\"")
    log.write(time.strftime("%d.%m.%Y %H:%M:%S")+" Delete user: "+user+defaultDomain+"\n")

log.close()
os.remove(pidfile)
