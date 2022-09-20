import os
import requests
import json
import zipfile
import io
import glob
import re
from datetime import datetime

def main():

    GITHUB_REF=os.environ["GITHUB_REF"]
    GITHUB_REPOSITORY=os.environ["GITHUB_REPOSITORY"]
    GITHUB_RUN_ID=os.environ["GITHUB_RUN_ID"]
    GITHUB_API_URL=os.environ["GITHUB_API_URL"]
    GITHUB_WORKFLOWID=os.environ["INPUT_WORKFLOWID"]
    GITHUB_TOKEN = os.environ.get("INPUT_GITHUB-TOKEN")

    # SPLUNK_HEC_URL=os.environ["INPUT_SPLUNK-URL"]+"services/collector/event"
    SPLUNK_HEC_URL = "https://prd-p-rrduq.splunkcloud.com:8088/services/collector/event"
    SPLUNK_HEC_TOKEN=os.environ["INPUT_HEC-TOKEN"]
    SPLUNK_SOURCE=os.environ["INPUT_SOURCE"]
    SPLUNK_SOURCETYPE=os.environ["INPUT_SOURCETYPE"]
    print('GITHUB_REF', GITHUB_REF)
    print('GITHUB_RUN_ID', GITHUB_RUN_ID)
    print('GITHUB_WORKFLOWID', GITHUB_WORKFLOWID)
    print('SPLUNK_SOURCE', SPLUNK_SOURCE)
    print('SPLUNK_SOURCETYPE', SPLUNK_SOURCETYPE)
    
    batch = count = 0
    eventBatch = ""
    headers = {"Authorization": "Splunk "+SPLUNK_HEC_TOKEN}
    host=os.uname()[1]

    summary_url = "{url}/repos/{repo}/actions/runs/{run_id}".format(url=GITHUB_API_URL,repo=GITHUB_REPOSITORY,run_id=GITHUB_WORKFLOWID)
    print(summary_url)

    try:
        x = requests.get(summary_url, stream=True, auth=('token',GITHUB_TOKEN))
        x.raise_for_status()
    except requests.exceptions.HTTPError as errh:
        output = "GITHUB API Http Error:" + str(errh)
        print(f"Error: {output}")
        print(f"::set-output name=result::{output}")
        return x.status_code
    except requests.exceptions.ConnectionError as errc:
        output = "GITHUB API Error Connecting:" + str(errc)
        print(f"Error: {output}")
        print(f"::set-output name=result::{output}")
        return x.status_code
    except requests.exceptions.Timeout as errt:
        output = "Timeout Error:" + str(errt)
        print(f"Error: {output}")
        print(f"::set-output name=result::{output}")
        return x.status_code
    except requests.exceptions.RequestException as err:
        output = "GITHUB API Non catched error conecting:" + str(err)
        print(f"Error: {output}")
        print(f"::set-output name=result::{output}")
        return x.status_code
    except Exception as e:
        print("Internal error", e)
        return x.status_code

    summary = x.json()

    summary.pop('repository')

    summary["repository"]=summary["head_repository"]["name"]
    summary["repository_full"]=summary["head_repository"]["full_name"]

    summary.pop('head_repository')

    utc_time = datetime.strptime(summary["updated_at"], "%Y-%m-%dT%H:%M:%SZ")
    epoch_time = (utc_time - datetime(1970, 1, 1)).total_seconds()

    event={'event':json.dumps(summary),'sourcetype':SPLUNK_SOURCETYPE,'source':'workflow_summary','host':host,'time':epoch_time}
    event=json.dumps(event)

    print(SPLUNK_HEC_URL)

    x=requests.post(SPLUNK_HEC_URL, data=event, headers=headers)


    url = "{url}/repos/{repo}/actions/runs/{run_id}/logs".format(url=GITHUB_API_URL,repo=GITHUB_REPOSITORY,run_id=GITHUB_WORKFLOWID)
    print(url)

    try:
        x = requests.get(url, stream=True, auth=('token',GITHUB_TOKEN))

    except requests.exceptions.HTTPError as errh:
        output = "GITHUB API Http Error:" + str(errh)
        print(f"Error: {output}")
        print(f"::set-output name=result::{output}")
        return
    except requests.exceptions.ConnectionError as errc:
        output = "GITHUB API Error Connecting:" + str(errc)
        print(f"Error: {output}")
        print(f"::set-output name=result::{output}")
        return
    except requests.exceptions.Timeout as errt:
        output = "Timeout Error:" + str(errt)
        print(f"Error: {output}")
        print(f"::set-output name=result::{output}")
        return
    except requests.exceptions.RequestException as err:
        output = "GITHUB API Non catched error conecting:" + str(err)
        print(f"Error: {output}")
        print(f"::set-output name=result::{output}")
        return

    content = io.BytesIO(x.content)
    try: 
        isJson = json.loads(x.content)
        print()
        raise Exception('content returns json', str(isJson))
    except:
        print('good to zip')

    z = zipfile.ZipFile(content)
    z.extractall('/app')

    timestamp = batch = count = 0

    for name in glob.glob('/app/*.txt'):
        logfile = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), name.replace('./','')),'r')
        Lines = logfile.readlines()
        for line in Lines:

            if line:
                count+=1
                if timestamp:
                    t2=timestamp
                timestamp = re.search("\d{4}-\d{2}-\d{2}T\d+:\d+:\d+.\d+Z",line.strip())

                if timestamp:
                    timestamp = re.sub("\dZ","",timestamp.group())
                    timestamp = datetime.strptime(timestamp,"%Y-%m-%dT%H:%M:%S.%f")
                    timestamp = (timestamp - datetime(1970,1,1)).total_seconds()
                else:
                    timestamp=t2

                x = re.sub("\d{4}-\d{2}-\d{2}T\d+:\d+:\d+.\d+Z","",line.strip())
                x=x.strip()
                job_name=re.search("\/\d+\_(?P<job>.*)\.txt",name)
                job_name=job_name.group('job')
                fields = {'lineNumber':count,'workflowID':GITHUB_WORKFLOWID,'job':job_name}
                if x:
                    print('batch', batch)
                    batch+=1
                    event={'event':x,'sourcetype':SPLUNK_SOURCETYPE,'source':SPLUNK_SOURCE,'host':host,'time':timestamp,'fields':fields}
                    eventBatch=eventBatch+json.dumps(event)
                else:
                    print("skipped line "+str(count))

                if batch>=500:
                    # batch=0
                    # print(eventBatch)
                    # x=requests.post(SPLUNK_HEC_URL, data=eventBatch, headers=headers)
                    # eventBatch=""
                    break
                    

    x=requests.post(SPLUNK_HEC_URL, data=eventBatch, headers=headers)

    try:
        print(x.content)
        print(json.dumps(x))
    except:
        print('can\'t parse')
    
if __name__ == '__main__':
    main()
