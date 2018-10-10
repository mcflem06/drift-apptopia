
## Admittedly, I built this quick and dirty over the weekend. Probably a few modules that don't need to be imported.
from time import time
from flask import Flask, request, redirect, session, url_for, make_response, Response, render_template, send_file, send_from_directory
from flask.json import jsonify
import requests
import json as js
from bson.json_util import loads, dumps
import os
from flask_sslify import SSLify
from flask_cors import CORS, cross_origin
import pandas as pd
from buckets import Buckets
from pandas.io.json import json_normalize

## Declare globals / keys
## Eventual plans to push this through redis / a worker. Right now it all runs on the web-server dyno
q = Queue(connection=r)
app = Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
sslify = SSLify(app)

#Drift Key
driftToken = "YOUR KEY HERE"

#Initialize apptopia client / secret. Use server variables if possible
APPTOPIA_CLIENT_ID = 'YOUR APPTOPIA CLIENT HERE'
APPTOPIA_SECRET_KEY = 'YOUR APPTOPIA KEY HERE'
APPTOPIA_TOKEN_REQUEST = requests.post('https://integrations.apptopia.com/api/login', params={'client': APPTOPIA_CLIENT_ID, 'secret': APPTOPIA_SECRET_KEY}, headers={'Content-Type': 'application/x-www-form-urlencoded'}).json()
APPTOPIA_TOKEN = APPTOPIA_TOKEN_REQUEST['token']

@app.route("/")
def index():
    """"""
    return """
    <h1>This page has no content.</h1>
    
    """ 

##listen for drift events
@cross_origin()
@app.route("/drift-event", methods=["POST","GET"])
def showEvent():
    
    data = js.loads(str(request.data))
    
    #App triggers off of a playbook goal.

    if data['type'] == "playbook_goal_met" and data['data']['goalId'] == "d93891e1-0d53-4166-be23-a8a4c1610cb0": 
        #Get conversation id

        conversationId = data['data']['conversationId']

        #Get app name + store from conversation
        appName,store = getAppName(data['data']['conversationId'])

        #Get a list of app ids from apptopia
        appIds = lookupAppId(appName,store)

        #Get a list of app names corresponding to those ids
        appNames = lookupAppNames(appIds, store)

        #get the app the user selected
        selection = getSelection(appNames, conversationId)

        #get a 30 days performance snapshot on that app
        appData = app_data(selection, store)

        #send the data back to Drift
        sendData(appData, conversationId)
    
    driftResponse = {'status':'200'}

    return jsonify(driftResponse)


## This parse through the conversation to grab the app name entered and the store selected.
def getAppName(conversationId):

    url = "https://driftapi.com/conversations/" + str(conversationId) + "/messages"
    authHeader = "Bearer " + driftToken
    headers = {'authorization': authHeader}
    tempList = []
    tempDict = {}

    r = requests.get(url = url, headers=headers)
    messages = r.json()
    messages = messages['data']['messages']
    appIndex = None
    store = None

    for index, m in enumerate(messages):
        try:
            if m['body'] == '<p>What app store?</p>':

                ## The message preceding 'what app store?' is the name of the app.
                appIndex = int(index) - 1

            if m['body'] == 'iTunes Connect' and m['author']['bot'] == False:
                store = "itunes_connect"

            elif m['body'] == 'Google Play' and m['author']['bot'] == False:
                store = "google_play"

        except Exception as e:
            print 'error ' + str(e)
            pass

    print 'exiting message loop'
    
    appName = messages[appIndex]
    
    return appName['body'], store

def lookupAppId(textAppName, textStore):
    
    #pulls a list of app ids that match against what the user entered.

    payload = js.dumps([["match", textAppName],
                              ["filter", ["=", "store_type", textStore]]
                              ])
    request = requests.post("https://integrations.apptopia.com/api/app_search?limit=10", data=payload, headers={'Authorization': APPTOPIA_TOKEN, 'Content-Type': "application/json"}).json()

    returnPayload = None

    try:
        if request['app_ids'][textStore]:
            returnPayload = request['app_ids'][textStore]
    except:
        pass

    return returnPayload

def lookupAppNames(ids, textStore):
    #pull a list of app names for the corresponding ids
    appDict = dict()
    for id in ids:
        request = requests.get("https://integrations.apptopia.com/api/" + textStore +"/app?id=" + str(id),
                                headers={'Authorization': APPTOPIA_TOKEN}).json()
        if 'name' in request[0]:
            appDict[id] = request[0]['name']
        else:
            appDict[id] = "Name not found"

    return appDict

#Had to do a bit of a hack to get around missing button_action events (wasn't receiving any). 
def getSelection(appNames, conversationId):
    #drift.conversations.create_message( conversation_id=conversationId, org_id=94716, type='chat', body='hi')
    
    url = "https://driftapi.com/conversations/" + str(conversationId) + "/messages"
    authHeader = "Bearer " + driftToken
    headers = {'authorization': authHeader, 'Content-Type': 'application/json'}
    data = {'type':'chat', 'body':'<p>We found a few matches, which one is right?</p>', }
    dataFinal = js.dumps(data)

    r = requests.post(url = url, headers=headers, data = dataFinal)

    tempButton = {}
    buttonList = []

    #Iterate through dictionary of app names + ids (key / value), create button structure, and append to list.
    for key,value in appNames.iteritems():
        tempButton['label'] = value
        tempButton['value'] = value
        buttonList.append(tempButton)
        tempButton = {}

    data = {'type':'chat', 'buttons':buttonList }
    dataFinal = js.dumps(data)
    r = requests.post(url = url, headers=headers, data = dataFinal)

    ##This gets a little hacky. Since I am not receiving button_action events for the buttons I inserted, I need to listen on this conversation. 
    ## I include a brief delay, check the conversation, and then check for up to 20 seconds.  Again, not great error handling.
    time.sleep(2)

    r = requests.get(url = url, headers=headers)
    messages = r.json()
    messages = messages['data']['messages']

    #As I'm checking the conversation, I want to break out of the loop as soon as I have a message that matches against the list of apps I generated. 
    #I'm specifically looking for messages that don't contain buttons, and the comparing it against the dictionary.

    bodyPresent = False  
    buttonsPresent = False
    counter = 0

    while buttonsPresent == False and bodyPresent == False and counter < 21:

        counter = counter + 1
        r = requests.get(url = url, headers=headers)
        messages = r.json()
        messages = messages['data']['messages']
        lastMessage = messages[-1]
        time.sleep(1)

        try:
            if lastMessage['body'] in appNames.values():
                bodyPresent = True
                break
        except Exception as e:
            print 'Error: ' + str(e)
            pass

        try:
            if lastMessage['buttons']:
                buttonsPresent = False
                
        except Exception as e:
            print 'Error: ' + str(e)
            buttonsPresent = True
            pass

    #iterate through all app names + ids, matching against the body of the last message.
    key = [key for key, value in appNames.items() if value == lastMessage['body']][0]

    print 'selected app id is.... ' + str(key)
    return key

def app_data(selection, store):
    #For Apptopia, we need to pass a country code to pull data, I'm manually specifiying it here, but we could also ask for it in Drift chat. 

    country = "WW"
    payload = {}

    #Get estimates by app id
    estimatesRequest = requests.get(
        "https://integrations.apptopia.com/api/" + str(store) + "/app_estimates?id=" + str(
            selection) + "&date_from=" + str(monthAgo) + "&date_to=" + str(yesterday) + "&country_iso=" + str(country),
        headers={'Authorization': APPTOPIA_TOKEN}).json()

    appInfoRequest = requests.get(
        "https://integrations.apptopia.com/api/" + str(store) + "/app?id=" + str(
            selection),
        headers={'Authorization': APPTOPIA_TOKEN}).json()
 
    #Proceed only if data is returned. Error handling for nulls / undefined is very minimal at this point.
    
    if len(estimatesRequest) > 0 and len(appInfoRequest) > 0 and 'name' in appInfoRequest[0]:
        dataFrame = json_normalize(estimatesRequest)
        payload['dau'] = getRange(dataFrame['dau'].mean())
        payload['downloads'] = getRange(dataFrame['downloads'].sum())
        payload['mau'] = getRange(dataFrame['mau'].mean())
        payload['total_revenue'] = getRange(dataFrame['total_revenue'].sum())
        payload['appName'] = appInfoRequest[0]['name']
        payload['publisher'] = appInfoRequest[0]['publisher_name']
        payload['detailLink'] = "https://apptopia.com/apps/" + str(store) + "/" + str(selection)

    return payload

def sendData (appData, conversationId):

    ## Sends data back into the Drift
    url = "https://driftapi.com/conversations/" + str(conversationId) + "/messages"
    authHeader = "Bearer " + driftToken
    headers = {'authorization': authHeader, 'Content-Type': 'application/json'}
    data = {'type':'chat', 'body':"<p><strong>Here's a quick look at our data:<strong></p>", }
    dataFinal = js.dumps(data)

    r = requests.post(url = url, headers=headers, data = dataFinal)

    data = {'type':'chat', 'body':"<p><i>In the last 30 days...</i>" }
    dataFinal = js.dumps(data)
    r = requests.post(url = url, headers=headers, data = dataFinal)
    data = {'type':'chat', 'body':"""<p><strong>Publisher: </strong> """ + appData['publisher'] +  """</p><p><strong>Total Revenue: </strong> """ + appData['total_revenue'] + """</p><p><strong>Downloads: </strong> """ + appData['downloads'] + """</p><p><strong>DAUs: </strong> """ + appData['dau'] + """</p><p><strong>MAUs: </strong> """ + appData['mau'] + """</p><p><a href='""" + appData['detailLink'] + """'>Get More Details &raquo;</a></p>""" }
    dataFinal = js.dumps(data)
    r = requests.post(url = url, headers=headers, data = dataFinal)

    return True

## We convert all of our precise data points to ranges. Don't want to give away everything for free.
def getRange(number):
    if number < 5000:
        return Buckets.UNDER_5K.value
    elif 5000 <= number < 10000:
        return Buckets.FROM_5K_TO_10K.value
    elif 10000 <= number < 50000:
        return Buckets.FROM_10K_TO_50K.value
    elif 50000 <= number < 100000:
        return Buckets.FROM_50K_TO_100K.value
    elif 100000 <= number < 500000:
        return Buckets.FROM_100K_TO_500K.value
    elif 500000 <= number < 1000000:
        return Buckets.FROM_500K_TO_1M.value
    elif 1000000 <= number < 5000000:
        return Buckets.FROM_1M_TO_5M.value
    elif 5000000 <= number < 10000000:
        return Buckets.FROM_5M_TO_10M.value
    elif 10000000 <= number < 50000000:
        return Buckets.FROM_10M_TO_50M.value
    elif 50000000 <= number < 100000000:
        return Buckets.FROM_50M_TO_100M.value
    elif 100000000 <= number < 500000000:
        return Buckets.FROM_100M_TO_500M.value
    elif 500000000 <= number < 1000000000:
        return Buckets.FROM_500M_TO_1B.value
    else:
        return Buckets.OVER_1B.value

# Converts estimates to number suffixes. E.g. 1.4M
def getNumberSuffixFormat(num):
    num = float('{:.3g}'.format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    while magnitude > 4:
        magnitude -= 1
        num *= 1000.0
    return '{}{}'.format('{:f}'.format(num).rstrip('0').rstrip('.'), ['', 'K', 'M', 'B', 'T'][magnitude])


if __name__ == "__main__":
    import os
    print 'starting....'
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0',debug=False, port=port)


