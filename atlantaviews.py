from __init__ import db
from flask import Flask, Blueprint, render_template
import folium
from folium.plugins import MarkerCluster, HeatMap
from geopy.geocoders import Nominatim, ArcGIS
import json
from models import Solar_List, Solar_Wattage, Florida_Facility
import numpy as np
import pandas as pd
import openrouteservice
from openrouteservice import client, Client
from openrouteservice.client import distance_matrix, pelias_search
import requests
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union


atlantaviews = Blueprint('atlantaviews', __name__)

ors_API_key = '5b3ce3597851110001cf624819743d9af4454a189cb1389e6f22df78'
base_url='http://192.168.3.104:8080/ors'
ors_client = client.Client(key=ors_API_key, base_url=base_url)

atlanta_location = [33.97189936097202, -83.97788941494869]
florida_location = [ 27.6, -82.3]

m = folium.Map(location=florida_location, zoom_start=9)


@atlantaviews.route('/')
def atlanta_home():

    # Only need to run this once to set the values to the right table
    # get_wattages()

    # Fills the 'state' column in Solar_Wattage to match Solar_List
    # get_state()

    # directions_check()

    determine_location()

    # generate_map()

    # lat_long_save()

    # florida_facility_stats()

    # per_minute_plot()

    # get_tech()

    return render_template('Cleanup (old html files)/home.html')


def get_state():
    states = Solar_List.query.all()

    for location in states:
        try:
            current_loc = Solar_Wattage.query.filter_by(id=location.id).first()
            current_loc.state = location.state
            db.session.commit()
        except Exception as e:
            print("Can't get state for id", location.id, e)
            continue


# Sets the highest wattage between the ac and dc capacities to the Solar_Wattage table.
def get_wattages():
    locations = Solar_List.query.all()


    for location in locations:
        try:
            # print('Location:', location)
            wattage = 0
            if location.dc_capacity is not None:
                if location.ac_capacity < location.dc_capacity:
                    wattage = location.dc_capacity
            else:
                wattage = location.ac_capacity

            current_loc = Solar_Wattage.query.filter_by(id=location.id).first()
            current_loc.highest_wattage = wattage
            db.session.commit()
        except Exception as e:
            print('Exception at', location.id, e)


def calculate_travel_time(start, end):
    coords = ((start[1], start[0]), (end[1], end[0]))
    routes = None
    try:
        routes = ors_client.directions(coordinates=coords, profile='driving-car')
        # print(routes)
    except Exception as e:
        # print("Exception in calculate travel time!", e)
        if routes:
            print(routes)
        return np.inf
    return routes['routes'][0]['summary']['duration'] / 3600


def calculate_score(location, facilities):
    score = 0
    highest_travel_time = 0
    for facility in facilities:
        atlanta_time = calculate_travel_time(atlanta_location, facility)
        travel_time = calculate_travel_time(location, facility)

        if travel_time == np.inf or atlanta_time == np.inf:
            continue

        if travel_time > atlanta_time:
            continue

        if travel_time > 10:
            print("Travel time is", travel_time)
            return -np.inf

        score += facility[2] / travel_time
        if travel_time > highest_travel_time:
            highest_travel_time = travel_time
    if highest_travel_time > 0:
        print('Highest Travel Time:', highest_travel_time)
    return score


def pull_states():
    nearby = Solar_Wattage.query.filter(Solar_Wattage.state.in_(["FL", "AL", "GA"])).all()

    return nearby


def determine_location():
    nearby = pull_states()
    facilities = []
    grid = np.mgrid[25:33:0.1, -87:-78:0.1].reshape(2, -1).T
    best_score = -np.inf
    best_location = None
    longest_travel = 0

    for item in nearby:
        if item.technology == "Batteries":
            print(item.id, "Batteries!")
        facilities.append([item.latitude, item.longitude, item.highest_wattage])

    for location in grid:
        try:
            print("Current Location", location)
            score = calculate_score(location, facilities)
            if score > best_score:
                best_score = score
                best_location = location
        except Exception as e:
            print('Exception! in grid loop!', location, e)
            continue

    if best_location is None:
        print("Best Location is None!")
        return

    print('Best Location:', best_location)

    folium.Marker(location=atlanta_location,
                  popup="<strong>Atlanta Facility</strong>",
                  icon=folium.Icon(icon='cloud', color='green')).add_to(m)

    folium.Marker(location=best_location).add_to(m)

    m.save('templates/determine-location.html')



def directions_check():
    location = [28.869204423374594, -81.99371476357938]
    coords=((atlanta_location[1], atlanta_location[0]), (location[1], location[0]))
    routes = ors_client.directions(coordinates=coords, profile='driving-car')

    print(routes)


def generate_map():
    """
    Used to generate a map that showed the Atlanta and Florida facilities.
    Includes travel time for each point.
    :return:
    """
    best_location = [27.6, -82.3]

    fg1 = folium.FeatureGroup(name="Recycling Locations")
    fg2 = folium.FeatureGroup(name="Atlanta Reach")
    fg3 = folium.FeatureGroup(name="Florida Reach")

    facilities = []
    nearby = pull_states()

    for item in nearby:
        facilities.append([item.latitude, item.longitude])

    for facility in facilities:
        try:
            print(facility)

            if facility is [None, None]:
                print('Location is None!', facility)
                continue

            atlanta_time = calculate_travel_time(facility, atlanta_location)
            florida_time = calculate_travel_time(facility, best_location)

            if atlanta_time is None or florida_time is None:
                print('Location is None!', facility)
                continue

            if atlanta_time < florida_time:
                folium.Marker(location=facility, popup=f'<strong>{atlanta_time} hours to Atlanta</strong>', icon=folium.Icon(icon='chevron-double-up', color='red')).add_to(fg2)
            elif florida_time is not np.inf:
                folium.Marker(location=facility, popup=f'<strong>{florida_time} hours to Florida</strong>', icon=folium.Icon(icon='chevron-double-down')).add_to(fg3)
        except Exception as e:
            print('Facility is None!', e)

    folium.Marker(location=atlanta_location, popup='<strong>Atlanta Location</strong>', icon=folium.Icon(color='green')).add_to(fg1)
    folium.Marker(location=best_location, popup='<strong>Florida Location</strong>',
                  icon=folium.Icon(color='green')).add_to(fg1)

    fg1.add_to(m)
    fg2.add_to(m)
    fg3.add_to(m)

    folium.LayerControl().add_to(m)

    m.save('templates/plot-locations.html')


def lat_long_save():
    facilities = Solar_List.query.all()

    for location in facilities:
        try:
            current_loc = Solar_Wattage.query.filter_by(id=location.id).first()
            current_loc.latitude = location.latitude
            current_loc.longitude = location.longitude
            db.session.commit()
        except Exception as e:
            print("Exception!", location.id, e)



def get_right_time(facility, highest_wattage):

    score = 0
    # check = [facility.latitude, facility.longitude]
    atlanta_time = calculate_travel_time(atlanta_location, facility)
    travel_time = calculate_travel_time(florida_location, facility)
    # try:
    if travel_time == np.inf or atlanta_time == np.inf:
        print('Infinite time!')
        return None, None, None

    # if travel_time > atlanta_time:
    #     print('Atlanta Location!')
    #     return None, None

    # if travel_time > 10:
    #     print("Travel time is", travel_time)
    #     return -np.inf

    if atlanta_time < travel_time:
        cf = "Atlanta"
        score += facility[2] / atlanta_time
        return atlanta_time, score, cf

    if atlanta_time > travel_time:
        cf = "Florida"
        score += facility[2] / travel_time
        return travel_time, score, cf

    # except Exception as e:
    #     print('Get Right Time Error!', atlanta_time, travel_time, e)
    #     return None, None


def florida_facility_stats():
    """
    Used to fill Florida_Facility table in database with relevant stats.
    :return:
    Outputs info to database
    """
    florida_facilities = Solar_List.query.filter_by(state="FL").all()

    for facility in florida_facilities:
        if facility.technology == "Batteries":
            print(facility.id, "Batteries!")
            continue

        id = facility.id
        solar_wattage_table = Solar_Wattage.query.filter_by(id=id).first()
        highest_wattage = solar_wattage_table.highest_wattage
        latitude = facility.latitude
        longitude = facility.longitude
        street_address = str(facility.street_address + ", " + facility.city + ", " + facility.state + " " + str(facility.zip))
        try:
            time_to_facility, score, cf = get_right_time([facility.latitude, facility.longitude, highest_wattage], highest_wattage)
        except Exception as e:
            time_to_facility, score, cf = None, None, None
            print('Exception!', id, facility.latitude, facility.longitude, highest_wattage, e)

        mw_minute = 0
        if time_to_facility is not None:
            mw_minute = highest_wattage / (time_to_facility * 60)
        else:
            mw_minute = None



        # print(id, "Time:", time_to_facility, "Wattage:", highest_wattage, "Per Minute:", mw_minute)


        # print(street_address)
        # print(id, time_to_facility, score)

        db.session.add(Florida_Facility(id=id, closest_facility=cf, highest_wattage=highest_wattage, latitude=latitude,
                                        longitude=longitude, street_address=street_address, time_to_facility=time_to_facility,
                                        score=score, mW_per_minute=mw_minute))
    db.session.commit()


def per_minute_plot():
    fg1 = folium.FeatureGroup(name="Recycling Locations")
    fg2 = folium.FeatureGroup(name="Atlanta Reach")
    fg3 = folium.FeatureGroup(name="Florida Reach")

    nearby = Florida_Facility.query.all()

    for item in nearby:
        try:
            location = ([item.latitude, item.longitude])

            text = f'<strong>{item.street_address}</br>{item.time_to_facility} hours to {item.closest_facility}</br>{item.mW_per_minute} mW/min</strong>'
            iframe = folium.IFrame(text)
            popup = folium.Popup(iframe, min_width=250, max_width=1000)
            tooltip = "Click Here for Info"

            if item.closest_facility == "Florida":

                folium.Marker(location=location,
                              popup=popup,
                              tooltip=tooltip,
                              icon=folium.Icon(icon='arrow-down-circle-fill')).add_to(fg3)

            if item.closest_facility == "Atlanta":
                folium.Marker(location=location,
                              popup=popup,
                              tooltip=tooltip,
                              icon=folium.Icon(icon='arrow-up-circle-fill', color='red')).add_to(fg2)

        except Exception as e:
            print('Exception!', item.id, e)

    folium.Marker(location=atlanta_location, popup='<strong>Atlanta Location</strong>',
                  icon=folium.Icon(color='green')).add_to(fg1)
    folium.Marker(location=florida_location, popup='<strong>Florida Location</strong>',
                  icon=folium.Icon(color='green')).add_to(fg1)

    fg1.add_to(m)
    fg2.add_to(m)
    fg3.add_to(m)

    folium.LayerControl().add_to(m)

    m.save('templates/mW-per-minute.html')


def get_tech():
    items = Solar_Wattage.query.all()
    for item in items:
        current_item = Solar_List.query.filter_by(id=item.id).first()
        item.technology = current_item.technology
        db.session.commit()



