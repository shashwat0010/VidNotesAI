import os
import sqlite3

for p in ['backend/vidnotes.db', 'vidnotes.db']:
    if os.path.exists(p):
        conn = sqlite3.connect(p)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cursor.fetchall()]
        print(f"{p} tables: {tables}")
        if 'keyframes' in tables:
            cursor.execute("SELECT id, s3_url FROM keyframes")
            rows = cursor.fetchall()
            for kf_id, s3_url in rows:
                if s3_url and ('/uploads/' in s3_url or '/vidnotes-storage/' in s3_url):
                    clean = s3_url.replace('/uploads/', '').replace('/vidnotes-storage/', '').lstrip('/')
                    new_url = f"https://vid-notes-storage.s3.us-east-1.amazonaws.com/{clean}"
                    cursor.execute("UPDATE keyframes SET s3_url = ? WHERE id = ?", (new_url, kf_id))
            conn.commit()
            print(f"Successfully updated keyframe URLs to AWS S3 in {p}")
        conn.close()
