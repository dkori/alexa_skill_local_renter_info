# -*- coding: utf-8 -*-
#
# Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may not
# use this file except in compliance with the License. A copy of the License
# is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.
#

# This is a skill for getting device address.
# The skill serves as a simple sample on how to use the
# service client factory and Alexa APIs through the SDK.

from ask_sdk_core.skill_builder import CustomSkillBuilder
from ask_sdk_core.api_client import DefaultApiClient
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.utils import is_request_type, is_intent_name
from ask_sdk_model.ui import AskForPermissionsConsentCard
from ask_sdk_model.services import ServiceException
from ask_sdk_model.ui import SimpleCard
from ask_sdk_core.response_helper import get_text_content
from utils import create_presigned_url
import pandas as pd
import boto3
import io
import regex as re
from ask_sdk_model import ui, Response
from ask_sdk_model.interfaces.alexa.presentation.apl import (
    RenderDocumentDirective, ExecuteCommandsDirective, SpeakItemCommand,
    AutoPageCommand, HighlightMode)
import ask_sdk_core.utils as ask_utils
# import the state/abbreviation crosswalk
state_crosswalk = pd.read_csv('resources/state_crosswalk.csv')
sb = CustomSkillBuilder(api_client=DefaultApiClient())

WELCOME = ("Welcome to the Alexa local tenant rights Skill!  "
           #"This skill demos a feature we hope to implement in the local information domain. "
           #"you can say things like 'security deposit', or 'rent increase'?"
           )
WHAT_DO_YOU_WANT = "What do you want to ask?"
NOTIFY_MISSING_PERMISSIONS = ("Please enable Location permissions in "
                              "the Amazon Alexa app.")
NO_ADDRESS = ("It looks like you don't have an address set. "
              "You can set your address from the companion app.")
ADDRESS_AVAILABLE = "Here is your full address: {}, {}, {}"
ERROR = "Uh Oh. Looks like something went wrong."
LOCATION_FAILURE = ("There was an error with the Device Address API. "
                    "Please try again.")
GOODBYE = "Bye! Thanks for using the Sample Device Address API Skill!"
UNHANDLED = "This skill doesn't support that. Please ask something else"
HELP = ("You can use this skill by asking something like: "
        "whats my address?")
covid_tts = "Nationwide moratorium on evictions ends on June 30th. To find out what your options are based on where you live, you could connect with housing advocates in your area."
legal_aid_prompt = ". If you need further details from a local resource, you can say 'search local legal information' or 'find someone to help'"
# Rent increase tts - first placeholder = foo
#RentIncreaseTTS = ('bla bla bla rent {}')
#RentIncreaseDisplayText('')
card_info = """'security deposit'\n \n'can my landlord raise my rent'\n \n'I am getting evicted'\n \n'does my landlord need to repair my plumbing'\n \n
'can my landlord charge me for late rent'\n \n'what do I have to fix in my apartment'\n \n
'does my landlord need to disclose anything'"""
permissions = ["read::alexa:device:all:address"]
# Location Consent permission to be shown on the card. More information
# can be checked at
# https://developer.amazon.com/docs/custom-skills/device-address-api.html#sample-response-with-permission-card
class LaunchRequestHandler(AbstractRequestHandler):
    # Handler for Skill Launch
    def can_handle(self, handler_input):
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        handler_input.response_builder.speak(WELCOME).ask(WHAT_DO_YOU_WANT).set_card(
            SimpleCard(
                title='You can say...',
                content=card_info))
        return handler_input.response_builder.response
## Handler for legal aid
class LegalAssistanceHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("LegalAssistanceIntent")(handler_input)
    def handle(self, handler_input):
        req_envelope = handler_input.request_envelope
        response_builder = handler_input.response_builder
        service_client_fact = handler_input.service_client_factory
        if not (req_envelope.context.system.user.permissions and
                req_envelope.context.system.user.permissions.consent_token):
            response_builder.speak(NOTIFY_MISSING_PERMISSIONS)
            response_builder.set_card(
                AskForPermissionsConsentCard(permissions=permissions))
            return response_builder.response
        try:
            device_id = req_envelope.context.system.device.device_id
            device_addr_client = service_client_fact.get_device_address_service()
            addr = device_addr_client.get_full_address(device_id)
            # return No_Address if city fails
            if addr.state_or_region is None:
                response_builder.speak(NO_Address)
            else:
                # define city and state based on user info
                city = str(addr.city)
                state_abbr = str(addr.state_or_region)
                state = state_crosswalk[state_crosswalk['Code']==state_abbr].iloc[0]['State']
                # attempt to override city and state if possible
                if ask_utils.request_util.get_slot_value(handler_input, "City") is not None:
                    city = ask_utils.request_util.get_slot_value(handler_input, "City")
                if ask_utils.request_util.get_slot_value(handler_input, "State") is not None:
                    state = ask_utils.request_util.get_slot_value(handler_input, "State")
                    state_abbr = state_crosswalk[state_crosswalk['State'].str.contains(state,flags=re.IGNORECASE)].iloc[0]['Code']
                # pull rent increase information for given state_or_region
                bucket = "0b10d467-ca13-406a-9a3e-d400ac46d666-us-east-1"
                try:
                    file_name = "Media/state_tenant_rights/"+state_abbr+"/legal_aid.csv"
                    #file_name = "Media/state_tenant_rights/PA/rent_increases.csv"
                    #file_url = create_presigned_url(file_name)
                    s3 = boto3.client('s3') 
                    # 's3' is a key word. create connection to S3 using default config and all buckets within S3
                    obj = s3.get_object(Bucket= bucket, Key= file_name) 
                    # get object and file (key) from bucket
                    df = pd.read_csv(io.BytesIO(obj['Body'].read()))
                    # limit DF to just the city in question
                    df = df[df['City'].str.contains(city,flags=re.IGNORECASE)]
                    if df.shape[0]==0:
                        df.iloc[0]
                    #df = df[~df['rent_increases'].str.contains('Rent-related fees')]
                    # join the name and link
                    df['joint'] = df['Resource name']+ ' - ' + df['Link']
                    # max out at 4 resources 
                    if df.shape[0]>4:
                        df = df.iloc[0:3]
                    output = '\r\n \n'.join([x for x in df['joint']])
                    #response_builder.speak("Here are some rules about rent increases in "+state).set_card(
                    #SimpleCard(title = 'Rent increases in '+state+':',content = output))
                    response_builder.speak("Ive posted some resources to help in {} to your device".format(city)).set_card(
                        ui.StandardCard(
                        title='Housing resources in {} :'.format(city),
                        text=output))
                except Exception as e:
                    #response_builder.speak('error').set_card(SimpleCard(title='error',content=str(e)))
                    response_builder.speak("Sorry, I don't have that information for {}".format(city))
            return response_builder.response
        except ServiceException:
            response_builder.speak(ERROR)
            return response_builder.response
        except Exception as e:
            raise e
## Handler for rent increases
class RentIncreaseHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("RentIncreaseIntent")(handler_input)
    def handle(self, handler_input):
        req_envelope = handler_input.request_envelope
        response_builder = handler_input.response_builder
        service_client_fact = handler_input.service_client_factory
        if not (req_envelope.context.system.user.permissions and
                req_envelope.context.system.user.permissions.consent_token):
            response_builder.speak(NOTIFY_MISSING_PERMISSIONS)
            response_builder.set_card(
                AskForPermissionsConsentCard(permissions=permissions))
            return response_builder.response
        try:
            device_id = req_envelope.context.system.device.device_id
            device_addr_client = service_client_fact.get_device_address_service()
            addr = device_addr_client.get_full_address(device_id)
            # return No_Address if city fails
            if addr.state_or_region is None:
                response_builder.speak(NO_Address)
            else:
                # define city and state based on user info
                city = str(addr.city)
                state_abbr = str(addr.state_or_region)
                state = state_crosswalk[state_crosswalk['Code']==state_abbr].iloc[0]['State']
                # attempt to override city and state if specified by user
                if ask_utils.request_util.get_slot_value(handler_input, "City") is not None:
                    city = ask_utils.request_util.get_slot_value(handler_input, "City")
                if ask_utils.request_util.get_slot_value(handler_input, "State") is not None:
                    state = ask_utils.request_util.get_slot_value(handler_input, "State")
                    state_abbr = state_crosswalk[state_crosswalk['State'].str.contains(state,flags=re.IGNORECASE)].iloc[0]['Code']
                # attempt to override city and state if possible
                if ask_utils.request_util.get_slot_value(handler_input, "City") is not None:
                    city = ask_utils.request_util.get_slot_value(handler_input, "City")
                if ask_utils.request_util.get_slot_value(handler_input, "State") is not None:
                    state = ask_utils.request_util.get_slot_value(handler_input, "State")
                    state_abbr = state_crosswalk[state_crosswalk['State'].str.contains(state,flags=re.IGNORECASE)].iloc[0]['Code']
                # define state
                # pull rent increase information for given state_or_region
                bucket = "0b10d467-ca13-406a-9a3e-d400ac46d666-us-east-1"
                try:
                    file_name = "Media/state_tenant_rights/"+state_abbr+"/rent_increases.csv"
                    #file_name = "Media/state_tenant_rights/PA/rent_increases.csv"
                    #file_url = create_presigned_url(file_name)
                    s3 = boto3.client('s3') 
                    # 's3' is a key word. create connection to S3 using default config and all buckets within S3
                    obj = s3.get_object(Bucket= bucket, Key= file_name) 
                    # get object and file (key) from bucket
                    df = pd.read_csv(io.BytesIO(obj['Body'].read()))
                    # eliminate fees to shorten tts 
                    df = df[~df['rent_increases'].str.contains('Rent-related fees')]
                    # separate out the first clause
                    df['first_clause'] = df['rent_increases'].str.replace('(?<=\.).*','')
                    #df['first_clause_bold'] = '<b>'+df['first_clause']+'</b>'
                    df['first_clause_break'] = '**'+df['first_clause']+'**\r\n'
                    # add bold tags around first clause
                    df['rent_increases'] = df.apply(lambda x: x['rent_increases'].replace(str(x['first_clause']), str(x['first_clause_break'])), axis=1)
                    #df = pd.read_csv(obj['Body'])
                    #df = pd.read_csv(file_url)
                    output = '\r\n'.join([x for x in df['rent_increases']])
                    #response_builder.speak("Here are some rules about rent increases in "+state).set_card(
                    #SimpleCard(title = 'Rent increases in '+state+':',content = output))
                    if state_abbr == 'CA':
                        response_builder.speak("Here's some info about rent control and rent increases in "+state+legal_aid_prompt).set_card(
                            ui.StandardCard(
                            title='Rent increases in '+state+':',
                            text=output))
                    else:
                        response_builder.speak("Here's some info about rent control and rent increases in "+state).set_card(
                            ui.StandardCard(
                            title='Rent increases in '+state+':',
                            text=output))
                except:
                    response_builder.speak("Sorry, I don't have that information for {}".format(state))
            return response_builder.response
        except ServiceException:
            response_builder.speak(ERROR)
            return response_builder.response
        except Exception as e:
            raise e
## Handler for lease termination
class LeaseTerminationHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("LeaseTerminationIntent")(handler_input)
    def handle(self, handler_input):
        req_envelope = handler_input.request_envelope
        response_builder = handler_input.response_builder
        service_client_fact = handler_input.service_client_factory
        if not (req_envelope.context.system.user.permissions and
                req_envelope.context.system.user.permissions.consent_token):
            response_builder.speak(NOTIFY_MISSING_PERMISSIONS)
            response_builder.set_card(
                AskForPermissionsConsentCard(permissions=permissions))
            return response_builder.response
        try:
            device_id = req_envelope.context.system.device.device_id
            device_addr_client = service_client_fact.get_device_address_service()
            addr = device_addr_client.get_full_address(device_id)
            # return No_Address if city fails
            if addr.state_or_region is None:
                response_builder.speak(NO_Address)
            else:
                # define city and state based on user info
                city = str(addr.city)
                state_abbr = str(addr.state_or_region)
                state = state_crosswalk[state_crosswalk['Code']==state_abbr].iloc[0]['State']
                # attempt to override city and state if possible
                if ask_utils.request_util.get_slot_value(handler_input, "City") is not None:
                    city = ask_utils.request_util.get_slot_value(handler_input, "City")
                if ask_utils.request_util.get_slot_value(handler_input, "State") is not None:
                    state = ask_utils.request_util.get_slot_value(handler_input, "State")
                    state_abbr = state_crosswalk[state_crosswalk['State'].str.contains(state,flags=re.IGNORECASE)].iloc[0]['Code']
                # define state
                # pull rent increase information for given state_or_region
                bucket = "0b10d467-ca13-406a-9a3e-d400ac46d666-us-east-1"
                try:
                    file_name = "Media/state_tenant_rights/"+state_abbr+"/lease_termination.csv"
                    #file_name = "Media/state_tenant_rights/PA/rent_increases.csv"
                    #file_url = create_presigned_url(file_name)
                    s3 = boto3.client('s3') 
                    # 's3' is a key word. create connection to S3 using default config and all buckets within S3
                    obj = s3.get_object(Bucket= bucket, Key= file_name) 
                    # get object and file (key) from bucket
                    df = pd.read_csv(io.BytesIO(obj['Body'].read()))
                    # join the two columns into one
                    df['combined'] = df['Rent Payment Frequency']+' - '+ df['Notice Needed']
                    output = '\r\n \n'.join([x for x in df['combined']])
                    #response_builder.speak("Here are some rules about rent increases in "+state).set_card(
                    #SimpleCard(title = 'Rent increases in '+state+':',content = output))
                    response_builder.speak("I’ve posted the notice needed for lease termination on the Alexa app:"+state).set_card(
                        ui.StandardCard(
                        title='Notice for lease termination in '+state+':',
                        text=output))
                except Exception as e:
                    #response_builder.speak('error').set_card(SimpleCard(title='error',content=str(e)))
                    response_builder.speak("Sorry, I don't have that information for {}".format(state))
            return response_builder.response
        except ServiceException:
            response_builder.speak(ERROR)
            return response_builder.response
        except Exception as e:
            raise e
## Handler for LandlordResponsibilities
class LandlordResponsibilityHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("LandlordResponsibilityIntent")(handler_input)
    def handle(self, handler_input):
        req_envelope = handler_input.request_envelope
        response_builder = handler_input.response_builder
        service_client_fact = handler_input.service_client_factory
        if not (req_envelope.context.system.user.permissions and
                req_envelope.context.system.user.permissions.consent_token):
            response_builder.speak(NOTIFY_MISSING_PERMISSIONS)
            response_builder.set_card(
                AskForPermissionsConsentCard(permissions=permissions))
            return response_builder.response
        try:
            device_id = req_envelope.context.system.device.device_id
            device_addr_client = service_client_fact.get_device_address_service()
            addr = device_addr_client.get_full_address(device_id)
            #slots = handler_input.request_envelope.request.intent.slots
            #amenity = slots['Amenity']
            amenity = ask_utils.request_util.get_slot_value(handler_input, "Amenity")
            #amenity = "plumbing"
            # return No_Address if city fails
            if addr.state_or_region is None:
                response_builder.speak(NO_Address)
            else:
                # define city and state based on user info
                city = str(addr.city)
                state_abbr = str(addr.state_or_region)
                state = state_crosswalk[state_crosswalk['Code']==state_abbr].iloc[0]['State']
                # attempt to override city and state if possible
                if ask_utils.request_util.get_slot_value(handler_input, "City") is not None:
                    city = ask_utils.request_util.get_slot_value(handler_input, "City")
                if ask_utils.request_util.get_slot_value(handler_input, "State") is not None:
                    state = ask_utils.request_util.get_slot_value(handler_input, "State")
                    state_abbr = state_crosswalk[state_crosswalk['State'].str.contains(state,flags=re.IGNORECASE)].iloc[0]['Code']
                # pull rent increase information for given state_or_region
                bucket = "0b10d467-ca13-406a-9a3e-d400ac46d666-us-east-1"
                try:
                    file_name = "Media/state_tenant_rights/"+state_abbr+"/landlord_responsibilities.csv"
                    #file_name = "Media/state_tenant_rights/PA/rent_increases.csv"
                    #file_url = create_presigned_url(file_name)
                    s3 = boto3.client('s3') 
                    # 's3' is a key word. create connection to S3 using default config and all buckets within S3
                    obj = s3.get_object(Bucket= bucket, Key= file_name) 
                    # get object and file (key) from bucket
                    df = pd.read_csv(io.BytesIO(obj['Body'].read()))
                    # eliminate fees to shorten tts 
                    #df = df[~df['rent_increases'].str.contains('Rent-related fees')]
                    # find row associated with the amenity
                    amenity_row = df[df['Item'].str.contains(amenity,flags=re.IGNORECASE)]
                    if amenity_row.iloc[0]['Landlord Responsibility?']=='Yes':
                        output = "In {}, it is your landlord's responsibility to take care of {}".format(state,amenity)
                        response_builder.speak(output).set_card(
                            ui.StandardCard(
                                title='Landlord responsibility in '+state+':',
                                text=output))
                    else:
                        output = "It is not your landlord's responsibility to take care of {} in {}".format(amenity,state)
                        response_builder.speak(output).set_card(
                            ui.StandardCard(
                                title='Landlord responsibility in '+state+':',
                                text=output))
                except Exception as e:
                    #response_builder.speak('error').set_card(SimpleCard(title='error',content=str(e)))
                    response_builder.speak("Sorry, I don't have that information for {}".format(state))
            return response_builder.response
        except ServiceException:
            response_builder.speak(ERROR)
            return response_builder.response
        except Exception as e:
            raise e
## Handler for rent related fees
class RentRelatedFeesHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("RentRelatedFeesIntent")(handler_input)
    def handle(self, handler_input):
        req_envelope = handler_input.request_envelope
        response_builder = handler_input.response_builder
        service_client_fact = handler_input.service_client_factory
        if not (req_envelope.context.system.user.permissions and
                req_envelope.context.system.user.permissions.consent_token):
            response_builder.speak(NOTIFY_MISSING_PERMISSIONS)
            response_builder.set_card(
                AskForPermissionsConsentCard(permissions=permissions))
            return response_builder.response
        try:
            device_id = req_envelope.context.system.device.device_id
            device_addr_client = service_client_fact.get_device_address_service()
            addr = device_addr_client.get_full_address(device_id)
            # return No_Address if city fails
            if addr.state_or_region is None:
                response_builder.speak(NO_Address)
            else:
                # define city and state based on user info
                city = str(addr.city)
                state_abbr = str(addr.state_or_region)
                state = state_crosswalk[state_crosswalk['Code']==state_abbr].iloc[0]['State']
                # attempt to override city and state if possible
                if ask_utils.request_util.get_slot_value(handler_input, "City") is not None:
                    city = ask_utils.request_util.get_slot_value(handler_input, "City")
                if ask_utils.request_util.get_slot_value(handler_input, "State") is not None:
                    state = ask_utils.request_util.get_slot_value(handler_input, "State")
                    state_abbr = state_crosswalk[state_crosswalk['State'].str.contains(state,flags=re.IGNORECASE)].iloc[0]['Code']
                # pull rent increase information for given state_or_region
                bucket = "0b10d467-ca13-406a-9a3e-d400ac46d666-us-east-1"
                try:
                    file_name = "Media/state_tenant_rights/"+state_abbr+"/rent_increases.csv"
                    #file_name = "Media/state_tenant_rights/PA/rent_increases.csv"
                    #file_url = create_presigned_url(file_name)
                    s3 = boto3.client('s3') 
                    # 's3' is a key word. create connection to S3 using default config and all buckets within S3
                    obj = s3.get_object(Bucket= bucket, Key= file_name) 
                    # get object and file (key) from bucket
                    df = pd.read_csv(io.BytesIO(obj['Body'].read()))
                    # limit only to fees 
                    df = df[df['rent_increases'].str.contains('(Rent-related fees)|(back rent)')]
                    # separate out the first clause
                    df['first_clause'] = df['rent_increases'].str.replace('(?<=\.).*','')
                    #df['first_clause_bold'] = '<b>'+df['first_clause']+'</b>'
                    df['first_clause_break'] = '**'+df['first_clause']+'**\r\n'
                    # add bold tags around first clause
                    df['rent_increases'] = df.apply(lambda x: x['rent_increases'].replace(str(x['first_clause']), str(x['first_clause_break'])), axis=1)
                    #df = pd.read_csv(obj['Body'])
                    #df = pd.read_csv(file_url)
                    output = '\r\n'.join([x for x in df['rent_increases']])
                    #response_builder.speak("Here are some rules about rent increases in "+state).set_card(
                    #SimpleCard(title = 'Rent increases in '+state+':',content = output))
                    response_builder.speak("I've posted some rent related fees in {} to your device".format(state)).set_card(
                        ui.StandardCard(
                        title='Rent-related fees in '+state+':',
                        text=output))
                except:
                    response_builder.speak("Sorry, I don't have that information for {}".format(state))
            return response_builder.response
        except ServiceException:
            response_builder.speak(ERROR)
            return response_builder.response
        except Exception as e:
            raise e
class EvictionReasonsHandler(AbstractRequestHandler):
    # Handler for Getting Device Address or asking for location consent
    def can_handle(self, handler_input):
        return is_intent_name("EvictionReasonsIntent")(handler_input)

    def handle(self, handler_input):
        req_envelope = handler_input.request_envelope
        response_builder = handler_input.response_builder
        service_client_fact = handler_input.service_client_factory

        if not (req_envelope.context.system.user.permissions and
                req_envelope.context.system.user.permissions.consent_token):
            response_builder.speak(NOTIFY_MISSING_PERMISSIONS)
            response_builder.set_card(
                AskForPermissionsConsentCard(permissions=permissions))
            return response_builder.response
        try:
            device_id = req_envelope.context.system.device.device_id
            device_addr_client = service_client_fact.get_device_address_service()
            addr = device_addr_client.get_full_address(device_id)
            # return No_Address if city fails
            if addr.state_or_region is None:
                response_builder.speak(NO_Address)
            else:
                # define city and state based on user info
                city = str(addr.city)
                state_abbr = str(addr.state_or_region)
                state = state_crosswalk[state_crosswalk['Code']==state_abbr].iloc[0]['State']
                # attempt to override city and state if possible
                if ask_utils.request_util.get_slot_value(handler_input, "City") is not None:
                    city = ask_utils.request_util.get_slot_value(handler_input, "City")
                if ask_utils.request_util.get_slot_value(handler_input, "State") is not None:
                    state = ask_utils.request_util.get_slot_value(handler_input, "State")
                    state_abbr = state_crosswalk[state_crosswalk['State'].str.contains(state,flags=re.IGNORECASE)].iloc[0]['Code']
                # pull rent increase information for given state_or_region
                bucket = "0b10d467-ca13-406a-9a3e-d400ac46d666-us-east-1"
                try:
                    file_name = "Media/state_tenant_rights/"+state_abbr+"/eviction_reasons.csv"
                    #file_name = "Media/state_tenant_rights/Pennsylvania/eviction_reasons.csv"
                    #file_url = create_presigned_url(file_name)
                    s3 = boto3.client('s3') 
                    # 's3' is a key word. create connection to S3 using default config and all buckets within S3
                    obj = s3.get_object(Bucket= bucket, Key= file_name) 
                    # get object and file (key) from bucket
                    df = pd.read_csv(io.BytesIO(obj['Body'].read()))
                    # extract just the short reasons for eviction_reasons
                    reasons_short = df['eviction_reasons'].str.replace(' - .*','').tolist()
                    df['reasons_short'] = df['eviction_reasons'].str.replace(' - .*','')
                    #df['reasons_short_bold'] = '<b>'+df['reasons_short']+'</b>'
                    # add a line break after the short the first clause
                    df['reasons_short_break'] = '**'+df['reasons_short']+'**\r\n'
                    df['eviction_reasons'] = df.apply(lambda x: x['eviction_reasons'].replace(str(x['reasons_short']), str(x['reasons_short_break'])), axis=1)
                    # join together reasons by comma
                    reasons_join = ', '.join(reasons_short)
                    #df = pd.read_csv(obj['Body'])
                    #df = pd.read_csv(file_url)
                    output = '\r\n \n'.join([x for x in df['eviction_reasons']])
                    response_builder.speak("In {}, you can be evicted for ".format(state)+reasons_join+legal_aid_prompt).set_card(
                        ui.StandardCard(
                        title='Reasons for eviction in '+state+':',
                        text=output
                        ))
                except:
                    response_builder.speak("Sorry, I don't have that information for ".format(state))
                #title = 'Reasons for eviction in '+state+':'
                #primary_text = output
                #apl_doc = {"type": "APL",
                #"version": "1.6",
                #"mainTemplate": {
                #    "item": {
                #        "title":title,
                #        "type": "Text",
                #        "text": primary_text}}}
                #response_builder.speak("In your state, you can be evicted for "+reasons_join).add_directive(
                #        RenderDocumentDirective(document = apl_doc))
            return response_builder.response
        except ServiceException:
            response_builder.speak(ERROR)
            return response_builder.response
        except Exception as e:
            raise e

class MandatoryDisclosureHandler(AbstractRequestHandler):
    # Handler for Getting Device Address or asking for location consent
    def can_handle(self, handler_input):
        return is_intent_name("MandatoryDisclosuresIntent")(handler_input)

    def handle(self, handler_input):
        req_envelope = handler_input.request_envelope
        response_builder = handler_input.response_builder
        service_client_fact = handler_input.service_client_factory

        if not (req_envelope.context.system.user.permissions and
                req_envelope.context.system.user.permissions.consent_token):
            response_builder.speak(NOTIFY_MISSING_PERMISSIONS)
            response_builder.set_card(
                AskForPermissionsConsentCard(permissions=permissions))
            return response_builder.response
        try:
            device_id = req_envelope.context.system.device.device_id
            device_addr_client = service_client_fact.get_device_address_service()
            addr = device_addr_client.get_full_address(device_id)
            # return No_Address if city fails
            if addr.state_or_region is None:
                response_builder.speak(NO_Address)
            else:
                # define city and state based on user info
                city = str(addr.city)
                state_abbr = str(addr.state_or_region)
                state = state_crosswalk[state_crosswalk['Code']==state_abbr].iloc[0]['State']
                # attempt to override city and state if possible
                if ask_utils.request_util.get_slot_value(handler_input, "City") is not None:
                    city = ask_utils.request_util.get_slot_value(handler_input, "City")
                if ask_utils.request_util.get_slot_value(handler_input, "State") is not None:
                    state = ask_utils.request_util.get_slot_value(handler_input, "State")
                    state_abbr = state_crosswalk[state_crosswalk['State'].str.contains(state,flags=re.IGNORECASE)].iloc[0]['Code']
                # pull rent increase information for given state_or_region
                bucket = "0b10d467-ca13-406a-9a3e-d400ac46d666-us-east-1"
                try:
                    file_name = "Media/state_tenant_rights/"+state_abbr+"/mandatory_disclosures.csv"
                    #file_name = "Media/state_tenant_rights/Pennsylvania/eviction_reasons.csv"
                    #file_url = create_presigned_url(file_name)
                    s3 = boto3.client('s3') 
                    # 's3' is a key word. create connection to S3 using default config and all buckets within S3
                    obj = s3.get_object(Bucket= bucket, Key= file_name) 
                    # get object and file (key) from bucket
                    df = pd.read_csv(io.BytesIO(obj['Body'].read()))
                    # extract just the short reasons for eviction_reasons
                    reasons_short = df['mandatory_diclosures'].str.replace('(?<=\.).*','').tolist()
                    df['reasons_short'] = df['mandatory_diclosures'].str.replace('(?<=\.).*','')
                    #df['reasons_short_bold'] = '<b>'+df['reasons_short']+'</b>'
                    # add a line break after the short the first clause
                    df['reasons_short_break'] = '**'+df['reasons_short']+'**\r\n'
                    df['mandatory_diclosures'] = df.apply(lambda x: x['mandatory_diclosures'].replace(str(x['reasons_short']), str(x['reasons_short_break'])), axis=1)
                    # join together reasons by comma
                    reasons_join = ', '.join(reasons_short)
                    #df = pd.read_csv(obj['Body'])
                    #df = pd.read_csv(file_url)
                    output = '\r\n \n'.join([x for x in df['mandatory_diclosures']])
                    response_builder.speak("In {}, your landlord must disclose ".format(state)+reasons_join+legal_aid_prompt).set_card(
                        ui.StandardCard(
                        title='Mandatory landlord disclosures in '+state+':',
                        text=output
                        ))
                except Exception as e:
                    response_builder.speak('error').set_card(SimpleCard(title='error',content=str(e)))
                    #response_builder.speak("Sorry, I don't have that information for {}".format(state))
                #title = 'Reasons for eviction in '+state+':'
                #primary_text = output
                #apl_doc = {"type": "APL",
                #"version": "1.6",
                #"mainTemplate": {
                #    "item": {
                #        "title":title,
                #        "type": "Text",
                #        "text": primary_text}}}
                #response_builder.speak("In your state, you can be evicted for "+reasons_join).add_directive(
                #        RenderDocumentDirective(document = apl_doc))
            return response_builder.response
        except ServiceException:
            response_builder.speak(ERROR)
            return response_builder.response
        except Exception as e:
            raise e

class SecurityDepositHandler(AbstractRequestHandler):
    # Handler for Getting Device Address or asking for location consent
    def can_handle(self, handler_input):
        return is_intent_name("SecurityDepositsIntent")(handler_input)

    def handle(self, handler_input):
        req_envelope = handler_input.request_envelope
        response_builder = handler_input.response_builder
        service_client_fact = handler_input.service_client_factory

        if not (req_envelope.context.system.user.permissions and
                req_envelope.context.system.user.permissions.consent_token):
            response_builder.speak(NOTIFY_MISSING_PERMISSIONS)
            response_builder.set_card(
                AskForPermissionsConsentCard(permissions=permissions))
            return response_builder.response
        try:
            device_id = req_envelope.context.system.device.device_id
            device_addr_client = service_client_fact.get_device_address_service()
            addr = device_addr_client.get_full_address(device_id)
            # return No_Address if city fails
            if addr.state_or_region is None:
                response_builder.speak(NO_Address)
            else:
                # define city and state based on user info
                city = str(addr.city)
                state_abbr = str(addr.state_or_region)
                state = state_crosswalk[state_crosswalk['Code']==state_abbr].iloc[0]['State']
                # attempt to override city and state if possible
                if ask_utils.request_util.get_slot_value(handler_input, "City") is not None:
                    city = ask_utils.request_util.get_slot_value(handler_input, "City")
                if ask_utils.request_util.get_slot_value(handler_input, "State") is not None:
                    state = ask_utils.request_util.get_slot_value(handler_input, "State")
                    state_abbr = state_crosswalk[state_crosswalk['State'].str.contains(state,flags=re.IGNORECASE)].iloc[0]['Code']
                # pull rent increase information for given state_or_region
                bucket = "0b10d467-ca13-406a-9a3e-d400ac46d666-us-east-1"
                try:
                    file_name = "Media/state_tenant_rights/"+state_abbr+"/security_deposits.csv"
                    #file_name = "Media/state_tenant_rights/Pennsylvania/eviction_reasons.csv"
                    #file_url = create_presigned_url(file_name)
                    s3 = boto3.client('s3') 
                    # 's3' is a key word. create connection to S3 using default config and all buckets within S3
                    obj = s3.get_object(Bucket= bucket, Key= file_name) 
                    # get object and file (key) from bucket
                    df = pd.read_csv(io.BytesIO(obj['Body'].read()))
                    # extract just the short reasons for eviction_reasons
                    reasons_short = df['security_deposits'].str.replace(' - .*','').tolist()
                    df['reasons_short'] = df['security_deposits'].str.replace(' - .*','')
                    #df['reasons_short_bold'] = '<b>'+df['reasons_short']+'</b>'
                    # add a line break after the short the first clause
                    df['reasons_short_break'] = '**'+df['reasons_short']+'**\r\n'
                    df['security_deposits'] = df.apply(lambda x: x['security_deposits'].replace(str(x['reasons_short']), str(x['reasons_short_break'])), axis=1)
                    # join together reasons by comma
                    reasons_join = ', '.join(reasons_short)
                    #df = pd.read_csv(obj['Body'])
                    #df = pd.read_csv(file_url)
                    output = '\r\n \n'.join([x for x in df['security_deposits']])
                    response_builder.speak("I've posted limitations on security deposits in {} to your device".format(state)).set_card(
                        ui.StandardCard(
                        title='Security deposit limitations in '+state+':',
                        text=output
                        ))
                except:
                    response_builder.speak("Sorry, I don't have that information for ".format(state))
                #title = 'Reasons for eviction in '+state+':'
                #primary_text = output
                #apl_doc = {"type": "APL",
                #"version": "1.6",
                #"mainTemplate": {
                #    "item": {
                #        "title":title,
                #        "type": "Text",
                #        "text": primary_text}}}
                #response_builder.speak("In your state, you can be evicted for "+reasons_join).add_directive(
                #        RenderDocumentDirective(document = apl_doc))
            return response_builder.response
        except ServiceException:
            response_builder.speak(ERROR)
            return response_builder.response
        except Exception as e:
            raise e
# covid restrictions Handler
class CovidEvictionHandler(AbstractRequestHandler):
    # Handler for Getting Device Address or asking for location consent
    def can_handle(self, handler_input):
        return is_intent_name("CovidEvictionIntent")(handler_input)

    def handle(self, handler_input):
        req_envelope = handler_input.request_envelope
        response_builder = handler_input.response_builder
        service_client_fact = handler_input.service_client_factory

        if not (req_envelope.context.system.user.permissions and
                req_envelope.context.system.user.permissions.consent_token):
            response_builder.speak(NOTIFY_MISSING_PERMISSIONS)
            response_builder.set_card(
                AskForPermissionsConsentCard(permissions=permissions))
            return response_builder.response
        try:
            response_builder.speak(covid_tts+legal_aid_prompt).set_card(SimpleCard(title = 'Nationwide Eviction Moratorium',content = covid_tts))
            return response_builder.response
        except ServiceException:
            response_builder.speak(ERROR)
            return response_builder.response
        except Exception as e:
            raise e

class TenantResponsibilitiesHandler(AbstractRequestHandler):
    # Handler for Getting Device Address or asking for location consent
    def can_handle(self, handler_input):
        return is_intent_name("TenentResponsibilitiesIntent")(handler_input)

    def handle(self, handler_input):
        req_envelope = handler_input.request_envelope
        response_builder = handler_input.response_builder
        service_client_fact = handler_input.service_client_factory

        if not (req_envelope.context.system.user.permissions and
                req_envelope.context.system.user.permissions.consent_token):
            response_builder.speak(NOTIFY_MISSING_PERMISSIONS)
            response_builder.set_card(
                AskForPermissionsConsentCard(permissions=permissions))
            return response_builder.response
        try:
            device_id = req_envelope.context.system.device.device_id
            device_addr_client = service_client_fact.get_device_address_service()
            addr = device_addr_client.get_full_address(device_id)
            # return No_Address if city fails
            if addr.state_or_region is None:
                response_builder.speak(NO_Address)
            else:
                # define city and state based on user info
                city = str(addr.city)
                state_abbr = str(addr.state_or_region)
                state = state_crosswalk[state_crosswalk['Code']==state_abbr].iloc[0]['State']
                # attempt to override city and state if possible
                if ask_utils.request_util.get_slot_value(handler_input, "City") is not None:
                    city = ask_utils.request_util.get_slot_value(handler_input, "City")
                if ask_utils.request_util.get_slot_value(handler_input, "State") is not None:
                    state = ask_utils.request_util.get_slot_value(handler_input, "State")
                    state_abbr = state_crosswalk[state_crosswalk['State'].str.contains(state,flags=re.IGNORECASE)].iloc[0]['Code']
                # pull rent increase information for given state_or_region
                bucket = "0b10d467-ca13-406a-9a3e-d400ac46d666-us-east-1"
                try:
                    file_name = "Media/state_tenant_rights/"+state_abbr+"/tenant_responsibilities.csv"
                    #file_name = "Media/state_tenant_rights/Pennsylvania/eviction_reasons.csv"
                    #file_url = create_presigned_url(file_name)
                    s3 = boto3.client('s3') 
                    # 's3' is a key word. create connection to S3 using default config and all buckets within S3
                    obj = s3.get_object(Bucket= bucket, Key= file_name) 
                    # get object and file (key) from bucket
                    df = pd.read_csv(io.BytesIO(obj['Body'].read()))
                    responsibilities_join = '\r\n \n'.join([x for x in df['tenant_responsibilities']])
                    output = responsibilities_join
                    response_builder.speak("I've posted renter responsibilities in {} to your device".format(state)).set_card(
                        ui.StandardCard(
                        title='Renter responsibilities in '+state+':',
                        text=output
                        ))
                except:
                    response_builder.speak("Sorry, I don't have that information for ".format(state))
                #title = 'Reasons for eviction in '+state+':'
                #primary_text = output
                #apl_doc = {"type": "APL",
                #"version": "1.6",
                #"mainTemplate": {
                #    "item": {
                #        "title":title,
                #        "type": "Text",
                #        "text": primary_text}}}
                #response_builder.speak("In your state, you can be evicted for "+reasons_join).add_directive(
                #        RenderDocumentDirective(document = apl_doc))
            return response_builder.response
        except ServiceException:
            response_builder.speak(ERROR)
            return response_builder.response
        except Exception as e:
            raise e

class SessionEndedRequestHandler(AbstractRequestHandler):
    # Handler for Session End
    def can_handle(self, handler_input):
        return is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        return handler_input.response_builder.response


class HelpIntentHandler(AbstractRequestHandler):
    # Handler for Help Intent
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        handler_input.response_builder.speak(HELP).ask(HELP)
        return handler_input.response_builder.response


class CancelOrStopIntentHandler(AbstractRequestHandler):
    # Single handler for Cancel and Stop Intent
    def can_handle(self, handler_input):
        return (is_intent_name("AMAZON.CancelIntent")(handler_input) or
                is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        handler_input.response_builder.speak(GOODBYE)
        return handler_input.response_builder.response


class FallbackIntentHandler(AbstractRequestHandler):
    # AMAZON.FallbackIntent is only available in en-US locale.
    # This handler will not be triggered except in that locale,
    # so it is safe to deploy on any locale
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        handler_input.response_builder.speak(UNHANDLED).ask(HELP)
        return handler_input.response_builder.response


class GetAddressExceptionHandler(AbstractExceptionHandler):
    # Custom Exception Handler for handling device address API call exceptions
    def can_handle(self, handler_input, exception):
        return isinstance(exception, ServiceException)

    def handle(self, handler_input, exception):
        if exception.status_code == 403:
            handler_input.response_builder.speak(
                NOTIFY_MISSING_PERMISSIONS).set_card(
                AskForPermissionsConsentCard(permissions=permissions))
        else:
            handler_input.response_builder.speak(
                LOCATION_FAILURE).ask(LOCATION_FAILURE)

        return handler_input.response_builder.response


class CatchAllExceptionHandler(AbstractExceptionHandler):
    # Catch all exception handler, log exception and
    # respond with custom message
    def can_handle(self, handler_input, exception):
        return True
    def handle(self, handler_input, exception):
        print("Encountered following exception: {}".format(exception))
        speech = "Sorry, there was some problem. Please try again!!"
        handler_input.response_builder.speak(speech).ask(speech)
        return handler_input.response_builder.response
sb.add_request_handler(LegalAssistanceHandler())
sb.add_request_handler(CovidEvictionHandler())
sb.add_request_handler(LeaseTerminationHandler())
sb.add_request_handler(LandlordResponsibilityHandler())
sb.add_request_handler(MandatoryDisclosureHandler())
sb.add_request_handler(SecurityDepositHandler())
sb.add_request_handler(RentRelatedFeesHandler())
sb.add_request_handler(TenantResponsibilitiesHandler())
sb.add_request_handler(EvictionReasonsHandler())
sb.add_request_handler(RentIncreaseHandler())
sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())

sb.add_exception_handler(GetAddressExceptionHandler())
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
