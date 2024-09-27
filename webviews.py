"""
Created: 09-23-24
Creator: Dustin
"""
import openrouteservice

from __init__ import db, ors_client, solarEngine
import datetime
from flask import Flask, Blueprint, render_template, flash, redirect, url_for, send_from_directory, safe_join
from forms import ImportForm, SearchForm
import folium
from models import Solar_List
import numpy as np
import pandas as pd
from openrouteservice import client
from multiprocessing import Pool
import csv
from openrouteservice import exceptions as ors_exceptions
import os
from werkzeug.utils import secure_filename
from sqlalchemy import func, cast, Date
from sqlalchemy.inspection import inspect


webviews = Blueprint('webviews', __name__)
user_data_folder = 'UserData'

# Coordinates of Lebanon, Kansas, near the center of the contiguous U.S. states.
# This is used for full U.S. folium maps.
us_center_coords = [39.809860, -98.555183]
# Temporary stand in for max travel time that will be user modifiable in the future.
max_travel_time = 15.0  # Float in hours


@webviews.route('/')
def web_home():
    """
    The home view for webviews and user interactivity. This will link to the other pages necessary
    for user interaction.
    :return: HTML landing page with links.
    """

    return render_template('webviews_home.html')


@webviews.route('/files')
def list_files():
    """
    Lists all files for the user to view or download.
    :return:
    """
    files = os.listdir(user_data_folder)
    # Filter out files here that don't need to be displayed, if necessary.
    return render_template('webviews_display_files.html', files=files)


@webviews.route('/user_data/<path:filename>')
def serve_user_data(filename):
    """
    Lets user interact with files inside the UserData directory.
    :param filename: The filename of the file the user is interested in.
    :return: The file the user is requesting.
    """
    return send_from_directory(user_data_folder, filename)


@webviews.route('/download/<path:filename>')
def download_file(filename):
    """
    Downloads a user-selected file.
    :param filename: The filepath for the file to be downloaded.
    :return: Attachment containing the file the user requested.
    """
    return send_from_directory(user_data_folder, filename, as_attachment=True)


@webviews.route('/show-all-facilities', methods=['GET'])
def show_all_facilities():
    """
    Show all the recently uploaded facilities across the U.S.
    :return: HTML folium map with all the facilities plotted.
    """
    # Create an empty map centered on Lebanon, Kansas.
    m = folium.Map(location=us_center_coords, zoom_start=5)
    # Query the database for a list of facilities
    locations = Solar_List.query.filter_by(uploaded_datetime=get_recent_upload_time()).all()

    for location in locations: # Add a marker for each location
        if location.latitude is None or location.longitude is None:
            demsg(f'{location.id} {location.plant_name} {location.latitude} {location.longitude}')
            continue
        folium.Marker(location=[location.latitude, location.longitude],
                      popup=f'{location.plant_name}\n({location.latitude}, {location.longitude})',
                      icon=folium.Icon(icon='cloud', color='green')
                      ).add_to(m)

    # Saves the map to the user data folder so that it doesn't need to be generated a
    # second time by the user to view again.
    m.save(f'./UserData/all_us_facilities_{datetime.date.today()}.html')

    # Converts the folium map to html so that it can be displayed directly.
    map_html = m._repr_html_()
    # Returns the map html to be used in a template.
    return render_template('webviews_display_map.html', map_html=map_html)


@webviews.route('/import', methods=['GET', 'POST'])
def web_import():
    """
    Show a form to import a new SEIA solar information and handle the data programmatically.
    :return:
    """
    import_form = ImportForm()

    # Handle form data after submission.
    if import_form.validate_on_submit():
        # Get a reference to the data submitted through the Import Form.
        file = import_form.file.data
        # Make sure the filename isn't something crazy that's going to break my database.
        filename = secure_filename(file.filename)
        # If the uploads folder doesn't exist, create it.
        if not os.path.exists('uploads'):
            os.makedirs('uploads')
        # Get a local relative reference to the new path to save the data at.
        upload_path = os.path.join('uploads', filename)
        # Save the original upload for review later.
        file.save(upload_path)

        try:
            # Read the Excel sheet needed, skipping the first four rows.
            df = pd.read_excel(
                io=upload_path,
                sheet_name='Major Projects List',
                header=4,
            )

            # Drop the first 3 columns from the dataframe, as these are left empty.
            df = df.iloc[:, 4:]
            # Add the current datetime as a column so that all the entries have an upload period.
            uploaded_datetime = datetime.datetime.now().replace(microsecond=0)
            df['uploaded_datetime'] = uploaded_datetime
            # Get a list of column names from the model in models.py
            column_names = get_model_column_names(Solar_List)
            # Make sure the length of columns from the model match the number found in the spreadsheet
            if len(df.columns) != len(column_names):
                raise ValueError(f'Number of columns do not match: {len(df.columns)}  {len(column_names)}')
            # Set the columns for the dataframe to the ones pulled from the model.
            df.columns = column_names

            # Import the modified dataframe into the database.
            df.to_sql('solar_facility_list', con=solarEngine, if_exists='append', index=False)

            flash('Data imported successfully.', 'success')

        # Handle exceptions and display to user.
        except Exception as e:
            import traceback
            traceback.print_exc()
            flash(f'An error occurred while uploading: {e}', 'danger')
        # Handle all final tasks after data upload is attempted.
        # finally:
            # This is an option to remove the uploaded file after processing.
            # os.remove(upload_path)

        # Return the user back to the 'GET' version of this page
        return redirect(url_for('webviews.web_import'))

    # Handle normal 'GET' processing of import webpage.
    return render_template('import.html', form=import_form)


@webviews.route('/state-search', methods=['GET', 'POST'])
def state_search():
    """
    Allow the user to choose a state to search for a new facility in.
    They can specify a group of states to include in the search.
    :return:
    """
    form = SearchForm()

    if form.validate_on_submit():
        # Create an empty list to store filters. These filters can then be passed into other functions to further
        # refine the search queries without having to do it all over again.
        query = Solar_List.query
        filters = []

        # Get a reference to the state acronym the user is targeting. Remove extraneous whitespace.
        state = form.new_facility_state_code.data.strip().upper()
        demsg('State:', state)
        # Get a reference to the states the user wants to include in the search.
        search_group = form.states_search.data
        # Get a reference to the search precision the user has chosen.
        precision = form.precision.data
        demsg('User set this precision:', precision)
        # Split and strip the group of states the user has included. If they did not include one, use the
        # targeted state as the search group.
        if search_group != '':
            search_group = [code.strip().upper() for code in search_group.split(',')]
        else:
            search_group = [state]

        # Get a SQLAlchemy query that contains the most recently uploaded data.
        # This is the most recent datetime uploaded.
        most_recent_datetime = get_recent_upload_time()
        demsg('Time:', most_recent_datetime)

        try:
            # Check if any records exist. If so, continue processing.
            if most_recent_datetime is None:
                raise ValueError('No most recently uploaded datetime found.')
            filters.append(cast(Solar_List.uploaded_datetime, Date) == most_recent_datetime.date())

            # Create an empty pandas Dataframe to store data that will later be exported to an Excel spreadsheet.
            data = pd.DataFrame(columns=['id',
                                         'highest_mW',
                                         'latitude',
                                         'longitude',
                                         'street_address',
                                         'time_to_facility(hours)',
                                         'score',
                                         'mW_per_minute'])

            # determine the bounds for the state the user has submitted.
            boundaries = determine_state_bounds(state, filters)
            demsg(boundaries)

            # Add the entire search zone that user specified to the filters list and query.
            filters.append(Solar_List.state.in_(search_group))
            records = Solar_List.query.filter(*filters).all()
            demsg('Number of records:', len(records))

            # Iterate over every record and add them to the DataFrame for processing.
            for record in records:
                if record.latitude is None or record.longitude is None:
                    demsg(f'No latitude or longitude found for record {record.id}')
                    continue
                else:
                    data = pd.concat([data, get_record_dataframe(record)], ignore_index=True)
            demsg(data.head())

            # Create a grid to search over using the calculated state boundaries.
            search_grid = create_map_grid(boundaries, precision)
            # TODO: Remove grid points that are not within the state bounds.
            # Create a variable for storing the best_score and best_location
            best_score = -np.inf  # This value will not show up organically, so it's good for debugging.
            best_location = None  # Keeps track of the current best location if one has been found.

            # This basically attaches the DataFrame to each point in the grid.
            grid_data = [(point, data) for point in search_grid]

            with Pool(processes=4) as pool:  # Start a multithreading process
                results = pool.map(calculate_location_score, grid_data)

            for location, score in results:  # Iterate over the return from the multithread Pool
                # If the location has a better score, update best score and best location.
                if score is not None and score > best_score:
                    best_score = score
                    best_location = location

            if best_location is None:
                demsg("Couldn't find a best location!")
                return

            demsg("Best Location:", best_location)

            # Create a map with the best location as the only point.
            m = folium.Map(location=best_location, zoom_start=7)
            folium.Marker(location=best_location).add_to(m)
            m.save(f'./UserData/best_location_{state}_{datetime.date.today()}.html')

            # Save the DataFrame to an Excel file.
            data.to_excel(f'./UserData/best_location_data_{state}_{datetime.date.today()}.xlsx', index=False)

            return redirect(url_for('webviews.state_search'))

        except Exception as e:
            import traceback
            traceback.print_exc()

    return render_template('webviews_search.html', form=form)


def calculate_location_score(args):
    """
    Handles calculation of multithreaded locations.
    The real purpose is as an interface for multithreading that allows me to
    simplify calculating so many scores at once.
    This differs from calculate_score, but they don't necessarily need to be separate.
    :param args: Takes a tuple with the grid point and the data DataFrame
    :return: Tuple with location and score, or location and None if no score could be determined.
    """
    location, data = args
    try:
        score = calculate_score(location, data)
        return (location, score)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return (location, None)


def calculate_score(location, data):
    """
    Handles the actual calculations for scores based on weighted distance. Returns a score for the location.
    :param location: A grid coordinate consisting of lat and longitude.
    :param data: A DataFrame that includes lat, long, and wattage.
    :return: Float with the calculated score for the location.
    """
    score = 0  # Initialize an empty score.
    highest_travel_time = 0  # Initialize an empty highest travel time.
    travel_times = []  # List of travel times.

    for index, row in data.iterrows():
        # Create a list with coordinates
        facility = [row['latitude'], row['longitude']]
        # Calculate the travel time for the current facility to the grid point being compared.
        travel_time = calculate_travel_time(location, facility)

        if travel_time == np.inf:  # If no travel time could be determined, go to the next facility.
            demsg('Couldn\'t determine travel time for', location, 'Continuing to next grid location.')
            continue
        if travel_time > max_travel_time:  # Don't assess locations with too long of a travel time.
            demsg(f'{index}: Travel time of {travel_time} is too great! Limit set to {max_travel_time}.')
            return -np.inf

        score += row['highest_mW'] / max(1, travel_time)  # Add the facility score to the total location score.
        travel_times.append(travel_time)  # Add the travel time to the list of travel times to determine an avg.
        if travel_time > highest_travel_time:  # Keep track of the highest travel time for a location.
            highest_travel_time = travel_time

    if highest_travel_time > 0:  # Make sure the highest travel time exists.
        demsg('Highest Travel Time:', highest_travel_time)

    # Calculate the average travel time from this location to all facilities.
    if len(travel_times) > 0:
        avg = sum(travel_times) / len(travel_times)
        demsg(location, 'travel avg:', avg)
    else:
        avg = np.inf

    return score


def calculate_travel_time(start, end):
    """
    Calculates the travel time between two points using ORS
    :param start: The grid coordinates to start at.
    :param end: The location of the facility whose distance is being calculated.
    :return: Float with the duration in hours, or np.inf if no route was found.
    """
    coords = ((start[1], start[0]), (end[1], end[0]))  # Reverse the order of the coords so longitude is first.
    routes = None  # Initialize an empty route.
    try:
        # Get available routes from ORS.
        routes = ors_client.directions(coordinates=coords, profile='driving-hgv')
        return routes['routes'][0]['summary']['duration'] / 3600  # Get the duration in hours.
    except ors_exceptions.ApiError as e:
        error_code = e.args[0]['error']['code']
        if error_code == 2010:
            demsg(f'No routable point near coordinate: {e}')
        elif error_code == 2004:
            demsg(f'Route distance exceeds limit: {e}')
        else:
            demsg(f'API Error: {e}')
    except Exception as e:
        import traceback
        if routes:
            demsg('Failed to return route for', start, end, routes)
        else:
            demsg('Failed to find a route for', start, end)
        traceback.print_exc()
        return np.inf


def demsg(*args):
    """
    Take any number of arguments and print them in a message together.
    :param args: The arguments that will be combined and printed.
    :return: None. Prints to console
    """
    message = ' '.join(str(arg) for arg in args)
    print(message)


def get_model_column_names(model):
    """
    Pull all the column names from the model as it exists
    :param model: The SQLAlchemy model to be processed from models.py
    :return: List containing model column names
    """
    mapper = inspect(model)
    column_names = []
    for column in mapper.attrs:
        if hasattr(column, 'columns'):
            # Exclude the primary key column if necessary.
            if not column.columns[0].primary_key:
                column_names.append(column.columns[0].name)
    return column_names


def determine_state_bounds(state, filters=None):
    """
    Determine the minimum and maximum boundaries for the state to search over with a grid.
    :param state:
    :param filters: The list of filters used for the SQLAlchemy query.
    :return: A dictionary containing the minimum and maximum boundaries.
    """
    if filters is None:
        filters = []
    bound_filters = filters.copy()
    # Add the state as temporary filter for this query if state was provided.
    bound_filters.append(Solar_List.state == state)
    # Filter the results from the database
    query = Solar_List.query.filter(*bound_filters)

    # This is a debug function designed to help verify that state bounds are printing correctly.
    # for entry in query.all():
    #     demsg('Determine state bounds:', entry.id, entry.state)

    # Get a reference to the bounds for each point.
    min_lat = query.with_entities(func.min(Solar_List.latitude)).scalar()
    max_lat = query.with_entities(func.max(Solar_List.latitude)).scalar()
    min_lon = query.with_entities(func.min(Solar_List.longitude)).scalar()
    max_lon = query.with_entities(func.max(Solar_List.longitude)).scalar()

    # Return the dictionary with the results.
    return {'min_lat': min_lat, 'max_lat': max_lat, 'min_lon': min_lon, 'max_lon': max_lon}


def get_recent_upload_time():
    """
    The point of this function is to return the most recent datetime that an upload occurred.
    :return: Datetime scalar with most recent upload time.
    """
    return Solar_List.query.with_entities(func.max(Solar_List.uploaded_datetime)).scalar()


def get_street_address(record):
    """
    Takes a single record from a SQLAlchemy query and returns a string containing the full street address.
    :param record: A database record for a facility.
    :return: String containing full U.S. street address.
    """
    return f'{record.street_address}, {record.city}, {record.state} {record.zip}'


def get_record_dataframe(record):
    """
    Returns a pandas DataFrame of data to be appended to dataframe of temporary data.
    This is for things like highest_wattage, street address, and later, score, ttf, etc.
    :return: DataFrame containing data to be appended to dataframe of temporary data.
    """
    # Set the ac or dc capacity after making sure both exist.
    capacity = None
    if record.ac_capacity and record.dc_capacity:
        capacity = record.ac_capacity if record.ac_capacity > record.dc_capacity else record.dc_capacity
    elif record.ac_capacity:
        capacity = record.ac_capacity
    elif record.dc_capacity:
        capacity = record.dc_capacity
    else:
        capacity = 1

    # Create a dictionary that will be appended to the pandas DataFrame.
    row = {'id': record.id,
           'highest_mW': capacity,
           'latitude': record.latitude,
           'longitude': record.longitude,
           'street_address': get_street_address(record),
           'time_to_facility(hours)': None,
           'score': None,
           'mW_per_minute': None
           }

    return pd.DataFrame([row])


def create_map_grid(boundaries, precision=0.1):
    """
    Create a grid to search over based on the calculated state bounds.
    :param boundaries: A dictionary containing the latitude and longitude coordinates.
    :param precision: The precision of the grid coordinates, provided through the SearchForm
    :return: A list of grid coordinates based on the precision the user provided
    """
    grid = (np.mgrid[boundaries['min_lat']:boundaries['max_lat']:precision,
            boundaries['min_lon']:boundaries['max_lon']:precision]
            .reshape(2, -1).T
    )
    return grid


def address_search(coords):
    """
    Runs a reverse pelias search against the coordinates to check what address it matches up to.
    :param coords: A tuple or list with coordinates to get an address for.
    :return: A dictionary containing address details or None if not found.
    """
    try:
        # Note: The coordinate order is (longitude, latitude) for ORS.
        params = {'point.lon': coords[1], 'point.lat': coords[0]}
        response = ors_client.pelias_reverse(params)
        if response and 'features' in response and len(response['features']) > 0:
            return response['features'][0]['properties']
        else:
            print(f'No address found for coordinate: {coords}')

    except ors_exceptions.ApiError as e:
        demsg(f'No address found for coordinate: {coords}')
        return None
    except Exception as e:
        demsg(f'An error occurred during reverse geocoding: {e}')
        return None


def reverse_geocode_coordinate(coord):
    """
    Perform reverse geocoding to find the address of a coordinate.

    :param coord: A tuple or list with coordinates to get an address for containing (latitude, longitude)
    :return: A dictionary containing address details or None if not found.
    """
    # TODO: This requires the setup of a Pelias server to do revere geocoding.
    try:
        # Coordinate order is longitude, latitude for ORS.
        response = openrouteservice.geocode.pelias_reverse(
            client=ors_client,
            point=[coord[1], coord[0]],
            size=1,
        )
        if response and 'features' in response and len(response['features']) > 0:
            return response['features'][0]['properties']
        else:
            demsg(f'No address found for coordinate: {coord}')
            return None

    except ors_exceptions.ApiError as e:
        import traceback
        demsg(f'API Error during reverse geocoding: {coord}')
        traceback.print_exc()
        return None
    except Exception as e:
        import traceback
        demsg(f'An unknown error occurred during reverse geocoding: {e}')
        traceback.print_exc()
        return None


