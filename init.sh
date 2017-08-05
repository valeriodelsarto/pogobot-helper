#!/bin/bash
virtualenv env
sqlite3 pogohelper.db < pogohelper.db.sql
