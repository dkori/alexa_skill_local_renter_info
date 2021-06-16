from bs4 import BeautifulSoup
import requests
import pandas as pd
import regex as re
import os
# create a directory to store results
try:
    os.mkdir('state_tenant_rights')
except:
    print('dir exists')
# read in the state/abbrevi crosswalk
state_frame = pd.read_csv('state_abbrev_crosswalk.csv')
# remove D.C. since its not supported
state_frame = state_frame[~state_frame['State'].str.contains('District')]
# convert ' ' to '-'
state_frame['State'] = state_frame['State'].str.replace(' ','-')
# loop through state names, use beautiful soup to read in the tenant rights page for each state
# create a blank list of "exceptions" to store any info category where a match wasn't found in beautiful soup
exceptions = []
for state in state_frame['State']:
    abbrev = state_frame[state_frame['State']==state].iloc[0]['Code']
    # create a subdirectory for the state
    subdir = 'state_tenant_rights/'+abbrev
    try:
        os.mkdir(subdir)
    except:
        print(state+' directory exists')
    # define URL for state
    url = 'https://ipropertymanagement.com/laws/'+state+'-landlord-tenant-rights'
    # replace smart quotes since they're causing errors
    req = requests.get(url)
    original = req.content.decode('utf-8')
    replacement = original.replace('&ldquo;', '"').replace('&rdquo;', '"').replace('&rsquo;', "'").replace('&#8211;','-').replace('–','-')
    soup = BeautifulSoup(replacement, 'html.parser')
    # find and store table of landlord responsibilities
    try:
        landlord_responsibilities = soup.find('table')
        landlord_responsibilities_frame = pd.concat(pd.read_html(str(landlord_responsibilities)))
        landlord_responsibilities_frame.to_csv(subdir+'/landlord_responsibilities.csv',index=False)
    except:
        exceptions.append(pd.DataFrame({'state':abbrev,
                                        'exception':'landlord_responsibilities'},index=[0]))
    # find and store tenant responsibilities
    try:
        tenant_responsibilities = soup.find(id='tenant-responsibilities').find_next('ul').find_all("li")
        tenant_responsibilities_list = [li.get_text() for li in tenant_responsibilities]
        pd.DataFrame({'tenant_responsibilities':tenant_responsibilities_list}).to_csv(subdir+'/tenant_responsibilities.csv',index=False)
    except:
        exceptions.append(pd.DataFrame({'state':abbrev,
                                        'exception':'tenant_responsibilities'},index=[0]))
    # find and store eviction reasons
    try:
        eviction_reasons = soup.find(id='evictions').find_next('ol').find_all("li")
        eviction_reasons_list = [li.get_text() for li in eviction_reasons]
        pd.DataFrame({'eviction_reasons':eviction_reasons_list}).to_csv(subdir+'/eviction_reasons.csv',index=False)
    except: 
        exceptions.append(pd.DataFrame({'state':abbrev,
                                        'exception':'eviction_reasons'},index=[0]))
    # find and store security deposits
    try:
        security_deposits = soup.find(id='security-deposits').find_next('ul').find_all("li")
        security_deposits_list = [li.get_text() for li in security_deposits]
        pd.DataFrame({'security_deposits':security_deposits_list}).to_csv(subdir+'/security_deposits.csv',index=False)
    except: 
        exceptions.append(pd.DataFrame({'state':abbrev,
                                        'exception':'security_deposits'},index=[0]))
    # find and store lease termination rules
    try:
        lease_termination = soup.find(id='lease-termination').find_next('table')
        lease_termination_frame = pd.concat(pd.read_html(str(lease_termination)))
        lease_termination_frame.to_csv(subdir+'/lease_termination.csv',index=False)
    except: 
        exceptions.append(pd.DataFrame({'state':abbrev,
                                        'exception':'lease_termination'},index=[0]))
    # find and store rent increase rules
    try:
        rent_increases = soup.find(id='rent-increases-fees').find_next('ul').find_all("li")
        rent_increases_list = [li.get_text() for li in rent_increases]
        pd.DataFrame({'rent_increases':rent_increases_list}).to_csv(subdir+'/rent_increases.csv',index=False)
    except:
        exceptions.append(pd.DataFrame({'state':abbrev,
                                        'exception':'rent_increases'},index=[0]))
    # find and store mandatory disclosures
    try:
        mandatory_disclosures = soup.find(id='mandatory-disclosures').find_next('ol').find_all("li")
        mandatory_disclosures_list = [li.get_text() for li in mandatory_disclosures]
        pd.DataFrame({'mandatory_diclosures':mandatory_disclosures_list}).to_csv(subdir+'/mandatory_disclosures.csv',index=False)
    except:
        exceptions.append(pd.DataFrame({'state':abbrev,
                                        'exception':'mandatory_disclosures'},index=[0]))
    # find and store local laws
    try:
        cities = []
        links = []
        # start at local laws, go through the list until you arrive at another h2, appending cities/links as you go
        next = soup.find(id = 'local-laws')
        end = False
        while end == False:
            next = next.find_next()
            if next.name == 'h3':
                cities.append(next.get_text())
            if next.name == 'p':
                links.append(next.find('a').get('href'))
            if next.name == 'h2':
                end = True
        # store in df
        local_law_df = pd.DataFrame({'city': cities,
                            'link': links})
        # write df
        local_law_df.to_csv(subdir+'/local_links.csv',index=False)
    except:
        exceptions.append(pd.DataFrame({'state':abbrev,
                                        'exception': 'local_laws'},index=[0]))
# concatenate exceptions and write
if len(exceptions)>0:
    pd.concat(exceptions).to_csv('state_tenant_rights/exceptions.csv',index=False)
