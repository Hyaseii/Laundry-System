from flask import Flask,redirect, url_for,render_template,request, jsonify,session
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_connection
import os
from dotenv import load_dotenv
from decimal import Decimal, InvalidOperation

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

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
        SELECT id_service, nama_layanan, harga_per_kg 
        FROM laundry.services
        WHERE is_active = TRUE
        """)

        services = cursor.fetchall()

        return render_template('order.html', services = services)

    finally :
        connection.close()
        cursor.close()


# CREATE ORDER
@app.route('/create_order', methods =['POST'])
def create_order():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    layanan = request.form['layanan']
    qty = request.form['qty']
    metode = request.form['metode_bayar']
    alamat = request.form['alamat']

    user_id = session['user_id']

    if not layanan or not qty or not metode or not alamat:
        return 'Semua data harus di isi'

    try : 

        berat = Decimal(qty)

        if berat <= 0 :
            return 'berat harus lebih dari 0'
    except (ValueError, InvalidOperation) :
        return 'data tidak valid'

    if metode not in ('cash', 'debit'):
        return 'Metode pembayaran tidak valid'

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
        SELECT id_customer FROM laundry.customers
        WHERE user_id = %s
        """,(user_id,))

        customer = cursor.fetchone()

        if customer is None :
            return 'Data pelanggan tidak ditemukan'

        id_customer = customer[0]

        id_service = int(layanan)

        cursor.execute("""
            SELECT id_service, harga_per_kg, estimasi_hari
            FROM laundry.services
            WHERE id_service = %s
            AND is_active = TRUE
        """, (id_service,))

        service = cursor.fetchone()
        print("DATA SERVICE:", service)
        print("JUMLAH KOLOM:", len(service) if service else 0)


        if service is None:
            return 'Layanan tidak sedang tersedia'

        harga = service[1]
        estimasi = service[2]

        subtotal = berat * harga

        cursor.execute("""
        INSERT INTO laundry.orders (id_customer, user_id ,tanggal_pesanan, target_selesai, status_pengerjaan,
            total_harga, alamat_penjemputan)
            VALUES (%s, %s,CURRENT_TIMESTAMP,CURRENT_DATE + %s, %s, %s, %s)  
            RETURNING id_order
        """,(id_customer, user_id,estimasi, 'Menunggu', subtotal, alamat))
# CURRENT DATE error column "current_date" does not exist
        id_order = cursor.fetchone()[0]

        cursor.execute("""
        INSERT INTO laundry.orders_detail
            (id_order, id_service, berat_kg ,harga_per_kg, subtotal)
            VALUES (%s,%s,%s,%s,%s)
        """,(id_order, id_service, berat, harga, subtotal))

        cursor.execute("""
        INSERT INTO laundry.payments
            (id_order, jumlah_bayar, metode_pembayaran, status_pembayaran)
            VALUES(%s,%s,%s,%s)
        """,(id_order, subtotal, metode, 'Belum Bayar'))

        connection.commit()

        print('ID USER:', user_id)
        print('ID CUSTOMER:', id_customer)
        print('ID ORDER:', id_order)
        print('ID SERVICE:', id_service)
        print('BERAT:', berat)
        print('SUBTOTAL:', subtotal)
        return "Pesanan berhasil dibuat"
        

    except Exception as e:
        connection.rollback()
        print('Pemesanan gagatl',e)
        return f'GAGAL : {e}'

    finally:
        connection.close()
        cursor.close()

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