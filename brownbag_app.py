import streamlit as st
import sqlite3
import pandas as pd
import smtplib
import time
from email.mime.text import MIMEText
from datetime import datetime
from fpdf import FPDF

# --- 1. DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('ssn_research.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS departments 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, 
                  head_email TEXT, coord_email TEXT, preferred_day TEXT, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS presentations 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, presenter TEXT, designation TEXT, 
                  title TEXT, abstract TEXT, date TEXT, time TEXT, venue_hall TEXT, dept_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE)''')
    c.execute('CREATE TABLE IF NOT EXISTS credentials (role TEXT UNIQUE, password TEXT)')
    c.execute("INSERT OR IGNORE INTO credentials (role, password) VALUES ('admin', 'admin123')")
    conn.commit()
    conn.close()

# --- 2. HELPERS ---
def send_mail(subject, body, recipients, sender_email, app_password):
    if not sender_email or not app_password: return "Mail credentials missing."
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = ", ".join(recipients)
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.sendmail(sender_email, recipients, msg.as_string())
        server.quit()
        return True
    except Exception as e: return str(e)

def generate_pdf(df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="Shiv Nadar University | Brown Bag Presentation Schedule", ln=True, align='C')
    pdf.ln(10)
    for _, row in df.iterrows():
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 10, txt=f"Date: {row['date']} | Dept: {row['Dept']}", ln=True)
        pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 5, txt=f"Topic: {row['title']}\nPresenter: {row['presenter']} ({row['designation']})\nVenue: Hall {row['venue_hall']} | Time: {row['time']}\nAbstract: {row['abstract']}\n" + "-"*80)
    return pdf.output(dest='S').encode('latin-1')

def delayed_refresh(message, icon="✅"):
    st.success(f"{icon} {message}")
    time.sleep(3)
    st.rerun()

# --- 3. APP UI ---
st.set_page_config(page_title="Shiv Nadar University | Brown Bag Portal", layout="wide")
init_db()

if 'auth' not in st.session_state: st.session_state['auth'] = False
if 'dept' not in st.session_state: st.session_state['dept'] = None

st.title("🎓 Shiv Nadar University | Brown Bag Portal")
tabs = st.tabs(["📅 Public Schedule", "🔐 Coordinator Access", "🛠️ Admin Control"])

# --- TAB 1: PUBLIC VIEW (Search & Sort Included) ---
with tabs[0]:
    conn = sqlite3.connect('ssn_research.db')
    try:
        query = "SELECT p.*, d.name as Dept FROM presentations p JOIN departments d ON p.dept_id = d.id"
        df = pd.read_sql_query(query, conn)
        if not df.empty:
            df['date_obj'] = pd.to_datetime(df['date'])
            today = pd.to_datetime(datetime.now().date())
            search_query = st.text_input("🔍 Search Presentations...", "")
            
            c1, c2 = st.columns(2)
            view_mode = c1.radio("View", ["Upcoming", "Past"], horizontal=True)
            sort_by = c2.selectbox("Sort By", ["Date", "Department"])
            
            filtered = df[df['date_obj'] >= today] if view_mode == "Upcoming" else df[df['date_obj'] < today]
            if search_query:
                filtered = filtered[filtered.apply(lambda row: row.astype(str).str.contains(search_query, case=False).any(), axis=1)]
            
            filtered = filtered.sort_values('date_obj', ascending=(view_mode=="Upcoming")) if sort_by=="Date" else filtered.sort_values(['Dept', 'date_obj'])

            for _, row in filtered.iterrows():
                with st.expander(f"📌 {row['date']} | {row['Dept']} - {row['title']}"):
                    st.write(f"**Presenter:** {row['presenter']} ({row['designation']}) | **Venue:** Hall {row['venue_hall']}")
                    st.info(row['abstract'])
        else: st.info("No records found.")
    finally: conn.close()

# --- TAB 2: COORDINATOR ACCESS ---
with tabs[1]:
    if not st.session_state['auth']:
        conn = sqlite3.connect('ssn_research.db')
        depts_df = pd.read_sql_query("SELECT * FROM departments", conn)
        conn.close()
        if not depts_df.empty:
            col1, col2 = st.columns(2)
            sel_dept = col1.selectbox("Dept", depts_df['name'].tolist())
            pwd_in = col2.text_input("Password", type="password")
            if st.button("Login"):
                target_pwd = depts_df[depts_df['name'] == sel_dept]['password'].values[0]
                if pwd_in == target_pwd:
                    st.session_state['auth'], st.session_state['dept'] = True, sel_dept
                    delayed_refresh(f"Login Successful! Welcome {sel_dept}.")
                else: st.error("Invalid Credentials")
    else:
        st.subheader(f"Dashboard: {st.session_state['dept']}")
        if st.button("Logout"):
            st.session_state['auth'] = False
            st.rerun()
        
        c_tabs = st.tabs(["➕ Add New", "🗑️ Manage"])
        with c_tabs[0]:
            with st.form("sub_form", clear_on_submit=True):
                p_name, p_title = st.text_input("Presenter"), st.text_input("Title")
                p_desig = st.selectbox("Designation", ["Faculty", "Research Scholar", "Student"])
                p_abs = st.text_area("Abstract", max_chars=500)
                ca, cb, cc = st.columns(3)
                p_date, p_time, p_hall = ca.date_input("Date"), cb.text_input("Time"), cc.text_input("Hall")
                if st.form_submit_button("Submit Presentation"):
                    conn = sqlite3.connect('ssn_research.db')
                    d_id = conn.execute("SELECT id FROM departments WHERE name=?", (st.session_state['dept'],)).fetchone()[0]
                    conn.execute("INSERT INTO presentations (presenter, designation, title, abstract, date, time, venue_hall, dept_id) VALUES (?,?,?,?,?,?,?,?)",
                                 (p_name, p_desig, p_title, p_abs, str(p_date), p_time, p_hall, d_id))
                    conn.commit(); conn.close()
                    delayed_refresh("Presentation Recorded!")

        with c_tabs[1]:
            conn = sqlite3.connect('ssn_research.db')
            d_id = conn.execute("SELECT id FROM departments WHERE name=?", (st.session_state['dept'],)).fetchone()[0]
            my_pres = pd.read_sql_query(f"SELECT * FROM presentations WHERE dept_id = {d_id}", conn)
            conn.close()
            for _, row in my_pres.iterrows():
                col_x, col_y = st.columns([4, 1])
                col_x.write(f"**{row['date']}** - {row['title']}")
                if col_y.button("Delete", key=f"del_{row['id']}"):
                    conn = sqlite3.connect('ssn_research.db')
                    conn.execute("DELETE FROM presentations WHERE id=?", (row['id'],))
                    conn.commit(); conn.close()
                    delayed_refresh("Entry removed.", icon="🗑️")

# --- TAB 3: ADMIN CONTROL ---
with tabs[2]:
    if st.text_input("Admin Password", type="password", key="admin_pwd") == "admin123":
        adm_opt = st.radio("Admin Tool", ["Manage Depts", "Manage Subscribers", "Broadcast & PDF"], horizontal=True)
        
        if adm_opt == "Manage Depts":
            with st.form("add_d"):
                n, h, c, p = st.text_input("Dept Name"), st.text_input("HOD Email"), st.text_input("Coord Email"), st.text_input("Password")
                day = st.selectbox("Day", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
                if st.form_submit_button("Add Dept"):
                    conn = sqlite3.connect('ssn_research.db')
                    conn.execute("INSERT INTO departments (name, head_email, coord_email, preferred_day, password) VALUES (?,?,?,?,?)", (n, h, c, day, p))
                    conn.commit(); conn.close()
                    delayed_refresh(f"Dept {n} Added.")

        elif adm_opt == "Manage Subscribers":
            st.subheader("📢 Subscriber List")
            col_l, col_r = st.columns(2)
            with col_l:
                new_email = st.text_input("Email to Subscribe")
                if st.button("➕ Add"):
                    try:
                        conn = sqlite3.connect('ssn_research.db')
                        conn.execute("INSERT INTO subscriptions (email) VALUES (?)", (new_email,))
                        conn.commit(); conn.close()
                        delayed_refresh(f"Subscribed {new_email}")
                    except: st.error("Exists or Invalid")
            with col_r:
                conn = sqlite3.connect('ssn_research.db')
                subs = pd.read_sql_query("SELECT * FROM subscriptions", conn)
                conn.close()
                if not subs.empty:
                    to_del = st.selectbox("Remove Email", subs['email'].tolist())
                    if st.button("🗑️ Delete"):
                        conn = sqlite3.connect('ssn_research.db')
                        conn.execute("DELETE FROM subscriptions WHERE email=?", (to_del,))
                        conn.commit(); conn.close()
                        delayed_refresh(f"Removed {to_del}", icon="🗑️")

        elif adm_opt == "Broadcast & PDF":
            s_email, s_pass = st.text_input("Admin Gmail"), st.text_input("App Password", type="password")
            mode = st.selectbox("Broadcast Type", ["Tailored Message", "Future Schedule"])
            
            conn = sqlite3.connect('ssn_research.db')
            today = datetime.now().strftime('%Y-%m-%d')
            upcoming = pd.read_sql_query(f"SELECT p.*, d.name as Dept FROM presentations p JOIN departments d ON p.dept_id = d.id WHERE p.date >= '{today}' ORDER BY p.date ASC", conn)
            conn.close()

            if mode == "Future Schedule":
                b_subj = "SSN Brown Bag: Upcoming Research Schedule"
                if not upcoming.empty:
                    # UPDATED: DETAILED EMAIL BODY
                    b_body = "Dear SSN Community,\n\nHere are the complete details for the upcoming presentations:\n\n"
                    for _, r in upcoming.iterrows():
                        b_body += f"🗓️ DATE: {r['date']} | 🕒 TIME: {r['time']}\n"
                        b_body += f"🏫 DEPT: {r['Dept']} | 📍 VENUE: Hall {r['venue_hall']}\n"
                        b_body += f"👤 PRESENTER: {r['presenter']} ({r['designation']})\n"
                        b_body += f"📖 TOPIC: {r['title']}\n"
                        b_body += f"📝 ABSTRACT: {r['abstract']}\n"
                        b_body += "-"*45 + "\n\n"
                    
                    st.download_button("📥 Get PDF Copy", data=generate_pdf(upcoming), file_name="Schedule.pdf")
                else:
                    b_body = "No upcoming presentations found."
            else:
                b_subj, b_body = st.text_input("Subject"), st.text_area("Message")

            if st.button("🚀 Send Broadcast"):
                conn = sqlite3.connect('ssn_research.db')
                h_c = pd.read_sql_query("SELECT head_email, coord_email FROM departments", conn)
                subs = pd.read_sql_query("SELECT email FROM subscriptions", conn)
                recipients = list(set(h_c['head_email'].tolist() + h_c['coord_email'].tolist() + subs['email'].tolist()))
                conn.close()
                res = send_mail(b_subj, b_body, recipients, s_email, s_pass)
                if res == True: delayed_refresh("Broadcast Successfully Sent!")
                else: st.error(res)
