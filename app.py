import os
from flask import Flask, render_template, request, redirect, session, url_for
from datetime import datetime, timedelta
from dotenv import load_dotenv
import mysql.connector
import pytz  # Add this import

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret')

# Define India timezone
IST = pytz.timezone('Asia/Kolkata')

#----------------DATABASE CONNECTION-----------------------------

def get_db_connection():
    host = os.getenv("DB_HOST")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    database = os.getenv("DB_NAME")
    port = os.getenv("DB_PORT")
    ssl_ca = os.getenv("SSL_CA")

    if not all([host, user, password, database, port, ssl_ca]):
        raise ValueError("❌ Missing one or more DB environment variables!")

    return mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=int(port),
        ssl_ca=ssl_ca
    )

#-----------------current date (India timezone)----------------------

def get_current_ist_time():
    """Returns current time in IST timezone"""
    return datetime.now(IST)

def format_ist_time(dt):
    """Format datetime to string in IST"""
    if dt.tzinfo is None:
        dt = IST.localize(dt)
    return dt.strftime("%d-%m-%Y %H:%M")

# Update current_date to use IST
now_date = get_current_ist_time()
current_date = format_ist_time(now_date)

#----------------EMAIL-----------------------------


# ---------------- REMINDER JOB ----------------

#-----------------USER CHECK--------------------------

def get_user(user_id, password):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM Users WHERE Username = %s AND password=%s",(user_id, password))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user


#----------------ROUTS START----------------------------

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        password = request.form.get('password')
        user = get_user(user_id, password)
        if user:
            session['user_id'] = user['ID']
            return redirect(url_for('Uncomplete_tasks'))
    return render_template('login.html')

#------------task page-------------------------------

@app.route("/tasks", methods=["GET", "POST"])
def Uncomplete_tasks():
    if "user_id" not in session:
        return redirect("/")
    
    q = (request.args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        query = (
            "SELECT * FROM todo_tasks WHERE "
            "(task_id LIKE %s OR "
            "task_for LIKE %s OR "
            "task_name LIKE %s OR "
            "task_description LIKE %s OR "
            "status LIKE %s) AND is_completed=%s"
        )
        params = (like, like, like, like, like, "False")
    else:
        query = "SELECT * FROM todo_tasks WHERE is_completed = %s"
        params = ("False",)
    
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute(query, params)
    tasks = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template("Uncomplete_tasks.html", tasks=tasks, search_query=q)



@app.route("/tasks/<int:task_id>")
def mark_complete_task(task_id):
    if "user_id" not in session:
        return redirect("/")
    
    # Get current IST time for completion
    current_ist_date = format_ist_time(get_current_ist_time())
    
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("UPDATE todo_tasks SET is_completed=%s, status=%s, complete_date=%s WHERE task_id=%s",
                ("True", "Complete", current_ist_date, task_id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("Uncomplete_tasks"))

@app.route("/tasks/completed", methods=['GET', 'POST'])
def completed_tasks():
    if "user_id" not in session:
        return redirect("/")
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True,  buffered=True)
    cur.execute("SELECT * FROM todo_tasks WHERE is_completed = %s",("True",))
    tasks = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("completed.html", tasks = tasks)

@app.route("/task/view-details/<int:task_id>")
def view_task_details(task_id):
    if "user_id" not in session:
        return redirect("/")
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True, buffered=True)
    cur.execute("SELECT * FROM todo_tasks WHERE task_id = %s", (task_id,))
    details = cur.fetchone()
    cur.close()
    conn.close()
    return render_template("view_task_details.html", details=details)

@app.route("/tasks/add-task", methods=['GET', 'POST'])
def add_task():
    if "user_id" not in session:
        return redirect("/")
    if request.method == "POST":
        # Use IST time
        now = get_current_ist_time()
        current_ist_date = format_ist_time(now)
        
        task_for = request.form["task_for"]
        task_name = request.form["task_name"]
        task_description = request.form["task_description"]
        d_date = request.form["due_date"]
        d_time = request.form["due_time"]
        notify_me_in = request.form["notify_me_in"]

        html_date = f"{d_date} {d_time}"

        # Parse the date and make it timezone-aware (IST)
        dt_obj = datetime.strptime(html_date, "%Y-%m-%d %H:%M")
        dt_obj_ist = IST.localize(dt_obj)
        
        due_date2 = dt_obj_ist.strftime("%d-%m-%Y %H:%M")
        due_date = dt_obj_ist.strftime("%Y-%m-%d %H:%M")

        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("INSERT INTO todo_tasks(task_for, task_name, task_description, created_at, due_date, due_date2, notify_me_in) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (task_for, task_name, task_description, current_ist_date, due_date, due_date2, notify_me_in))

        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('Uncomplete_tasks'))
    return render_template("add_task.html")

@app.route("/tasks/completed-tasks/clear-all")
def clear_completed_tasks():
    if "user_id" not in session:
        return redirect("/")
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("DELETE FROM todo_tasks WHERE is_completed=%s",("True",))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("completed_tasks"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route('/tasks/sort-tasks', methods=['GET', 'POST'])
def sort_tasks():
    if "user_id" not in session:
        return redirect("/")
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        ids_to_delete = [int(i) for i in request.form.getlist('delete_checkbox')]
        print(ids_to_delete)
        if ids_to_delete:
            format_strings = ','.join(['%s'] * len(ids_to_delete))
            print(format_strings)
            cur.execute(f"UPDATE sort_task SET complete = 'True' WHERE id IN ({format_strings})", tuple(ids_to_delete))
            conn.commit()
            return redirect("/tasks/sort-tasks")
    
    cur.execute("SELECT id,name FROM sort_task WHERE complete=%s",("False",))
    statements = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('uncomplete_sort_work.html', statements=statements)

@app.route('/tasks/add-sort-tasks', methods=['GET', 'POST'])
def add_sort_tasks():
    if "user_id" not in session:
        return redirect("/")
    if request.method == 'POST':
        task_name = request.form["task_name"]
        # Use IST time
        current_ist_date = format_ist_time(get_current_ist_time())
        
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("INSERT INTO sort_task(name, add_dt) VALUES (%s, %s)",(task_name, current_ist_date))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('sort_tasks'))
    return render_template('add_sort_work.html')

@app.route("/tasks/completed-sort-work", methods=['GET', 'POST'])
def complete_sort_tasks():
    if "user_id" not in session:
        return redirect("/")
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True,  buffered=True)
    cur.execute("SELECT * FROM sort_task WHERE complete = %s",("True",))
    statements = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("completed_sort_work.html", statements = statements)

@app.route("/tasks/completed-sort-tasks/clear-all-sort-tasks")
def clear_complete_sort_tasks():
    if "user_id" not in session:
        return redirect("/")
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("DELETE FROM sort_task WHERE complete=%s",("True",))
    conn.commit()
    cur.close()
    conn.close()
    return redirect("/tasks/completed-sort-tasks/clear-all-sort-tasks")

#----------------ROUTS END----------------------------

# ---------------- SCHEDULER CONFIG ----------------
