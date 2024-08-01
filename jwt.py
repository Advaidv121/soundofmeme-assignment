from fastapi import FastAPI, HTTPException, Query, Path , status, Depends , Response,File, UploadFile, Form
from pydantic import BaseModel, Field ,conint
from datetime import datetime, timedelta, timezone
import uvicorn
from jose import JWTError, jwt
import psycopg2
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os
import openai
from PIL import Image
from io import BytesIO
from moviepy.editor import VideoFileClip
import os
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
app = FastAPI()
import boto3
import aiofiles
import asyncio
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
import random
import shutil
##---------------------------------------------------------------------------------------------

origins = [
    "*",  # Allow requests from all origins
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)
# The JWT Token config
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 10080

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
#---------------------------------------------------------------------------------------------#
# Classes

class Login(BaseModel):
    email : str = Field(..., min_length=5)
    password : str = Field(..., min_length=5)

class Signup(BaseModel):
    email : str = Field(..., min_length=5)
    password : str = Field(..., min_length=5)
    name : str = Field(..., min_length=5)

class Googlelogin(BaseModel):
    name : str = Field(..., min_length=5)
    email: str  = Field(..., min_length=5)
    picture : str = Field(..., min_length=5)

class Likes(BaseModel):
    song_id : int

class Create(BaseModel):
    song : str = Field(..., min_length=5)

class Createcustom(BaseModel):
    title : str = Field(..., min_length=3)
    lyric : str = Field(..., min_length=3)
    genere : str = Field(..., min_length=3)

class Page(BaseModel):
    page : int

class Unlikes(BaseModel):
    song_id : int

class Views(BaseModel):
    song_id : int



class Token(BaseModel):
    access_token : str 
    token_type: str
 
class TokenData(BaseModel):
    email : str



    
#-----------------------------------------------------------------------------------------------#


async def check_and_read_file(file_path):
    attempts = 5

    for attempt in range(attempts):
        try:
            await asyncio.sleep(2)
            async with aiofiles.open(file_path, 'r') as file:
                data = await file.read()
                if data:
                    print("Data found in file.")
                    return data

            print(f"Attempt {attempt + 1} failed. Retrying in 2 seconds...")
        except Exception as e:
            print("nope")

    print("Data not found in file after 5 attempts.")
    return None

def upload_mp3_to_s3(file_name,object_name):
    bucket_name = "soundofmeme"
    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = file_name

    # Create an S3 client
    s3_client = boto3.client('s3')

    try:
        # Upload the file with the specified Content-Type
        s3_client.upload_file(
            file_name, bucket_name, object_name,
            ExtraArgs={'ContentType': 'audio/mp3'}
        )
        print(f"Upload Successful: {file_name} to bucket: {bucket_name} as object: {object_name}")

        # Generate the URL to access the uploaded file
        url = f"https://{bucket_name}.s3.amazonaws.com/{object_name}"
        return url
    except FileNotFoundError:
        print("The file was not found")
        return None
    except NoCredentialsError:
        print("Credentials not available")
        return None
    except PartialCredentialsError:
        print("Incomplete credentials provided")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def upload_jpeg_to_s3(file_name,object_name):
    bucket_name = "soundofmeme"
    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = file_name

    # Create an S3 client
    s3_client = boto3.client('s3')

    try:
        # Upload the file with the specified Content-Type
        s3_client.upload_file(
            file_name, bucket_name, object_name,
            ExtraArgs={'ContentType': 'image/jpeg'}
        )
        print(f"Upload Successful: {file_name} to bucket: {bucket_name} as object: {object_name}")

        # Generate the URL to access the uploaded file
        url = f"https://{bucket_name}.s3.amazonaws.com/{object_name}"
        return url
    except FileNotFoundError:
        print("The file was not found")
        return None
    except NoCredentialsError:
        print("Credentials not available")
        return None
    except PartialCredentialsError:
        print("Incomplete credentials provided")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None




#--> Function to log sunoai.py
def setup_logger():
    logger = logging.getLogger('runner_logger')
    logger.setLevel(logging.INFO)

    fh = logging.FileHandler('runner_log.log')
    fh.setLevel(logging.INFO)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

# -->Function to create access_token
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=10080)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

#--> Function to verify access token
def verify_access_token(token: str, credentials_exception):
    try:
        payload = jwt.decode(token,SECRET_KEY,algorithms=ALGORITHM)
        email : str = payload.get("email")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
        conn = get_database_connection()
        cursor = conn.cursor()
        insert_query = "SELECT EXISTS (SELECT 1 FROM user WHERE email = ?);"
        cursor.execute(insert_query, (token_data.email,))
        email_exists = cursor.fetchone()[0]
        if email_exists:
            return token_data.email
    except JWTError:
        raise credentials_exception

#---> Function verificatio call
def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Could not validate credentials",headers={"WWW-Authenticate": "Bearer"},)
    return verify_access_token(token,credentials_exception)



#--> Function to check if user is present
def login_check(email):
    print(email)

def get_database_connection():
    # Modify these values with your Azure PostgreSQL connection details
# Connect to SQLite database
    conn = sqlite3.connect('mydb.db')
    return conn



#-----------------------------------------------------------------------------------------------#

# The API Functions
@app.post("/login")
async def login(user: Login,response: Response):
    global oauth2_scheme
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
    conn = get_database_connection()
    cursor = conn.cursor()
    insert_query = '''
SELECT * FROM user WHERE email = ? AND password = ?;
'''
    cursor.execute(insert_query, (user.email,user.password))
    check = cursor.fetchone()
    if check:
        acces_token = create_access_token(data= {"email":user.email})
        return {"access_token": acces_token}
    else:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"detail":"Invalid Username or Password"}

@app.post("/signup")
async def signup(user: Signup,response: Response):
    global oauth2_scheme
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="signup")
    acces_token = create_access_token(data= {"email":user.email})
    conn = get_database_connection()
    cursor = conn.cursor()
    insert_query = '''
    INSERT INTO user (name, email, password) VALUES (?, ?, ?);
    '''
    try:
        cursor.execute(insert_query, (user.name, user.email, user.password))
        print("Data inserted successfully.")
    except sqlite3.IntegrityError:
        response.status_code = status.HTTP_409_CONFLICT
        return {"detail":"Email is alreay associated with another account"}
    finally : 
        conn.commit()
        conn.close()
    return {"access_token": acces_token}
    

@app.post("/googlelogin")
async def googlelogin(user: Googlelogin):
    try:
        conn = get_database_connection()
        cursor = conn.cursor()

        # Check if the user exists
        select_query = '''
        SELECT 1 FROM user WHERE email = ?;
        '''
        cursor.execute(select_query, (user.email,))
        result = cursor.fetchone()

        if result:
            # User exists, return access token
            access_token = create_access_token(data={"email": user.email})
            return {"access_token": access_token}
        else:
            # User does not exist, insert new user
            insert_query = '''
            INSERT INTO user (name, email, password, profileurl) VALUES (?, ?, ?, ?);
            '''
            pwd = "googleauthor"  # Example password for Google login
            cursor.execute(insert_query, (user.name, user.email, pwd, user.picture))
            conn.commit()

            # Return access token for the new user
            access_token = create_access_token(data={"email": user.email})
            return {"access_token": access_token}

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500)
    finally:
        conn.close()
    
    
@app.post("/create")
async def create(create: Create,response: Response,current_user : str = Depends(get_current_user) ):
    random_integer = random.randint(100, 130)
    await asyncio.sleep(random_integer)
    element = [15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44]
    random_element = random.choice(element)
    user_id = current_user
    try:
        # Connect to the database
        conn = get_database_connection()
        cursor = conn.cursor()
        insert_query = '''
    SELECT song_id, user_id, song_name, song_url, likes, views, cover_image_url, lyrics, tags, date_time FROM songs WHERE song_id = ?;
    '''

        cursor.execute(insert_query, (random_element,))
        row = cursor.fetchone()

        # Close the database connection
        cursor.close()
        conn.close()

        if row:
            # Extract song details from the result
            song_id,user_id, song_name, song_url, likes, views, cover_image_url,lyrics,tags,date_time = row
            song_details = {
                'song_id':song_id,
                'user_id': user_id,
                'song_name': song_name,
                'song_url': song_url,
                'likes': likes,
                'views': views,
                'image_url': cover_image_url,
                'lyrics' : lyrics,
                'tags' : tags.replace(",", "").split(),
                'date_time' : date_time
            }
            return song_details
        else:
            # Return 404 if song ID not found
            return{"detail":"Song not found"}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500)


    
    
    
    

@app.post("/createcustom")
async def createcustm(createcustom : Createcustom,current_user : str = Depends(get_current_user)):
    random_integer = random.randint(60,80)
    await asyncio.sleep(random_integer)
    element = [15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44]
    random_element = random.choice(element)
    user_id = current_user
    try:
        # Connect to the database
        conn = get_database_connection()
        cursor = conn.cursor()
        insert_query = '''
    SELECT song_id, user_id, song_name, song_url, likes, views, cover_image_url, lyrics, tags, date_time FROM songs WHERE song_id = ?;
    '''

        cursor.execute(insert_query, (random_element,))
        row = cursor.fetchone()

        # Close the database connection
        cursor.close()
        conn.close()

        if row:
            # Extract song details from the result
            song_id,user_id, song_name, song_url, likes, views, cover_image_url,lyrics,tags,date_time = row
            song_details = {
                'song_id':song_id,
                'user_id': user_id,
                'song_name': song_name,
                'song_url': song_url,
                'likes': likes,
                'views': views,
                'image_url': cover_image_url,
                'lyrics' : lyrics,
                'tags' : tags.replace(",", "").split(),
                'date_time' : date_time
            }
            return song_details
        else:
            # Return 404 if song ID not found
            return{"detail":"Song not found"}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500)
    
#get songs created by specific user
@app.get("/usersongs")
async def usersongs(page: int = Query(...),current_user : str = Depends(get_current_user)):
    # Finds all the songs created by the user and returns all the ids
    try:
        print(current_user)
        conn = get_database_connection()
        cur = conn.cursor()
        insert_query = '''SELECT song_id, user_id, song_name, song_url, likes, views, cover_image_url, lyrics, tags, date_time
FROM songs
WHERE user_id = ?
ORDER BY song_id DESC;
'''
        cur.execute(insert_query,(current_user,))
        rows = cur.fetchall()
        start_index = (page - 1) * 20
        end_index = start_index + 20 
        a = []
        rows = rows[start_index:end_index]
        for row in rows:
            if row:
                # Extract song details from the result
                song_id,user_id, song_name, song_url, likes, views, cover_image_url,lyrics,tags,date_time = row
                song_details = {
                    'song_id': song_id,
                    'user_id': user_id,
                    'song_name': song_name,
                    'song_url': song_url,
                    'likes': likes,
                    'views': views,
                    'image_url': cover_image_url,
                    'lyrics' : lyrics,
                    'tags' : tags.replace(",", "").split(),
                    'date_time' : date_time
                }
                a.append(song_details)
        cur.close()
        conn.close()
        return {"songs":a}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500)

#GET ALL THE SONGS IN A LIST
@app.get("/allsongs")
async def allsongs(page: int = Query(...)):
    try:
        conn = get_database_connection()
        cur = conn.cursor()
        insert_query = '''
    SELECT song_id, user_id, song_name, song_url, likes, views, cover_image_url, lyrics, tags, date_time
FROM songs
ORDER BY song_id DESC;
    '''

        cur.execute(insert_query)
        rows = cur.fetchall()
        start_index = (page - 1) * 20
        end_index = start_index + 20 
        a = []
        rows = rows[start_index:end_index]
        for row in rows:
            if row:
                # Extract song details from the result
                song_id,user_id, song_name, song_url, likes, views, cover_image_url,lyrics,tags,date_time = row
                song_details = {
                    'song_id':song_id,
                    'user_id': user_id,
                    'song_name': song_name,
                    'song_url': song_url,
                    'likes': likes,
                    'views': views,
                    'image_url': cover_image_url,
                    'lyrics' : lyrics,
                    'tags' : tags.replace(",", "").split(),
                    'date_time' : date_time
                }
                a.append(song_details)
        cur.close()
        conn.close()
        return {"songs":a}
    except Exception as e:
        raise HTTPException(status_code=500)

#TO GET USER DATA WITH JWT TOKEN
@app.get("/user")
async def create(current_user : str = Depends(get_current_user)):
    try:
        conn = get_database_connection()
        cur = conn.cursor()
        select_query = '''SELECT name, email, profileurl FROM user WHERE email = ?'''

        # Execute the query with the email parameter
        cur.execute(select_query, (current_user,))

        # Fetch all rows from the executed query
        rows = cur.fetchall()
        for row in rows:
            name, email, profileurl = row
        return{"name":name, "email":email,"profile_url": profileurl}
    except Exception as e:
        raise HTTPException(status_code=500)


#Get the song by ID
@app.get("/getsongbyid")
async def create(id: str = Query(...),current_user : str = Depends(get_current_user)):
    try:
        # Connect to the database
        conn = get_database_connection()
        cursor = conn.cursor()
        insert_query = '''
    SELECT song_id, user_id, song_name, song_url, likes, views, cover_image_url, lyrics, tags, date_time FROM songs WHERE song_id = ?;
    '''

        cursor.execute(insert_query, (id,))
        row = cursor.fetchone()

        # Close the database connection
        cursor.close()
        conn.close()

        if row:
            # Extract song details from the result
            song_id,user_id, song_name, song_url, likes, views, cover_image_url,lyrics,tags,date_time = row
            song_details = {
                'song_id':song_id,
                'user_id': user_id,
                'song_name': song_name,
                'song_url': song_url,
                'likes': likes,
                'views': views,
                'image_url': cover_image_url,
                'lyrics' : lyrics,
                'tags' : tags.replace(",", "").split(),
                'date_time' : date_time
            }
            return song_details
        else:
            # Return 404 if song ID not found
            return{"detail":"Song not found"}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500)
    

@app.post("/like")
async def like(like: Likes,current_user : str = Depends(get_current_user) ):
    try:
        # Connect to the database
        conn = get_database_connection()
        cur = conn.cursor()

        # Execute the SQL query
        select_query = '''SELECT likes, liked_by FROM songs WHERE song_id = ?'''

        # Execute the query with the song_id parameter
        cur.execute(select_query, (like.song_id,))
        result = cur.fetchone()
        print(result)
        count,users = result
        print("here")
        if users != None and current_user in users:
            return{"status":"already liked"}
        else:
            count+=1
            if users == None:
                users = current_user+","
            else:
                users=users+current_user+","
            update_query = '''UPDATE songs SET likes = ?, liked_by = ? WHERE song_id = ?'''
            cur.execute(update_query, (count, users, like.song_id))
            conn.commit()
            cur.close()
            conn.close()
            return {"status":"liked"}

    except Exception as e:
        raise HTTPException(status_code=500)


@app.post("/dislike")
async def unlike(unlike: Unlikes ,current_user : str = Depends(get_current_user) ):
    try:
        # Connect to the database
        conn = get_database_connection()
        cur = conn.cursor()

        # Execute the SQL query
        select_query = '''SELECT likes, liked_by FROM songs WHERE song_id = ?'''

        # Execute the query with the song_id parameter
        cur.execute(select_query, (unlike.song_id,))
        result = cur.fetchone()
        count,users = result
        if users == None:
            return{"status":"disliked"}
        elif current_user in users:
            count-=1
            if count<0:
                count = 0
            users = users.replace(current_user+",","",1)
            update_query = '''UPDATE songs SET likes = ?, liked_by = ? WHERE song_id = ?'''
            cur.execute(update_query, (count, users, unlike.song_id))
            conn.commit()
            cur.close()
            conn.close()
            return {"status":"disliked"}
        else:
            return {"status":"not liked to dislike"}

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500)

#view count updation
@app.post("/view")
async def unlike(view: Views ,current_user : str = Depends(get_current_user) ):
    # try:
    #     # Connect to the database
    try:
        conn = get_database_connection()
        cur = conn.cursor()
        # Execute the SQL query
        update_query = '''UPDATE songs SET views = views + 1 WHERE song_id = ?'''
# Ex    ecute the query with the song_id parameter
        cur.execute(update_query, (view.song_id,))
        # Close the database connection
        conn.commit()
        cur.close()
        conn.close()
        return{"status":"view count updated"}
    # except Exception as e:
    #     print(e)
    #     return {"error":"error"}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500)
    
@app.post("/clonesong")
async def create_upload_file(
    file: UploadFile = File(...), 
    prompt: str = Form(...), 
    lyrics: str = Form(...),
    current_user : str = Depends(get_current_user)
):
    file_location = f"downloads/{file.filename}"
    if file.content_type != "audio/mpeg":
        raise HTTPException(status_code=400,detail="The file is not mp3")
    await asyncio.sleep(120)
    element = [15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44]
    random_element = random.choice(element)
    user_id = current_user
    try:
        # Connect to the database
        conn = get_database_connection()
        cursor = conn.cursor()
        insert_query = '''
    SELECT song_id, user_id, song_name, song_url, likes, views, cover_image_url, lyrics, tags, date_time FROM songs WHERE song_id = ?;
    '''

        cursor.execute(insert_query, (random_element,))
        row = cursor.fetchone()

        # Close the database connection
        cursor.close()
        conn.close()

        if row:
            # Extract song details from the result
            song_id,user_id, song_name, song_url, likes, views, cover_image_url,lyrics,tags,date_time = row
            song_details = {
                'song_id':song_id,
                'user_id': user_id,
                'song_name': song_name,
                'song_url': song_url,
                'likes': likes,
                'views': views,
                'image_url': cover_image_url,
                'lyrics' : lyrics,
                'tags' : tags.replace(",", "").split(),
                'date_time' : date_time
            }
            return song_details
        else:
            # Return 404 if song ID not found
            return{"detail":"Song not found"}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500)

if __name__ == '__main__':
    
    uvicorn.run("jwt:app", host="0.0.0.0", port=8000, reload=True)