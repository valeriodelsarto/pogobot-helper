# pogobot-helper

pogobot-helper is a Telegram Bot that helps Pokémon-Go Players to collaborate and coordinate in order to succesfully accomplish the RAID Battles.

It's written in Python and uses the [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) API.
It uses a local SQLite database for data persistence.
It uses [GNU Screen](https://www.gnu.org/software/screen/) to launch itself with a Bash startup script.

### Installation

* Clone this GitHub repo!
* Install dependencies (if needed)
* Create a local Python Virtual Environment (suggested) (step included into init.sh script file)
* Create the local SQLite database from the provided SQL schema file (step included into init.sh script file)
* Get a custom BOT TOKEN from Telegram [@BotFather](https://core.telegram.org/bots#6-botfather)
* Run the BOT!

```sh
$ git clone https://github.com/valeriodelsarto/pogobot-helper.git
$ cd pogobot-helper
$ ./init.sh
$ cp token_id.example token_id
$ vi token_id (insert your personal Telegram BOT Token here)
$ cp admins.txt.example admins.txt
$ vi admins.txt (insert only your(s) Telegram ID(s) here)
$ ./startup.sh
```

### Things to know

Some useful files included in this repo and their meanings (authorized.json right now is not used, only blocked.json is used):

| File | Content |
| ------ | ------ |
| authorized.json | a JSON list of Telegram users authorized to use this BOT |
| blocked.json | a JSON list of Telegram users blocked and not able to use this BOT |
| init.sh | a BASH script that create a local Python Virtual Environment and the local SQLite database |
| launch.sh | a BASH script that launch the BOT from GNU Screen |
| pogohelper.db.sql | a SQL file that contains the SQLite database schema |
| raidboss | a TEXT file that contains the actual Pokemon-Go RAID Bosses |
| startup.sh | a BASH script that starts GNU Screen with launch.sh (include this script into /etc/rc.local) |
| token_id | a TEXT file that contains your personal Telegram BOT TOKEN |
| admins.txt | a TEXT file that contains IDs of Telegram users that can restart your bot |
| languages/*.json | JSON files that contains the localizations of the BOT in different languages |

authorized.json, blocked.json, token_id and admins.txt files are provided with .example extension, copy and modify them as needed. 

### Development

Want to contribute? Great! [Fork my repo, apply your changes and open me a PR](https://help.github.com/articles/creating-a-pull-request-from-a-fork/)!

### Translations

If you want to help me adding support for your language into this BOT, please make a copy of languages/english.json and translate the value of every row, then send me a PR or directly the new JSON file! Thanks!

### Todos

 - To be defined!

License
----

GPL
