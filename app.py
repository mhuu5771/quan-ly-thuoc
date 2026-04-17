from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import sqlite3
import pandas as pd
from datetime import datetime
import os
import sys

def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

app = Flask(__name__, template_folder=get_resource_path('templates'))
app.secret_key = "pharmacy_ultra_design_2026"

# Cấu hình đường dẫn DB an toàn cho Render
if os.environ.get('RENDER'):
    DB_PATH = os.path.join('/tmp', 'database.db')
else:
    DB_PATH = os.path.join(os.path.abspath(os.path.dirname(sys.argv[0])), 'database.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """ Đảm bảo các bảng luôn tồn tại trước khi dùng """
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        batch_code TEXT UNIQUE, 
        created_at DATETIME)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS returns (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        batch_id INTEGER, 
        medicine_name TEXT, 
        package_type TEXT, 
        quantity INTEGER, 
        reason TEXT, 
        FOREIGN KEY (batch_id) REFERENCES batches (id))''')
    conn.commit()
    conn.close()

@app.route('/', methods=['GET', 'POST', 'HEAD'])
def index():
    if request.method == 'HEAD':
        return '', 200
    
    # MẸO QUAN TRỌNG: Luôn gọi init_db() mỗi khi vào trang chủ 
    # để đảm bảo nếu DB bị xóa thì nó sẽ tự tạo lại bảng ngay lập tức.
    init_db() 
    
    conn = get_db_connection()
    batches = conn.execute('SELECT * FROM batches ORDER BY created_at DESC').fetchall()
    stats = conn.execute('''SELECT 
            SUM(CASE WHEN package_type = 'Hộp' THEN quantity ELSE 0 END) as total_hop,
            SUM(CASE WHEN package_type = 'Chai' THEN quantity ELSE 0 END) as total_chai,
            SUM(CASE WHEN package_type = 'Lọ' THEN quantity ELSE 0 END) as total_lo,
            SUM(CASE WHEN package_type = 'Bì' THEN quantity ELSE 0 END) as total_bi
        FROM returns''').fetchone()
    conn.close()
    return render_template('index.html', batches=batches, stats=stats)

@app.route('/create_batch', methods=['POST'])
def create_batch():
    batch_code = f"BATCH-{datetime.now().strftime('%d%m%y-%H%M%S')}"
    conn = get_db_connection()
    conn.execute('INSERT INTO batches (batch_code, created_at) VALUES (?, ?)',
                 (batch_code, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/batch/<int:id>')
def view_batch(id):
    conn = get_db_connection()
    batch = conn.execute('SELECT * FROM batches WHERE id = ?', (id,)).fetchone()
    items = conn.execute('SELECT * FROM returns WHERE batch_id = ? ORDER BY id DESC', (id,)).fetchall()
    conn.close()
    return render_template('batch_detail.html', batch=batch, items=items)

@app.route('/batch/<int:id>/add', methods=['POST'])
def add_item(id):
    conn = get_db_connection()
    conn.execute('INSERT INTO returns (batch_id, medicine_name, package_type, quantity, reason) VALUES (?, ?, ?, ?, ?)',
                 (id, request.form['medicine_name'], request.form['package_type'], request.form['quantity'], request.form['reason']))
    conn.commit()
    conn.close()
    return redirect(url_for('view_batch', id=id))

@app.route('/delete_item/<int:batch_id>/<int:item_id>')
def delete_item(batch_id, item_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM returns WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('view_batch', id=batch_id))

@app.route('/delete_batch/<int:id>')
def delete_batch(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM returns WHERE batch_id = ?', (id,))
    conn.execute('DELETE FROM batches WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/export/<int:id>')
def export_excel(id):
    conn = get_db_connection()
    batch = conn.execute('SELECT batch_code FROM batches WHERE id = ?', (id,)).fetchone()
    df = pd.read_sql_query("SELECT medicine_name as 'Tên Thuốc', package_type as 'Loại', quantity as 'Số Lượng', reason as 'Lý Do' FROM returns WHERE batch_id = ?", conn, params=(id,))
    conn.close()
    
    filename = f"Phieu_Tra_Hang_{batch['batch_code']}.xlsx"
    # Trên Render lưu vào /tmp, trên Mac lưu cạnh file chạy
    if os.environ.get('RENDER'):
        export_path = os.path.join('/tmp', filename)
    else:
        export_path = os.path.join(os.path.abspath(os.path.dirname(sys.argv[0])), filename)
        
    df.to_excel(export_path, index=False)
    return send_file(export_path, as_attachment=True)

if __name__ == '__main__':
    init_db()
    # Tự động chọn Port cho Render hoặc mặc định 5005 cho Mac
    port = int(os.environ.get("PORT", 5005))
    app.run(host='0.0.0.0', port=port, debug=False)