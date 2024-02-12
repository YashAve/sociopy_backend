import os
from flask import Flask, jsonify, request
import psycopg2
from psycopg2.extras import RealDictCursor
import traceback
import hashlib
from datetime import datetime
import json
from helper import decrypt

app = Flask(__name__)

SUCCESS = "success"
FAILURE = "failure"
INCOMPLETE = "incomplete"
POSTS_FILE_PATH = "/home/yash/learning/python/post_images"
POSTS_DATA_PATH = "/home/yash/learning/python/post_data"

def get_connection():
    connection = psycopg2.connect(database="sociopy", password="7", host="127.0.0.1", port="5432", user="postgres")
    connection.autocommit = True
    return connection

def fetch(cursor, details, selection=0):
    query = str()
    if selection == 0:
        query = "select count(*) from profile where email = '{}';".format(details['email'])
    elif selection == 1:
        query = "select email, first_name, last_name from profile where email = '{}' and encrypted_password = '{}';".format(details['email'], details['password'])
    elif selection == 2:
        query = "select count(*) from posts where post_signature = 'empty' and email = '{}';".format(details['email'])
    elif selection == 3:
        query = "select email, first_name, last_name from profile where email != '{}' and email not in (select followed from friends where follower = '{}');".format(details['email'], details['email'])
    elif selection == 4:
        query = "select email, first_name, last_name from profile where email != '{}' and email in (select followed from friends where follower = '{}');".format(details['email'], details['email'])
    cursor.execute(query)
    return cursor.fetchall()

def insert(cursor, email, first_name, second_name, password):
    query = f"insert into posts (post_signature, email, creation_time) values ('empty', '{email}', '{datetime.now()}')"
    cursor.execute(query)
    query = f"insert into profile values ('{email}', '{first_name}', '{second_name}', '{password}');"
    cursor.execute(query)

def save_post(cursor, data):
    query = str()
    result = fetch(cursor=cursor, details=data, selection=2)
    if result[0][0] == 1:
        query = "update posts set post_signature = '{}', media = '{}', caption_signature = '{}', creation_time = '{}';".format(data['post_signature'], data['media'], data['caption_signature'], data['creation_time'])
    else:
        query = "insert into posts (post_signature, email, media, caption_signature, creation_time) values ('{}', '{}', '{}', '{}', '{}');".format(
            data['post_signature'], data['email'], data['media'], data['caption_signature'], data['creation_time']
        )
    cursor.execute(query)

@app.route("/connections/<string:email>/<string:connections>", methods=["GET"])
def connections(email, connections="no"):
    connection = get_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    result = FAILURE
    value = 333
    data = {'email': email}
    try:
        if connections == "no":
            data['connections'] = fetch(cursor=cursor, details=data, selection=3)
        else:
            data['connections'] = fetch(cursor=cursor, details=data, selection=4)
        result = SUCCESS
        value = 200
    except:
        result = traceback.format_exc()
    finally:
        connection.close()
        data['message'] = result
        return jsonify(data), value
    
def load(request_file):
    pass


@app.route("/post", methods=["POST"])
def post():
    connection = get_connection()
    cursor = connection.cursor()
    result = {'message': FAILURE}
    value = 333
    data = {'post_signature': str(), 'media': str(), 'caption_signature': str(), 'likes': int(), 'creation_time': datetime.now()}
    try:
        if 'post_data' in request.files:
            user_data = request.files['post_data']
            if user_data.filename != '':
                if not os.path.exists(POSTS_DATA_PATH):
                    os.mkdir(POSTS_DATA_PATH)
                file_extension = user_data.filename.split(".")[1]
                file_path = os.path.join(POSTS_DATA_PATH, f"{hashlib.md5(user_data.read()).hexdigest()}.{file_extension}")
                if os.path.exists(file_path):
                    os.remove(file_path)
                user_data.seek(0)
                user_data.save(file_path)
                with open(file_path, "r") as f:
                    temp_data = json.load(f)
                    data['email'] = temp_data['email']
                    if 'email' in temp_data:
                        if data['email'] != '' and fetch(cursor=cursor, details={'email': data['email']})[0][0] > 0:
                            if not os.path.exists(POSTS_FILE_PATH):
                                os.mkdir(POSTS_FILE_PATH)
                            caption_signature = data['caption_signature']
                            if caption_signature != 'no_comment':
                                data['caption_signature'], data['post_signature'] = caption_signature, caption_signature
                            if 'post_image' in request.files:
                                file = request.files['post_image']
                                if file.filename != '':
                                    data['post_signature'] = hashlib.md5(file.read()).hexdigest()
                                    file_extension = file.filename.split(".")[1]
                                    data['media'] = f"{data['post_signature']}.{file_extension}"
                                    if data['caption_signature'] != "":
                                        data['post_signature'] = data['caption_signature']
                                    file_path = os.path.join(POSTS_FILE_PATH, f"{data['post_signature']}.{file_extension}")
                                    if not os.path.exists(file_path):
                                        file.seek(0)
                                        file.save(file_path)
                                    if os.path.exists(file_path):
                                        result['message'] = SUCCESS
                            else:
                                result['message'] = INCOMPLETE
                                value = 200
        data['creation_time'] = datetime.now()
    except:
        result['message'] = traceback.format_exc()
    finally:
        if result['message'] in (SUCCESS, INCOMPLETE):
            save_post(cursor=cursor, data=data)
        connection.close()
        return jsonify(result), value

@app.route("/login/<string:email>/<string:password>", methods=["GET"])
def login(email, password):
    connection = get_connection()
    cursor = connection.cursor()
    message = ""
    value = 333
    result_dictionary = {'email': str(), 'first_name': str(), 'last_name': str()}
    try:
        result = fetch(cursor=cursor, details={'email': email})
        if result[0][0] > 0:
            data_cursor = connection.cursor(cursor_factory=RealDictCursor)
            result = fetch(cursor=data_cursor, details={'email': email, 'password': password}, selection=1)
            if len(result) == 1:
                message = SUCCESS
                value = 200
                result_dictionary = result[0]
            else:
                value = 202
                message = FAILURE
        else:
            value = 201
            message = FAILURE
    except Exception as error:
        message = str(traceback.format_exc())
    finally:
        connection.close()
        return jsonify(result_dictionary), value


@app.route("/register/<string:signature>", methods=["POST"])
def register(signature):
    connection = get_connection()
    cursor = connection.cursor()
    message = ""
    value = 333
    try:
        if "post_data" in request.files:
            file = request.files['post_data']
            if file.filename != "":
                if hashlib.md5(file.read()).digest() == signature:
                    filepath = os.path.join(POSTS_DATA_PATH, f"{signature}.7z")
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    file.seek(0)
                    file.save(filepath)
        result = fetch(cursor=cursor, details={'email': email})
        if result[0][0] == 0:
            insert(cursor=cursor, email=email, first_name=first_name, second_name=second_name, password=password)
            message = SUCCESS
            value = 200
        else:
            value = 201
            message = FAILURE
    except Exception as error:
        message = str(traceback.format_exc())
    finally:
        connection.close()
        return jsonify({"message": message}), value

@app.route("/")
def check():
    return "success"

if __name__ == '__main__':
    app.run(debug=True, port=7777)
