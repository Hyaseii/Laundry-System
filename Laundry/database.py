import psycopg2

def get_connection() :
    try:
        connection = psycopg2.connect(
            user = 'postgres',
            password = 'razan1234',
            host = 'localhost',
            port = 5432,
            database = 'laundry-db'
        )

        print('berhasil terhubung')
        return connection

    except Exception as error:
        print('Gagal terhubung')
        print(error)
        return None

get_connection()