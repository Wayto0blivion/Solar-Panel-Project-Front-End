from __init__ import db
from flask import Flask, Blueprint, render_template
import folium
from models import Solar_List, Texas_Facility
import numpy as np
from openrouteservice import client
import asyncio
import aiohttp
import concurrent.futures
from shapely.geometry import Point, Polygon
from multiprocessing import Pool


texasviews = Blueprint('texasviews', __name__)

ors_API_key = '5b3ce3597851110001cf624819743d9af4454a189cb1389e6f22df78'
base_url = 'http://192.168.3.104:8080/ors'
ors_client = client.Client(key=ors_API_key, base_url=base_url)
texas_map_location = [99.9, 31.96]

# This is for reference to compare the async version to.
Best_Location = [31.7, -102.7]
Waco_Location = [31.56, -97.18]

@texasviews.route('/', methods=['GET', 'POST'])
def texas_home():

    # determine_location()

    add_to_database()

    add_waco_stats()

    return render_template('home.html')


@texasviews.route('/testing', methods=['GET', 'POST'])
def texas_testing():

    return render_template('home.html')


def texas_facility_stats():
    '''
    For filling the Texas Facility table with relevant stats
    :return:
    Outputs info to database
    '''

    texas_facilities = Solar_List.query.filter_by(state='TX').all()

    for facility in texas_facilities:
        if facility.technology == "Batteries":
            print(facility.id, "Batteries!")
            continue

        id = facility.id
        highest_wattage = None
        if facility.ac_capacity >= facility.dc_capacity:
            highest_wattage = facility.ac_capacity
        else:
            highest_wattage = facility.dc_capacity
        latitude = facility.latitude
        longitude = facility.longitude
        try:
            street_address = str(facility.street_address + ", " + facility.city + ", " + facility.state + " " + str(facility.zip))
        except Exception as e:
            street_address = 'TBD'
            print(facility.id, e)

        try:
            db.session.add(Texas_Facility(id=id, closest_facility=None, highest_wattage=highest_wattage, latitude=latitude,
                                            longitude=longitude, street_address=street_address, time_to_facility=0,
                                            score=0, mW_per_minute=0))
        except Exception as e:
            print("Exception with", facility.id, e)

        db.session.commit()


# def determine_location():
#     nearby = Texas_Facility.query.all()
#     facilities = []
#     grid = np.mgrid[26:36:0.1, -106:-93:0.1].reshape(2, -1).T
#     best_score = -np.inf
#     best_location = None
#     longest_travel = 0
#
#     for item in nearby:
#         facilities.append([item.latitude, item.longitude, item.highest_wattage])
#
#     for location in grid:
#         try:
#             print("Current Location:", location)
#             score = calculate_score(location, facilities)
#             if score > best_score:
#                 best_score = score
#                 best_location = location
#         except Exception as e:
#             print('Exception! in grid loop!', location, e)
#             continue
#
#     if best_location is None:
#         print("Best Location is None!")
#         return
#
#     print('Best Location:', best_location)
#
#     m = folium.Map(location=texas_map_location, zoom_start=9)
#
#     folium.Marker(location=best_location,).add_to(m)
#
#     m.save('/determine-location-texas.html')


def determine_location():
    nearby = Texas_Facility.query.all()
    facilities = []
    grid = np.mgrid[26:36:0.1, -106:-93:0.1].reshape(2, -1).T
    best_score = -np.inf
    best_location = None
    longest_travel = 0

    for item in nearby:
        facilities.append([item.latitude, item.longitude, item.highest_wattage])

    locations_with_facilities = [(location, facilities) for location in grid]

    with Pool(processes=6) as pool:
        results = pool.map(calculate_score_for_location, locations_with_facilities)

    for location, score in results:
        if score is not None and score > best_score:
            best_score = score
            best_location = location

    if best_location is None:
        print("Best Location is None!")
        return

    print('Best Location:', best_location)

    m = folium.Map(location=texas_map_location, zoom_start=9)

    folium.Marker(location=best_location,).add_to(m)

    m.save('/determine-location-texas.html')


def calculate_score(location, facilities):
    score = 0
    highest_travel_time = 0
    for facility in facilities:
        travel_time = calculate_travel_time(location, facility)

        if travel_time == np.inf:
            continue

        if travel_time > 15:
            # print("Travel time is", travel_time)
            return -np.inf
        # else:
            # print("Too High! Travel time is", travel_time)

        score += facility[2] / travel_time
        if travel_time > highest_travel_time:
            highest_travel_time = travel_time

    if highest_travel_time > 0:
        print("Highest Travel Time:", highest_travel_time)
    return score


def calculate_travel_time(start, end):
    coords = ((start[1], start[0]), (end[1], end[0]))
    routes = None
    try:
        routes = ors_client.directions(coordinates=coords, profile='driving-car')
        return routes['routes'][0]['summary']['duration'] / 3600
    except Exception as e:
        if routes:
            print(routes)
        print("No route found", e)
        return np.inf


@texasviews.route('/show-location')
def show_location():
    m = folium.Map(location=Best_Location, zoom_start=7)

    folium.Marker(location=Best_Location).add_to(m)

    m.save('./determine-location-texas.html')

    return 'Location Map Generated!'


@texasviews.route('/show-facility-locations')
def show_all_locations():
    m = folium.Map(location=Best_Location, zoom_start=7)

    nearby = Texas_Facility.query.all()
    facilities = []

    for item in nearby:
        facilities.append([item.latitude, item.longitude, item.highest_wattage])

    for facility in facilities:
        folium.Marker(location=[facility[0], facility[1]],
                      popup=f"{facility[2]}",
                      icon=folium.Icon(icon='cloud', color='green')
                      ).add_to(m)

    m.save('./all-texas-facilities.html')

    return "Facility Map Generated!"


def calculate_score_for_location(args):
    location, facilities = args
    try:
        score = calculate_score(location, facilities)
        return (location, score)
    except Exception as e:
        print(f"Exception calculating score for location {location}: {e}")
        return (location, None)


def add_to_database():
    facilities = []
    nearby = Texas_Facility.query.all()

    for item in nearby:
        facilities.append([item.latitude, item.longitude, item.highest_wattage])

    for item in nearby:
        try:
            time = calculate_travel_time((item.latitude, item.longitude), Best_Location)
            if time != float('inf'):
                item.time_to_facility = time
                mw_per_min = item.highest_wattage / (time * 60)
                item.mW_per_minute = mw_per_min
            else:
                print(f"Skipping update for {item.id} due to infinite travel time")
                continue
            score = calculate_score(Best_Location, facilities)
            item.score = score
            db.session.commit()

        except Exception as e:
            db.session.rollback()
            print(f"Error! Location: {item.id} --- {str(e)}")


def add_waco_stats():
    facilities = []
    nearby = Texas_Facility.query.all()

    for item in nearby:
        facilities.append([item.latitude, item.longitude, item.highest_wattage])

    for item in nearby:
        try:
            time = calculate_travel_time((item.latitude, item.longitude), Waco_Location)
            if time != float('inf'):
                item.waco_ttf = time
                mw_per_min = item.highest_wattage / (time * 60)
                item.waco_mw_per_min = mw_per_min
            else:
                print(f"Skipping update for {item.id} due to infinite travel time")
                continue
            score = calculate_score(Waco_Location, facilities)
            item.waco_score = score
            db.session.commit()

        except Exception as e:
            db.session.rollback()
            print(f"Error! Location: {item.id} --- {str(e)}")