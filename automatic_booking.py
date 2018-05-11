#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 20 21:57:01 2016

@author: Michel HUNSICKER
"""

# Data base and initial data import
from datetime import timedelta, date, datetime

# Internet access
import requests

#Import of the private data for Heitzfit access and mailserver.
import private_data

# Intenet site access variables for Heitzfit
HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:58.0)\
            Gecko/20100101 Firefox/58.0'}
LOGIN = private_data.LOGIN #string
PASSWORD = private_data.PASSWORD #string
URL_JSON = private_data.URL_JSON #string
ACTIVITY_LIST = private_data.ACTIVITY_LIST #dictionnary
DAY_LIST = private_data.DAY_LIST #List


#Emails for booking notification
USER_EMAIL = private_data.USER_EMAIL
SUPPORT_EMAIL = private_data.SUPPORT_EMAIL



def send_email(receiver, subject, text):
    """
    Envoi d'email via mailgun
    """
    key = private_data.key
    sandbox = private_data.sandbox

    request_url = 'https://api.mailgun.net/v3/{0}/messages'.format(sandbox)

    request = requests.post(request_url, auth=('api', key), data={
        'from': 'Gymclass_bot@mailgun.net',
        'to': receiver,
        'subject': subject,
        'text': text})
    log_print('Email status: {0}'.format(request.status_code))


def get_next_weekday(weekday):
    """
    @weekday: week day as a integer, between 0 (Monday) to 6 (Sunday)
    """
    today = date.today()
    target_day = today + timedelta((weekday - 1 -today.weekday()) % 7 + 1)
    return target_day

def log_print(text):
    """
    Impression préfixée par l'horodatage.
    """
    print((datetime.now()).strftime("%Y-%m-%dT%H:%M:%S"), ": ", text)

def authenticate():
    """
    Authentification pour récupérer l'id de session.
    """
    payload = {"email":LOGIN,
               "code": PASSWORD,
               "status":0,
               "idErreur":0,
               "type":1}
    req = requests.post(URL_JSON, HEADERS, params=payload)
    request_answer = req.json()
    return request_answer["idSession"]


def course_booking(id_session, id_cours):
    """
    Demande de réservation en cas de succès renvoie True et False en cas
    de problème avec le code d'erreur.
    """
    payload = {"idErreur":0,
               "idRequete":id_cours,
               "idSession": id_session,
               "place":1, #Nombre de places à réserver
               "status":0,
               "type":301}
    req = requests.post(URL_JSON, HEADERS, params=payload)
    request_answer = req.json()
    if request_answer['status'] == "ko":
        return (False, request_answer['idErreur'])
    return (True, 0)

def reservation_cours(activity_list):
    """
    #Récupération des cours du samedi et du dimanche matin)
    #cf. Aurélie, le délai est de 48h
    """
    id_session = authenticate()
    #Détermination du prochain samedi et dimanche
    jours_liste = [get_next_weekday(i).strftime('%d-%m-%Y') for i in DAY_LIST]
    #Récupération de la liste des cours
    for key in activity_list.keys():
        for jours in jours_liste:
            payload = {"dates":jours,
                       "idErreur":0,
                       "idSession": id_session,
                       "status":0,
                       "taches":activity_list[key],
                       "type":12}

            req = requests.post(URL_JSON, HEADERS, params=payload)
            request_answer = req.json()
            #On prend le cours du matin (supposé être le premier cours).
            cours_disponible = dict(request_answer["reservation"][0])
            result = course_booking(id_session, cours_disponible['id'])
            log_print(f"Résa pour {key} le {jours} donne {result}")
            if result[0]:
                synthese = f"Cours de {key}\
                          réservé le {cours_disponible['date']} à\
                          {cours_disponible['debutHeure']} "
                log_print(synthese)
                send_email(SUPPORT_EMAIL, synthese, "Well done")
                send_email(USER_EMAIL, synthese, "My husband is fantastic !")

            else:
                synthese = f"Cours non réservé cf. erreur {result[1]}"
                #send_email(SUPPORT_EMAIL, synthese, "Well done")

try:
    log_print("Démarrage du processus de réservation")
    reservation_cours(ACTIVITY_LIST)

except Exception as exception:
    log_print("Erreur dans la  " + str(exception))
    send_email(SUPPORT_EMAIL, "Le processus de réservation cours a planté",
               "L'erreur est :" + str(exception))

log_print("Le processus de réservation s'est bien déroulé")
