#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 20 21:57:01 2016

@author: Michel HUNSICKER
"""

# Data base and initial data import
from datetime import timedelta, date, datetime, time

#Import de time
import time as system_time

# Used to launch a request for multiple courses 
import threading
THREAD_ITER = 20 #Nombre de requêtes successives de chaque thread
THREAD_NUMBER = 10 #Nombre de thread pour les requêtes
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
COURSE_LIST = private_data.COURSE_LIST
BOOKING_DELAY = 8*24  # en heure normalement 48
INTERVAL_DELAY = 0.1 # en heure normalement 6 minutes
DELAY_SUP = (BOOKING_DELAY + INTERVAL_DELAY) * 3600  #Mettre 48h et 10 minutes soit 48.1*3600
DELAY_INF = (BOOKING_DELAY - INTERVAL_DELAY) * 3600  #Après 10m, on considère que le cours est complet

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
    Impression à l'écran avec l'horodatage préfixée.
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


def booking_thread_function(id_thread,id_session, id_course, course, 
                            course_datetime,iterations):
    log_print(f"Le thread {id_thread} a été lancé)")
    for i in range(iterations):
        result = course_booking(id_session, id_course)
        log_print(f"Le résultat de la requête {i+1} du thread {id_thread} pour\
                  la séance de {course['activity']} référencée {id_course} est {result}")
        if result[0]:
            synthese = f"Cours de {course['activity']} réservé le\
                        {course_datetime.date()} à\
                        {course_datetime.time()}"
            log_print(synthese)
            send_email(SUPPORT_EMAIL, synthese, "Well done")
            send_email(USER_EMAIL, synthese, "My husband is fantastic !")
            
            return
    log_print(f"Le thread {id_thread} pour la séance de {course['activity']}\
              référencée  {id_course} est terminé)")

def reservation_cours(course_list):
    """
    Récupération des cours listés et selon la liste des jours. Le cours est
    supposé du matin.
    A priori l'ouverture de la réservation survient 48 heures avant le cours
    A faire: Revoir le process des jours cf. utilisation de crontab.
    """
    id_session = authenticate()
    
    #Selection des cours à réserver en fonction du temps du démarrage.
    
    course_to_book = None
    id_course_to_book = None
    booking_datetime = None #La date est unique par lancem,net cf. délai des cours.
    now = datetime.now()    
    
    for course in course_list: 
                
        #Au final il n'y aura qu'un cours retenu (cf. délai et pas de
        #superposition de cours possible (A tester en théorie à la saisie
        #des cours). 
        course_date = get_next_weekday(course['day'])
        course_time = time(hour=course['start']['hour'],
                           minute=course['start']['minute'] )
        course_datetime = datetime.combine(course_date, course_time)
        time_to_course = (course_datetime - now).total_seconds()
        
        if (time_to_course < DELAY_SUP) and (time_to_course > DELAY_INF):
            course_to_book = course   
            booking_datetime = course_datetime
    if course_to_book == None: 
        log_print("Pas de cours à réserver dans l'intervalle")
    
    else:
        #Récupération de l'ID du cours concerné
        payload = {"dates":booking_datetime.date().strftime('%d-%m-%Y'),
                   "idErreur":0,
                   "idSession": id_session,
                   "status":0,
                   "taches":ACTIVITY_LIST[course_to_book['activity']],
                   "type":12}
                         
        req = requests.post(URL_JSON, HEADERS, params=payload)
        request_answer = req.json()
        #On prend le cours du matin (supposé être le premier cours).
        for possible_course in request_answer["reservation"]:
            content = dict(possible_course)
            time_components = content['debutHeure'].split(":")
            #On récupère la séance correspondant à l'heure préuve 
            if (int(time_components[0]) == booking_datetime.time().hour ) and \
               (int(time_components[1]) == booking_datetime.time().minute): 
                   id_course_to_book = dict(request_answer["reservation"][0])['id']
    
        #Boucle pour attendre la seconde précédent la minute suivante
        #A revoir peut être avec le système de thread pour déclencher tout.                
        while datetime.now().second   < 59:
            system_time.sleep(0.5)
        #lancement des threads cf. parallélisation des requêtes
        threads = []
        for id_thread in range(THREAD_NUMBER):
            t = threading.Thread(target=booking_thread_function, 
                                 args=(id_thread,
                                       id_session, 
                                       id_course_to_book,
                                       course_to_book,
                                       booking_datetime,                              
                                       THREAD_ITER))
            threads.append(t)
        [t.start() for t in threads]
        #Pour attendre la fin de tous les threads.
        [t.join() for t in threads]
                    
#                    result = course_booking(id_session, cours_disponible['id'])
#                    #log_print(f"Résa pour {key} le {jours} donne {result}")
#                    if result[0]:
#                        synthese = f"Cours de {key}\
#                                  réservé le {cours_disponible['date']} à\
#                                  {cours_disponible['debutHeure']} "
#                        log_print(synthese)
#                        send_email(SUPPORT_EMAIL, synthese, "Well done")
#                        send_email(USER_EMAIL, synthese, "My husband is fantastic !")
#                        return
#        
#                log_print(f"Cours non réservé cf. erreur {result[1]}")
            
            #send_email(SUPPORT_EMAIL, synthese, "Well done")


#reservation_cours(ACTIVITY_LIST)

try:
    log_print("Démarrage du processus de réservation")
    reservation_cours(COURSE_LIST)

except Exception as exception:
    log_print("Erreur dans la  " + str(exception))
    send_email(SUPPORT_EMAIL, "Le processus de réservation cours a planté",
               "L'erreur est :" + str(exception))

log_print("Le processus de réservation s'est bien déroulé")
