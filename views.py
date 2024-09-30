from __init__ import db
from flask import Flask, Blueprint, render_template, redirect, url_for
import folium
from folium.plugins import MarkerCluster, HeatMap
from forms import WeightForm
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


views = Blueprint('views', __name__)

ors_API_key = '5b3ce3597851110001cf624819743d9af4454a189cb1389e6f22df78'
base_url='http://192.168.3.104:8080/ors'
ors_client = client.Client(key=ors_API_key, base_url=base_url)
ors_api = client.Client(key=ors_API_key)

# @views.route('/', methods=['GET', 'POST'])
# def home():
#     """
#     Blank page whose only function is as a landing page
#     :return: home.html, which has no content.
#     """
#     # record = Solar_List.query.filter_by(id=1).first()
#     # print(record.id)
#     # record2 = Solar_List.query.filter_by(id=2).first()
#     #
#     # lon_1 = record.longitude
#     # lat_1 = record.latitude
#     # lon_2 = record2.longitude
#     # lat_2 = record2.latitude
#     #
#     # print(lon_1, lat_1, lon_2, lat_2)
#
#     # call the OSRM API
#
#     # r = requests.get(f"http://router.project-osrm.org/route/v1/car/{lon_1},{lat_1};{lon_2},{lat_2}?overview=false""")
#     #
#     # routes = json.loads(r.content)
#     # route_1 = routes.get('routes')[0]
#     #
#     # print(route_1)
#
#     # nearby, shortlist = pull_states()
#
#     # generate_heat()
#     # calculate_near_atlanta()
#     # points_heatmap()
#
#     # calculate_heat_chat()
#
#     # calculate_heat_second()
#
#     # check_address(-85.7301900, 31.3311480)
#
#     # convert_address()
#
#     # direction_test()
#
#     # geopy_coords()
#
#     # plot_map()
#
#     # get_time()
#
#     return render_template('home.html')

@views.route('/address')
def address_function():
    # check_address(27.681278, -82.16466)
    fix_address()
    return render_template('Cleanup (old html files)/templates/home.html')



@views.route('/generate-folium-map', methods=['GET'])
def folium_map():
    """
    Generates the map with all icons necessary.

    :return: creates map.html and displays it.
    """

    # Generate the start of the map. First step
    m = folium.Map(location=[32.23, -83.20], zoom_start=6)

    tooltip = "Click Here for Info"

    # Add the Atlanta Facility to the map with an individual map marker
    atlanta_facility = [33.97, -83.98]
    atlanta_marker = folium.Marker(
        location=atlanta_facility,
        popup="<strong>Powerhouse Atlanta Facility</strong>",
        tooltip=tooltip,
        icon=folium.Icon(icon='cloud', color='red')
    )
    atlanta_marker.add_to(m)

    # Get all locations from the SouthEast US.
    locations = pull_states()

    # Plot locations in the SouthEast
    for location in locations:
        marker = folium.Marker(
            location = [location.latitude, location.longitude],
            popup=f"<strong>{location.id} - {location.plant_name}</strong>",
            tooltip=tooltip,
        )
        marker.add_to(m)

    # Save the map as an HTML file. Last step.
    m.save("templates/map.html")

    return render_template('Cleanup (old html files)/map.html')


@views.route('/show-map', methods=['GET', 'POST'])
def show_map():
    """
    renders the already generated map

    :return: map.html
    """

    return render_template('Cleanup (old html files)/isochrones.html')


@views.route('/show-map-cluster', methods=['GET', 'POST'])
def show_map_cluster():
    """
    renders the already generated map

    :return: map.html
    """

    locations, shortlist = pull_states()

    # print(shortlist)

    query_matrix(shortlist)

    return render_template('map_cluster.html')


def pull_states():
    """
    Get a list of locations in the Southeast.

    :return: a list of states near Florida
    """
    nearby_list = Solar_List.query.filter(Solar_List.state.in_(["FL"]))
    shortlist = nearby_list.limit(10).all()
    nearby = nearby_list.all()
    count = nearby_list.count()

    # for item in nearby:
    #     print(item.id, "Address:", item.latitude, item.longitude)
    print("Count:", count)

    return nearby, shortlist


@views.route("/calculate-kW")
def calcuate_kW():
    """
    Should only need to call this function once, as once it's generated the data is in MySQL
    """
    list = Solar_List.query.all()

    for item in list:
        try:
            ac = 0
            dc = 0
            if item.ac_capacity != None:
                ac = item.ac_capacity
            if item.dc_capacity != None:
                dc = item.dc_capacity

            newRow = Solar_Wattage(id=item.id, wattage=(
                    (item.ac_capacity if item.ac_capacity is not None else 0) +
                    (item.dc_capacity if item.dc_capacity is not None else 0)
            ))
            db.session.add(newRow)
        except Exception as e:
            print(item.id, e)
            # db.session.rollback()

        db.session.commit()

    return render_template("Cleanup (old html files)/map.html")


def query_matrix(locations):
    """
    Input: locations is from pull_states()
    for querying openrouteservice for a matrix of locations.
    This is currently used for testing the limits.
    Setup to be called while generating map.
    :return:
    """

    client = Client(key=ors_API_key)

    coords = []

    for item in locations:
        try:
            coords.append([float(item.longitude), float(item.latitude)])

        except Exception as e:
            print(item.id, e)

    print(coords)


    # Instructions from the openrouteservice website
    # body = {"locations": coords}
    #
    # print(body)
    #
    # headers = {
    #     'Accept': 'applicatioin/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
    #     'Authorization': ors_API_key,
    #     'Content-Type': 'application/json; charset=utf-8'
    # }
    #
    # call = requests.post('https://api.openrouteservice.org/v2/matrix/driving-car', json=body, headers=headers)
    #
    # print(call.status_code, call.reason)
    # print(call.text)


    # ChatGPT instructions for request
    request = {"locations": coords, "metrics": ['duration']}
    print("Request:", request)
    matrix = distance_matrix(client, request)

    m = folium.Map(location=[sum([c[1] for c in coords])/len(coords),
                             sum([c[0] for c in coords])/len(coords)], zoom_start=6)

    marker_cluster = MarkerCluster().add_to(m)

    for idx, coord in enumerate(coords):
        popup_text = f"<strong>Location {idx+1}</strong?<br>"
        popup_text += "<br>".join([f"Drive time to location {i+1}: {matrix['durations'][idx][i]/60:.2f} mins"
                                   for i in range(len(coords))])

        folium.Marker(location=[coord[1], coord[0]],
                      popup=popup_text,
                      icon=folium.Icon(color='blue', icon='car', prefix='fa')).add_to(marker_cluster)

    m.save('templates/map_cluster.html')


@views.route('/chat-matrix')
def chat_matrix():

    # This first bit still gets the error where location is in the wrong format.
    # client = Client(key=ors_API_key)
    #
    # # Define a list of locations (longitude, latitude)
    # locations = ((8.34234, 48.23424), (8.34423, 48.26424), (8.34523, 48.24424))
    #
    # # Create a distance matrix request
    # request = {'locations': locations, 'metrics': ['distance']}
    #
    # # Send the request
    # matrix = distance_matrix(client, request)
    #
    # # Calculate the average longitude and latitude for the center of the map
    # avg_longitude = sum([location[0] for location in locations]) / len(locations)
    # avg_latitude = sum([location[1] for location in locations]) / len(locations)
    #
    # # Create a Folium map centered around the average coordinates
    # map = folium.Map(location=[avg_latitude, avg_longitude], zoom_start=12)
    #
    # # Add markers to the map for each location
    # for i, location in enumerate(locations):
    #     folium.Marker([location[1], location[0]], popup=f'Location {i + 1}').add_to(map)
    #
    # # Display the map
    # map.save('templates/chat-map.html')

    # This is to generate isochrones
    ors = client.Client(key=ors_API_key, base_url='http://192.168.3.104:8080/ors')

    # list of locations
    locations = []

    nearby, shortlist = pull_states()

    for location in nearby:
        locations.append([location.longitude, location.latitude])

    # This sets the starting location of the map to the mean latitude and longitude of the provided coords
    m = folium.Map(location=[sum([c[1] for c in locations]) / len(locations),
                             sum([c[0] for c in locations]) / len(locations)], zoom_start=6)

    # for each location, generate an isochrone and add it to the map
    for location in locations:
        try:
            isochrone = ors.isochrones(
                locations=[location],  # longitude, latitude
                profile='driving-car',
                # range=[18000],  # 5 hours in seconds, but cannot be used with the website API.
                range=[3600],
            )
        except Exception as e:
            print(location, e)

        style = {'fillColor': 'red', 'color': 'red'}

        # add the isochrone to the map
        folium.GeoJson(
            isochrone,
            name='geojson',
            style_function=lambda x:style
        ).add_to(m)

    for location in locations:
        # print(location[1], location[0])
        marker = folium.Marker(
            location=[location[1], location[0]]
        ).add_to(m)

    m.save('templates/isochrones.html')

    return render_template('Cleanup (old html files)/isochrones.html')


def sum_and_norm():
    """
    Calculate the sum of the wattage of all entries in the south, then normalize it.
    :return:
    """

    locations, shortlist = pull_states()

    # # Calculated total wattage is 52619.100000000144
    # total_wattage = 0
    #
    # for location in locations:
    #     wattage = Solar_Wattage.query.filter_by(id=location.id).first()
    #     total_wattage += wattage.wattage

    # print(total_wattage)

    min_value = 1000

    max_value = 0

    for location in locations:
        value = Solar_Wattage.query.filter_by(id=location.id).first()
        if value.wattage < min_value:
            min_value = value.wattage
        elif value.wattage > max_value:
            max_value = value.wattage

    print("Min_Value:", min_value)
    print("Max_Value:", max_value)

    for location in locations:
        try:
            item = Solar_Wattage.query.filter_by(id=location.id).first()
            normalized = (item.wattage-min_value)/ (max_value - min_value)
            print(item.id, ":", normalized)
            item.norm_wattage = normalized
            db.session.commit()
        except Exception as e:
            print("EXCEPTION!", location.id, e)



# Instructions on how to generate a heatmap as provided by ChatGPT.
# @views.route('/generate-heat-map')
# def heat_map():
#     ors = client.Client(key=ors_API_key, base_url=base_url)
#
#     locations = [
#         [-81.97983, 34.956394],
#         [-81.8019, 27.3232],
#         [-80.6811, 28.4586],
#         [-81.95638, 30.320748],
#         [-82.33783, 29.700407],
#         [-81.18222, 28.488889]
#     ]
#
#     matrix = ors.distance_matrix(locations, profile='driving-car')
#
#     durations = matrix['durations']
#
#     weights = [sum(row) / len(row) for row in durations]
#     points = [loc[::-1] + [weight] for loc, weight in zip(locations, weights)]
#
#     avg_location = [sum(loc[0] for loc in locations) / len(locations), sum(loc[1]for loc in locations) / len(locations)]
#     m = folium.Map(location=avg_location[::-1], zoom_start=6)
#
#     HeatMap(points).add_to(m)
#
#     m.save('templates/heatmap.html')
#
#     return render_template('heatmap.html')


def generate_heat():
    ors = client.Client(key=ors_API_key, base_url=base_url)

    nearby, shortlist = pull_states()


    locations = [[item.longitude, item.latitude] for item in nearby]

    print(locations)

    matrix = ors.distance_matrix(locations, profile='driving-car')

    durations = matrix['durations']

    weights = [item.wattage for item in nearby]

    points = [loc[::-1] + [weight] for loc, weight in zip(locations, weights)]

    avg_location = [sum(loc[0] for loc in locations) / len(locations), sum(loc[1] for loc in locations) / len(locations)]

    m = folium.Map(location=avg_location[::-1], zoom_start=6)

    HeatMap(points).add_to(m)

    m.save('templates/heatmap.html')






@views.route('/display-heat-map')
def display_heat():
    return render_template('Cleanup (old html files)/heatmap.html')



def points_heatmap():

    """
    Get a list of locations in the Southeast.

    :return: a list of states near Florida
    """

    nearby_list = Solar_List.query.filter(Solar_List.state.in_(["FL"]))
    nearby = nearby_list.all()
    count = nearby_list.count()
    print("Count:", count)


    outputs = []
    locations = []
    for item in nearby:
        locations.append([item.longitude, item.latitude])
        current = Solar_Wattage.query.filter_by(id=item.id).first()
        outputs.append(current.wattage)

    print(locations)

    matrix = ors_client.distance_matrix(locations[::-1], profile='driving-car')

    adjusted_matrix = [[distance / output if distance is not None and output !=0 else None for distance in row] for row, output in zip(matrix['durations'], outputs)]

    optimal_index = min(range(len(adjusted_matrix)), key=lambda i: sum(row[i] for row in adjusted_matrix if row[i] is not None))
    optimal_location = locations[optimal_index]

    heatmap_data = [[*location, 1 / adjusted_matrix[i][optimal_index]] for i, location in enumerate(locations) if adjusted_matrix[i][optimal_index] is not None and adjusted_matrix[i][optimal_index] != 0]

    m = folium.Map(location=optimal_location[::-1], zoom_start=6)

    HeatMap(heatmap_data).add_to(m)

    m.save('templates/chat-heatmap.html')





def calculate_near_atlanta():
    nearby, shortlist = pull_states()

    coords = [[item.longitude, item.latitude] for item in nearby]

    atlanta_coords = [-83.97788941494869, 33.97189936097202]

    coords.insert(0, atlanta_coords)

    matrix = ors_client.distance_matrix(locations=coords, sources=[0], profile='driving-car')

    atlanta_durations = matrix['durations'][0]

    locations = [loc for i, loc in enumerate(coords) if atlanta_durations[i] is not None and atlanta_durations[i] > 9000]

    print("Coords Len:", len(coords))
    print("Locations len:", len(locations))
    print("Locations:", locations)

    m = folium.Map(location=atlanta_coords[::-1], zoom_start=6)

    for location in locations:
        folium.Marker(location=[location[1], location[0]]).add_to(m)

    m.save('templates/atlanta_reach.html')


def calculate_travel_time(start, end):
    coords = ((start[1], start[0]), (end[1], end[0]))
    try:
        routes = ors_client.directions(coordinates=coords, profile='driving-car')
    except Exception as e:
        print("Exception in calculate travel time!", e)
        return np.inf
    return routes['routes'][0]['summary']['duration'] / 3600


def calculate_score(location, facilities):
    score = 0
    for facility in facilities:
        print(facility)
        # print(facility[2])
        travel_time = calculate_travel_time(location, facility[:2])
        # print("Travel Time:", travel_time)
        if travel_time > 5:
            return -np.inf
        # print(facility[2])
        score += facility[2] / travel_time
    # print("Score:", score)
    return score


def total_score(location, facilities):
    score = 0
    highest_travel_time = 1
    for facility in facilities:
        travel_time = calculate_travel_time(location, facility)
        # print(location, facility, "-- Travel Time:", travel_time)
        if travel_time > 8:
            check_address(facility[0], facility[1])
            # print("Bad return!")
            return -np.inf
        score += facility[2] / travel_time
        if travel_time > highest_travel_time:
            highest_travel_time = float(travel_time)
    print("Highest Travel Time:", highest_travel_time)
    return score


def calculate_heat_chat():
    nearby, shortlist = pull_states()

    facilities = []

    for item in nearby:
        current = Solar_Wattage.query.filter_by(id=item.id).first()
        # print(current.id, current.wattage)
        facilities.append([item.latitude, item.longitude, current.wattage])

    grid = np.mgrid[25:33:0.1, -87:-78:0.1].reshape(2, -1).T
    best_score = -np.inf
    best_location = None

    for location in grid:
        try:
            score = calculate_score(location, facilities)
            # print(f'Score: {score}, Best Score: {best_score}, Best Location: {best_location}')
            # print(score)
            if score > best_score:
                best_score = score
                best_location = location
            # print(f'Score: {score}, Best Score: {best_score}, Best Location: {best_location}')
        except Exception as e:
            # print("EXCEPTION!:", location, e)
            pass

    if best_location is not None:
        print("Best Location:", best_location)

        m = folium.Map(location = best_location, zoom_start= 7)

        fg1 = folium.FeatureGroup(name='Best Location')
        fg2 = folium.FeatureGroup(name='All Locations')
        fg3 = folium.FeatureGroup(name='Location Reach')

        folium.Marker(location=best_location, popup=str(best_location), icon=folium.Icon(icon='cloud', color='red')).add_to(fg1)

        for item in nearby:
            folium.Marker(item).add_to(fg2)





        m.save('templates/best_location.html')
    else:
        print('Best location is NONE!')


@views.route('/folium-layer-test')
def folium_layers():
    m = folium.Map(location=[33.97189936097202, -83.97788941494869], zoom_start=6)

    fg1 = folium.FeatureGroup(name='Layer 1')
    fg2 = folium.FeatureGroup(name='Layer 2')

    nearby, shortlist = pull_states()

    unique_nearby = [[item.latitude, item.longitude] for item in nearby if item.id not in [x.id for x in shortlist]]

    for item in unique_nearby:
        folium.Marker(item, icon=folium.Icon(icon='cloud', color='red')).add_to(fg1)

    for item in shortlist:
        folium.Marker([item.latitude, item.longitude]).add_to(fg2)


    fg1.add_to(m)
    fg2.add_to(m)

    folium.LayerControl().add_to(m)

    m.save('templates/layers.html')

    return render_template('Cleanup (old html files)/layers.html')


def calculate_heat_second():
    nearby = Solar_Wattage.query.filter_by(state="FL").all()

    facilities = []

    for item in nearby:
        # if item.id == 2089 or item.id == 60 or item.id == 2851 or item.id == 61 or item.id == 1627 or item.id == 76 or item.id == 173 or item.id == 3109 or item.id == 218 or item.id == 425 or item.id ==743or item.id == 1314:
        #     continue
        # print("Coords:", item.latitude, item.longitude)
        # print(f'ID: {item.id} -- Coords: {item.latitude}, {item.longitude} -- Wattage: {current_id.wattage}')
        facilities.append([item.latitude, item.longitude, item.wattage])

    grid = np.mgrid[25:33:0.1, -87:-78:0.1].reshape(2, -1).T
    best_score = -np.inf
    best_location = None
    longest_travel = 0

    for location in grid:
        try:
            # print("Grid:", location)
            #     for facility in facilities:
            #         travel_time = calculate_travel_time(location, facility)
            #         print(f'Grid: {location} -- Travel Time: {travel_time}')
            print("Current Location:", location)
            score = total_score(location, facilities)
            if score > best_score:
                best_score = score
                best_location = location
        except Exception as e:
            print("Exception in highest travel time!", location, e)
            continue

    if best_location is not None:
        m = folium.Map(location=best_location, zoom_start=7)
        # folium.Marker(best_location).add_to(m)

        fg1 = folium.FeatureGroup(name='Best Location')
        fg2 = folium.FeatureGroup(name='All Locations')
        fg3 = folium.FeatureGroup(name='Location Reach')

        folium.Marker(location=best_location, popup=f'{best_location} Travel: {longest_travel}',
                      icon=folium.Icon(icon='cloud', color='red')).add_to(fg1)

        for item in nearby:
            folium.Marker([item.latitude, item.longitude]).add_to(fg2)

        print("Best Location:", best_location)

        isochrone = None
        try:
            location_list = best_location.tolist()
            print(location_list)
            isochrone = ors_client.isochrones(
                locations=[[location_list[1], location_list[0]]],  # longitude, latitude
                profile='driving-car',
                # range=[18000],  # 5 hours in seconds, but cannot be used with the website API.
                range=[8 * 3600],
            )
        except Exception as e:
            print(best_location, e)

        style = {'fillColor': 'green', 'color': 'green'}

        # add the isochrone to the map
        if isochrone is not None:
            folium.GeoJson(
                isochrone,
                name='Location Reach',
                style_function=lambda x:style
            ).add_to(fg3)
        else:
            print("Isochrone is none!")

        fg1.add_to(m)
        fg2.add_to(m)
        fg3.add_to(m)

        folium.LayerControl().add_to(m)
        m.save('templates/best_location.html')
    else:
        print('No best location found!')


def convert_address():
    entries, shortlist = pull_states()

    for entry in entries:
        current_entry = Solar_Wattage.query.filter_by(id=entry.id).first()

        try:
            if current_entry.latitude is None:
                if entry.street_address is None:
                    current_entry.latitude = entry.latitude
                    current_entry.longitude = entry.longitude
                else:
                    address = f'{str(entry.street_address)}, {str(entry.city)}, {str(entry.state)} {str(entry.zip)}'
                    latitude, longitude = geopy_coords(address)
                    current_entry.latitude = latitude
                    current_entry.longitude = longitude
                    current_entry.state = entry.state
                db.session.commit()
        except Exception as e:
            print('Exception!', entry.id, e)





def check_address(latitude, longitude):
    addresses = Solar_Wattage.query.filter_by(longitude=longitude, latitude=latitude).all()
    if addresses is None:
        print("Address not found!")
        return
    for location in addresses:
        print("Bad ID:", location.id)


def direction_test():
    try:
        routes = ors_client.directions(coordinates=[[-83.232, 30.055],[-82.546,29.478]], profile='driving-car')
        print(routes['routes'][0]['summary']['duration'])
        search = ors_client.pelias_search('617 Young Mill Rd, Lexington, NC 27292')
        print(search)

    except Exception as e:
        print('EXCEPTION!', e)


def geopy_coords(address):
    geolocator = ArcGIS(user_agent='SolarpowerProject-132545')

    try:
        location = geolocator.geocode(address)

        print(location.address)
        print((location.latitude, location.longitude))

        return location.latitude, location.longitude

    except Exception as e:
        print("Can't get location!", e)
        return None, None


def fix_address():
    nearby, shortlist = pull_states()

    for location in nearby:
        if location.street_address == "TBD":
            current_item = Solar_Wattage.query.filter_by(id=location.id).first()
            current_item.latitude = location.latitude
            current_item.longitude = location.longitude
            print(location.id)
            db.session.commit()


def plot_map():
    nearby, shortlist = pull_states()
    best_location = [27.6, -82.3]

    isochrone = ors_client.isochrones(
        locations=[[best_location[1], best_location[0]]],
        profile='driving-car',
        range=[4 * 3600]
    )

    m = folium.Map(location=best_location, zoom_start=8)

    folium.GeoJson(
     isochrone
    ).add_to(m)

    m.save('templates/plot_test.html')

    return render_template('Cleanup (old html files)/plot_test.html')


def get_time():
    longest_time = 0
    nearby, shortlist = pull_states()
    best_location = [27.6, -82.3]
    # best_location = [ 29.9, -82.7]

    locations = [[location.longitude, location.latitude] for location in nearby]

    locations.insert(0, best_location[::-1])

    distances = ors_client.distance_matrix(locations=locations, sources=[0], profile='driving-car')

    durations = distances['durations'][0]

    print(durations)

    for duration in durations:
        if duration is not None:
            if duration > longest_time:
                longest_time = duration

    longest_time = longest_time / 3600

    print(longest_time)



@views.route('/plot-all')
def plot_all():
    locations = Solar_List.query.filter(Solar_List.longitude <= -100).all()

    m = folium.Map(location=[32.23, -83.20], zoom_start=4)

    for location in locations:
        try:
            folium.Marker(location=[location.latitude, location.longitude],
                          popup=f"<strong>{location.id} - {location.plant_name}</strong>").add_to(m)

        except Exception as e:
            print('Error with location:', location.id, e)

    m.save('templates/plot-all.html')

    return render_template('Cleanup (old html files)/plot-all.html')


# def plot_with_multiple():


@views.route('/', methods=['GET', 'POST'])
def get_custom_weights():
    """
    1. display form on home page.
    2. accept data from form.
    3. Use data to determine lat and long of street address.
    4. Use lat and long to calculate mW per minute.
    5. Display facility name, address, and mW per minute to user.
    :return:
    """

    # form = WeightForm()
    # errors = ''
    # shape = {}
    #
    #
    # if form.validate_on_submit():
    #     # print(form.street_address.data, form.city.data, form.state.data, form.zip.data)
    #
    #     address = f'{form.street_address.data}, {form.city.data}, {form.state.data} {str(form.zip.data)}'
    #     # print(address)
    #
    #     lat, long = geopy_coords(address)
    #     coords = (lat, long)
    #
    #     score = 0
    #
    #     current_facilities = Solar_List.query.filter_by(state="FL").all()
    #
    #     for facility in current_facilities:
    #         try:
    #
    #             if facility.technology == "Batteries":
    #                 print(facility.id, "Batteries!")
    #                 continue
    #
    #             id = facility.id
    #             facility_address = f'{facility.street_address}, {facility.city}, {facility.state} {facility.zip}'
    #             # print(facility_address)
    #             facility_coords = (facility.latitude, facility.longitude)
    #             highest_wattage = Florida_Facility.query.filter_by(id=id).first().highest_wattage
    #             # print(highest_wattage)
    #             time = travel_time(coords, facility_coords)
    #
    #             # if time is np.inf:
    #             #     new_lat, new_long = geopy_coords(facility_address)
    #             #     new_coords = (new_lat, new_long)
    #             #     time = travel_time(coords, new_coords)
    #             # print(time)
    #
    #             if time is not np.inf:
    #                 mw_minute = highest_wattage / (time)
    #                 score += mw_minute
    #                 shape[id] = {"address": facility_address, "coordinates": facility_coords,
    #                              "wattage": highest_wattage, "time": time/60, "mwm": mw_minute}
    #             else:
    #                 print("Infinite Time!", id, facility_address)
    #
    #         except Exception as e:
    #             errors += (str(e) + '\n')
    #
    #     errors += str(score)
    #
    #     return render_template('Cleanup (old html files)/home.html', form=form, errors=errors, shape=shape)
    #
    # return render_template('Cleanup (old html files)/home.html', form=form, errors=errors, shape=shape)

    return redirect(url_for('webviews.web_home'))


def travel_time(start, end):
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
    return routes['routes'][0]['summary']['duration'] / 60