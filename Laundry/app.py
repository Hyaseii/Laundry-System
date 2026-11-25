from flask import Flask,redirect, url_for,render_template,request, jsonify,session, flash
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
@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    nama_lengkap = request.form['nama_lengkap']
    name = request.form['username_user']
    password = request.form['password_user']
    email = request.form['email_user']
    no_telp = request.form['no_telp']

    password_hash = generate_password_hash(password)

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            INSERT INTO auth.users (username, password_hash, email)
            VALUES (%s, %s, %s)
            RETURNING user_id
        """, (name, password_hash, email))

        user_id = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO laundry.customers
                (user_id, nama_lengkap, no_telp)
            VALUES (%s, %s, %s)
        """, (user_id, nama_lengkap, no_telp))

        connection.commit()

    except Exception as e:
        connection.rollback()
        print('Registrasi Gagal:', e)
        return "Registrasi Gagal"

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('login'))   


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
    flash('Username atau password salah. Silakan periksa kembali!', 'error')
    return redirect(url_for('login'))



@app.route('/orderpage', methods=['GET'])
def orderpage():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    connection = get_connection()
    cursor = connection.cursor()

    try:
        # Mengambil data layanan
        cursor.execute("""
            SELECT id_service, nama_layanan, harga_per_kg
            FROM laundry.services
            WHERE is_active = TRUE
        """)
        services = cursor.fetchall()

        # Mengambil riwayat pesanan & status pembayaran pelanggan
        # Urutan kolom:
        # 0: id_order
        # 1: tanggal_pesanan
        # 2: target_selesai
        # 3: status_pengerjaan
        # 4: total_harga
        # 5: alamat_penjemputan
        # 6: berat_kg
        # 7: nama_layanan
        # 8: status_pembayaran
        # 9: metode_pembayaran
        cursor.execute("""
            SELECT
                o.id_order,
                o.tanggal_pesanan,
                o.target_selesai,
                o.status_pengerjaan,
                o.total_harga,
                o.alamat_penjemputan,
                od.berat_kg,
                s.nama_layanan,
                p.status_pembayaran,
                p.metode_pembayaran,
                c.id_customer
            FROM laundry.orders o
            JOIN laundry.customers c
                ON o.id_customer = c.id_customer
            LEFT JOIN laundry.orders_detail od
                ON o.id_order = od.id_order
            LEFT JOIN laundry.services s
                ON od.id_service = s.id_service
            LEFT JOIN laundry.payments p
                ON o.id_order = p.id_order
            WHERE c.user_id = %s
            ORDER BY o.tanggal_pesanan DESC
        """, (user_id,))

        rows = cursor.fetchall()
        riwayat_pesanan = rows
        active_order = rows[0] if rows else None
        id_customer = rows[0][10] if rows else None

        # Mengambil data profil pengguna (termasuk nama_lengkap)
        cursor.execute("""
            SELECT
                u.username,
                u.email,
                c.no_telp,
                c.nama_lengkap
            FROM auth.users u
            JOIN laundry.customers c
                ON u.user_id = c.user_id
            WHERE u.user_id = %s
        """, (user_id,))

        profile = cursor.fetchone()

        if profile is None:
            return 'Data profil tidak ditemukan'

        return render_template(
            'order.html',
            services=services,
            profile=profile,
            username=profile[0],
            orders=riwayat_pesanan,
            riwayat_pesanan=riwayat_pesanan,
            active_order=active_order,
            id_customer=id_customer
        )

    finally:
        cursor.close()
        connection.close()


# CREATE ORDER
@app.route('/create_order', methods=['POST'])
def create_order():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    layanan = request.form.get('layanan')
    qty = request.form.get('qty')
    metode = request.form.get('metode_bayar')
    alamat = request.form.get('alamat', '').strip()

    user_id = session['user_id']

    if not layanan or not qty or not metode or not alamat:
        flash('Semua data pesanan harus diisi!', 'error')
        return redirect(url_for('orderpage'))

    try:
        berat = Decimal(qty)
        id_service = int(layanan)

        if berat <= 0:
            raise ValueError

    except (ValueError, InvalidOperation):
        flash('Jumlah berat atau layanan tidak valid!', 'error')
        return redirect(url_for('orderpage'))

    if metode not in ('cash', 'debit'):
        flash('Metode pembayaran tidak valid!', 'error')
        return redirect(url_for('orderpage'))

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            SELECT id_customer
            FROM laundry.customers
            WHERE user_id = %s
        """, (user_id,))

        customer = cursor.fetchone()

        if customer is None:
            flash('Data pelanggan tidak ditemukan!', 'error')
            return redirect(url_for('orderpage'))

        id_customer = customer[0]

        cursor.execute("""
            SELECT harga_per_kg, estimasi_hari
            FROM laundry.services
            WHERE id_service = %s
            AND is_active = TRUE
        """, (id_service,))

        service = cursor.fetchone()

        if service is None:
            flash('Layanan tidak tersedia!', 'error')
            return redirect(url_for('orderpage'))

        harga = service[0]
        estimasi = service[1]
        subtotal = berat * harga

        cursor.execute("""
            INSERT INTO laundry.orders
                (id_customer, user_id, tanggal_pesanan,
                 target_selesai, status_pengerjaan,
                 total_harga, alamat_penjemputan)
            VALUES (
                %s, %s, CURRENT_TIMESTAMP,
                CURRENT_DATE + %s, %s, %s, %s
            )
            RETURNING id_order
        """, (
            id_customer, user_id, estimasi,
            'Menunggu', subtotal, alamat
        ))

        id_order = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO laundry.orders_detail
                (id_order, id_service, berat_kg,
                 harga_per_kg, subtotal)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            id_order, id_service, berat, harga, subtotal
        ))

        cursor.execute("""
            INSERT INTO laundry.payments
                (id_order, jumlah_bayar,
                 metode_pembayaran, status_pembayaran)
            VALUES (%s, %s, %s, %s)
        """, (
            id_order, subtotal, metode, 'Belum Bayar'
        ))

        connection.commit()

        flash(
            f'Pesanan berhasil dibuat! Nomor pesanan: {id_order}',
            'success'
        )

    except Exception as e:
        connection.rollback()
        print('Pemesanan gagal:', e)
        flash('Pesanan gagal dibuat. Silakan coba kembali!', 'error')

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('orderpage'))


# DASHBOARD
@app.route('/dashboardpage')
def dashboardpage():
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("""
        SELECT COALESCE(SUM(jumlah_bayar), 0)
            FROM laundry.payments
            WHERE LOWER(status_pembayaran) IN ('lunas', 'sudah bayar', 'paid')
        """)
        total_pendapatan = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM laundry.customers")
        total_pelanggan = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM laundry.orders")
        total_pesanan = cursor.fetchone()[0]

        return render_template (
            'index.html',
            total_pendapatan=total_pendapatan,
            total_pelanggan=total_pelanggan,
            total_pesanan=total_pesanan
        )

    except Exception as e:
        print('Error fetching dashboard data:', e)
    finally:
        cursor.close()
        connection.close()

# PAYMENT PAGE - DASHBOARD
@app.route('/paymentdashboard')
def paymentdashboardpage():
    connection = get_connection()
    cursor = connection.cursor()

    try :
        cursor.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN LOWER(status_pembayaran) IN ('lunas', 'sudah bayar') THEN jumlah_bayar ELSE 0 END), 0) AS total_masuk,
                COALESCE(SUM(CASE WHEN LOWER(status_pembayaran) NOT IN ('lunas', 'sudah bayar') THEN jumlah_bayar ELSE 0 END), 0) AS belum_dibayar,
                COALESCE(SUM(CASE WHEN LOWER(metode_pembayaran) = 'debit' AND LOWER(status_pembayaran) IN ('lunas', 'sudah bayar') THEN jumlah_bayar ELSE 0 END), 0) AS non_tunai,
                COALESCE(SUM(CASE WHEN LOWER(metode_pembayaran) = 'cash' AND LOWER(status_pembayaran) IN ('lunas', 'sudah bayar') THEN jumlah_bayar ELSE 0 END), 0) AS tunai
            FROM laundry.payments
        """)
        summary = cursor.fetchone()

        cursor.execute("""
            SELECT
                p.id_payment,
                o.id_order,
                c.nama_lengkap,
                o.tanggal_pesanan,
                p.metode_pembayaran,
                p.jumlah_bayar,
                p.status_pembayaran
            FROM laundry.payments p
            JOIN laundry.orders o ON p.id_order = o.id_order
            JOIN laundry.customers c ON o.id_customer = c.id_customer
            ORDER BY p.id_payment DESC
        """)

        payments = cursor.fetchall()

        return render_template(
            'pembayaran.html',
            summary=summary,
            payments=payments,
        )
    finally:
        cursor.close()
        connection.close()

# UPDATE PAYMENT STATUS
@app.route('/update_payment_status', methods=['POST'])
def update_payment_status():
    id_payment = request.form.get('id_payment')
    status_baru = request.form.get('status_pembayaran')

    if status_baru not in ('Belum Bayar', 'Lunas'):
        flash('Status pembayaran tidak valid!', 'error')
        return redirect(url_for('paymentdashboardpage'))

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            UPDATE laundry.payments
            SET status_pembayaran = %s
            WHERE id_payment = %s
        """, (status_baru, id_payment))
        connection.commit()
        flash('Status pembayaran berhasil diperbarui!', 'success')
    except Exception as e:
        connection.rollback()
        print('Update status pembayaran gagal:', e)
        flash('Gagal memperbarui status pembayaran.', 'error')
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('paymentdashboardpage'))

# ORDER - DASHBOARD
@app.route('/orderdashboard')
def orderdashboardpage():
    return render_template ('pesanan.html')


@app.route('/update_profile', methods=['POST'])
def update_profile():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    nama_lengkap = request.form.get('nama_lengkap', '').strip()
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    no_telp = request.form.get('no_telp', '').strip()

    if not nama_lengkap or not username or not email or not no_telp:
        flash('Semua data profil harus diisi.', 'error')
        return redirect(url_for('orderpage'))

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute("""
            UPDATE auth.users
            SET username = %s,
                email = %s
            WHERE user_id = %s
        """, (username, email, user_id))

        cursor.execute("""
            UPDATE laundry.customers
            SET nama_lengkap = %s,
                no_telp = %s
            WHERE user_id = %s
        """, (nama_lengkap, no_telp, user_id))

        connection.commit()

        session['username'] = username

        flash('profile : Pengaturan profil berhasil diperbarui.', 'success')

    except Exception as e:
        connection.rollback()
        print('Update profil gagal:', e)

        flash('Gagal memperbarui pengaturan profil.', 'error')

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for('orderpage'))

if __name__ == "__main__":  #harus di taro paling bawah
    app.run(debug=True)