from telegram.ext import Updater, CommandHandler
import telegram

import tweepy
import pymongo

import threading
import requests
import urllib.parse
from time import sleep


# twitter api

auth = tweepy.OAuthHandler('consumer_token', 'consumer_secret')
auth.set_access_token('key', 'secret')
api = tweepy.API(auth)

# connect to mongodb

myclient = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = myclient["twitter"]
mycol = mydb["pages"]

# telegram bot updater

TOKEN = 'TOKEN'
updater = Updater(TOKEN)
dispatcher = updater.dispatcher


admins = [] # list of allowed chat IDs (int)


def twitter_updater():

	while True:

		pages = mycol.find()

		for page in pages:

			sn = page['screen_name']

			tweets = api.user_timeline(sn, count = 1 if not page['last_tweet'] else 6, tweet_mode="extended")

			tweets_to_send = []

			for tweet in tweets:
				if tweet.id_str == page['last_tweet']:
					break
				tweets_to_send.append(tweet)

			
			for tweet in tweets_to_send:
				if hasattr(tweet, 'retweeted_status'):
					tweet_text = tweet.retweeted_status.full_text
				else:
					tweet_text = tweet.full_text

				if 'https://t.co/' in tweet_text:
					tweet_text = tweet_text.replace(tweet_text[tweet_text.find('https://t.co/'):], '')

				permalink = 'https://twitter.com/' + sn + '/status/' + tweet.id_str
				to_send = permalink + '\n\n' + tweet_text

				for cid in page['chats']:
					queryString = urllib.parse.urlencode({'chat_id': cid, 'text': to_send})
					requests.get(('https://api.telegram.org/bot%s/sendMessage?' % TOKEN) + queryString)

			if tweets_to_send:
				mycol.update_one({'screen_name': sn}, {'$set': {'last_tweet' : tweets_to_send[0].id_str }})

			sleep(5)

		sleep(60)



###################################
########## BOT FUNCTIONS ##########
###################################



def start(bot, update):
	cid = update.message.chat_id
	fname = update.message.chat.first_name
	if cid in cids:
		bot.sendMessage(chat_id=cid, text='Welcome, ' + fname)


def add_page(bot, update):
	cid = update.message.chat_id
	if cid > 0 and cid not in cids:
		return
	text = update.message.text
	parms = text.split(' ')[1:]
	screen_name = ''.join(parms)
	try:
		api.get_user(screen_name=screen_name)
	except:
		bot.sendMessage(chat_id=cid, text='page not found !')
		return
	update_result = mycol.update_one({'screen_name': screen_name}, {'$push': {'chats': cid}})
	if not update_result.modified_count:
		page = {'screen_name': screen_name, 'chats': [cid], 'last_tweet': ''}
		mycol.insert_one(page)
	bot.sendMessage(chat_id=cid, text='page added !')
	

def pages_list(bot, update):
	cid = update.message.chat_id
	if cid > 0 and cid not in cids:
		return
	pages = list(mycol.find({'chats': {'$all':[cid]}}))
	if pages:
		to_send = 'chat id: %s \n\nlist of pages:\n\n' % cid
		for page in pages:
			to_send += '<a href="https://twitter.com/%s">%s</a> \n' % (page['screen_name'], page['screen_name'])
		bot.sendMessage(chat_id=cid, text=to_send, parse_mode=telegram.ParseMode.HTML, disable_web_page_preview=True)
	else:
		bot.sendMessage(chat_id=cid, text='no pages yet !')


def remove_page(bot, update):
	cid = update.message.chat_id
	if cid > 0 and cid not in cids:
		return
	text = update.message.text
	parms = text.split(' ')[1:]
	screen_name = ''.join(parms)
	page = mycol.find_one({'screen_name': screen_name, 'chats': {'$all': [cid]}})
	if not page:
		bot.sendMessage(chat_id=cid, text='page not found !')
	elif len(page['chats']) == 1:
		mycol.delete_one({'screen_name': screen_name})
		bot.sendMessage(chat_id=cid, text='page removed !')
	else:
		mycol.update_one({'screen_name': screen_name}, {'$pull': {'chats': cid}})
		bot.sendMessage(chat_id=cid, text='page removed !')


##############################
########## COMMANDS ##########
##############################

dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('add', add_page))
dispatcher.add_handler(CommandHandler('pages', pages_list))
dispatcher.add_handler(CommandHandler('remove', remove_page))

# start twitter updater

twitter_thread = threading.Thread(target=twitter_updater)
twitter_thread.start()

# start telegram bot updater

updater.start_polling()
updater.idle()
