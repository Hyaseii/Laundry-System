from flask import Flask,redirect, url_for,render_template,request, jsonify,session
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_connection
import os
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# home
@app.route('/')
def home():
    return(render_template('register.html'))

# REGISTER
@app.route('/register',methods =['POST','GET'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    name = request.form['username_user']
    password = request.form['password_user']
    email = request.form['email_user']
    no_telp = request.form['no_telp']

    password_hash = generate_password_hash(password)

    connection = get_connection()
    cursor = connection.cursor()

    try :
        cursor.execute("""
            INSERT INTO auth.users ( username, password_hash, email)
                VALUES (%s,%s,%s)
                RETURNING user_id
        """,(name, password_hash, email))

        user_id = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO laundry.customers(user_id,no_telp)
                VALUES (%s, %s)
        """,(user_id,no_telp))

        connection.commit()

    except Exception as e:
        connection.rollback()
        print('Registrasi Gagal: ',e)
        return "Registrasi Gagal"

    finally:
        cursor.close()
        connection.close()

    return redirect (url_for('login'))


# LOGIN
@app.route('/login', methods =['GET','POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    name = request.form['username_user']
    password = request.form['password_user']

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT user_id, username, password_hash, role
            FROM auth.users
            WHERE username = %s
        """, (name,))

        user_id = cursor.fetchone()

    finally:
        cursor.close()
        connection.close()

    if user_id and check_password_hash(user_id[2], password):

        session.clear()

        session['user_id'] = user_id[0]
        session['username'] = user_id[1]
        session['role'] = user_id[3]

        if user_id[3] == 'admin':
            return redirect(url_for('dashboardpage'))

        else:
            return redirect(url_for('orderpage'))
    return 'Username atau password salah'

# ORDER
@app.route('/orderpage', methods = ['GET'])
def orderpage():
    return render_template ('order.html')

# CREATE ORDER
@app.route('/create_order', methods =['POST'])
def create_order():

    layanan = request.form['layanan']
    qty = request.form['qty']
    metode = request.form['metode_bayar']
    alamat = request.form['alamat']

    connection = get_connection()
    cursor = connection.cursor()

    try : 
        cursor.execute("""
        INSERT INTO laundry.orders (user_id, alamat_penjemputan, id_customer)
            VALUES (%s, %s, %s)
            RETURNING id_order
        """,(user_id, alamat, id_customer))

        id_customer = cursor.fetchone()
        user_id = cursor.fetchone()
        id_order = cursor.fetchone()[0]

        cursor.execute("""
        INSERT INTO laundry.payments (metode_pembayaran)
            VALUES (%s)
            RETURNING id_payment
        """,(id_order, metode))

        id_payment = cursor.fetchone()[0]

        session['layanan'] = user_id[6]

    except :
        return 'GAGAL'

    print('Layanan : ',layanan)
    print('Berat : ',qty)
    print('Metode : ',metode)
    print('Alamat : ',alamat)

    return 'DATA BERHASIL DI CATAT'

# DASHBOARD
@app.route('/dashboardpage')
def dashboardpage():
    return render_template ('index.html')

# PAYMENT PAGE - DASHBOARD
@app.route('/paymentdashboard')
def paymentdashboardpage():
    return render_template('pembayaran.html')

# ORDER - DASHBOARD
@app.route('/orderdashboard')
def orderdashboardpage():
    return render_template ('pesanan.html')


if __name__ == "__main__":  #harus di taro paling bawah
    app.run(debug=True)