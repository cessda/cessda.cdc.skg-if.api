'''
Copyright CESSDA ERIC 2017-2022

Licensed under the Apache License, Version 2.0 (the "License"); you may not
use this file except in compliance with the License.
You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Title: It is a simple Python Code to extract tweets from the CESSDA_Data account.

Goal: to collect tweets on the CESSDA Twitter account and save the information as an excel file.
This code extracts the last N* (any number from 1) of tweets from a certain twitter account.

It collects:
(1) links,
(2) the beginning of the text,
(3) number of likes and retweets,
(4) type (retweet, reply, tweet),
(5) first 5 hashtags,
(6) date,
(7) media type.

Based on the keywords from hashtags or text, a content type can be defined.
In this code, CESSDA keywords are used.

At the end, an excel file with original tweets (excl. retweets and replies) only are produced.
Contact: Yevhen Voronin, yevhen.voronin@gesis.org

Documentation: https://developer.twitter.com/en/docs/twitter-api/v1/tweets/timelines/api-reference/get-statuses-user_timeline
https://developer.twitter.com/en/docs/twitter-api/v1/data-dictionary/object-model/tweet
'''
#!/usr/bin/env python
# coding: utf-8

#Importing libraries
import tweepy as tweepy #import tweepy library
from tweepy import *
import pandas as pd #import pandas
import re #import re
import datetime

######### Part 1: Authentication and settings #########
 #Twitter Auth Data
consumer_key = "<consumer_key>"
consumer_secret = "<consumer_secret>"
access_key= "<access_key>"
access_secret = "<access_secret>"
#Getting Acess to Twitter
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_key, access_secret)
api = tweepy.API(auth,wait_on_rate_limit=True)
print("Access is granted")
#Define username and max number of tweets
username = "CESSDA_Data" #Add the twitter account name here!
max_tweets = 2000 #Add the max number of collected tweets. 180 means the last 180 tweets!
sequence = 1 #Number to keep the correct order

######### Part 2: Extracting tweets from the account #########
tweets = tweepy.Cursor(api.user_timeline,id=username,tweet_mode='extended',exclude_replies = True).items(max_tweets) #max_id=1379332243773067264
tweets_list = [] #create an empty list

######### Part 3: Saving info from each tweets to a separate variables #########
#Start a loop for each tweet;
##### Part 3.1: Saving my info points #####
for tweet in tweets:
    tweet_link = "https://twitter.com/" + username + "/status/" + tweet.id_str #Get a proper link
    tweet_likes = tweet.favorite_count #Save likes
    tweet_retweets = tweet.retweet_count #Save retweets
    tweet_text = tweet.full_text.replace("\n", " ") #Save text without line breaks
    tweet_text = tweet_text.replace("&amp;", "") #Save text without "&amp;" elements
    tweet_text = tweet_text.replace("  ", " ") #Save text without empty spaces

    #Define the type: tweet, retweet, reply
    if tweet.full_text.startswith('RT @') is True:
        tweet_type = "Retweet"
        tweet_likes = None #delete likes for retweets
        tweet_retweets = None #delete retweets for retweets
    elif  tweet.in_reply_to_status_id_str is not None:
        tweet_type = "Reply"
    else:
        tweet_type = "Tweet"

    #Empty code variables:
    content = ""
    hashtags = ""
    media = ""

    #Extract first 5 hashtags:
    try:
        hashtag1 = tweet.entities['hashtags'][0]['text']
    except:
        hashtag1 = ""
    try:
        hashtag2 = tweet.entities['hashtags'][1]['text']
    except:
        hashtag2 = ""
    try:
        hashtag3 = tweet.entities['hashtags'][2]['text']
    except:
        hashtag3 = ""
    try:
        hashtag4 = tweet.entities['hashtags'][3]['text']
    except:
        hashtag4 = ""
    try:
        hashtag5 = tweet.entities['hashtags'][4]['text']
    except:
        hashtag5 = ""
    #Create a separate var that includes first five hashtags
    hashtags = hashtag1 + ' ' + hashtag2 + ' ' + hashtag3 + ' ' + hashtag4 + ' ' + hashtag5

    #Define Media type
    try:
        if tweet.entities['media']:
            if re.search("video", tweet.entities['media'][0]['expanded_url']):
                media = "video"
            elif re.search("photo", tweet.entities['media'][0]['expanded_url']):
                media = "photo"
            else:
                media = "other"
    except:
        media = ""

##### Part 3.2: Groping tweets to categories #####
    #Create a variable that contains text, hashtags and tweets links together
    temp_test = tweet_text.replace("@"," ") + " " + hashtags + " " + tweet_link
    temp_test = temp_test.replace ("  ", " ")
    #DMEG
    dmeg = ['DMMonday', 'DataManagement ExpertGuide', 'DMEG', 'Data Management Expert Guide', 'DataManagementExpertGuide', 'Management Expert Guide'] #Keywords for DMEG
    for word in dmeg:
        if word.lower() in temp_test.lower():
            content = "DMEG"

    #CDC
    cdc = ['CESSDA Data Catalogue', 'DataCatalogue', 'Data Catalogue', '#CESSDAData', 'CESSDADataCatalogue', 'CESSDA_Data Catalogue', 'CESSDA_DataCatalogue'] #Keywords for "CESSDA Data Catalogue"
    for word in cdc:
        if word.lower() in temp_test.lower():
            content = "CESSDA Data Catalogue"

    #COVID
    сovid = ['COVID19data', 'COVID19 datasets'] #Keywords for "COVID19 data campaign"
    for word in сovid:
        if word.lower() in temp_test.lower():
            content = "COVID19 data campaign"

    #SP Promotion
    promo = ['CESSDAArchives'] #Keywords for "SP Promotion"
    for word in promo:
        if word.lower() in temp_test.lower():
            content = "SP Promotion"

    #Interview
    interview = ['10questionsto'] #Keywords
    for word in interview:
        if word.lower() in temp_test.lower():
            content = "CESSDA Interviews"

    if 'interview' in temp_test.lower():
        if "cessda" in temp_test.lower():
            content = "CESSDA Interviews"
        elif "cessda_data" in temp_test.lower():
            content = "CESSDA Interviews"
    elif 'interviews' in temp_test.lower():
        if "cessda" in temp_test.lower():
            content = "CESSDA Interviews"
        elif "cessda_data" in temp_test.lower():
            content = "CESSDA Interviews"

    #SP & CESSDA Partner job opportunities
    job = ["JobFairy", 'hiring', 'jobs', 'open positions', 'openpositions', 'open position', 'vacancy']
    for word in job:
        if word.lower() in temp_test.lower():
            content = "SP & CESSDA Partner job opportunities"

    #Newsletter
    newsletter = ['CESSDANewsletter', "CESSDA Newsletter", "CESSDA_Data Newslatter"] #Keywords
    for word in newsletter:
        if word.lower() in temp_test.lower():
            content = "CESSDA Newsletter"
    if 'newsletter' in temp_test.lower():
        if "cessda" in temp_test.lower():
            content = "CESSDA Newsletter"
        elif "cessda_data" in temp_test.lower():
            content = "CESSDA Newsletter"

    #Tour of CESSDA news article
    tour = ["TourofCESSDA"]
    for word in tour:
        if word.lower() in temp_test.lower():
            content = "Tour of CESSDA news article"

    #CESSDA Training events_NEW: phrases and combination of two words
    training = ['CESSDATraining', 'CESSDA Training', 'CESSDA Trainings',
    'CESSDA event', 'CESSDA webinar', 'CESSDA workshop', 'CESSDA online hands-on',
    'TrainTheTrainer Workshop', 'CESSDARoadshow', 'Making Social Science Research Transparent'] #Keywords for "CESSDA Training events (from Training Calendar)"
    for word in training:
        if word.lower() in temp_test.lower():
            content = "CESSDA Training events"

##### Part 3.3: Manually change categories for certain tweets #####
    training_links = ['https://twitter.com/CESSDA_Data/status/1410228924827721732',
    'https://twitter.com/CESSDA_Data/status/1410202883539222534', 'https://twitter.com/CESSDA_Data/status/1410197219895037959',
    'https://twitter.com/CESSDA_Data/status/1410195741075726342', 'https://twitter.com/CESSDA_Data/status/1409831259161849856',
    'https://twitter.com/CESSDA_Data/status/1409468871325618176', 'https://twitter.com/CESSDA_Data/status/1408360324894502913',
    'https://twitter.com/CESSDA_Data/status/1407971207048306691', 'https://twitter.com/CESSDA_Data/status/1405815558428319746',
    'https://twitter.com/CESSDA_Data/status/1404385629207633928', 'https://twitter.com/CESSDA_Data/status/1403355086537969674',
    'https://twitter.com/CESSDA_Data/status/1403289573753561088', 'https://twitter.com/CESSDA_Data/status/1392035387627954176',
    'https://twitter.com/CESSDA_Data/status/1388132531048960000', 'https://twitter.com/CESSDA_Data/status/1387401534401662976',
    'https://twitter.com/CESSDA_Data/status/1387375039419494404', 'https://twitter.com/CESSDA_Data/status/1385590279348973573',
    'https://twitter.com/CESSDA_Data/status/1385142579478548481', 'https://twitter.com/CESSDA_Data/status/1384882112910831620',
    'https://twitter.com/CESSDA_Data/status/1384831114372603905', 'https://twitter.com/CESSDA_Data/status/1383042503335546881',
    'https://twitter.com/CESSDA_Data/status/1382307649165856774', 'https://twitter.com/CESSDA_Data/status/1382264112307179520',
    'https://twitter.com/CESSDA_Data/status/1380538606104817670', 'https://twitter.com/CESSDA_Data/status/1380097334651072512',
    'https://twitter.com/CESSDA_Data/status/1379709744185810949', 'https://twitter.com/CESSDA_Data/status/1379419295675990018',
    'https://twitter.com/CESSDA_Data/status/1376854970318790664', 'https://twitter.com/CESSDA_Data/status/1374726445864415234',
    'https://twitter.com/CESSDA_Data/status/1374698007229132802', 'https://twitter.com/CESSDA_Data/status/1371815964585697280',
    'https://twitter.com/CESSDA_Data/status/1371524801672658948', 'https://twitter.com/CESSDA_Data/status/1369953752388616192',
    'https://twitter.com/CESSDA_Data/status/1366759280989331461', 'https://twitter.com/CESSDA_Data/status/1359468448192094208',
    'https://twitter.com/CESSDA_Data/status/1352605182006181893', 'https://twitter.com/CESSDA_Data/status/1351507700660666369']
    for word in training_links:
        if word.lower() in temp_test.lower():
            content = "CESSDA Training events"

##### Part 3.4: Saving variables as a list to the list #####
    #Final list of lists - save only original tweets
    if tweet_type == "Tweet" and datetime.datetime(2020, 12, 31) < tweet.created_at:
        tweets_list.append([sequence, tweet.created_at, content, tweet_link,
        tweet.user.screen_name, tweet_likes, tweet_retweets, media, tweet_text,
        tweet_type, hashtags])
        print("Tweet ",sequence,"finished. Type: ",tweet_type, " ", tweet.created_at)
        sequence = sequence+1
        #print(tweet.entities)

##### Part 4: Saving lits to the dataframe #####
tweets_df = pd.DataFrame(tweets_list,columns=['Number', 'Date of publication',
'Content', 'Link to tweet', 'Author', 'Likes', 'Retweets', "Media",
'Text', 'Type', 'Hashtags']) #save all data to the dataframe

##### Part 5: Saving dataframe to the excel file #####
writer = pd.ExcelWriter('Data_Twitter1.xlsx') #enter the title
tweets_df.to_excel(writer, 'Sheet1')
writer.save()
