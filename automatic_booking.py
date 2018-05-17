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

#import asyncio
import asyncio
import aiohttp #Asynchronous web access

# Internet access
import requests #Synchronous web access

#Import of the private data for Heitzfit access and mailserver.
import private_data

# Used to launch a request for multiple courses
REQUEST_ITER = 20 #Nombre de requêtes successives pour chaque series
SERIES_NUMBER = 5 #Nombre d'appel successif  pour les requêtes

#Used to synchronise:
SEMAPHORE = False #The course has not yet been booked.

# Intenet site access variables for Heitzfit
HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:58.0)\
            Gecko/20100101 Firefox/58.0'}
LOGIN = private_data.LOGIN #string
PASSWORD = private_data.PASSWORD #string
URL_JSON = private_data.URL_JSON #string
ACTIVITY_LIST = private_data.ACTIVITY_LIST #dictionnary
DAY_LIST = private_data.DAY_LIST #List
COURSE_LIST = private_data.COURSE_LIST
CODES_ARRET_NEGATIF = {202:"cours déjà réservé", 201:"cours complet"}
CODES_ARRET = (CODES_ARRET_NEGATIF.copy())
CODES_ARRET.update({203:"cours pas encore ouvert à la réservation"})

#Parammètres de la fenêtre de réservation du cours
BOOKING_DELAY = 2*24  # en heure normalement 48
BOOKING_INTERVAL_DELAY = 0.3 # en heure normalement 6 minutes soit 0.1
#Mettre 48h et 10 minutes soit 48.1*3600
BOOKING_DELAY_SUP = (BOOKING_DELAY + BOOKING_INTERVAL_DELAY) * 3600
#Après 10m, on considère que le cours est complet
BOOKING_DELAY_INF = (BOOKING_DELAY - BOOKING_INTERVAL_DELAY) * 3600

#Paramètres de la fenêtre de lancement des requêtes:
REQUEST_INTERVAL_DELAY_INF = 250000 #59 seconds + X Microseconds

REQUEST_INTERVAL_DELAY_SUP = 50000 #0 seconds + Microseconds


REQUEST_SERIES_INTERVAL = 0.2 #seconds


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
    try:
        req = requests.post(URL_JSON, HEADERS, params=payload)
        request_answer = req.json()
        return (True, request_answer["idSession"])
    except Exception as exception:
        log_print("Fonction authenticate() - Erreur de la connexion request :"+
                  str(exception))
        return (False, "")

async def course_booking(iteration, id_session, id_course, course,
                         course_datetime):
    """
    Demande de réservation en cas de succès renvoie True et False en cas
    de problème avec le code d'erreur.
    """
    global SEMAPHORE
    #log_print(f"L'iteration {iteration} a été lancée")
    payload = {"idErreur":0,
               "idRequete":id_course,
               "idSession": id_session,
               "place":1, #Nombre de places à réserver
               "status":0,
               "type":301}

    async with aiohttp.ClientSession() as session:
        if SEMAPHORE:
            return
        async with session.post(URL_JSON, data=payload, headers=HEADERS) as resp:
            request_answer = await resp.json()
            if request_answer['status'] == "ko":
                code_erreur = request_answer['idErreur']
                #Si le cours est complet ou déjà réservé on update le sémaphore
                if code_erreur in CODES_ARRET:
                    if code_erreur  in CODES_ARRET_NEGATIF:
                        #Il faut arrêter car requête inutile.
                        SEMAPHORE = True
                        log_print(f"Arrêt car {CODES_ARRET_NEGATIF[code_erreur]}")

                    log_print(f"Le résultat de la requête {iteration} " +
                              f"pour la séance de {course['activity']} "+
                              f"référencée {id_course} est négatif car "+
                              f"{CODES_ARRET[code_erreur]}")
                else:
                    #Le
                    await log_print(f"Le résultat de la requête {iteration} " +
                                    f"pour la séance de {course['activity']} "+
                                    f"référencée {id_course} est négatif cf. code "+
                                    f"{request_answer['idErreur']}")
                return (False, code_erreur)

            else:
                #La réservation a aboutie.
                SEMAPHORE = True
                synthese = f"Cours de {course['activity']} réservé le\
                           {course_datetime.date()} à\
                           {course_datetime.time()}"
                log_print(synthese)
                send_email(SUPPORT_EMAIL, synthese, "Well done")
                send_email(USER_EMAIL, synthese, "My husband is fantastic !")

def launch_bookings(i, id_session, id_course_to_book, course_to_book,
                    booking_datetime):
    """
    Interface pour lancer la série de requêtes en parallèle
    """
    log_print(f"Lancement de course_booking numéro {i}")
    loop = asyncio.get_event_loop()
    jobs = (course_booking(i, id_session, id_course_to_book, course_to_book,
                           booking_datetime) for i in range(REQUEST_ITER))

    loop.run_until_complete(asyncio.gather(* jobs))
    log_print("Fin de course_booking")


def reservation_cours(course_list):
    """
    Récupération des cours listés et selon la liste des jours. Le cours est
    supposé du matin.
    A priori l'ouverture de la réservation survient 48 heures avant le cours
    A faire: Revoir le process des jours cf. utilisation de crontab.
    """

    authentication = authenticate()
    #Vérification du résultat de l'authentification
    if authentication[0] != True:
        log_print("reservation_cours : l'authentification n'a pas fonctionné")
        #return

    id_session = authentication[1]

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
                           minute=course['start']['minute'])
        course_datetime = datetime.combine(course_date, course_time)
        time_to_course = (course_datetime - now).total_seconds()

        if (time_to_course < BOOKING_DELAY_SUP) and (time_to_course > BOOKING_DELAY_INF):
            course_to_book = course
            booking_datetime = course_datetime

    if course_to_book is None:
        log_print("Pas de cours à réserver dans l'intervalle")

    else:
        log_print("Un cours est à réserver dans l'intervalle")
        #Récupération de l'ID du cours concerné
        payload = {"dates":booking_datetime.date().strftime('%d-%m-%Y'),
                   "idErreur":0,
                   "idSession": id_session,
                   "status":0,
                   "taches":ACTIVITY_LIST[course_to_book['activity']],
                   "type":12}

        try:
            req = requests.post(URL_JSON, HEADERS, params=payload)
            request_answer = req.json()

            #On prend le cours du matin (supposé être le premier cours).
            for possible_course in request_answer["reservation"]:
                content = dict(possible_course)
                time_components = content['debutHeure'].split(":")
                #On récupère la séance correspondant à l'heure préuve
                if (int(time_components[0]) == booking_datetime.time().hour) and \
                    (int(time_components[1]) == booking_datetime.time().minute):
                    id_course_to_book = dict(request_answer["reservation"][0])['id']
        except Exception as exception:
            log_print("Fonction reservation_cours() -"+
                      "Erreur de la connexion request :"+
                      str(exception))
            return

        # Lancement de la procédure asynchrone après le timing pour viser l'heure
        # exacte de déblocage de la réservation.

        while True:
            now = datetime.now().time()
            #log_print(now)
            if ((now.second == 59) and (now.microsecond > REQUEST_INTERVAL_DELAY_INF)) or\
                ((now.second) == 0 and (now.microsecond < REQUEST_INTERVAL_DELAY_SUP)):
                break
            else:
                system_time.sleep(0.1)
        #Launch series of asynchronous series.
        for i in range(SERIES_NUMBER):
            if not SEMAPHORE:
                launch_bookings(i+1, id_session, id_course_to_book,
                                course_to_book, booking_datetime,)
                system_time.sleep(REQUEST_SERIES_INTERVAL)

#Lancement
reservation_cours(COURSE_LIST)

log_print("Le processus de réservation est terminé")
