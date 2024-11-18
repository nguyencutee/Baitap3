from flask import Flask, request, jsonify, Response, render_template
from flask_cors import CORS
import psycopg2
import json
from psycopg2 import sql
from unidecode import unidecode
from collections import OrderedDict

app = Flask(__name__)
CORS(app)

DB_CONFIG = {
    'dbname': 'dbtest',
    'host': 'localhost',
    'port': '5432',
    'table_name': 'danhsach'
}

global_session = {
    'is_logged_in': False,
    'username': None,
    'password': None
}


def connect_db(username, password):
    try:
        conn = psycopg2.connect(
            dbname=DB_CONFIG['dbname'],
            user=username,
            password=password,
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port']
        )
        return conn
    except Exception as e:
        raise e


@app.route('/')
def login_page():
    return render_template('login.html')


@app.route('/connect', methods=['POST'])
def connect():
    if not request.is_json: 
        return jsonify({'error': 'Đầu vào không hợp lệ: Yêu cầu JSON'}), 400

    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Vui lòng cung cấp cả tên người dùng và mật khẩu.'}), 400

    try:
        conn = connect_db(username, password)
        conn.close()
        global_session['is_logged_in'] = True
        global_session['username'] = username
        global_session['password'] = password
        return jsonify({'message': 'Kết nối đến cơ sở dữ liệu thành công'}), 200
    except Exception as e:
        global_session['is_logged_in'] = False
        return jsonify({'error': 'Không thể kết nối đến cơ sở dữ liệu. Vui lòng kiểm tra tài khoản và mật khẩu.'}), 500


def connect_db_session():
    username = global_session.get('username')
    password = global_session.get('password')
    if not username or not password:
        raise Exception('Không có thông tin đăng nhập trong session.')
    return connect_db(username, password)


def check_connection():
    if not global_session['is_logged_in']:
        return jsonify({'error': 'Vui lòng kết nối với cơ sở dữ liệu trước.'}), 400
    try:
        conn = connect_db_session()
        conn.close()
        return None
    except Exception:
        return jsonify({'error': 'Kết nối cơ sở dữ liệu không thành công.'}), 500


@app.route('/load_data', methods=['GET'])
def load_data():
    check_response = check_connection()
    if check_response:
        return check_response

    mssv = request.args.get('mssv')
    try:
        conn = connect_db_session()
        cur = conn.cursor()

        if mssv:
            query = sql.SQL("SELECT * FROM {} WHERE mssv = %s").format(sql.Identifier(DB_CONFIG['table_name']))
            cur.execute(query, [mssv])
            row = cur.fetchone()
            if row:
                data = OrderedDict([
                    ("ID", row[0]),
                    ("Họ và tên", row[1]),
                    ("MSSV", row[2]),
                    ("Tình trạng", row[3]),
                    ("Email", row[4])
                ])
            else:
                data = {"message": "Không tìm thấy học sinh."}
        else:
            query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(DB_CONFIG['table_name']))
            cur.execute(query)
            rows = cur.fetchall()
            data = [
                OrderedDict([
                    ("ID", row[0]),
                    ("Họ và tên", row[1]),
                    ("MSSV", row[2]),
                    ("Tình trạng", row[3]),
                    ("Email", row[4])
                ])
                for row in rows
            ]
        conn.close()
        return Response(
            json.dumps(data, ensure_ascii=False),
            mimetype='application/json',
            status=200
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/insert', methods=['POST'])
def insert_data():
    if not request.is_json:
        return jsonify({'error': 'Đầu vào không hợp lệ: Yêu cầu JSON'}), 400

    try:
        data = request.json
        hoten = data['hoten']
        mssv = data['mssv']
        tinhtrang = data['tinhtrang']
        last_name = unidecode(hoten.split()[-1].lower())
        email = f"{last_name}.{mssv}@vanlanguni.vn"

        conn = connect_db_session()
        cur = conn.cursor()
        query = sql.SQL("INSERT INTO {} (hoten, mssv, tinhtrang, email) VALUES (%s, %s, %s, %s)").format(
            sql.Identifier(DB_CONFIG['table_name'])
        )
        cur.execute(query, (hoten, mssv, tinhtrang, email))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Thêm sinh viên thành công'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/delete', methods=['POST'])
def delete_data():
    check_response = check_connection()
    if check_response:
        return check_response

    if not request.is_json:
        return jsonify({'error': 'Đầu vào không hợp lệ: Yêu cầu JSON'}), 400

    mssv = request.json.get('mssv')
    try:
        conn = connect_db_session()
        cur = conn.cursor()
        if mssv:
            query = sql.SQL("DELETE FROM {} WHERE mssv = %s").format(sql.Identifier(DB_CONFIG['table_name']))
            cur.execute(query, (mssv,))
        else:
            query = sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY").format(sql.Identifier(DB_CONFIG['table_name']))
            cur.execute(query)
        conn.commit()
        conn.close()
        return jsonify({'message': 'Dữ liệu đã được xóa thành công'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/update', methods=['POST'])
def update_data():
    check_response = check_connection()
    if check_response:
        return check_response

    if not request.is_json:
        return jsonify({'error': 'Đầu vào không hợp lệ: Yêu cầu JSON'}), 400

    try:
        data = request.json
        id = data['id']
        mssv = data.get('mssv')
        hoten = data.get('hoten')
        tinhtrang = data.get('tinhtrang')

        if not all([id, mssv, hoten, tinhtrang]):
            return jsonify({'error': 'Thiếu dữ liệu cần thiết'}), 400

        last_name = unidecode(hoten.split()[-1].lower())
        email = f"{last_name}.{mssv}@vanlanguni.vn"

        conn = connect_db_session()
        cur = conn.cursor()

        query = sql.SQL("UPDATE {} SET hoten = %s, tinhtrang = %s, email = %s, mssv = %s WHERE id = %s").format(
            sql.Identifier(DB_CONFIG['table_name'])
        )
        cur.execute(query, (hoten, tinhtrang, email, mssv, id))
        conn.commit()

        if cur.rowcount == 0:
            return jsonify({'error': 'Không tìm thấy bản ghi với ID này'}), 404

        conn.close()
        return jsonify({'message': 'Học sinh đã được cập nhật thành công'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
