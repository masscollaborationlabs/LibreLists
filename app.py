import os, shutil, sqlite3, json
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_cors import CORS, cross_origin
from werkzeug.exceptions import abort


app = Flask(__name__)
CORS(app)
PROJECT_DIR = "projects"
CONFIG_DIR = "config"
CONFIG_FILE = "config.json"
ADDONS_FILE = "addons.json"
TABLE_CONFIG_FILE = "tables.json"
INFO_FILE = "info.json"
TABLE_DEFAULT_CONFIG = {"id_col": "id"}
VERSION = "0.1.0"

# FUNCTIONS

def updateAddons():
    with open(f"{CONFIG_DIR}/{ADDONS_FILE}") as f:
        return json.load(f)

def get_db_connection(id):
    conn = sqlite3.connect(f'{PROJECT_DIR}/{id}/{id}.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_item(id, table, item_id):
    conn = get_db_connection(id)
    item = conn.execute(f'SELECT * FROM {table} WHERE id = ?',
                        (item_id,)).fetchone()
    conn.close()
    if item is None:
        abort(404)
    return item

def get_columns_names(id, table):
    conn = get_db_connection(id)
    cursor = conn.execute(f'SELECT * FROM {table}')
    columnNames = list(map(lambda x: x[0], cursor.description))
    conn.close()
    return columnNames

def get_columns_types(id, table):
    conn = get_db_connection(id)
    columnsQuery = conn.execute(f"pragma table_info('{table}')")
    columnInfos = columnsQuery.fetchall()
    columnTypes = [item[2] for item in columnInfos]
    conn.close()
    return columnTypes

# ROUTES

@app.route('/')
def openfile():
    if not os.path.exists(PROJECT_DIR):
        os.makedirs(PROJECT_DIR)
    databases = os.listdir(PROJECT_DIR)
    return render_template("index.html", databases=databases, ver=VERSION, addons=updateAddons())

@app.route('/edit/<id>')
def edit(id):
    return render_template("edit.html", id=id, ver=VERSION, addons=updateAddons())

@app.route('/remove/<id>')
def remove(id):
    shutil.rmtree(f'{PROJECT_DIR}/{id}')
    return redirect("/", code=302)

@app.route('/create/<id>')
def create(id):
    if not os.path.exists(f"{PROJECT_DIR}/{id}"):
        os.makedirs(f"{PROJECT_DIR}/{id}")
        shutil.copyfile(f"{CONFIG_DIR}/{INFO_FILE}", f"{PROJECT_DIR}/{id}/{INFO_FILE}")
        shutil.copyfile(f"{CONFIG_DIR}/{TABLE_CONFIG_FILE}", f"{PROJECT_DIR}/{id}/{TABLE_CONFIG_FILE}")
    return redirect("/", code=302)

@app.route('/exec/<id>', methods=('GET', 'POST'))
def database_exec(id):
    try: 
        conn = get_db_connection(id)
        if request.method == 'POST':
            jsonRequest = request.get_json()
            sql_query = f"""{jsonRequest['query']}"""
            conn.executescript(sql_query)
            conn.commit()
        conn.close()
        return jsonify({"response": "OK"})
    except sqlite3.Error as error:
        return jsonify({"response": "Error", "why": ' '.join(error.args)})

@app.route('/json/database/<id>', methods=('GET', 'POST'))
def jsonDatabase(id):
    data = {"metadata" : {}, "tables": []}

    with open(f"{PROJECT_DIR}/{id}/{INFO_FILE}") as f:
        info = json.load(f)
    
    for infoName in info:
        data["metadata"].update({infoName : info[infoName]})

    conn = get_db_connection(id)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    for table in cursor.fetchall():
        if table[0] not in data["metadata"]["hidden_tables"]:
            data["tables"].append(table[0])

    return jsonify(data)

@app.route('/json/table/<id>/<table>', methods=('GET', 'POST'))
def jsonTable(id, table):
    data = {"columns_names" : [], "columns_types" : {}, "table_config": {}, "items" : []}
    try:
        filters = request.args.get('f', type = str)
        conn = get_db_connection(id)
        rows = conn.execute(f'SELECT * FROM {table} {filters}').fetchall()
        conn.close()

        with open(f"{PROJECT_DIR}/{id}/{TABLE_CONFIG_FILE}") as f:
            configs = json.load(f)

        try: 
            for config in configs[table]:
                data["table_config"].update({config : configs[table][config]})
        except:
            data["table_config"].update(TABLE_DEFAULT_CONFIG)

        for column in get_columns_names(id, table):
            data["columns_names"].append(column)

        for x in range(len(get_columns_types(id, table))):
            item = {get_columns_names(id, table)[x] : get_columns_types(id, table)[x]}
            data["columns_types"].update(item) 

        for row in rows:
            item = {"id" : row["id"]}
            for column in row.keys():
                item[column] = row[column]
            data["items"].append(item)
        return jsonify(data)
    except sqlite3.Error as error:
        return jsonify(data)

@app.route('/json/config', methods=('GET', 'POST'))
def jsonConfig():
    with open(f"{CONFIG_DIR}/{CONFIG_FILE}") as f:
        return jsonify(json.load(f))

@app.route('/update', methods=['POST'])
def update():
    jsonRequest = request.get_json()
    if jsonRequest["context"] == "DB_METADATA":
        with open(f"{PROJECT_DIR}/{jsonRequest['database']}/{INFO_FILE}", "r+") as f:
            data = json.load(f)
            for config in jsonRequest["data"]:
                data[config] = jsonRequest["data"][config]
            f.seek(0)
            json.dump(data, f)
            f.truncate()
    elif jsonRequest["context"] == "LL_CONFIG":
        with open(f"{CONFIG_DIR}/{CONFIG_FILE}", "r+") as f:
            data = json.load(f)
            for config in jsonRequest["data"]:
                data[config] = jsonRequest["data"][config]
            f.seek(0)
            json.dump(data, f)
            f.truncate()
    return {"response": "OK"}