from flask import Flask,redirect, url_for,render_template

app = Flask(__name__)

@app.route('/register',methods =['POST'])
def login():
    return redirect (url_for('orderpage'))

@app.route('/login', methods =['POST'])
def register():
    return redirect (url_for('orderpage'))

@app.route('/orderpage')
def orderpage():
    return render_template ('order.html')

if __name__ == "__main__":  #harus di taro paling bawah
    app.run(debug=True)