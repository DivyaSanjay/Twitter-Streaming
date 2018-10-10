# Importing the modules
import pandas as pd
import pymongo
import dateutil.parser
import requests
import tweepy

from datetime import datetime
from flask import Flask, request
from flask_jsonpify import jsonify
from flask_restful import Resource, Api
from pymodm.connection import connect
from tweepy import OAuthHandler, Stream, API
from tweepy.streaming import StreamListener

from models import Tweets

# Twitter API credentials
ckey = "**"
csecret = "**"
atoken = "**"
asecret = "**"

# Authenticating Twitter API
auth = OAuthHandler(ckey, csecret)
auth.set_access_token(atoken, asecret)

# Connecting to MongoDB database
connect("mongodb://localhost:27017/Twitter", alias="my-app")

app = Flask(__name__)
api = Api(app)
twitter_api = API(auth)

# All column names
valid_cols = ['tweet', 'created_at', 'name', 'handle', 'fav_count', 'retweet_count', 'followers', 'friends', 'favorites']

class Listener(StreamListener):
    '''
    class implementing streaming of Twitter data
    '''
    def __init__(self,api,count):
        self.count = count
        self.api = api
    def on_status(self, status):
        if(self.count!=0):
            print(self.count)
            tweet = status.text
            created_at = status.created_at
            name = status.user.name
            handle = status.user.screen_name
            fav_count = status.favorite_count
            retweet_count = status.retweet_count
            followers = status.user.followers_count
            friends = status.user.friends_count
            favorites = status.user.favourites_count
            Tweets(tweet=tweet, created_at=created_at, name=name, handle=handle, fav_count=fav_count,
                   retweet_count=retweet_count, followers=followers, friends=friends, favorites=favorites).save()
            self.count -= 1
            return True
        else:
            return False

def show_result(query):
    '''
    function to convert queryset into list of dictionaries
    '''
    result = []
    for i in query:
        d = {'tweet': i.tweet, 'created_at': i.created_at, 'name': i.name, 'handle': i.handle,
             'favorites_count': i.fav_count, 'retweet_count': i.retweet_count, 'followers': i.followers, 
             'friends': i.friends, 'favorites': i.favorites }
        result.append(d)
    return result

def paginate(result,url_next,url_prev, skip, limit, count):
    '''
    Function to implement pagination
    '''
    if skip==0:
        response = {'data': result, 'skip':skip, 'limit': limit, 'next': url_next}
    elif skip>0 and skip<count-1:
        response = {'data': result, 'skip':skip, 'limit': limit, 'prev': url_prev, 'next': url_next}
    elif skip>=count:
        response = {'error':'Request exceeding limit of table'}
    elif skip+limit>=count-1:
        response = {'data': result, 'skip':skip, 'limit': limit, 'prev': url_prev}
    elif skip>=count:
        response = {'error': 'invalid query parameters'}
    else:
        response = {'error': 'invalid query parameters'}
    return response

class Export_CSV(Resource):
    '''
    class to export database as csv file
    '''
    def get(self):
        query = list(Tweets.objects.all())
        if query:
            result = []
            for i in query:
                d = {'tweet': i.tweet.encode('utf-8'), 'created_at': i.created_at, 'name': i.name, 'handle': i.handle,
                     'favorites_count': i.fav_count, 'retweet_count': i.retweet_count, 'followers': i.followers, 
                     'friends': i.friends, 'favorites': i.favorites }
                result.append(d)
            df = pd.DataFrame(result)
            df.to_csv('F:/ML/tweets.csv', header=True, index=False)      
            return jsonify({'message':'The file has been exported in csv format'})
        else:
            return jsonify({'error':'No data to be exported'})

# Date Range filter for API 2
class Filter_Date(Resource):
    '''
    class to filter the data based on a date range with sorting
    '''
    def get(self, date1, date2, sort_by, order):
        if sort_by not in valid_cols:
            return jsonify({'error':'Please enter one of the following {}'.format(valid_cols)})

        skip = int(request.args.get('skip', 0))
        limit = int(request.args.get('limit', 3))
        count = Tweets.objects.count()

        if order=='asc': 
            order_sort = pymongo.ASCENDING
        elif order=='desc': 
            order_sort = pymongo.DESCENDING
        else:
            return jsonify({'error':'Order must be either asc or desc'})

        query = list(Tweets.objects.raw({'created_at':{"$gte": date1+" 00:00:00","$lte": date2+"23:59:59"}}).order_by([(sort_by, order_sort)]).skip(skip).limit(limit))
        result = show_result(query)
        url_next = '/filter_date/{}/{}/{}/{}?skip={}&limit={}'.format(date1, date2,sort_by,order, skip+limit, limit)
        url_prev = '/filter_date/{}/{}/{}/{}?skip={}&limit={}'.format(date1, date2, sort_by,order, skip-limit, limit)
        response = paginate(result, url_next, url_prev, skip, limit, count)
        if not result:
            return jsonify({'message':'We did not find anything for this filter'})
        return jsonify(response)


class Filter_Integer(Resource):
    '''
    class to filter data based on the integer columns with sorting
    '''
    def get(self, column, operator, number, sort_by, order):
        if sort_by not in valid_cols:
            return jsonify({'error':'Please enter one of the following {}'.format(valid_cols)})

        skip = int(request.args.get('skip', 0))
        limit = int(request.args.get('limit', 3))
        count = Tweets.objects.count()
        if column in ['fav_count', 'retweet_count', 'followers', 'favorites', 'friends']:
            if order=='asc':
                order_sort = pymongo.ASCENDING
            elif order=='desc':
                order_sort = pymongo.DESCENDING
            else:
                return jsonify({'error':'order must be either asc or desc'})
            
            if operator=='<':
                query = list(Tweets.objects.raw( {column: {'$lt': int(number)}}).order_by([(sort_by, order_sort)]).skip(skip).limit(limit))
            elif operator=='=':
                query = list(Tweets.objects.raw( {column: int(number)}).skip(skip).limit(limit))
            elif operator=='>':
                query = list(Tweets.objects.raw( {column: {'$gt': int(number)}}).order_by([(sort_by, order_sort)]).skip(skip).limit(limit))
            else :
                result = {'error':"Please enter one of the following operators: '<','>','='"}
                return jsonify(result)
            
            result = show_result(query)
            url_next = '/filter_integer/{}/{}/{}/{}/{}?skip={}&limit={}'.format(column, operator, number, sort_by, order, skip+limit,limit)
            url_prev = '/filter_integer/{}/{}/{}/{}/{}?skip={}&limit={}'.format(column, operator, number, sort_by, order, skip-limit,limit)
            response = paginate(result, url_next, url_prev, skip, limit, count)
            
            if not result: #len(result)==0
                response = {'message': 'We did not find anything for this filter'}
        else:
            response = {'error': "Please enter one of the following:'fav_count', 'retweet_count', 'followers', 'favorites', 'friends'"}
        return jsonify(response)

class Filter_String(Resource):
    '''
    class to filter data based on the string columns with sorting
    '''
    def get(self, column, operator, search_text, sort_by, order):
        if sort_by not in valid_cols:
            return jsonify({'error':'Please enter one of the following {}'.format(valid_cols)})

        if column in ['name','handle','tweet']:
            skip = int(request.args.get('skip', 0))
            limit = int(request.args.get('limit', 3))
            count = Tweets.objects.count()
            if order=='asc':
                order_sort = pymongo.ASCENDING
            elif order=='desc':
                order_sort = pymongo.DESCENDING
            else:
                return jsonify({'error':'order must be either asc or desc'})
        
            if operator == 'starts with':
                query = list(Tweets.objects.raw({column:{"$regex":"^{}".format(search_text), "$options":"$i"}}).order_by([(sort_by, order_sort)]).skip(skip).limit(limit))
            elif operator == 'ends with':
                query = list(Tweets.objects.raw({column:{"$regex":"{}$".format(search_text), "$options":"$i"}}).order_by([(sort_by, order_sort)]).skip(skip).limit(limit))
            elif operator == 'contains':
                query = list(Tweets.objects.raw({column:{"$regex":search_text, "$options":"$i"}}).order_by([(sort_by, order_sort)]).skip(skip).limit(limit))
            elif operator == 'is':
                query = list(Tweets.objects.raw( {column: search_text} ).order_by([(sort_by, order_sort)]).skip(skip).limit(limit))
            else:
                return jsonify({'error':"operator must be one of 'starts with', 'ends with', 'is', 'contains'"})


            result = show_result(query)
            url_next = '/filter_string/{}/{}/{}/{}/{}?skip={}&limit={}'.format(column, operator, search_text, sort_by,
                                                                               order, skip+limit,limit)
            url_prev = '/filter_string/{}/{}/{}/{}/{}?skip={}&limit={}'.format(column, operator, search_text, sort_by,
                                                                               order, skip-limit,limit)
            response = paginate(result, url_next, url_prev, skip, limit, count)
            
            if not result: #len(result)==0
                response = {'message': 'We did not find anything for this filter'}
            return jsonify(response)
        else:
            response = {'error': "Please enter one of the following:'name', 'handle', 'tweet'"}
            return jsonify(response)

class Get_Count(Resource):
    '''
    class to get count of all tweets
    '''
    def get(self):
        query = Tweets.objects.count()
        return jsonify({'message': "The total number of tweets is {}".format(query)})

class Get_Data(Resource): 
    '''
    class to access all the stored data with sorting
    '''
    def get(self, sort_by, order):
        if sort_by not in valid_cols:
            return jsonify({'error':'Please enter one of the following {}'.format(valid_cols)})
        skip = int(request.args.get('skip', 0))
        limit = int(request.args.get('limit', 3))
        count = Tweets.objects.count()
        if order=='asc':
            order_sort = pymongo.ASCENDING
        elif order=='desc':
            order_sort = pymongo.DESCENDING
        else:
            return jsonify({'error':'order must be either asc or desc'})
        query = list(Tweets.objects.all().order_by([(sort_by, order_sort)]).skip(skip).limit(limit))
        result = show_result(query)
        if result:
            url_next = '/get_data/{}/{}?skip={}&limit={}'.format(sort_by, order,skip+limit,limit)
            url_prev = '/get_data/{}/{}?skip={}&limit={}'.format(sort_by, order,skip-limit,limit)
            response = paginate(result, url_next, url_prev, skip, limit, count)
        else:
            response = {'message':'no data to display'}
        return jsonify(response)

class Stream_Data(Resource):
    '''
    class to stream specified number of tweets according to search word
    '''
    def get(self, hash_tag, count):
        count = int(count)
        try:
            l = Listenr(twitter_api, count)
            twitterStream = Stream(auth, l)
            twitterStream.filter(track=[hash_tag])
            return jsonify({'message':'The required number of tweets for the specified hashtag have been stored!'})
        except (requests.exceptions.ConnectionError, tweepy.error.TweepError) as e:
            return jsonify({'error': 'Please check your Internet connection'})
            
# Adding resources for all APIs
api.add_resource(Export_CSV, '/export_csv') #API 3
api.add_resource(Filter_Date, '/filter_date/<date1>/<date2>/<order>/<sort_by>') #Filter by date range
api.add_resource(Filter_Integer, '/filter_integer/<column>/<operator>/<number>/<sort_by>/<order>') #Filter by integer values
api.add_resource(Filter_String, '/filter_string/<column>/<operator>/<search_text>/<sort_by>/<order>') #Filter by text
api.add_resource(Get_Count, '/get_count') # API to get count of all results
api.add_resource(Get_Data, '/get_data/<sort_by>/<order>') # API 2
api.add_resource(Stream_Data, '/stream_data/<hash_tag>/<count>') # API 1

if __name__ == '__main__':
    app.run(port='5002', debug=True)
