from flask_wtf import FlaskForm
from wtforms import FloatField, IntegerField, StringField, SubmitField, FileField
from wtforms.fields.numeric import FloatField
from wtforms.validators import DataRequired, NumberRange, Optional


class WeightForm(FlaskForm):
    street_address = StringField('Street Address', validators=[DataRequired()])
    city = StringField('City', validators=[DataRequired()])
    state = StringField('State (2 Letters)', validators=[DataRequired()])
    zip = StringField('Zip Code', validators=[DataRequired()])
    submit = SubmitField('Get Weights')


class ImportForm(FlaskForm):
    file = FileField('CSV', validators=[DataRequired()])
    submit = SubmitField('Import', validators=[Optional()])


class SearchForm(FlaskForm):
    """
    Designed to allow a user to select a state or group of states they would like to determine the best location for.
    Allows the user to select a state to find a new location in, and a single or group of states
    to use the solar facilities for.
    If no states_search is provided, it will default to only the state the user is looking for.
    """
    new_facility_state_code = StringField('New Facility State Code', validators=[DataRequired()])
    states_search = StringField('States Search')
    # Allows user to choose how precise they want the returned results to be.
    precision = FloatField('Precision', default=0.1, validators=[NumberRange(min=0.02, max=0.5), DataRequired()])
    # TODO: Include maximum travel time IntegerField that the user can adjust.
    # TODO: Add required email field where user can be emailed the results.
    # TODO: Add Checkbox so user can exclude results that haven't begun construction (Under Development)
    submit = SubmitField('Search')





