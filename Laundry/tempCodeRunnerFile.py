
@app.route('/register',methods =['POST'])
def new_user():
    return redirect (url_for('orderpage'))