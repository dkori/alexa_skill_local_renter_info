# alexa_skill_local_renter_info
For the Alexa Local Info Hackathon for 2021, we deployed an Alexa Skill to prove the concept of how the Alexa Local Info domain can:
+ inform our customers of state renter laws to protect them from tenant rights violations
+ direct them to local resources such as local housing rights advocacy groups to provide them recourse when landlords try to take advantage of them

The lambda function deploys logic for 10 different intents to deliver the correct information to our customer, based on a range of utterance shapes. 

The scraper also scrapes links to additional information for a few dozen cities across America. We didn't have time to deploy this information for the customer experience, but it could easily be integrated into a more full-feature Local Info experience.
