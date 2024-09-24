"""
Created: 09-23-24
Creator: Dustin
"""


from __init__ import db, ors_client, solarEngine
import datetime
from flask import Flask, Blueprint, render_template, flash, redirect, url_for
from forms import ImportForm, SearchForm
import folium
from models import Solar_List
import numpy as np
import pandas as pd
from openrouteservice import client
from multiprocessing import Pool
import csv
import os
from werkzeug.utils import secure_filename
from sqlalchemy import func
from sqlalchemy.inspection import inspect


webviews = Blueprint('webviews', __name__)

# Coordinates of Lebanon, Kansas, near the center of the contiguous U.S. states.
# This is used for full U.S. folium maps.
us_center_coords = [39.809860, -98.555183]


@webviews.route('/')
def web_home():
    """
    The home view for webviews and user interactivity. This will link to the other pages necessary
    for user interaction.
    :return: HTML landing page with links.
    """
    return render_template('webviews_home.html')


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
            uploaded_datetime = datetime.datetime.now()
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
        # Split and strip the group of states the user has included. If they did not include one, use the
        # targeted state as the search group.
        if search_group is not None:
            search_group = search_group.split(',')
            for code in search_group:
                code = code.strip().upper()
        else:
            search_group = state

        # Get a SQLAlchemy query that contains the most recently uploaded data.
        # This is the most recent datetime uploaded.
        most_recent_datetime = get_recent_upload_time()

        try:
            # Check if any records exist. If so, continue processing.
            if most_recent_datetime is None:
                raise ValueError('No most recently uploaded datetime found.')
            filters.append(Solar_List.uploaded_datetime == most_recent_datetime)

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

            # Iterate over every record and add them to the DataFrame for processing.
            for record in records:
                if record.latitude is None or record.longitude is None:
                    demsg(f'No latitude or longitude found for record {record.id}')
                    continue
                else:
                    data = pd.concat([data, get_record_dataframe(record)], ignore_index=True)
            demsg(data.head())

            # Create a grid to search over using the calculated state boundaries.


            return redirect(url_for('webviews.state_search'))

        except Exception as e:
            import traceback
            traceback.print_exc()

    return render_template('webviews_search.html', form=form)


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
    # Add the state as temporary filter for this query if state was provided.
    filters.append(Solar_List.state == state)
    # Filter the results from the database
    query = Solar_List.query.filter(*filters)

    # This is a debug function designed to help verify that state bounds are printing correctly.
    for entry in query.all():
        demsg('Determine state bounds:', entry.id, entry.state)

    # Get a reference to the bounds for each point.
    min_lat = query.with_entities(func.min(Solar_List.latitude)).scalar() if not None else None
    max_lat = query.with_entities(func.max(Solar_List.latitude)).scalar() if not None else None
    min_lon = query.with_entities(func.min(Solar_List.longitude)).scalar() if not None else None
    max_lon = query.with_entities(func.max(Solar_List.longitude)).scalar() if not None else None

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
    # Create a dictionary that will be appended to the pandas DataFrame.
    row = {'id': record.id,
           'highest_mW': record.ac_capacity if record.ac_capacity > record.dc_capacity else record.dc_capacity,
           'latitude': record.latitude,
           'longitude': record.longitude,
           'street_address': get_street_address(record),
           'time_to_facility(hours)': None,
           'score': None,
           'mW_per_minute': None
           }

    return pd.DataFrame([row])


def create_map_grid(coords, precision=0.1):
    """
    Create a grid to search over based on the calculated state bounds.
    :param coords: A dictionary containing the latitude and longitude coordinates.
    :param precision: The precision of the grid coordinates, provided through the SearchForm
    :return: A list of grid coordinates based on the precision the user provided
    """

