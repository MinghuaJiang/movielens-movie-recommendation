import logging
import json
from flask import Flask, render_template, request, redirect, url_for
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, HiddenField
from custom_validators import Username
from wtforms.validators import InputRequired, Email, Length, EqualTo
from dao import UserDao
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from flask_paginate import Pagination
import api

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

application = Flask(__name__)
with open('aws_config_secret.json') as cred:
    creds = json.load(cred)
    application.config['SECRET_KEY'] = creds['aws_secret_access_key']
Bootstrap(application)
login_manager = LoginManager()
login_manager.init_app(application)
login_manager.login_view = 'login'
userDao = UserDao()


@login_manager.user_loader
def load_user(username):
    u = userDao.find_user(username)
    if u is None:
        return None
    return User(u['username'], u['email'], u['isAdmin'])


class User:
    def __init__(self, username, email, isAdmin):
        self.username = username
        self.email = email
        self.isAdmin = isAdmin

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return self.username

    @staticmethod
    def validate_login(password_hash, password):
        return check_password_hash(password_hash, password)


class LoginForm(FlaskForm):
    username = StringField('username', validators=[InputRequired(), Length(min=4, max=15)])
    password = PasswordField('password', validators=[InputRequired(), Length(min=8, max=80)])
    remember = BooleanField('remember me')


class RegistrationForm(FlaskForm):
    email = StringField("email", validators=[InputRequired(), Email(message="invalid email"), Length(max=50)])
    username = StringField('username', validators=[Username(), InputRequired(), Length(min=4, max=15)], render_kw = {"placeholder": "Please enter 4 - 15 characters"})
    password = PasswordField('password', validators=[InputRequired(), Length(min=8, max=80)], render_kw = {"placeholder": "Use at least 8 characters"})
    confirm = PasswordField('retype password',
                            validators=[EqualTo('password', message="password not match"), InputRequired(),
                                        Length(min=8, max=80)])


class ForgotForm(FlaskForm):
    email = StringField("", validators=[InputRequired(), Email(message="invalid email"), Length(max=50)])


class ResetForm(FlaskForm):
    password = PasswordField('password', validators=[InputRequired(), Length(min=8, max=80)])
    confirm = PasswordField('retype password',
                            validators=[EqualTo('password', message="password not match"), InputRequired(),
                                        Length(min=8, max=80)])
    token = HiddenField('token')


@application.route("/")
@login_required
def index():
    datalist_pop = json.loads(api.get_most_popular(8))
    datalist_rate = json.loads(api.get_top_rated(8))
    rate_count = json.loads(api.get_rated_count(current_user.username))
    if rate_count["count"] >= 5:
        datalist_recommendation = api.get_personalized_recommendation(current_user.username, 8)
        show_recommendation = True
    else:
        datalist_recommendation = []
        show_recommendation = False
    return render_template('index.html', datalist_pop=datalist_pop, datalist_rate=datalist_rate, datalist_recommendation = datalist_recommendation,
                           show_recommendation=show_recommendation, user=current_user)


@application.route("/login", methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if request.method == 'POST' and form.validate_on_submit():
        user = userDao.find_user(form.username.data)
        if user and User.validate_login(user["password"], form.password.data):
            user_obj = User(user['username'], user['email'], user['isAdmin'])
            login_user(user_obj, remember=form.remember.data)
            return redirect(url_for("index"))

    return render_template('login.html', form=form)


@application.route("/signup", methods=['GET', 'POST'])
def signup():
    form = RegistrationForm()
    if request.method == 'POST' and form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data, method='sha256')
        userDao.add_new_user(form.username.data, form.email.data, hashed_password)
        user = userDao.find_user(form.username.data)
        user_obj = User(user['username'], user['email'], user['isAdmin'])
        login_user(user_obj)
        return redirect(url_for("index"))

    return render_template('signup.html', form=form)


@application.route("/forgot", methods=['GET', 'POST'])
def forgot():
    form = ForgotForm()
    if request.method == 'POST' and form.validate_on_submit():
        email = form.email.data
        return redirect(url_for('login'))

    return render_template('forgot.html', form=form)


@application.route("/reset", methods=['GET', 'POST'])
def reset():
    form = ResetForm(token=request.args.get("token"))
    if request.method == 'POST' and form.token.data and form.validate_on_submit():
        return redirect(url_for('login'))
    return render_template('reset.html', form=form)


@application.route("/movies/genre/<genre>", methods=['GET'])
def movies_genre(genre):
    page = request.args.get('page')
    if page is None:
        page = 1
    datalist = json.loads(api.get_paging_genre_movies(genre, page))
    pagination = Pagination(page=int(page), total=100, per_page=16, css_framework='bootstrap3')
    return render_template('movie-list.html', datalist=datalist, page=page, pagination=pagination, type=genre+" Movies", user=current_user)


@application.route("/movie/<int:movie_id>", methods=['GET'])
def movie_detail(movie_id):
    data = json.loads(api.get_movie_detail(current_user.username, movie_id))
    return render_template('movie-detail.html', data=data, user=current_user)


@application.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


if __name__ == '__main__':
    application.run()
