import os
from flask import Flask, render_template, request, redirect, session, url_for
from datetime import datetime
from dotenv import load_dotenv
import mysql.connector
from flask_apscheduler import APScheduler
import mysql.connector
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret')


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
#-----------------current date----------------------

now_date = datetime.now()
current_date = now_date.strftime("%d-%m-%Y %H:%M")

#----------------EMAIL-----------------------------
def send_email(subject, body):
    sender = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASSWORD")
    receiver = os.getenv("RECIVER_EMAIL")
    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, receiver, msg.as_string())
        print(f"✅ Email sent to {receiver}")
    except Exception as e:
        print("❌ Email error:", e)


# ---------------- REMINDER JOB ----------------
def reminder_job():
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M")
    recent_date_time = datetime.strptime(now_str, "%Y-%m-%d %H:%M")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    now = datetime.now()

    query = """
        SELECT * FROM todo_tasks
        WHERE is_completed = False AND due_date > %s
    """
    cursor.execute(query, (recent_date_time,))
    tasks = cursor.fetchall()

    for task in tasks:
        last_reminded = task["last_reminded"]
        interval_time = task["notify_me_in"]
        remind_due = (last_reminded is None or recent_date_time >= last_reminded + timedelta(hours=interval_time))

        if remind_due:
            send_email(
                subject=f"Reminder: {task['task_name']}",
                body=f"Task '{task['task_name']}' is still pending.\nDue: {task['due_date']}"
            )

            # Update last_reminded in DB
            update_q = "UPDATE todo_tasks SET last_reminded=%s WHERE task_id=%s"
            cursor.execute(update_q, (recent_date_time, task["task_id"]))
            conn.commit()

    cursor.close()
    conn.close()


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
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("UPDATE todo_tasks SET is_completed=%s, status=%s, complete_date=%s WHERE task_id=%s",("True", "Complete", current_date, task_id))
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
    cur = conn.cursor(dictionary=True, buffered=True)  # added buffered=True
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
        now = datetime.now()
        dt_obj = now.strftime("%d-%m-%Y %H:%M")
        task_for = request.form["task_for"]
        task_name = request.form["task_name"]
        task_description = request.form["task_description"]
        d_date = request.form["due_date"]
        d_time = request.form["due_time"]
        notify_me_in = request.form["notify_me_in"]

        html_date = f"{d_date} {d_time}"

        dt_obj1 = datetime.strptime(html_date, "%Y-%m-%d %H:%M")
        due_date2 = dt_obj1.strftime("%d-%m-%Y %H:%M")

        dt_obj = datetime.strptime(html_date, "%Y-%m-%d %H:%M")

        due_date = dt_obj.strftime("%Y-%m-%d %H:%M")

        
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("INSERT INTO todo_tasks(task_for, task_name, task_description, created_at, due_date, due_date2, notify_me_in) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (task_for, task_name, task_description, current_date, due_date, due_date2, notify_me_in))

        conn.commit()
        cur.close()
        conn.close()
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
        # Get checked statement IDs from the submitted form
        ids_to_delete = [int(i) for i in request.form.getlist('delete_checkbox')]
        print(ids_to_delete)
        if ids_to_delete:
            format_strings = ','.join(['%s'] * len(ids_to_delete))
            print(format_strings)
            # Uncomment when ready to delete:
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
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("INSERT INTO sort_task(name, add_dt) VALUES (%s, %s)",(task_name, current_date))
        conn.commit()
        cur.close()
        conn.close()
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
class Config:
    SCHEDULER_API_ENABLED = True

app.config.from_object(Config())
scheduler = APScheduler()
scheduler.init_app(app)

scheduler.add_job(
    id="task_reminder",
    func=reminder_job,
    trigger="interval",
    hours=1
)
scheduler.start()
if __name__ == '__main__':
    app.run()
