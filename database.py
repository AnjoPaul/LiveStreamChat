import sqlite3
def setup_db():
    conn = sqlite3.connect('streams.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS streams
                 (streamer TEXT, status TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS chat
                 (streamer_name TEXT, client_name TEXT, message TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS member
                 (name TEXT PRIMARY KEY, password TEXT)''')  # Added member table
    conn.commit()
    conn.close()