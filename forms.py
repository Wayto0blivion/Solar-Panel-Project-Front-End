from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired


class WeightForm(FlaskForm):
    street_address = StringField('Street Address', validators=[DataRequired()])
    city = StringField('City', validators=[DataRequired()])
    state = StringField('State (2 Letters)', validators=[DataRequired()])
    zip = StringField('Zip Code', validators=[DataRequired()])
    submit = SubmitField('Get Weights')