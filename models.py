from pymodm import MongoModel, fields
from pymongo.write_concern import WriteConcern

# creating the Tweets collection
class Tweets(MongoModel):
    tweet = fields.CharField()
    name = fields.CharField()
    handle = fields.CharField()
    created_at = fields.CharField()
    fav_count = fields.IntegerField()
    retweet_count = fields.IntegerField()
    followers = fields.IntegerField()
    friends = fields.IntegerField()
    favorites = fields.IntegerField()

    class Meta:
        write_concern = WriteConcern(j=True)
        connection_alias = 'my-app'
