# Memo

## Introduction

To track the activities of CESSDA on the social network Twitter, among
the main tasks is to collect relevant to the following template:

- Date of publication.

- Content-type according to the internal classification.

- URL Link to the tweet.

- Author.

- Type of the tweet (retweet, reply, tweet).

- Number of Retweets.

- Number of Likes.

- Full text of the Tweet.

- First five hashtags.

- Media used (photo/video).

Accessing data via the free Twitter API will allow extracting some
information automatically. The python code was created to collect tweets
on the CESSDA Twitter account and insert information into the pre-built
template.

In order to be able to run the code, it is essential to apply for the
Twitter Developer Platform
([[https://developer.twitter.com/en/apply-for-access]{.underline}](https://developer.twitter.com/en/apply-for-access))
and receive credentials for APIs access (consumer_key, consumer_secret,
access_key, access_secret).

## Explanation of the coding procedure

The current version of the Python Code:
Twitter_Api_collect_tweets_v0.4_YV.py is available here:
[[https://drive.google.com/file/d/1GqFW24lapfl7jQBx1prqs4hTyYmnjkms/view?usp=sharing]{.underline}](https://drive.google.com/file/d/1GqFW24lapfl7jQBx1prqs4hTyYmnjkms/view?usp=sharing)

The code begins with the importing necessary libraries (tweepy, pandas,
re, datetime) that we are working with (should be installed in advance):

> *import tweepy as tweepy #import tweepy library*
>
> *from tweepy import \**
>
> *import pandas as pd #import pandas*
>
> *import re #import re*
>
> *import datetime*

At the next step, the twitter authentication is required. For this it is
needed to insert the credentials (consumer_key, consumer_secret,
access_key, access_secret) and go through the authentication process:

> *#Twitter Auth Data*
>
> *consumer_key = \"INSERT\"*
>
> *consumer_secret = \"INSERT\"*
>
> *access_key= \"INSERT\"*
>
> *access_secret = \"INSERT\"*
>
> *#Getting Acess to Twitter*
>
> *auth = tweepy.OAuthHandler(consumer_key, consumer_secret)*
>
> *auth.set_access_token(access_key, access_secret)*
>
> *api = tweepy.API(auth,wait_on_rate_limit=True)*
>
> *print(\"Access is granted\")*

For the next step, it is better to define (i) the username of the
Twitter account ("CESSDA_Data"), (ii) the maximum number of collected
tweets (if we insert 290, it means that the last 290 tweets will be
collected) and (iii) the sequence instrumental variable to track the
correct numbering (order) of tweets:

> *username = \"CESSDA_Data\" #Add the twitter account name here!*
>
> *max_tweets = 2000 #Add the max number of collected tweets.*
>
> *sequence = 1 #Number to keep the correct order*

After that, we move to the search of tweets via Tweepy Cursor and create
an empty list to save relevant information in the next step:

> *#Find tweets*
>
> *tweets = tweepy.Cursor(api.user_timeline,
> id=username,tweet_mode=\'extended\',exclude_replies =
> True).items(max_tweets)*
>
> *tweets_list = \[\] #create an empty list*

After the collection of tweets, we start the loop that will go through
each collected tweet and perform certain actions. We start with creating
a tweet link using the tweet id, extracting a number of likes, retweets
and the text without the line breaks:

> *for tweet in tweets:*
>
> *tweet_link = \"https://twitter.com/\" + username + \"/status/\" +
> tweet.id_str #Get link*
>
> *tweet_likes = tweet.favorite_count #Save likes*
>
> *tweet_retweets = tweet.retweet_count #Save retweets*
>
> *tweet_text = tweet.full_text.replace(\"\\n\", \" \") #Save text
> without line breaks*
>
> *tweet_text = tweet_text.replace(\"&amp;\", \"\") #Save text without
> \"&amp;\" elements*
>
> *tweet_text = tweet_text.replace(\" \", \" \") #Save text without
> empty spaces*

Within the loop, we can define the type of the tweets following this
logic: if the test starts with "RT @", then the type is "Retweet; if
there is a status id for the reply, the type is "Reply"; for all other
cases the type is "Tweet" (original tweet). If the type is "Retweet",
then we delete the number of likes and retweets because they indicate
numbers for the original tweet that was retweeted, so this information
is not relevant for the analysis of CESSDA activities:

> *if tweet.full_text.startswith(\'RT @\') is True:*
>
> *tweet_type = \"Retweet\"*
>
> *tweet_likes = None #delete likes for retweets*
>
> *tweet_retweets = None #delete retweets for retweets*
>
> *elif tweet.in_reply_to_status_id_str is not None:*
>
> *tweet_type = \"Reply\"*
>
> *else:*
>
> *tweet_type = \"Tweet\"*

In order to reproduce the same structure of the template, we need to
create empty variables for that information that we will extract at the
next step:

> *content = \"\"*
>
> *hashtags = \"\"*
>
> *media = \"\"*

Then we try to extract 5 first hashtags and save it in a separate scale
variables (separated by spaces):

> *#Extract first 5 hashtags:*
>
> *try:*
>
> *hashtag1 = tweet.entities\[\'hashtags\'\]\[0\]\[\'text\'\]*
>
> *except:*
>
> *hashtag1 = \"\"*
>
> *try:*
>
> *hashtag2 = tweet.entities\[\'hashtags\'\]\[1\]\[\'text\'\]*
>
> *except:*
>
> *hashtag2 = \"\"*
>
> *try:*
>
> *hashtag3 = tweet.entities\[\'hashtags\'\]\[2\]\[\'text\'\]*
>
> *except:*
>
> *hashtag3 = \"\"*
>
> *try:*
>
> *hashtag4 = tweet.entities\[\'hashtags\'\]\[3\]\[\'text\'\]*
>
> *except:*
>
> *hashtag4 = \"\"*
>
> *try:*
>
> *hashtag5 = tweet.entities\[\'hashtags\'\]\[4\]\[\'text\'\]*
>
> *except:*
>
> *hashtag5 = \"\"*
>
> *#Create a separate var that includes first five hashtags*
>
> *hashtags = hashtag1 + \' \' + hashtag2 + \' \' + hashtag3 + \' \' +
> hashtag4 + \' \' + hashtag5*

Based on the first attached media, we classify tweets as a tweet with
photo(s), video(s), without attached media:

> *#Define Media type*
>
> *try:*
>
> *if tweet.entities\[\'media\'\]:*
>
> *if re.search(\"video\",
> tweet.entities\[\'media\'\]\[0\]\[\'expanded_url\'\]):*
>
> *media = \"video\"*
>
> *elif re.search(\"photo\",
> tweet.entities\[\'media\'\]\[0\]\[\'expanded_url\'\]):*
>
> *media = \"photo\"*
>
> *else:*
>
> *media = \"other\"*
>
> *except:*
>
> *media = \"\"*

Then we can define the content type of the tweet based on keywords found
in the text or in the list of hashtags. For example, if the beginning of
the text or hashtags (converted to lower cases) contains "COVID19data"
or "COVID19 datasets" (converted to lower cases), then the content type
is assigned to be "Covid data campaign".

To structure the promotion on Twitter, all publications were grouped
into **nine** main categories and one group "Other" (undefined
category).

1. [CESSDA Training events (from Training Calendar).]{.underline}

2. [DMEG.]{.underline}

3. CESSDA Data Catalogue.

4. COVID19 data campaign.

5. SPs Promotion (*from 01.09*).

6. CESSDA Interviews.

7. SP & CESSDA Partner job opportunities.

8. CESSDA Newsletter.

9. Tour of CESSDA news article.

The use of main and additional keywords (hashtags) indicates the
assignment of a particular tweet to a specific category. Table 1
presents the list of all keywords and corresponding categories. The
logic of assigning a tweet to a category is as follows: if the full text
of the tweet contains a keyword (case insensitive), the tweet is
assigned to the category to which this keyword corresponds. For example,
if the tweet includes "#CESSDATraining" hashtag, then the category is
"CESSDA Training events (from Training Calendar)".

Table 1. Categories of tweets with keywords

  --------------------------------------------------------------------------
  **Category**       **Main keyword**    **Additional keywords**
  ------------------ ------------------- -----------------------------------
  CESSDA Training    #CESSDATraining     CESSDA webinar, CESSDA workshop,
  events (from                           CESSDA event, CESSDA training(s),
  Training Calendar)                     CESSDARoadshow, Making Social
                                         Science Research Transparent

  DMEG               #DMMonday           DataManagement ExpertGuide, DMEG,
                                         Data Management Expert Guide

  CESSDA Data        #CESSDAData         CESSDA Data Catalogue,
  Catalogue                              DataCatalogue, Data Catalogue,
                                         CESSDADataCatalogue

  COVID19 data       #COVID19data        COVID19 datasets
  campaign

  SPs Promotion      #CESSDAArchives
  (from 01.09)

  CESSDA Interviews  #10questionsto      "CESSDA" & "Interview"

  SPs & CESSDA       #JobFairy           hiring, jobs, open positions,
  Partner job                            openpositions, open position,
  opportunities                          vacancy

  CESSDA Newsletter  #CESSDANewsletter   CESSDA & Newsletter, CESSDA_data &
                                         Newsletter

Tour of CESSDA     #TourofCESSDA
  news article
  --------------------------------------------------------------------------

In case one tweet contains keywords from more than one category, the
tweet is attributed to the most general category that describes the main
promotion goal of the tweet. This condition is created in order to
attribute tweets only to the single most important category. For
example, suppose a tweet is related to the training on data management.
In that case, this tweet falls into the category "CESSDA Training events
(from Training Calendar)", because it is of the highest importance in
terms of content (and not into the category "DMEG"). Similarly, if a
tweet promotes the CESSDA newsletter that contains the CT events, then
the category of the analysis is "CESSDA Newsletter" (and not "CESSDA
Training events (from Training Calendar)").

The hierarchy (importance) of categories is considered as follows: DMEG
\> CESSDA Data Catalogue \> COVID19 data campaign \> SPs Promotion (from
01.09) \> CESSDA Interviews \> SPs & CESSDA Partner job opportunities \>
CESSDA Newsletter \> Tour of CESSDA news article \> CESSDA Training
events (from Training Calendar). This condition is created in order to
attribute tweets only to the single most important category.

The logic is implemented for all content types using this code in the
loop:

> *#Create a variable that contains text, hashtags and tweets links
> together*
>
> *temp_test = tweet_text.replace(\"@\",\" \") + \" \" + hashtags + \"
> \" + tweet_link*
>
> *temp_test = temp_test.replace (\" \", \" \")*
>
> *#DMEG*
>
> *dmeg = \[\'DMMonday\', \'DataManagement ExpertGuide\', \'DMEG\',
> \'Data Management Expert Guide\', \'DataManagementExpertGuide\',
> \'Management Expert Guide\'\] #Keywords for DMEG*
>
> *for word in dmeg:*
>
> *if word.lower() in temp_test.lower():*
>
> *content = \"DMEG\"*
>
> *#CDC*
>
> *cdc = \[\'CESSDA Data Catalogue\', \'DataCatalogue\', \'Data
> Catalogue\', \'#CESSDAData\', \'CESSDADataCatalogue\', \'CESSDA_Data
> Catalogue\', \'CESSDA_DataCatalogue\'\] #Keywords for \"CESSDA Data
> Catalogue\"*
>
> *for word in cdc:*
>
> *if word.lower() in temp_test.lower():*
>
> *content = \"CESSDA Data Catalogue\"*
>
> *#COVID*
>
> *сovid = \[\'COVID19data\', \'COVID19 datasets\'\] #Keywords for
> \"COVID19 data campaign\"*
>
> *for word in сovid:*
>
> *if word.lower() in temp_test.lower():*
>
> *content = \"COVID19 data campaign\"*
>
> *#SP Promotion*
>
> *promo = \[\'CESSDAArchives\'\] #Keywords for \"SP Promotion\"*
>
> *for word in promo:*
>
> *if word.lower() in temp_test.lower():*
>
> *content = \"SP Promotion\"*
>
> *#Interview*
>
> *interview = \[\'10questionsto\'\] #Keywords*
>
> *for word in interview:*
>
> *if word.lower() in temp_test.lower():*
>
> *content = \"CESSDA Interviews\"*
>
> *if \'interview\' in temp_test.lower():*
>
> *if \"cessda\" in temp_test.lower():*
>
> *content = \"CESSDA Interviews\"*
>
> *elif \"cessda_data\" in temp_test.lower():*
>
> *content = \"CESSDA Interviews\"*
>
> *elif \'interviews\' in temp_test.lower():*
>
> *if \"cessda\" in temp_test.lower():*
>
> *content = \"CESSDA Interviews\"*
>
> *elif \"cessda_data\" in temp_test.lower():*
>
> *content = \"CESSDA Interviews\"*
>
> *#SP & CESSDA Partner job opportunities*
>
> *job = \[\"JobFairy\", \'hiring\', \'jobs\', \'open positions\',
> \'openpositions\', \'open position\', \'vacancy\'\]*
>
> *for word in job:*
>
> *if word.lower() in temp_test.lower():*
>
> *content = \"SP & CESSDA Partner job opportunities\"*
>
> *#Newsletter*
>
> *newsletter = \[\'CESSDANewsletter\', \"CESSDA Newsletter\",
> \"CESSDA_Data Newslatter\"\] #Keywords*
>
> *for word in newsletter:*
>
> *if word.lower() in temp_test.lower():*
>
> *content = \"CESSDA Newsletter\"*
>
> *if \'newsletter\' in temp_test.lower():*
>
> *if \"cessda\" in temp_test.lower():*
>
> *content = \"CESSDA Newsletter\"*
>
> *elif \"cessda_data\" in temp_test.lower():*
>
> *content = \"CESSDA Newsletter\"*
>
> *#Tour of CESSDA news article*
>
> *tour = \[\"TourofCESSDA\"\]*
>
> *for word in tour:*
>
> *if word.lower() in temp_test.lower():*
>
> *content = \"Tour of CESSDA news article\"*
>
> *#CESSDA Training events_NEW: phrases and combination of two words*
>
> *training = \[\'CESSDATraining\', \'CESSDA Training\', \'CESSDA
> Trainings\',*
>
> *\'CESSDA event\', \'CESSDA webinar\', \'CESSDA workshop\', \'CESSDA
> online hands-on\',*
>
> *\'TrainTheTrainer Workshop\', \'CESSDARoadshow\', \'Making Social
> Science Research Transparent\'\] #Keywords for \"CESSDA Training
> events (from Training Calendar)\"*
>
> *for word in training:*
>
> *if word.lower() in temp_test.lower():*
>
> *content = \"CESSDA Training events\"*

If it is necessary to manually assign certain tweets to certain
categories after additional manual verification, this is based on the
use of a unique link to a tweet according to the following pattern:

> *#Manually change categories for certain tweets*
>
> *training_links =
> \[\'https://twitter.com/CESSDA_Data/status/1410228924827721732\',*
>
> *\'https://twitter.com/CESSDA_Data/status/1410202883539222534\',
> \'https://twitter.com/CESSDA_Data/status/1410197219895037959\',\.....\]*
>
> *for word in training_links:*
>
> *if word.lower() in temp_test.lower():*
>
> *content = \"CESSDA Training events\"*

As the final step in the loop, we append only original tweets (type =
"Tweet") to the list with the relevant information that were published
in 2021, print the notification and update the sequence:

> *if tweet_type == \"Tweet\" and datetime.datetime(2020, 12, 31) \<
> tweet.created_at:*
>
> *tweets_list.append(\[sequence, tweet.created_at, content,
> tweet_link,*
>
> *tweet.user.screen_name, tweet_likes, tweet_retweets, media,
> tweet_text,*
>
> *tweet_type, hashtags\])*
>
> *print(\"Tweet \",sequence,\"finished. Type: \",tweet_type, \" \",
> tweet.created_at)*
>
> *sequence = sequence+1*

After that we finish the loop, save the data to the dataframe and export
it to the excel file:

> *tweets_df = pd.DataFrame(tweets_list,columns=\[\'Number\', \'Date of
> publication\',*
>
> *\'Content\', \'Link to tweet\', \'Author\', \'Likes\', \'Retweets\',
> \"Media\",*
>
> *\'Text\', \'Type\', \'Hashtags\'\]) #save all data to the dataframe*
>
> *#Saving dataframe to the excel file*
>
> *writer = pd.ExcelWriter(\'Data_Twitter1.xlsx\') #enter the title*
>
> *tweets_df.to_excel(writer, \'Sheet1\')*
>
> *writer.save()*

This python code presents [only an extensive example]{.underline} of the
possible actions that can be done automatically in python to extract the
last N\* (any number from 1) of tweets from a certain twitter account
with free Twitter API access. This code is **not a perfect solution**.
There are a lot of ways how it is possible to improve it by advanced
cleaning, making it more compact, or adding new functions.
