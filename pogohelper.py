
from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, ParseMode, Bot)
from telegram.ext import (Updater, CommandHandler, MessageHandler, Filters, RegexHandler,
                          ConversationHandler, Job)
from functools import wraps
from datetime import datetime, timedelta

import logging
import json
import pprint
import sqlite3
import time
import os
import sys
import ast
import re

# Default language
default_language = 1 # 1 - English, 2 - Italian, 3 - Dutch

# Admins that are enabled to restart the bot with /r command
LIST_OF_ADMINS = []
fileadmin = open('admins.txt','r')
temp = fileadmin.read().splitlines()
fileadmin.close()
for line in temp:
    LIST_OF_ADMINS.append(int(line))

# Def to build a dynamic reply menu
def build_menu(buttons,
               n_cols,
               header_buttons=None,
               footer_buttons=None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, header_buttons)
    if footer_buttons:
        menu.append(footer_buttons)
    return menu

# Def to return a datetime rounded to a specific delta
def ceil_dt(dt, delta):
    return dt + (datetime.min - dt) % delta

# Enable logs
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

# Load TOKEN ID from file
with open('token_id') as token_file:
    token_id = token_file.read()

# Load authorized users
with open('authorized.json') as data_file:    
    users = json.load(data_file)
# Load blocked users
with open('blocked.json') as data_file:
    blocked_users = json.load(data_file)

# Open database connection
conn = sqlite3.connect('pogohelper.db')
# Load BOSS names
raidboss = []
sel = "SELECT DISTINCT(BOSS) FROM RAIDBOSS ORDER BY BOSS;"
cursor = conn.execute(sel)
for row in cursor:
    raidboss.append(row[0])
# Load available languages
languages = []
languages_id = []
sel = "SELECT ID,LANGUAGE FROM LANGUAGES;"
cursor = conn.execute(sel)
for row in cursor:
    languages.append(str(row[1]).lower())
    languages_id.append(int(row[0]))
# Close db connection
conn.close()

# Conversation handler possible status
TEAM, CONFIRM, CONFIRMYESNO, RAID, RAIDEDIT, RAIDFRIENDS, RAIDPREFERREDTIME, USERLANGUAGE, TYPING_REPLY, TYPING_LOCATION = range(10)

# Custom reply keyboards
def build_custom_keyboards():
    # Build custom keyboars with selected language
    global team_markup
    global confirm_markup
    global confirmok_markup
    global confirmyesno_markup
    global raid_markup
    global raidboss_markup
    global raidbossexpire
    global raidbossexpire_markup
    global sqlexpire
    global raid_friends_markup
    team_reply_keyboard = language["team_reply_keyboard"]
    team_markup = ReplyKeyboardMarkup(team_reply_keyboard, one_time_keyboard=True)
    
    confirm_reply_keyboard = language["confirm_reply_keyboard"]
    confirm_markup = ReplyKeyboardMarkup(confirm_reply_keyboard, one_time_keyboard=True)
    
    confirmok_reply_keyboard = language["confirmok_reply_keyboard"]
    confirmok_markup = ReplyKeyboardMarkup(confirmok_reply_keyboard, one_time_keyboard=True)
    
    confirmyesno_reply_keyboard = language["confirmyesno_reply_keyboard"]
    confirmyesno_markup = ReplyKeyboardMarkup(confirmyesno_reply_keyboard, one_time_keyboard=True)
    
    raid_reply_keyboard = language["raid_reply_keyboard"]
    raid_markup = ReplyKeyboardMarkup(raid_reply_keyboard, one_time_keyboard=True)
    
    raidboss_reply_keyboard = [KeyboardButton(s) for s in raidboss]
    raidboss_markup = ReplyKeyboardMarkup(build_menu(raidboss_reply_keyboard, n_cols=3))
    
    raidbossexpire = language["raidbossexpire"]
    raidbossexpire_reply_keyboard = language["raidbossexpire_reply_keyboard"]
    raidbossexpire_markup = ReplyKeyboardMarkup(raidbossexpire_reply_keyboard, one_time_keyboard=True)
    sqlexpire = ['+30 Minute','+45 Minute','+60 Minute','+75 Minute','+90 Minute','+105 Minute','+120 Minute']
    
    raid_friends_reply_keyboard = language["raid_friends_reply_keyboard"]
    raid_friends_markup = ReplyKeyboardMarkup(raid_friends_reply_keyboard, resize_keyboard=True, one_time_keyboard=True)

    return True

# Restricted access to some specific command
def restricted(func):
    @wraps(func)
    def wrapped(bot, update, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in LIST_OF_ADMINS:
            print("Unauthorized access denied for {}.".format(user_id))
            return
        return func(bot, update, *args, **kwargs)
    return wrapped


# Restart command definition
@restricted
def restart(bot, update):
    bot.send_message(update.message.chat_id, "Bot is restarting...")
    time.sleep(0.2)
    os.execl(sys.executable, sys.executable, *sys.argv)

# Convert a list into a multiline string
def facts_to_str(user_data):
    facts = list()

    for key, value in user_data.items():
        if key != 'choice' and key != 'job_delete_old_raids' and key != 'job_notifications':
            facts.append('%s - %s' % (key, value))

    return "\n".join(facts).join(['\n', '\n'])


# Start command
def start(bot, update, job_queue, user_data):
    # Check if user is authorized
    #pprint.pprint(users)
    #if str(update.message.chat_id) in users: # uses authorized.json
    if not str(update.message.chat_id) in blocked_users: # uses blocked.json
        # Check if user is already registered in database
        # Open database connection
        conn = sqlite3.connect('pogohelper.db')
        sel = "SELECT NAME,LANGUAGE FROM USERS WHERE ID = %d;" % (update.message.chat_id)
        cursor = conn.execute(sel)
        present = 0
        default_language = 1 # it will be changed in the next cycle
        for row in cursor:
            name = row[0]
            present = 1
            default_language = int(row[1])
        # Close db connection
        conn.close()

        # Load language file
        global language
        with open('languages/'+str(languages[languages_id.index(default_language)]).lower()+'.json') as language_file:
            language = json.load(language_file)
        build_custom_keyboards()

        # if a user is already registered
        if present == 1:
            update.message.reply_text(language["welcome1"] % (name),
                                      reply_markup=raid_markup)
            sel = "SELECT NOTIFICATIONS FROM USERS WHERE ID = %d;" % (update.message.chat_id)
            conn = sqlite3.connect('pogohelper.db')
            cursor = conn.execute(sel)
            for row in cursor:
                if row[0] == 1 or row[0] == True:
                    job = job_queue.run_repeating(notify_raids, 60, context=update.message.chat_id)
                    user_data['job_notifications'] = job
            conn.close()
            return RAID
        else: # if the user is not already registered
            update.message.reply_text(language["welcome2"])

            return TYPING_REPLY
    else:
        update.message.reply_text(
            "User not authorized! Please ask for authorization with your ID:"
            "%s"
            % update.message.chat_id)
        return ConversationHandler.END


def received_information(bot, update, user_data):
    global language
    global raidbossexpire
    if not 'choice' in user_data:
        user_data['choice'] = "username"
    text = update.message.text
    category = user_data['choice']
    if not (text == language["confirmok_reply_keyboard"][0][0] and category == "gym"):
      user_data[category] = text
    #del user_data['choice']
    #pprint.pprint(update.message.from_user)

    if category == "username":
        answer = language["text_ok"]+"\n%s\n"+language["ask_team"]
        update.message.reply_text(answer % facts_to_str(user_data),
                                  reply_markup=team_markup)
        user_data['choice'] = "team"
        return TEAM
    elif category == "team":
        answer = language["text_ok"]+"\n%s\n"+language["ask_level"]
        update.message.reply_text(answer % facts_to_str(user_data),
                                  reply_markup=ReplyKeyboardRemove())
        user_data['choice'] = "level"
        return TYPING_REPLY
    elif category == "level":
        if text.isdigit():
            if int(text) > 0 and int(text) <= 40:
                userlanguage_reply_keyboard = [KeyboardButton(s) for s in languages]
                userlanguage_markup = ReplyKeyboardMarkup(build_menu(userlanguage_reply_keyboard, n_cols=3))
                update.message.reply_text(language["ask_language"],
                                          reply_markup=userlanguage_markup)
                user_data['choice'] = "language"
                return USERLANGUAGE
            else:
                update.message.reply_text(language["wrong_level"])
                user_data['choice'] = "level"
                return TYPING_REPLY
        else:
            update.message.reply_text(language["wrong_level"])
            user_data['choice'] = "level"
            return TYPING_REPLY
    elif category == "language":
        answer = language["text_ok"]+"\n%s\n"+language["ask_confirm"]
        update.message.reply_text(answer % facts_to_str(user_data),
                                  reply_markup=confirm_markup)
        user_data['choice'] = "confirm"
        return CONFIRM
    elif category == "confirm":
        if text == language["confirm_reply_keyboard"][1][0]:
            user_data.clear()
            #del user_data['username']
            #del user_data['level']
            #del user_data['team']
            user_data['choice'] = "username"
            update.message.reply_text(language["text_restart"])
            return TYPING_REPLY
        elif text == language["confirm_reply_keyboard"][0][0]:
            ins = "INSERT OR IGNORE INTO USERS (ID,NAME,TEAM,LEVEL,FIRSTNAME,SURNAME,USERNAME,LANGUAGE) \
                   VALUES (%d, '%s', '%s', %d, '%s', '%s', '%s', %d );" % (update.message.chat_id, user_data['username'], \
                                                                           user_data['team'], int(user_data['level']), \
                                                                           update.message.from_user.first_name,
                                                                           update.message.from_user.last_name,
                                                                           update.message.from_user.username,
                                                                           int(languages_id[languages.index(user_data['language'])]))
            upd = "UPDATE USERS SET NAME = '%s', TEAM = '%s', LEVEL = %d, FIRSTNAME = '%s', SURNAME = '%s', USERNAME = '%s', LANGUAGE = %d \
                   WHERE ID = %d;" % (user_data['username'], user_data['team'], int(user_data['level']), \
                                      update.message.from_user.first_name, update.message.from_user.last_name, \
                                      update.message.from_user.username, \
                                      int(languages_id[languages.index(user_data['language'])]), \
                                      update.message.chat_id)
            # Open database connection
            conn = sqlite3.connect('pogohelper.db')
            conn.execute(ins)
            conn.execute(upd)
            conn.commit()
            # Close database connection
            conn.close()

            default_language = int(languages_id[languages.index(user_data['language'])])
            # Load language file
            with open('languages/'+str(languages[languages_id.index(default_language)]).lower()+'.json') as language_file:
                language = json.load(language_file)
            build_custom_keyboards()
            update.message.reply_text(language["text_save"],
                                      reply_markup=raid_markup)
            del user_data['username']
            del user_data['level']
            del user_data['team']
            del user_data['confirm']
            del user_data['language']
            return RAID
                                      
        else:
            answer = language["generic_error"]+"\n%s\n"+language["ask_confirm"]
            update.message.reply_text(answer % facts_to_str(user_data),
                                      reply_markup=confirm_markup)
            user_data['choice'] = "confirm"
            return CONFIRM
    elif category == "raidboss":
        if not text in raidboss:
            update.message.reply_text(language["boss_unavailable"],
                                      reply_markup=raidboss_markup)
            user_data['choice'] = "raidboss"
            return TYPING_REPLY
        else:
            answer = language["text_ok"]+"\n%s\n"+language["ask_location"]
            update.message.reply_text(answer % facts_to_str(user_data),
                                      reply_markup=ReplyKeyboardRemove())
            user_data['choice'] = "position"
            return TYPING_LOCATION
    elif category == "position":
        if update.message.location == None:
            update.message.reply_text(language["location_error"],
                                      reply_markup=ReplyKeyboardRemove())
            user_data['choice'] = "position"
            return TYPING_REPLY
        else:
            user_data[category] = str(update.message.location)
            answer = language["text_ok"]+"\n%s\n"+language["raid_expire"]
            update.message.reply_text(answer % facts_to_str(user_data),
                                      reply_markup=raidbossexpire_markup)
            user_data['choice'] = "expire"
            return TYPING_REPLY
    elif category == "expire":
        if not text in raidbossexpire:
            update.message.reply_text(language["raid_expire_error"],
                                      reply_markup=raidbossexpire_markup)
            user_data['choice'] = "expire"
            return TYPING_REPLY
        else:
            answer = language["text_ok"]+"\n%s\n"+language["raid_gym_text"]
            update.message.reply_text(answer % facts_to_str(user_data),
                                      reply_markup=ReplyKeyboardRemove())
            user_data['choice'] = "gym"
            return TYPING_REPLY
    elif category == "gym":
        if text != language["confirm_reply_keyboard"][0][0]:
            answer = language["text_ok"]+"\n%s\n"+language["raid_gym_confirm"]
            update.message.reply_text(answer % facts_to_str(user_data),
                                      reply_markup=confirmok_markup)
            user_data['choice'] = "gym"
            return TYPING_REPLY
        else:
            answer = language["text_ok"]+"\n%s\n"+language["raid_confirm"]
            update.message.reply_text(answer % facts_to_str(user_data),
                                      reply_markup=confirm_markup)
            user_data['choice'] = "confirmraid"
            return CONFIRM
    elif category == "confirmraid":
        if text == language["confirm_reply_keyboard"][1][0]:
            user_data.clear()
            update.message.reply_text(language["text_cancel"],
                                      reply_markup=raid_markup)
            return RAID
        elif text == language["confirm_reply_keyboard"][0][0]:
            pos = ast.literal_eval(user_data['position'])
            lat = pos['latitude']
            lon = pos['longitude']

            ins = "INSERT INTO RAID (CREATED_BY,BOSS,LAT,LONG,TIME,GYM) \
                   VALUES (%d, '%s', %f, %f, datetime('now', 'localtime', '%s'), '%s');" \
                   % (update.message.chat_id, user_data['raidboss'], lat, lon, \
                      sqlexpire[raidbossexpire.index(user_data['expire'])], user_data['gym'])
            # Open database connection
            conn = sqlite3.connect('pogohelper.db')
            conn.execute(ins)
            conn.commit()
            # Close database connection
            conn.close()

            update.message.reply_text(language["raid_save"],
                                      reply_markup=raid_markup)
            return RAID
                                      
        else:
            answer = language["generic_error"]+"\n%s\n"+language["raid_confirm"]
            update.message.reply_text(answer % facts_to_str(user_data),
                                      reply_markup=confirm_markup)
            user_data['choice'] = "confirmraid"
            return CONFIRM
    elif category == "confirmraidattend":
        if text == language["confirmyesno_reply_keyboard"][1][0]:
            delete = "DELETE FROM RAIDPLAYERS WHERE RAIDID = %d AND PLAYERID = %d;" % (int(user_data['raidid']), \
                                                                                       update.message.chat_id)
            conn = sqlite3.connect('pogohelper.db')
            conn.execute(delete)
            conn.commit()
            conn.close()
            update.message.reply_text(language["raid_remove_attend"]
                                      % (int(user_data['raidid'])),
                                      reply_markup=raid_markup)
            user_data.clear()
            return RAID
        elif text == language["confirmyesno_reply_keyboard"][0][0]:
            if 'firstattend' in user_data:
                if user_data['firstattend']:
                    sel = "SELECT ID FROM RAIDPLAYERS WHERE RAIDID = %d AND PLAYERID = %d;" % (int(user_data['raidid']),update.message.chat_id)
                    conn = sqlite3.connect('pogohelper.db')
                    cursor = conn.execute(sel)
                    presente = False
                    for row in cursor:
                        presente = True
                    if not presente:
                        ins = "INSERT INTO RAIDPLAYERS (RAIDID,PLAYERID) VALUES (%d, %d);" % (int(user_data['raidid']),update.message.chat_id)
                        conn.execute(ins)
                        conn.commit()
                    update.message.reply_text(language["raid_add_attend"],
                                              reply_markup=ReplyKeyboardRemove())
                    sel = "SELECT DISTINCT(PLAYERID),FRIENDS,PREFERRED_TIME FROM RAIDPLAYERS WHERE RAIDID = %d;" % (int(user_data['raidid']))
                    cursor = conn.execute(sel)
                    totpartecipanti = 0
                    totrossi = 0
                    totblu = 0
                    totgialli = 0
                    totover30 = 0
                    totover35 = 0
                    tot40 = 0
                    totamici = 0
                    dict_preferred_time = {}
                    raidready = 0
                    for row in cursor:
                        sel2 = "SELECT NAME,TEAM,LEVEL FROM USERS WHERE ID = %d;" % (row[0])
                        cursor2 = conn.execute(sel2)
                        for row2 in cursor2:
                            if row2[1] == language["team_reply_keyboard"][0][0]:
                                totgialli += 1
                            elif row2[1] == language["team_reply_keyboard"][1][0]:
                                totblu += 1
                            elif row2[1] == language["team_reply_keyboard"][2][0]:
                                totrossi += 1
                            if row2[2] >= 40:
                                tot40 += 1
                            elif row2[2] >= 35:
                                totover35 += 1
                            elif row2[2] >= 30:
                                totover30 += 1

                            ora = str(datetime.now().strftime('%H:%M'))
                            tempo_preferito = str(datetime.strptime(row[2],'%Y-%m-%d %H:%M:%S').strftime('%H:%M'))
                            if row[0] == update.message.chat_id:
                                update.message.reply_text(language["raid_attend_you"],
                                                          reply_markup=ReplyKeyboardRemove())
                            else:
                                update.message.reply_text(language["raid_attend_another"]
                                                          % (row2[0], int(row2[2]), row2[1], tempo_preferito),
                                                          reply_markup=ReplyKeyboardRemove())
                            
                            if tempo_preferito != ora:
                                if tempo_preferito in dict_preferred_time:
                                    dict_preferred_time[tempo_preferito] += 1
                                else:
                                    dict_preferred_time[tempo_preferito] = 1
                            if row[1] > 0:
                                update.message.reply_text(language["raid_attend_another_friends"]
                                                          % (row2[0],row[1]))
                                totpartecipanti += row[1]
                                totamici += row[1]
                                dict_preferred_time[tempo_preferito] += row[1]
                        totpartecipanti += 1
                    preferred_time = language["raid_preferred_time"]
                    for key, value in dict_preferred_time.items():
                        preferred_time += language["hours"]+" "+str(key)+" "+language["attendees"]+" "+str(value)+"\n"
                    preferred_time = preferred_time[:-1]
                    answer = language["raid_final_info"]+"\n%s\n"+language["raid_ask_preferred_time_later"]
                    update.message.reply_text(answer % (totpartecipanti, totgialli, totblu, totrossi, tot40, totover35, \
                                              totover30, totamici, preferred_time),
                                              reply_markup=ReplyKeyboardRemove())
                    conn.close()
                    update.message.reply_text(language["raid_friends"],
                                              reply_markup=raid_friends_markup)
                    user_data['choice'] = "confirmraidattend_friends"
                    return RAIDFRIENDS
            else:
                update.message.reply_text(language["raid_attend_confirm"],
                                          reply_markup=raid_markup)
                user_data.clear()
                return RAID
        else:
            update.message.reply_text(language["raid_confirm_error"],
                                      reply_markup=confirmyesno_markup)
            user_data['raidid'] = user_data['raidid']
            user_data['choice'] = "confirmraidattend"
            return CONFIRMYESNO
    elif category == "confirmraidattend_friends":
        if text == language["raid_friends_reply_keyboard"][0][0]:
            upd = "UPDATE RAIDPLAYERS SET FRIENDS = 0 WHERE RAIDID = %d AND PLAYERID = %d;" % (int(user_data['raidid']),update.message.chat_id)
            conn = sqlite3.connect('pogohelper.db')
            conn.execute(upd)
            conn.commit()
            conn.close()
            scadenza = datetime.strptime(user_data['raidexpire'],'%Y-%m-%d %H:%M:%S')
            orario = datetime.now()
            pulsanti = []
            while orario < scadenza:
                pulsanti.append(str(ceil_dt(orario, timedelta(minutes=15)).strftime('%H:%M')))
                orario = orario + timedelta(minutes=15)
            raid_preferredtime_reply_keyboard = [KeyboardButton(s) for s in pulsanti]
            raid_preferredtime_markup = ReplyKeyboardMarkup(build_menu(raid_preferredtime_reply_keyboard, n_cols=4))
            update.message.reply_text(language["raid_ask_preferred_time"],
                                      reply_markup=raid_preferredtime_markup)
            user_data['choice'] = "confirmraidattend_preferredtime"
            return RAIDPREFERREDTIME
        else:
            upd = "UPDATE RAIDPLAYERS SET FRIENDS = %d WHERE RAIDID = %d AND PLAYERID = %d;" % (int(text),int(user_data['raidid']),update.message.chat_id)
            conn = sqlite3.connect('pogohelper.db')
            conn.execute(upd)
            conn.commit()
            conn.close()
            scadenza = datetime.strptime(user_data['raidexpire'],'%Y-%m-%d %H:%M:%S')
            orario = datetime.now()
            pulsanti = []
            while orario < scadenza:
                pulsanti.append(str(ceil_dt(orario, timedelta(minutes=15)).strftime('%H:%M')))
                orario = orario + timedelta(minutes=15)
            raid_preferredtime_reply_keyboard = [KeyboardButton(s) for s in pulsanti]
            raid_preferredtime_markup = ReplyKeyboardMarkup(build_menu(raid_preferredtime_reply_keyboard, n_cols=4))
            update.message.reply_text(language["raid_ask_preferred_time"],
                                      reply_markup=raid_preferredtime_markup)
            user_data['choice'] = "confirmraidattend_preferredtime"
            return RAIDPREFERREDTIME
    elif category == "confirmraidattend_preferredtime":
        tempo = user_data['raidexpire']
        tempo = re.sub(" [0-9][0-9]:[0-9][0-9]:"," "+text+":",tempo,count=1)
        upd = "UPDATE RAIDPLAYERS SET PREFERRED_TIME = '%s' WHERE RAIDID = %d AND PLAYERID = %d;" % (tempo,int(user_data['raidid']),update.message.chat_id)
        conn = sqlite3.connect('pogohelper.db')
        conn.execute(upd)
        conn.commit()
        conn.close()
        update.message.reply_text(language["saved_data"],
                                  reply_markup=raid_markup)
        user_data.clear()
        return RAID
    else:
        user_data.clear()
        #del user_data['username']
        #del user_data['level']
        #del user_data['team']
        user_data['choice'] = "username"
        update.message.reply_text(language["text_restart_error"],
                                  reply_markup=ReplyKeyboardRemove())
        return TYPING_REPLY


# Not used
def done(bot, update, user_data):
    if 'choice' in user_data:
        del user_data['choice']

    update.message.reply_text("Ciao!")

    user_data.clear()
    return ConversationHandler.END


def raid_management(bot, update, job_queue, user_data):
    text = update.message.text
    if text == language["raid_reply_keyboard"][0][0]:
        if 'job_delete_old_raids' not in user_data:
            # Add job to queue (delete old raids every 5 minutes)
            job = job_queue.run_repeating(delete_old_raids, 300)
            user_data['job_delete_old_raids'] = job
        # Open database connection
        conn = sqlite3.connect('pogohelper.db')
        update.message.reply_text(language["raid_list"],
                                  reply_markup=ReplyKeyboardRemove())
        sel = "SELECT RAID.ID,RAID.BOSS,RAID.LAT,RAID.LONG,RAID.TIME,RAID.GYM,USERS.FIRSTNAME,USERS.SURNAME,USERS.USERNAME \
               FROM RAID LEFT JOIN USERS ON RAID.CREATED_BY = USERS.ID ORDER BY RAID.TIME;"
        cursor = conn.execute(sel)
        totrighe = 0
        raids = []
        col = 1
        for row in cursor:
            scadenza = datetime.strptime(row[4],'%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
            update.message.reply_text(language["raid_info"]
                                      % (row[0], row[1], scadenza, row[5]))
            bot.sendLocation(update.message.chat_id,row[2],row[3])
            update.message.reply_text(language["raid_info_createdby"] % (row[6], row[7], row[8]))
            update.message.reply_text(language["raid_info_gymhuntr"] % (row[2],row[3]))
            raids.append(str(row[0]))
            totrighe += 1
            col += 1
            if col == 4:
                col = 1
        if totrighe == 0:
            update.message.reply_text(language["raid_empty"],
                                      reply_markup=raid_markup)
            # Close database connection
            conn.close()
            return RAID
        else:
            raids.append('Menu')
            raidedit_reply_keyboard = [KeyboardButton(s) for s in raids]
            raidedit_markup = ReplyKeyboardMarkup(build_menu(raidedit_reply_keyboard, n_cols=3))
            update.message.reply_text(language["raid_edit"],
                                      reply_markup=raidedit_markup)
            # Close database connection
            conn.close()
            return RAIDEDIT
        
    elif text == language["raid_reply_keyboard"][1][0]:
        update.message.reply_text(language["raid_create"],
                                  reply_markup=raidboss_markup)
        user_data['choice'] = "raidboss"
        return TYPING_REPLY
    elif text == language["raid_reply_keyboard"][3][0]:
        if 'job_notifications' not in user_data:
            # Add job to queue
            job = job_queue.run_repeating(notify_raids, 60, context=update.message.chat_id)
            user_data['job_notifications'] = job
            upd = "UPDATE USERS SET NOTIFICATIONS = 1 WHERE ID = %d;" % (update.message.chat_id)
            conn = sqlite3.connect('pogohelper.db')
            conn.execute(upd)
            conn.commit()
            conn.close()
            update.message.reply_text(language["raid_notifications_enabled"],
                                      reply_markup=raid_markup)
            return RAID
        else:
            update.message.reply_text(language["raid_notifications_already_enabled"],
                                      reply_markup=raid_markup)
            return RAID
    elif text == language["raid_reply_keyboard"][4][0]:
        if 'job_notifications' not in user_data:
            update.message.reply_text(language["raid_notifications_already_disabled"],
                                      reply_markup=raid_markup)
            return RAID
        else:
            # Remove job from queue
            job = user_data['job_notifications']
            job.schedule_removal()
            del user_data['job_notifications']
            upd = "UPDATE USERS SET NOTIFICATIONS = 0 WHERE ID = %d;" % (update.message.chat_id)
            conn = sqlite3.connect('pogohelper.db')
            conn.execute(upd)
            conn.commit()
            conn.close()
            update.message.reply_text(language["raid_notifications_disabled"],
                                      reply_markup=raid_markup)
            return RAID
    elif text == language["raid_reply_keyboard"][5][0]:
        if 'username' in user_data:
            del user_data['username']
        if 'level' in user_data:
            del user_data['level']
        if 'team' in user_data:
            del user_data['team']
        #if 'language' in user_data:
        #    del user_data['language']
        user_data['choice'] = "username"
        update.message.reply_text(language["profile_modify"])
        return TYPING_REPLY
    elif text == language["raid_reply_keyboard"][2][0]:
        utenti_registrati = language["users_list"]+"\n"
        sel = "SELECT NAME,TEAM,LEVEL FROM USERS ORDER BY LEVEL DESC;"
        conn = sqlite3.connect('pogohelper.db')
        cursor = conn.execute(sel)
        for row in cursor:
            utenti_registrati += row[0]+" "+language["users_team"]+" "+row[1]+" "+language["users_level"]+" "+str(row[2])+"\n"
        conn.close()
        utenti_registrati = utenti_registrati[:-1]
        update.message.reply_text(utenti_registrati,
                                  reply_markup=raid_markup)
        return RAID


def raidedit_management(bot, update, user_data):
    text = update.message.text
    if text == "Menu":
        update.message.reply_text(language["menu"],
                                  reply_markup=raid_markup)
        return RAID
    elif text.isdigit():
        presente = False
        conn = sqlite3.connect('pogohelper.db')
        sel = "SELECT RAID.CREATED_BY,RAID.BOSS,RAID.LAT,RAID.LONG,RAID.TIME,RAID.GYM,RAIDBOSS.STRENGTH \
               FROM RAID LEFT JOIN RAIDBOSS ON RAID.BOSS = RAIDBOSS.BOSS WHERE RAID.ID = %d;" % (int(text))
        cursor = conn.execute(sel)
        for row in cursor:
            presente = True
            user_data['raidexpire'] = row[4]
            raidbossstrength = float(row[6])
            update.message.reply_text(language["raid_selected"]
                                      % (int(text), row[1]),
                                      reply_markup=ReplyKeyboardRemove())
        if presente:
            sel = "SELECT DISTINCT(PLAYERID),FRIENDS,PREFERRED_TIME FROM RAIDPLAYERS WHERE RAIDID = %d;" % (int(text))
            cursor = conn.execute(sel)
            partecipo = False
            totpartecipanti = 0
            totrossi = 0
            totblu = 0
            totgialli = 0
            totover30 = 0
            totover35 = 0
            tot40 = 0
            totamici = 0
            dict_preferred_time = {}
            raidteamstrength = 0
            for row in cursor:
                if row[0] == update.message.chat_id:
                    partecipo = True
                sel2 = "SELECT NAME,TEAM,LEVEL FROM USERS WHERE ID = %d;" % (row[0])
                cursor2 = conn.execute(sel2)
                for row2 in cursor2:
                    if row2[1] == language["team_reply_keyboard"][0][0]:
                        totgialli += 1
                    elif row2[1] == language["team_reply_keyboard"][1][0]:
                        totblu += 1
                    elif row2[1] == language["team_reply_keyboard"][2][0]:
                        totrossi += 1
                    if row2[2] >= 40:
                        tot40 += 1
                    elif row2[2] >= 35:
                        totover35 += 1
                    elif row2[2] >= 30:
                        totover30 += 1
                    raidteamstrength += float(row2[2])/30
                        
                    tempo_preferito = str(datetime.strptime(row[2],'%Y-%m-%d %H:%M:%S').strftime('%H:%M'))
                    if row[0] == update.message.chat_id:
                        update.message.reply_text(language["raid_attend_you"],
                                                  reply_markup=ReplyKeyboardRemove())
                    else:
                        update.message.reply_text(language["raid_attend_another"]
                                                  % (row2[0], int(row2[2]), row2[1], tempo_preferito),
                                                  reply_markup=ReplyKeyboardRemove())
                    if tempo_preferito in dict_preferred_time:
                        dict_preferred_time[tempo_preferito] += 1
                    else:
                        dict_preferred_time[tempo_preferito] = 1
                    if row[1] > 0:
                        update.message.reply_text(language["raid_attend_another_friends"]
                                                  % (row2[0],row[1]))
                        totpartecipanti += row[1]
                        totamici += row[1]
                        dict_preferred_time[tempo_preferito] += row[1]
                totpartecipanti += 1
            if totpartecipanti == 0:
                update.message.reply_text(language["raid_no_attendees"],
                                          reply_markup=confirmyesno_markup)
                conn.close()
                user_data['raidid'] = text
                user_data['choice'] = "confirmraidattend"
                user_data['firstattend'] = True
                return CONFIRMYESNO
            else:
                preferred_time = language["raid_preferred_time"]
                for key, value in dict_preferred_time.items():
                    preferred_time += language["hours"]+" "+str(key)+" "+language["attendees"]+" "+str(value)+"\n"
                preferred_time = preferred_time[:-1]
                tempo_medio = str(datetime.now().strftime('%H:%M'))
                sel3 = "SELECT DATETIME(AVG(JULIANDAY(PREFERRED_TIME))) FROM RAIDPLAYERS WHERE RAIDID = %d" % (int(text))
                cursor3 = conn.execute(sel3)
                for row3 in cursor3:
                    tempo_medio = datetime.strptime(row3[0],'%Y-%m-%d %H:%M:%S').strftime('%H:%M')
                if raidteamstrength > raidbossstrength:
                    preferred_time += "\n"+language["raid_enough_attendees"]
                preferred_time += "\n"
                preferred_time += language["raid_average_preferred_time"] % (tempo_medio)
                if raidteamstrength > raidbossstrength:
                    preferred_time += language["raid_goodluck"]
                answer = language["raid_final_info"]+"\n%s"
                update.message.reply_text(answer % (totpartecipanti, totgialli, totblu, totrossi, tot40, totover35, \
                                          totover30, totamici, preferred_time),
                                          reply_markup=ReplyKeyboardRemove(), parse_mode=ParseMode.MARKDOWN)
                if partecipo:
                    update.message.reply_text(language["raid_confirm_attend"],
                                              reply_markup=confirmyesno_markup)
                    conn.close()
                    user_data['raidid'] = text
                    user_data['choice'] = "confirmraidattend"
                    return CONFIRMYESNO
                else:
                    update.message.reply_text(language["raid_attend_question"],
                                              reply_markup=confirmyesno_markup)
                    conn.close()
                    user_data['raidid'] = text
                    user_data['choice'] = "confirmraidattend"
                    return CONFIRMYESNO
        else:
            update.message.reply_text(language["raid_wrong"],
                                      reply_markup=raid_markup)
            conn.close()
            return RAID


def error(bot, update, error):
    logger.warn('Update "%s" caused error "%s"' % (update, error))


def delete_old_raids(bot, job):
    delete = "DELETE FROM RAID WHERE TIME < datetime('now','localtime');"
    conn = sqlite3.connect('pogohelper.db')
    conn.execute(delete)
    conn.commit()
    conn.close()


def notify_raids(bot, job):
    sel = "SELECT RAID.ID,RAID.BOSS,USERS.FIRSTNAME,USERS.SURNAME,USERS.USERNAME,RAID.LAT,RAID.LONG,RAID.TIME,RAID.READY \
           FROM RAID LEFT JOIN USERS ON RAID.CREATED_BY = USERS.ID WHERE RAID.CREATED_BY != %d ORDER BY RAID.ID;" \
           % (job.context)
    conn = sqlite3.connect('pogohelper.db')
    cursor = conn.execute(sel)
    for row in cursor:
        scadenza = datetime.strptime(row[7],'%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
        notificato = False
        sel2 = "SELECT ID,READY FROM NOTIFICATIONS WHERE RAIDID = %d AND PLAYERID = %d;" % (row[0], job.context)
        cursor2 = conn.execute(sel2)
        raidready = False
        if row[8] == 1:
            raidready = True
        for row2 in cursor2:
            notificato = True
            notificationready = False
            if row2[1] == 1:
                notificationready = True
        if not notificato:
            bot.send_message(job.context, text=language["raid_notification_create"] % (row[0],row[1],scadenza,row[2],row[3],row[4]))
            bot.sendLocation(job.context,row[5],row[6])
            ins = "INSERT INTO NOTIFICATIONS (RAIDID,PLAYERID) VALUES (%d, %d);" % (row[0], job.context)
            conn.execute(ins)
            conn.commit()
        if raidready:
            if not notificationready:
                tempo_medio = str(datetime.now().strftime('%H:%M'))
                sel3 = "SELECT DATETIME(AVG(JULIANDAY(PREFERRED_TIME))) FROM RAIDPLAYERS WHERE RAIDID = %d;" % (row[0])
                cursor3 = conn.execute(sel3)
                for row3 in cursor3:
                    tempo_medio = datetime.strptime(row3[0],'%Y-%m-%d %H:%M:%S').strftime('%H:%M')
                bot.send_message(job.context, text=language["raid_notification_enough_attendees"] % (row[0],row[1],scadenza,tempo_medio))
                upd = "UPDATE NOTIFICATIONS SET READY = 1 WHERE RAIDID = %d AND PLAYERID = %d;" % (row[0], job.context)
                conn.execute(upd)
                conn.commit()
    upd1 = "UPDATE USERS SET HEARTBEAT = datetime('now','localtime') WHERE ID = %d;" % (job.context)
    conn.execute(upd1)
    conn.commit()
    conn.close()


def botShutdown():
    bot = telegram.Bot(token_id.strip())
    sel = "SELECT ID FROM USERS WHERE NOTIFICATIONS = 1;"
    conn = sqlite3.connect('pogohelper.db')
    cursor = conn.execute(sel)
    for row in cursor:
        bot.send_message(row[0], text=language["bot_restart"], reply_markup=ReplyKeyboardRemove())
    conn.close()


def main():
    # Create the Updater and pass it your bot's token.
    updater = Updater(token_id.strip())

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Load language files for menu Regexs
    regex_team = '^('
    regex_confirm = '^('
    regex_yesno = '^('
    regex_menu = '^('
    regex_raidfriends = '^([1-9]|10|'
    for language_text in languages:
        with open('languages/'+language_text.lower()+'.json') as language_file_menu:
            language_menu = json.load(language_file_menu)
            for item in language_menu["team_reply_keyboard"]:
                regex_team += item[0]+'|'
            for item in language_menu["confirm_reply_keyboard"]:
                regex_confirm += item[0]+'|'
            for item in language_menu["confirmyesno_reply_keyboard"]:
                regex_yesno += item[0]+'|'
            for item in language_menu["raid_reply_keyboard"]:
                regex_menu += item[0]+'|'
            for item in language_menu["raid_friends_reply_keyboard"][0]:
                regex_raidfriends += item+'|'
    regex_team = regex_team[:-1]
    regex_confirm = regex_confirm[:-1]
    regex_yesno = regex_yesno[:-1]
    regex_menu = regex_menu[:-1]
    regex_raidfriends = regex_raidfriends[:-1]
    regex_team += ')$'
    regex_confirm += ')$'
    regex_yesno += ')$'
    regex_menu += ')$'
    regex_raidfriends += ')$'

    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start, pass_job_queue=True, pass_user_data=True)],

        states={
            TEAM: [RegexHandler(regex_team,
                                received_information,
                                pass_user_data=True),
                   ],
            CONFIRM: [RegexHandler(regex_confirm,
                                   received_information,
                                   pass_user_data=True),
                      ],
            CONFIRMYESNO: [RegexHandler(regex_yesno,
                                        received_information,
                                        pass_user_data=True),
                           ],
            RAID: [RegexHandler(regex_menu,
                                raid_management,
                                pass_job_queue=True,
                                pass_user_data=True),
                   ],
            RAIDEDIT: [RegexHandler('^([1-9]|[1-9][0-9]|[1-9][0-9][0-9]|[1-9][0-9][0-9][0-9]|[1-9][0-9][0-9][0-9][0-9]|Menu)$',
                                    raidedit_management,
                                    pass_user_data=True),
                       ],
            RAIDFRIENDS: [RegexHandler(regex_raidfriends,
                                       received_information,
                                       pass_user_data=True),
                          ],
            RAIDPREFERREDTIME: [RegexHandler('^([0-9]|0[0-9]|1[0-9]|2[0-3]):(0|1|3|4)(0|5)$',
                                             received_information,
                                             pass_user_data=True),
                                ],
            USERLANGUAGE: [RegexHandler('^('+'|'.join(languages)+')$',
                                        received_information,
                                        pass_user_data=True),
                           ],
            TYPING_REPLY: [MessageHandler(Filters.text,
                                          received_information,
                                          pass_user_data=True),
                           ],
            TYPING_LOCATION: [MessageHandler(Filters.location,
                                             received_information,
                                             pass_user_data=True),
                              ],
        },

        fallbacks=[RegexHandler('^Done$', done, pass_user_data=True)]
    )

    dp.add_handler(conv_handler)
    
    # Add restart command
    dp.add_handler(CommandHandler('r', restart))

    # Create notification jobs for each user that has the notification flag on
    #j = updater.job_queue
    #sel = "SELECT ID FROM USERS WHERE NOTIFICATIONS = 1"
    #conn = sqlite3.connect('pogohelper.db')
    #cursor = conn.execute(sel)
    #for row in cursor:
    #    j.run_repeating(notify_raids, 60, context=row[0])
    #conn.close()

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()

    # Send shutdown notifications
    #botShutdown()


if __name__ == '__main__':
    main()
