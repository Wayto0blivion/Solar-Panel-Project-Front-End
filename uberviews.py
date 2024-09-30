from __init__ import db
import datetime
from flask import Flask, Blueprint, render_template, flash, redirect, url_for
from forms import ImportForm
import folium
from models import Solar2024
import numpy as np
import pandas as pd
from openrouteservice import client
from multiprocessing import Pool
import csv
from werkzeug.utils import secure_filename


uberviews = Blueprint('uberviews', __name__)
ors_API_key = '5b3ce3597851110001cf624819743d9af4454a189cb1389e6f22df78'
base_url = 'http://192.168.3.104:8080/ors'
ors_client = client.Client(key=ors_API_key, base_url=base_url)


# These variables are to be changed as needed for new locations.
map_location = [43.41, -72.71]  # These tracks the starting view location of the map.
states = ['NJ', 'PA', 'CT', 'NY', 'RI', 'VT', 'MA', 'NH', 'ME']  # List of states to consider.
upper_grid_coords = [47.44, -66.73]  # Enter the upper right corner of the search area.
lower_grid_coords = [38.87, -80.61]  # Enter the lower left corner of the search area.
max_travel_time = 15  # Maximum number of hours of travel time for each facility.


@uberviews.route('/')
def home():
    """
    The main function for this view page.
    Determines the best location for a facility and creates a map.
    :return:
    """
    # determine_location()
    #
    # return render_template('home.html')
    return redirect(url_for('webviews.web_home'))


# Add trimmed information to database in the form of a CSV file.
@uberviews.route('/import', methods=['GET', 'POST'])
def import_csv():
    """
    Update the database with current information, trimmed to the states I need without 'Batteries'.
    Uploads to the table solar_jan_2024.
    Table should be truncated (using DBeaver) before uploading the new one.
    :return:
    """
    form = ImportForm()  # Use the import from to accept a new CSV file.

    if form.validate_on_submit():
        file = form.file.data  # Get a reference to the uploaded file
        filename = secure_filename(file.filename)
        if filename.endswith('.csv'):  # Check to make sure the file is a CSV
            df = pd.read_csv(file)  # Convert file to a pandas dataframe
            df.to_sql(name='solar_jan_2024', con=db.engine, if_exists='append', index=False)  # Upload the data
            flash('File successfully uploaded!', 'success')  # Flash messages don't work if they aren't setup
        else:
            flash('Invalid file type.', 'danger')

    return render_template('import.html', form=form)


@uberviews.route('/show-facility-locations')
def show_all_locations():
    """
    Plot all locations in the database table to a map.
    :return: String: alert the player that the map has been generated.
    """
    m = folium.Map(location=map_location, zoom_start=7)  # Create a map object centered on the map_location variable

    locations = get_location_list()

    for location in locations:  # Add a marker for each location
        folium.Marker(location=[location[0], location[1]],
                      popup=f'{location[2]}',
                      icon=folium.Icon(icon='cloud', color='green')
                      ).add_to(m)

    m.save(f'./all-facilities-{datetime.date.today()}.html')
    return "Facility map generated!"


def get_location_list():
    """
    Handles getting the highest wattage and coordinates for each facility.
    :return: a list of lists, containing coords and wattage
    """
    # Get a list of all facilities in the database. No further sorting should be necessary,
    # as it was sorted and filtered prior to upload.
    facilities = Solar2024.query.all()
    locations = []  # Create a blank list to store longitude, latitude, and highest wattage

    for facility in facilities:
        # If the ac capacity is higher than the dc capacity, set wattage to ac.
        if facility.ac_capacity > facility.dc_capacity:
            wattage = facility.ac_capacity
        else:  # Otherwise, set wattage to dc
            wattage = facility.dc_capacity
        locations.append([facility.latitude, facility.longitude, wattage])

    return locations


def determine_location():
    """
    Main logic for determining the best location for a new facility. Creates a map.
    :return: None
    """
    locations = get_location_list()  # Get a list of lists containing coordinates and wattage
    # Create a grid to search over using the bounds provided.
    grid = (np.mgrid[lower_grid_coords[0]:upper_grid_coords[0]:0.1, lower_grid_coords[1]:upper_grid_coords[1]:0.1]
            .reshape(2, -1).T)
    best_score = -np.inf  # Set a default for best_score that won't show up organically
    best_location = None  # Keep track of the current best location

    locations_with_facilities = [(point, locations) for point in grid]

    with Pool(processes=6) as pool:  # Start a multithreading process
        results = pool.map(calculate_score_for_location, locations_with_facilities)

    for location, score in results:  # Iterate over the return from calculate_score_for_location
        # If this location has a better score, update best_score and best_location
        if score is not None and score > best_score:
            best_score = score
            best_location = location

    if best_location is None:  # If no location was determined, alert user and return
        print('Best Location is None!')
        return

    print('Best Location:', best_location)

    # Create a map with the best location as the only point.
    m = folium.Map(location=map_location, zoom_start=7)
    folium.Marker(location=best_location).add_to(m)
    m.save(f'best-location-{datetime.date.today()}.html')


def calculate_score_for_location(args):
    """
    Handles calculation of multi-threaded locations.
    :param args: Takes a tuple with the grid point and all facility locations
    :return: Tuple with location and score, or location and None if no score could be determined
    """
    location, facilities = args
    try:
        score = calculate_score(location, facilities)
        return (location, score)
    except Exception as e:
        print(f'Exception in calculate_score_for_location: {e}')
        return (location, None)


def calculate_score(location, facilities):
    """
    Handles calculation of a score for each location to determine the best one.
    :param location: Grid point to compare
    :param facilities: List of solar panel facilities
    :return:
    """
    score = 0  # Initialize an empty score
    highest_travel_time = 0  # Initialize a highest travel time
    travel_times = []

    for facility in facilities:
        # Calculate the travel time for the current facility to the grid point being compared.
        travel_time = calculate_travel_time(location, facility)

        if travel_time == np.inf:  # If no travel time could be determined, go to the next facility.
            continue
        if travel_time > max_travel_time:  # Don't assess facilities with more than the maximum travel time.
            return -np.inf

        score += facility[2] / max(1, travel_time)  # Add the facility score to the total location score
        travel_times.append(travel_time)  # Add the travel time to list of travel times, to determine an avg
        if travel_time > highest_travel_time:  # If travel_time is the new highest, then set it.
            highest_travel_time = travel_time

    if highest_travel_time > 0:
        print("Highest travel time:", highest_travel_time)

    # Calculate the average travel time from this location to all facilities
    if len(travel_times) > 0:
        avg = sum(travel_times) / len(travel_times)
    else:
        avg = np.inf

    print(f'{location} travel Avg:', avg)

    return score


def calculate_travel_time(start, end):
    coords = ((start[1], start[0]), (end[1], end[0]))  # Reverse the order of lat and long
    routes = None  # Initialize routes to None
    try:
        # Get available routes from ors
        routes = ors_client.directions(coordinates=coords, profile='driving-car')
        return routes['routes'][0]['summary']['duration'] / 3600  # Get the duration in hours
    except Exception as e:
        if routes:
            print(routes)
        print('No routes found', e)
        return np.inf

