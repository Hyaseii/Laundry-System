
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def get_connection() :
    try:
        connection = psycopg2.connect(
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
            database=os.getenv('DB_NAME')
        )

        print('berhasil terhubung')
        return connection

    except Exception as error:
        print('Gagal terhubung')
        print(error)
        return None

get_connection()