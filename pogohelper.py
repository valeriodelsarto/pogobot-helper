
from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton)
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

LIST_OF_ADMINS = []
fileadmin = open('admins.txt','r')
temp = fileadmin.read().splitlines()
fileadmin.close()
for line in temp:
    LIST_OF_ADMINS.append(int(line))

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

# Load BOSS names
raidboss = []
# Open database connection
conn = sqlite3.connect('pogohelper.db')
sel = "SELECT DISTINCT(BOSS) FROM RAIDBOSS ORDER BY BOSS;"
cursor = conn.execute(sel)
for row in cursor:
    raidboss.append(row[0])
# Close db connection
conn.close()

TEAM, CONFIRM, CONFIRMYESNO, RAID, RAIDEDIT, RAIDFRIENDS, RAIDPREFERREDTIME, TYPING_REPLY, TYPING_LOCATION = range(9)

team_reply_keyboard = [['Istinto-Giallo'],
                      ['Saggezza-Blu'],
                      ['Coraggio-Rosso']]
team_markup = ReplyKeyboardMarkup(team_reply_keyboard, one_time_keyboard=True)

confirm_reply_keyboard = [['Confermo'],
                         ['Ricomincia']]
confirm_markup = ReplyKeyboardMarkup(confirm_reply_keyboard, one_time_keyboard=True)

confirmok_reply_keyboard = [['Confermo']]
confirmok_markup = ReplyKeyboardMarkup(confirmok_reply_keyboard, one_time_keyboard=True)

confirmyesno_reply_keyboard = [['Si'],['No']]
confirmyesno_markup = ReplyKeyboardMarkup(confirmyesno_reply_keyboard, one_time_keyboard=True)

raid_reply_keyboard = [['Vedi RAID Attivi'],['Crea Nuovo RAID'],
                      ['Vedi Utenti Registrati'],
                      ['Abilita Notifiche'],['Disabilita Notifiche'],
                      ['Edita Profilo']]
raid_markup = ReplyKeyboardMarkup(raid_reply_keyboard, one_time_keyboard=True)

raidboss_reply_keyboard = [KeyboardButton(s) for s in raidboss]
raidboss_markup = ReplyKeyboardMarkup(build_menu(raidboss_reply_keyboard, n_cols=3))

raidbossexpire = ['30 min','45 min','1 ora','1 ora e 15 min','1 ora e 30 min','1 ora e 45 min','2 ore']
raidbossexpire_reply_keyboard = [['30 min'],['45 min'],['1 ora'],
                                ['1 ora e 15 min'],['1 ora e 30 min'],
                                ['1 ora e 45 min'],['2 ore']]
raidbossexpire_markup = ReplyKeyboardMarkup(raidbossexpire_reply_keyboard, one_time_keyboard=True)
sqlexpire = ['+30 Minute','+45 Minute','+60 Minute','+75 Minute','+90 Minute','+105 Minute','+120 Minute']

raid_friends_reply_keyboard = [['Nessuno'],
                              ['1'],['2'],['3'],['4'],['5'],
                              ['6'],['7'],['8'],['9'],['10']]
raid_friends_markup = ReplyKeyboardMarkup(raid_friends_reply_keyboard, resize_keyboard=True, one_time_keyboard=True)


def restricted(func):
    @wraps(func)
    def wrapped(bot, update, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in LIST_OF_ADMINS:
            print("Unauthorized access denied for {}.".format(user_id))
            return
        return func(bot, update, *args, **kwargs)
    return wrapped


@restricted
def restart(bot, update):
    bot.send_message(update.message.chat_id, "Bot is restarting...")
    time.sleep(0.2)
    os.execl(sys.executable, sys.executable, *sys.argv)

def facts_to_str(user_data):
    facts = list()

    for key, value in user_data.items():
        if key != 'choice' and key != 'job_delete_old_raids' and key != 'job_notifications':
            facts.append('%s - %s' % (key, value))

    return "\n".join(facts).join(['\n', '\n'])


def start(bot, update, job_queue, user_data):
    # Check if user is authorized
    #pprint.pprint(users)
    #if str(update.message.chat_id) in users:
    if not str(update.message.chat_id) in blocked_users:
        # Check if user is already registered in database
        # Open database connection
        conn = sqlite3.connect('pogohelper.db')
        sel = "SELECT NAME FROM USERS WHERE ID = %d;" % (update.message.chat_id)
        cursor = conn.execute(sel)
        present = 0
        for row in cursor:
            name = row[0]
            present = 1
        # Close db connection
        conn.close()

        if present == 1:
            update.message.reply_text("Bentornato %s!" % (name),
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
        else:
            update.message.reply_text(
                "Ciao! Questo bot e' programmato per aiutare nell'organizzazione di RAID per Pokemon-Go.\n"
                "Intanto mi servono alcune informazioni. Qual'e' il tuo nickname su Pokemon-Go?")

            return TYPING_REPLY
    else:
        update.message.reply_text(
            "User not authorized! Please ask for authorization with your ID:"
            "%s"
            % update.message.chat_id)
        return ConversationHandler.END


def received_information(bot, update, user_data):
    if not 'choice' in user_data:
        user_data['choice'] = "username"
    text = update.message.text
    category = user_data['choice']
    if not (text == "Confermo" and category == "gym"):
      user_data[category] = text
    #del user_data['choice']
    #pprint.pprint(update.message.from_user)

    if category == "username":
        update.message.reply_text("Ok! Ecco i dati che conosco:"
                                  "%s"
                                  "Adesso ho bisogno di sapere a quale Team appartieni:"
                                  % facts_to_str(user_data),
                                  reply_markup=team_markup)
        user_data['choice'] = "team"
        return TEAM
    elif category == "team":
        update.message.reply_text("Ok! Ecco i dati che conosco:"
                                  "%s"
                                  "Adesso ho bisogno di sapere a quale livello sei:"
                                  % facts_to_str(user_data),
                                  reply_markup=ReplyKeyboardRemove())
        user_data['choice'] = "level"
        return TYPING_REPLY
    elif category == "level":
        if text.isdigit():
            if int(text) > 0 and int(text) <= 40:
                update.message.reply_text("Ok! Ecco i dati che conosco:"
                                          "%s"
                                          "Adesso conosco tutti i tuoi dati. Vuoi confermarli o cambiarli?"
                                          % facts_to_str(user_data),
                                          reply_markup=confirm_markup)
                user_data['choice'] = "confirm"
                return CONFIRM
            else:
                update.message.reply_text("Mi hai inviato un livello errato!\n"
                                          "Devi inviare un numero compreso fra 1 e 40.\n"
                                          "Riprova...")
                user_data['choice'] = "level"
                return TYPING_REPLY
        else:
            update.message.reply_text("Mi hai inviato un livello errato!\n"
                                      "Devi inviare un numero compreso fra 1 e 40.\n"
                                      "Riprova...")
            user_data['choice'] = "level"
            return TYPING_REPLY
    elif category == "confirm":
        if text == "Ricomincia":
            user_data.clear()
            #del user_data['username']
            #del user_data['level']
            #del user_data['team']
            user_data['choice'] = "username"
            update.message.reply_text("Ok! Ho cancellato tutti i dati che mi hai inviato.\n"
                                      "Ricominciamo!\n"
                                      "Qual'e' il tuo nickname su Pokemon-Go?")
            return TYPING_REPLY
        elif text == "Confermo":
            ins = "INSERT OR IGNORE INTO USERS (ID,NAME,TEAM,LEVEL,FIRSTNAME,SURNAME,USERNAME) \
                   VALUES (%d, '%s', '%s', %d, '%s', '%s', '%s' );" % (update.message.chat_id, user_data['username'], \
                                                                       user_data['team'], int(user_data['level']), \
                                                                       update.message.from_user.first_name,
                                                                       update.message.from_user.last_name,
                                                                       update.message.from_user.username)
            upd = "UPDATE USERS SET NAME = '%s', TEAM = '%s', LEVEL = %d, FIRSTNAME = '%s', SURNAME = '%s', USERNAME = '%s' \
                   WHERE ID = %d;" % (user_data['username'], user_data['team'], int(user_data['level']), \
                                      update.message.from_user.first_name, update.message.from_user.last_name, \
                                      update.message.from_user.username, update.message.chat_id)
            # Open database connection
            conn = sqlite3.connect('pogohelper.db')
            conn.execute(ins)
            conn.execute(upd)
            conn.commit()
            # Close database connection
            conn.close()

            update.message.reply_text("Ok, ho salvato i tuoi dati nel database interno del bot!\n"
                                      "Da ora puoi creare dei RAID o partecipare ai RAID che creano gli altri!",
                                      reply_markup=raid_markup)
            del user_data['username']
            del user_data['level']
            del user_data['team']
            del user_data['confirm']
            return RAID
                                      
        else:
            update.message.reply_text("Non ho capito! Ecco i dati che conosco:"
                                      "%s"
                                      "Adesso conosco tutti i tuoi dati. Vuoi confermarli o cambiarli?"
                                      % facts_to_str(user_data),
                                      reply_markup=confirm_markup)
            user_data['choice'] = "confirm"
            return CONFIRM
    elif category == "raidboss":
        if not text in raidboss:
            update.message.reply_text("Questo BOSS non esiste! Ripeti il nome del BOSS:",
                                      reply_markup=raidboss_markup)
            user_data['choice'] = "raidboss"
            return TYPING_REPLY
        else:
            update.message.reply_text("Ok! Ecco i dati che conosco:"
                                      "%s"
                                      "Adesso ho bisogno di sapere la posizione. Inviami la posizione da Telegram:"
                                      % facts_to_str(user_data),
                                      reply_markup=ReplyKeyboardRemove())
            user_data['choice'] = "position"
            return TYPING_LOCATION
    elif category == "position":
        if update.message.location == None:
            update.message.reply_text("Non mi hai inviato una posizione! Inviami la posizione:",
                                      reply_markup=ReplyKeyboardRemove())
            user_data['choice'] = "position"
            return TYPING_REPLY
        else:
            user_data[category] = str(update.message.location)
            update.message.reply_text("Ok! Ecco i dati che conosco:"
                                      "%s"
                                      "Adesso ho bisogno di sapere la scadenza del RAID.\n"
                                      "Dimmi fra quanto scade (all'incirca):\n"
                                      "Per potersi organizzare, non e' possibile inserire RAID che scadono fra meno di 30 minuti"
                                      % facts_to_str(user_data),
                                      reply_markup=raidbossexpire_markup)
            user_data['choice'] = "expire"
            return TYPING_REPLY
    elif category == "expire":
        if not text in raidbossexpire:
            update.message.reply_text("Non mi hai risposto correttamente! Ripeti fra quanto scade il RAID:",
                                      reply_markup=raidbossexpire_markup)
            user_data['choice'] = "expire"
            return TYPING_REPLY
        else:
            update.message.reply_text("Ok! Ecco i dati che conosco:"
                                      "%s"
                                      "Ok, se lo sai scrivi il nome della palestra o un riferimento comprensibile su dove si trova:"
                                      % facts_to_str(user_data),
                                      reply_markup=ReplyKeyboardRemove())
            user_data['choice'] = "gym"
            return TYPING_REPLY
    elif category == "gym":
        if text != "Confermo":
            update.message.reply_text("Ok! Ecco i dati che conosco:"
                                      "%s"
                                      "Confermi il nome o il riferimento assegnato alla palestra?\n"
                                      "(Se vuoi cambiarlo riscrivilo altrimenti premi Confermo)"
                                      % facts_to_str(user_data),
                                      reply_markup=confirmok_markup)
            user_data['choice'] = "gym"
            return TYPING_REPLY
        else:
            update.message.reply_text("Ok! Ecco i dati che conosco:"
                                      "%s"
                                      "Adesso conosco tutti i dati del RAID. Vuoi confermarli o cambiarli?"
                                      % facts_to_str(user_data),
                                      reply_markup=confirm_markup)
            user_data['choice'] = "confirmraid"
            return CONFIRM
    elif category == "confirmraid":
        if text == "Ricomincia":
            user_data.clear()
            update.message.reply_text("Ok! Ho cancellato tutti i dati che mi hai inviato.",
                                      reply_markup=raid_markup)
            return RAID
        elif text == "Confermo":
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

            update.message.reply_text("Ok, ho salvato i dati del RAID nel database interno del bot!\n"
                                      "Ora puoi visualizzare il nuovo RAID nella lista!",
                                      reply_markup=raid_markup)
            return RAID
                                      
        else:
            update.message.reply_text("Non ho capito! Ecco i dati che conosco:"
                                      "%s"
                                      "Adesso conosco tutti i dati del RAID. Vuoi confermarli o cambiarli?"
                                      % facts_to_str(user_data),
                                      reply_markup=confirm_markup)
            user_data['choice'] = "confirmraid"
            return CONFIRM
    elif category == "confirmraidattend":
        if text == "No":
            delete = "DELETE FROM RAIDPLAYERS WHERE RAIDID = %d AND PLAYERID = %d;" % (int(user_data['raidid']), \
                                                                                       update.message.chat_id)
            conn = sqlite3.connect('pogohelper.db')
            conn.execute(delete)
            conn.commit()
            conn.close()
            update.message.reply_text("Ok! Ho eliminato la tua partecipazione dal RAID numero %d!"
                                      % (int(user_data['raidid'])),
                                      reply_markup=raid_markup)
            user_data.clear()
            return RAID
        elif text == "Si":
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
                    update.message.reply_text("Ok, ho salvato la tua partecipazione a questo RAID nel database interno del bot!\n"
                                              "Ecco la lista aggiornata dei partecipanti a questo RAID:",
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
                    for row in cursor:
                        sel2 = "SELECT NAME,TEAM,LEVEL FROM USERS WHERE ID = %d;" % (row[0])
                        cursor2 = conn.execute(sel2)
                        for row2 in cursor2:
                            if row2[1] == "Istinto-Giallo":
                                totgialli += 1
                            elif row2[1] == "Saggezza-Blu":
                                totblu += 1
                            elif row2[1] == "Coraggio-Rosso":
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
                                update.message.reply_text("A questo RAID partecipi anche te!",
                                                          reply_markup=ReplyKeyboardRemove())
                            else:
                                update.message.reply_text("A questo RAID partecipa anche %s!\n"
                                                          "E' un livello %d e appartiene al Team %s\n"
                                                          "L'orario a cui preferisce partecipare al RAID e': %s"
                                                          % (row2[0], int(row2[2]), row2[1], tempo_preferito),
                                                          reply_markup=ReplyKeyboardRemove())
                            
                            if tempo_preferito != ora:
                                if tempo_preferito in dict_preferred_time:
                                    dict_preferred_time[tempo_preferito] += 1
                                else:
                                    dict_preferred_time[tempo_preferito] = 1
                            if row[1] > 0:
                                update.message.reply_text("%s ha anche %d amici che partecipano!"
                                                          % (row2[0],row[1]))
                                totpartecipanti += row[1]
                                totamici += row[1]
                                dict_preferred_time[tempo_preferito] += row[1]
                        totpartecipanti += 1
                    preferred_time = "Gli orari preferiti per il RAID sono (con i relativi partecipanti):\n"
                    for key, value in dict_preferred_time.items():
                        preferred_time += "Ore "+str(key)+" Partecipanti "+str(value)+"\n"
                    preferred_time = preferred_time[:-1]
                    update.message.reply_text("Per ora ci sono %d partecipanti a questo RAID!\n"
                                              "Ci sono %d del team Istinto-Giallo\n"
                                              "Ci sono %d del team Saggezza-Blu\n"
                                              "Ci sono %d del team Coraggio-Rosso\n"
                                              "Ci sono %d livelli 40\n"
                                              "Ci sono %d livelli 35 o superiore\n"
                                              "Ci sono %d livelli 30 o superiore\n"
                                              "Ci sono %d amici che partecipano\n"
                                              "%s\n"
                                              "Il tuo orario preferito non e' ancora inserito, te lo chiedero' fra poco."
                                              % (totpartecipanti, totgialli, totblu, totrossi, tot40, totover35, totover30, \
                                              totamici, preferred_time),
                                              reply_markup=ReplyKeyboardRemove())
                    conn.close()
                    update.message.reply_text("Ok! Ora dimmi se ci sono degli amici con te che parteciperanno\n"
                                              "e non hanno Telegram quindi non possono registrarsi in questo RAID:",
                                              reply_markup=raid_friends_markup)
                    user_data['choice'] = "confirmraidattend_friends"
                    return RAIDFRIENDS
            else:
                update.message.reply_text("Ok! Presenza confermata, Torno al menu' principale!",
                                          reply_markup=raid_markup)
                user_data.clear()
                return RAID
        else:
            update.message.reply_text("Non ho capito!\n"
                                      "Vuoi partecipare a questo RAID?",
                                      reply_markup=confirmyesno_markup)
            user_data['raidid'] = user_data['raidid']
            user_data['choice'] = "confirmraidattend"
            return CONFIRMYESNO
    elif category == "confirmraidattend_friends":
        if text == "Nessuno":
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
            update.message.reply_text("Ok! Ora dimmi l'orario a cui preferisci partecipare a questo RAID:",
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
            update.message.reply_text("Ok! Ora dimmi l'orario a cui preferisci partecipare a questo RAID:",
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
        update.message.reply_text("Ok! Dati salvati! Ritorno al menu' principale.",
                                  reply_markup=raid_markup)
        user_data.clear()
        return RAID
    else:
        user_data.clear()
        #del user_data['username']
        #del user_data['level']
        #del user_data['team']
        user_data['choice'] = "username"
        update.message.reply_text("Non ho capito!\n"
                                  "Ricominciamo!\n"
                                  "Qual'e' il tuo nickname su Pokemon-Go?",
                                  reply_markup=ReplyKeyboardRemove())
        return TYPING_REPLY


def done(bot, update, user_data):
    if 'choice' in user_data:
        del user_data['choice']

    update.message.reply_text("Ciao!")

    user_data.clear()
    return ConversationHandler.END


def raid_management(bot, update, job_queue, user_data):
    text = update.message.text
    if text == "Vedi RAID Attivi":
        if 'job_delete_old_raids' not in user_data:
            # Add job to queue (delete old raids every 5 minutes)
            job = job_queue.run_repeating(delete_old_raids, 300)
            user_data['job_delete_old_raids'] = job
        # Open database connection
        conn = sqlite3.connect('pogohelper.db')
        update.message.reply_text("Ecco la lista dei RAID attivi!",
                                  reply_markup=ReplyKeyboardRemove())
        sel = "SELECT RAID.ID,RAID.BOSS,RAID.LAT,RAID.LONG,RAID.TIME,RAID.GYM,USERS.FIRSTNAME,USERS.SURNAME,USERS.USERNAME \
               FROM RAID LEFT JOIN USERS ON RAID.CREATED_BY = USERS.ID ORDER BY RAID.TIME;"
        cursor = conn.execute(sel)
        totrighe = 0
        raids = []
        col = 1
        for row in cursor:
            scadenza = datetime.strptime(row[4],'%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
            update.message.reply_text("ID: %d,\nBoss: %s,\nScadenza: %s,\nPalestra: %s,\nsegue posizione:"
                                      % (row[0], row[1], scadenza, row[5]))
            bot.sendLocation(update.message.chat_id,row[2],row[3])
            update.message.reply_text("Questo RAID e' stato creato da %s %s @%s" % (row[6], row[7], row[8]))
            update.message.reply_text("Se vuoi controllare la correttezza di questo RAID usa il seguente link su GYMHUNTR:\n"
                                      "https://gymhuntr.com/#%f,%f" % (row[2],row[3]))
            raids.append(str(row[0]))
            totrighe += 1
            col += 1
            if col == 4:
                col = 1
        if totrighe == 0:
            update.message.reply_text("Non ci sono RAID attivi!",
                                      reply_markup=raid_markup)
            # Close database connection
            conn.close()
            return RAID
        else:
            raids.append('Menu')
            raidedit_reply_keyboard = [KeyboardButton(s) for s in raids]
            raidedit_markup = ReplyKeyboardMarkup(build_menu(raidedit_reply_keyboard, n_cols=3))
            update.message.reply_text("Scegli se vuoi editare un RAID o tornare al menu' principale:",
                                      reply_markup=raidedit_markup)
            # Close database connection
            conn.close()
            return RAIDEDIT
        
    elif text == "Crea Nuovo RAID":
        update.message.reply_text("Inviami i dati del RAID che vuoi creare!\n"
                                  "Per prima cosa dimmi il nome del BOSS:",
                                  reply_markup=raidboss_markup)
        user_data['choice'] = "raidboss"
        return TYPING_REPLY
    elif text == "Abilita Notifiche":
        if 'job_notifications' not in user_data:
            # Add job to queue
            job = job_queue.run_repeating(notify_raids, 60, context=update.message.chat_id)
            user_data['job_notifications'] = job
            upd = "UPDATE USERS SET NOTIFICATIONS = 1 WHERE ID = %d;" % (update.message.chat_id)
            conn = sqlite3.connect('pogohelper.db')
            conn.execute(upd)
            conn.commit()
            conn.close()
            update.message.reply_text("Notifiche di nuovi RAID abilitate!",
                                      reply_markup=raid_markup)
            return RAID
        else:
            update.message.reply_text("Le notifiche di nuovi RAID sono gia' attive!",
                                      reply_markup=raid_markup)
            return RAID
    elif text == "Disabilita Notifiche":
        if 'job_notifications' not in user_data:
            update.message.reply_text("Le notifiche di nuovi RAID sono gia' disabilitate!",
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
            update.message.reply_text("Notifiche di nuovi RAID disabilitate!",
                                      reply_markup=raid_markup)
            return RAID
    elif text == "Edita Profilo":
        if 'username' in user_data:
            del user_data['username']
        if 'level' in user_data:
            del user_data['level']
        if 'team' in user_data:
            del user_data['team']
        user_data['choice'] = "username"
        update.message.reply_text("Ok! Ripetimi i dati del tuo profilo:\n"
                                  "Qual'e' il tuo nickname su Pokemon-Go?")
        return TYPING_REPLY
    elif text == "Vedi Utenti Registrati":
        utenti_registrati = "Ecco l'elenco degli utenti registrati:\n"
        sel = "SELECT NAME,TEAM,LEVEL FROM USERS ORDER BY LEVEL DESC;"
        conn = sqlite3.connect('pogohelper.db')
        cursor = conn.execute(sel)
        for row in cursor:
            utenti_registrati += row[0]+" Team "+row[1]+" Livello "+row[2]+"\n"
        conn.close()
        utenti_registrati = utenti_registrati[:-1]
        update.message.reply_text(utenti_registrati,
                                  reply_markup=raid_markup)
        return RAID


def raidedit_management(bot, update, user_data):
    text = update.message.text
    if text == "Menu":
        update.message.reply_text("Ok! Ritorno al menu' principale.",
                                  reply_markup=raid_markup)
        return RAID
    elif text.isdigit():
        presente = False
        conn = sqlite3.connect('pogohelper.db')
        sel = "SELECT CREATED_BY,BOSS,LAT,LONG,TIME,GYM FROM RAID WHERE ID = %d;" % (int(text))
        cursor = conn.execute(sel)
        for row in cursor:
            presente = True
            user_data['raidexpire'] = row[4]
            update.message.reply_text("Ok! Selezionato il RAID numero %d con BOSS %s!"
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
            for row in cursor:
                if row[0] == update.message.chat_id:
                    partecipo = True
                sel2 = "SELECT NAME,TEAM,LEVEL FROM USERS WHERE ID = %d;" % (row[0])
                cursor2 = conn.execute(sel2)
                for row2 in cursor2:
                    if row2[1] == "Istinto-Giallo":
                        totgialli += 1
                    elif row2[1] == "Saggezza-Blu":
                        totblu += 1
                    elif row2[1] == "Coraggio-Rosso":
                        totrossi += 1
                    if row2[2] >= 40:
                        tot40 += 1
                    elif row2[2] >= 35:
                        totover35 += 1
                    elif row2[2] >= 30:
                        totover30 += 1
                        
                    tempo_preferito = str(datetime.strptime(row[2],'%Y-%m-%d %H:%M:%S').strftime('%H:%M'))
                    if row[0] == update.message.chat_id:
                        update.message.reply_text("A questo RAID partecipi anche te!",
                                                  reply_markup=ReplyKeyboardRemove())
                    else:
                        update.message.reply_text("A questo RAID partecipa anche %s!\n"
                                                  "E' un livello %d e appartiene al Team %s\n"
                                                  "L'orario a cui preferisce partecipare al RAID e': %s"
                                                  % (row2[0], int(row2[2]), row2[1], tempo_preferito),
                                                  reply_markup=ReplyKeyboardRemove())
                    if tempo_preferito in dict_preferred_time:
                        dict_preferred_time[tempo_preferito] += 1
                    else:
                        dict_preferred_time[tempo_preferito] = 1
                    if row[1] > 0:
                        update.message.reply_text("%s ha anche %d amici che partecipano!"
                                                  % (row2[0],row[1]))
                        totpartecipanti += row[1]
                        totamici += row[1]
                        dict_preferred_time[tempo_preferito] += row[1]
                totpartecipanti += 1
            if totpartecipanti == 0:
                update.message.reply_text("Per ora non ci sono partecipanti a questo RAID!\n"
                                          "Vuoi partecipare?",
                                          reply_markup=confirmyesno_markup)
                conn.close()
                user_data['raidid'] = text
                user_data['choice'] = "confirmraidattend"
                user_data['firstattend'] = True
                return CONFIRMYESNO
            else:
                preferred_time = "Gli orari preferiti per il RAID sono (con i relativi partecipanti):\n"
                for key, value in dict_preferred_time.items():
                    preferred_time += "Ore "+str(key)+" Partecipanti "+str(value)+"\n"
                preferred_time = preferred_time[:-1]
                update.message.reply_text("Per ora ci sono %d partecipanti a questo RAID!\n"
                                          "Ci sono %d del team Istinto-Giallo\n"
                                          "Ci sono %d del team Saggezza-Blu\n"
                                          "Ci sono %d del team Coraggio-Rosso\n"
                                          "Ci sono %d livelli 40\n"
                                          "Ci sono %d livelli 35 o superiore\n"
                                          "Ci sono %d livelli 30 o superiore\n"
                                          "Ci sono %d amici che partecipano\n"
                                          "%s"
                                          % (totpartecipanti, totgialli, totblu, totrossi, tot40, totover35, totover30, \
                                          totamici, preferred_time),
                                          reply_markup=ReplyKeyboardRemove())
                if partecipo:
                    update.message.reply_text("Partecipi gia' a questo RAID!\n"
                                              "Confermi la tua partecipazione?",
                                              reply_markup=confirmyesno_markup)
                    conn.close()
                    user_data['raidid'] = text
                    user_data['choice'] = "confirmraidattend"
                    return CONFIRMYESNO
                else:
                    update.message.reply_text("Per ora non stai partecipando a questo RAID!\n"
                                              "Vuoi partecipare?",
                                              reply_markup=confirmyesno_markup)
                    conn.close()
                    user_data['raidid'] = text
                    user_data['choice'] = "confirmraidattend"
                    return CONFIRMYESNO
        else:
            update.message.reply_text("Il RAID che mi hai indicato non esiste!\n"
                                      "Ritorno al menu' principale.",
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
    sel = "SELECT RAID.ID,RAID.BOSS,USERS.FIRSTNAME,USERS.SURNAME,USERS.USERNAME,RAID.LAT,RAID.LONG,RAID.TIME \
           FROM RAID LEFT JOIN USERS ON RAID.CREATED_BY = USERS.ID WHERE RAID.CREATED_BY != %d ORDER BY RAID.ID;" \
           % (job.context)
    conn = sqlite3.connect('pogohelper.db')
    cursor = conn.execute(sel)
    for row in cursor:
        notificato = False
        sel2 = "SELECT ID FROM NOTIFICATIONS WHERE RAIDID = %d AND PLAYERID = %d;" % (row[0], job.context)
        cursor2 = conn.execute(sel2)
        for row2 in cursor2:
            notificato = True
        if not notificato:
            scadenza = datetime.strptime(row[7],'%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
            bot.send_message(job.context, text="E' stato creato un nuovo RAID ID %d con BOSS %s e scadenza %s da %s %s @%s, segue posizione:" % (row[0],row[1],scadenza,row[2],row[3],row[4]))
            bot.sendLocation(job.context,row[5],row[6])
            ins = "INSERT INTO NOTIFICATIONS (RAIDID,PLAYERID) VALUES (%d, %d);" % (row[0], job.context)
            conn.execute(ins)
            conn.commit()
    upd = "UPDATE USERS SET HEARTBEAT = datetime('now','localtime') WHERE ID = %d;" % (job.context)
    conn.execute(upd)
    conn.commit()
    conn.close()


def main():
    # Create the Updater and pass it your bot's token.
    updater = Updater(token_id.strip())

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start, pass_job_queue=True, pass_user_data=True)],

        states={
            TEAM: [RegexHandler('^(Istinto-Giallo|Saggezza-Blu|Coraggio-Rosso)$',
                                received_information,
                                pass_user_data=True),
                   ],
            CONFIRM: [RegexHandler('^(Confermo|Ricomincia)$',
                                   received_information,
                                   pass_user_data=True),
                      ],
            CONFIRMYESNO: [RegexHandler('^(Si|No)$',
                                        received_information,
                                        pass_user_data=True),
                           ],
            RAID: [RegexHandler('^(Vedi RAID Attivi|Crea Nuovo RAID|Vedi Utenti Registrati|Abilita Notifiche|Disabilita Notifiche|Edita Profilo)$',
                                raid_management,
                                pass_job_queue=True,
                                pass_user_data=True),
                   ],
            RAIDEDIT: [RegexHandler('^([1-9]|[1-9][0-9]|[1-9][0-9][0-9]|[1-9][0-9][0-9][0-9]|[1-9][0-9][0-9][0-9][0-9]|Menu)$',
                                    raidedit_management,
                                    pass_user_data=True),
                       ],
            RAIDFRIENDS: [RegexHandler('^([1-9]|10|Nessuno)$',
                                       received_information,
                                       pass_user_data=True),
                          ],
            RAIDPREFERREDTIME: [RegexHandler('^([0-9]|0[0-9]|1[0-9]|2[0-3]):(0|1|3|4)(0|5)$',
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

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
