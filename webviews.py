from __init__ import db, ors_client, solarEngine
import datetime
from flask import Flask, Blueprint, render_template, flash
from forms import ImportForm
import folium
from models import Solar2024
import numpy as np
import pandas as pd
from openrouteservice import client
from multiprocessing import Pool
import csv
import os
from werkzeug.utils import secure_filename


webviews = Blueprint('webviews', __name__)


@webviews.route('/')
def web_home():
    """
    The home view for webviews and user interactivity. This will link to the other pages necessary
    for user interaction.
    :return: HTML landing page with links.
    """

    return render_template('webviews_home.html')


@webviews.route('/import')
def web_import():
    """
    Show a form to import a new SEIA solar information and handle the data programmatically.
    :return:
    """
    import_form = ImportForm()

    # Handle form data after submission.
    if import_form.validate_on_submit():
        file = import_form.file.data
        filename = secure_filename(file.filename)
        if not os.path.exists('uploads'):
            os.makedirs('uploads')
        upload_path = os.path.join('uploads', filename)
        file.save(upload_path)

        try:
            # Read the Excel sheet needed, skipping the first two rows.
            df = pd.read_excel(
                io=upload_path,
                sheet_name='Major Projects List',
                header=2,
            )

            # Drop the first 3 columns from the dataframe, as these are left empty.
            df = df.iloc[:,3:]
            # Add the current datetime as a column so that all of the entries have an upload period.
            uploaded_datetime = datetime.datetime.now()
            df['upload_datetime'] = uploaded_datetime

        except Exception as e:
            print('Error:', str(e))

