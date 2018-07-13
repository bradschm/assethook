"""Assethook: A flask application to listen for webhook calls to send
computer names and asset tags to the Jamf Pro Server.
"""

import logging
from logging.handlers import RotatingFileHandler

import os
import sqlite3
import time

import requests
from flask import (Flask, flash, g, redirect, render_template,
                   request, session, url_for)

# Next steps
# Implement username/password management like Flask-User
# Auto create the webhook in the jss
# CSV Handling for field mapping
# Don't allow duplicate entries, or ask to overwrite
# Delete all
# Edit row, reuse add, fill form, then update with new values
# Search for records
# Sort table (javascript?)
# Submit all without timestamp?

app = Flask(__name__)  # create the application instance :)
app.config.from_object(__name__)  # load config from this file

# Load default config and override config from an environment variable
app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'assethook.db'),
    SECRET_KEY='development key',
    USERNAME='admin',
    PASSWORD='default',
    DEBUG=False,

))
app.config.from_envvar('FLASKR_SETTINGS', silent=True)

# Logging
handler = RotatingFileHandler('assethook.log', maxBytes=10000, backupCount=1)
handler.setLevel(logging.INFO)
app.logger.setLevel(logging.INFO)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
app.logger.addHandler(handler)


# Database methods


def connect_db():
    """Connects to the specific database.
    """
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv


def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db


def init_db():
    """Initialized the db file"""
    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()


@app.cli.command('initdb')  # if you want to do it from the command line
def initdb_command():
    """Initializes the database."""
    init_db()
    print('Initialized the database.')


def load_settings():
    '''Loads settings from the database, if the table is empty, it will be initalized
        '''
    db = get_db()
    try:
        cur = db.execute('select setting_name, setting_value from settings')
        settings = cur.fetchall()
    except sqlite3.OperationalError:
        init_db()
        return redirect(url_for('landing'))

    if not settings:
        init_settings()
        cur = db.execute('select setting_name, setting_value from settings')
        settings = cur.fetchall()
    g.settings = settings
    return


def init_settings():
    '''Initialize the settings table'''
    db = get_db()
    v = [('jsshost', ''), ('jss_path', ''), ('jss_port', ''),
         ('jss_username', ''), ('jss_password', ''), ('set_name', '')]
    db.executemany(
        """insert into settings ('setting_name', 'setting_value') values (?,?)""", v)
    db.commit()


def write_settings(_request):
    '''Write settings to the database'''
    db = get_db()
    # Add https if not given
    if 'http' not in _request.form['jsshost']:
        jsshost = 'https://%s' % _request.form['jsshost']
    else:
        jsshost = _request.form['jsshost']
    v = [(jsshost, 'jsshost'),
         (_request.form['jss_path'], 'jss_path',),
         (_request.form['jss_port'], 'jss_port'),
         (_request.form['jss_username'], 'jss_username'),
         (_request.form['jss_password'], 'jss_password'),
         (_request.form['set_name'], 'set_name')]
    db.executemany(
        """update settings set setting_value = ? where setting_name = ?""", v)
    db.commit()

# App routes


@app.route("/log")
def logTest():
    app.logger.warning('testing warning log')
    app.logger.error('testing error log')
    app.logger.info('testing info log')
    return "Code Handbook !! Log testing."


@app.route('/')
def landing():
    '''Check to see if JSS Settings, database, etc are stored in the DB'''
    load_settings()
    for i in g.settings:
        if i[0] == 'jss_username':
            if i[1] == '':
                flash('Please enter the required information')
                session['logged_in'] = True
                return redirect(url_for('settings_page'))
    return redirect(url_for('get_devices'))


@app.route('/settings', methods=['GET', 'POST'])
def settings_page():
    '''Displays settings and allows them to be modified'''
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'GET':
        load_settings()
        return render_template('settings.html', rows=g.settings)

    if request.method == 'POST':
        write_settings(request)
        flash('Settings saved')
        return redirect(url_for('get_devices'))

    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    '''Login page for now'''
    error = None
    if request.method == 'POST':
        if request.form['username'] != app.config['USERNAME']:
            error = 'Invalid username'
        elif request.form['password'] != app.config['PASSWORD']:
            error = 'Invalid password'
        else:
            session['logged_in'] = True
            flash('You were logged in')
            return redirect(url_for('get_devices'))
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    """Logs out current user"""
    session.pop('logged_in', None)
    flash('You were logged out')
    return redirect(url_for('get_devices'))


@app.route('/devices', methods=['GET'])
def get_devices(error=None):
    '''Shows all devices in the database'''
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    db = get_db()
    cur = db.execute(
        'select id, asset_tag, serial_number, device_name, dt_sub_to_jss from devices order by id desc')
    devices = cur.fetchall()
    return render_template('assets.html', rows=devices, error=error)


@app.route('/submit_inventory')
def submit_to_jss(serial_number=None, device_type=None):
    '''If this is called from a webhook, the serial_number and type are set when called
        If not, it is being called manually from the devices page and type will be
        determined by trying the JSS with GET
    '''
    load_settings()
    settings_dict = dict((x, y) for x, y in g.settings)
    if serial_number is None:
        serial_number = request.args.get('serial_number')
    if serial_number is None:
        flash('Serial Number not passed')
        return redirect(url_for('get_devices'))
    db = get_db()
    cur = db.execute(
        'select asset_tag, device_name from devices where serial_number = \'%s\'' % serial_number)
    device_info = cur.fetchone()

    if device_info is None:
        return 400

    if device_type == 'Computer':
        device_type_xml = 'computer'
        device_type_url = 'computers'

    if device_type == 'MobileDevice':
        device_type_xml = 'mobile_device'
        device_type_url = 'mobiledevices'

    if device_type is None:
        url = settings_dict['jsshost'] + ':' + settings_dict['jss_port'] + settings_dict['jss_path'] + \
            '/JSSResource/mobiledevices/serialnumber/' + serial_number
        r = requests.get(url,
                         auth=(settings_dict['jss_username'],
                               settings_dict['jss_password']))
        if r.status_code == 200:
            device_type_xml = 'mobile_device'
            device_type_url = 'mobiledevices'
            device_type = 'MobileDevice'

    if device_type is None:
        url = settings_dict['jsshost'] + ':' + settings_dict['jss_port'] + settings_dict['jss_path'] + \
            '/JSSResource/computers/serialnumber/' + serial_number
        r = requests.get(url,
                         auth=(settings_dict['jss_username'],
                               settings_dict['jss_password']))
        if r.status_code == 200:
            device_type_xml = 'computer'
            device_type_url = 'computers'
            device_type = 'Computer'

    if device_type is None:
        flash('Could not determine device type')
        app.logger.warning('Could not determine device type')
        return redirect(url_for('get_devices'))
    # Check to see if there is a device name and if the device name setting is True
    if settings_dict['set_name'] == 'True' and device_info['device_name'] != '':
        body = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"no\"?>" \
            "<%s><general><name>%s</name><asset_tag>%s</asset_tag></general>" \
            "</%s>" % (device_type_xml,
                       device_info['device_name'], device_info['asset_tag'], device_type_xml)
    else:
        body = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"no\"?>" \
            "<%s><general><asset_tag>%s</asset_tag></general>" \
            "</%s>" % (device_type_xml,
                       device_info['asset_tag'], device_type_xml)

    try:
        r = requests.put(settings_dict['jsshost'] + ':' + settings_dict['jss_port'] + settings_dict['jss_path'] +
                         '/JSSResource/%s/serialnumber/' % device_type_url + serial_number,
                         auth=(settings_dict['jss_username'], settings_dict['jss_password']), data=body)
        if r.status_code == 409:
            # A 409 error can indicate that the device record has no name. This happens when the webhook is issued
            # and this program submits only an asset tag. The JSS responds that a name is reqiured. Delaying
            # and trying again seems to work fine.
            time.sleep(10)
            url = settings_dict['jsshost'] + ':' + settings_dict['jss_port'] + settings_dict['jss_path'] + \
                '/JSSResource/%s/serialnumber/' % device_type_url + serial_number
            r = requests.put(url,
                             auth=(settings_dict['jss_username'],
                                   settings_dict['jss_password']),
                             data=body)

    except requests.exceptions.RequestException as e:
        app.logger.error('Error submitting to JSS - %s' % e)
        error = 'Command failed - Please see the logs for more information...'
        return render_template('base.html', error=error)

    db = get_db()
    cur = db.execute(
        'update devices set dt_sub_to_jss = CURRENT_TIMESTAMP where serial_number = ?', [serial_number])

    db.commit()
    if r.status_code == 201:
        flash('{} Updated'.format(type))
        return redirect(url_for('get_devices'))

    
    flash('Connection made but device not updated. %s' % r.status_code)
    return redirect(url_for('get_devices'))


@app.route('/submit_all', methods=['GET'])
def submit_all_devices(error=None):
    '''Submit inventory for all devices in the database'''
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    db = get_db()
    cur = db.execute(
        'select id, asset_tag, serial_number, device_name, dt_sub_to_jss from devices order by id desc')
    devices = cur.fetchall()
    for device in devices:
        print(device['serial_number'])
        submit_to_jss(serial_number=device['serial_number'])
    return redirect(url_for('get_devices'))

@app.route('/webhook', methods=['POST'])
def mobile_device_enrolled():
    ''' This is what the webhook will call'''
    device = request.get_json()
    print(device)
    if not device:
        return '', 400

    if device['webhook']['webhookEvent'].startswith('Computer'):
        device_type = 'Computer'

    elif device['webhook']['webhookEvent'].startswith('Mobile'):
        device_type = 'MobileDevice'

    else:
        return 'Invalid Webhook format', 403
    submit_to_jss(serial_number=device['event'][u'serialNumber'], device_type=device_type)
    return '', 200


@app.route('/upload_file', methods=['GET', 'POST'])
def upload_file():
    '''Upload a csv file and import into the database'''
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        f = request.files['file']
        if f.filename == '':
            flash('No selected file')
            return redirect(request.url)
        db = get_db()
        raw_file = f.read()
        contents = iter(raw_file.split('\r\n'))
        next(contents)  # Skips the header
        for x in contents:
            if x.count(',') > 1:
                # Pulls out form feeds, I'm importing from a very old Filemaker DB so this helps clean it up
                c = x.replace('\x0b', '')

                # Pulls out spaces, If you have unneeded dashes you can add this: .replace('-','')
                asset_tag = c.split(',')[1].replace(' ', '')
                # Pulls out spaces, shouldn't be any there
                serial_number = c.split(',')[0].replace(' ', '')
                device_name = c.split(',')[2]

                db.execute('insert into devices (asset_tag, serial_number, device_name) values (?, ?, ?)',
                        [asset_tag, serial_number, device_name])
        db.commit()
        flash('Imported %s devices from: %s' %
              (len(raw_file.split('\r\n')) - 1, request.files['file'].filename))
        return redirect(url_for('get_devices'))
    return render_template('upload.html')


# Move to post in the future?
@app.route('/delete_device', methods=['POST', 'GET'])
def delete_device():
    '''Deletes a device passed as an arg'''
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    device_id = request.args.get('id')
    db = get_db()
    db.execute('delete from devices where id = %s' % device_id)
    db.commit()
    flash('{} Deleted from the local database.'.format(
        request.args.get('serial_number')))
    return redirect(url_for('get_devices'))


# Move to post in the future?
@app.route('/add_device', methods=['POST', 'GET'])
def add_device():
    '''Add a single device'''
    #device_id = request.args.get('id')
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if request.method == 'POST':
        db = get_db()
        db.execute('insert into devices (asset_tag, serial_number, device_name) values (?, ?, ?)',
                   [request.form['asset_tag'], request.form['serial_number'], request.form['device_name']])
        db.commit()
        flash('Device Added')
        return redirect(url_for('get_devices'))

    return render_template('add_device.html')


@app.route('/help')
def documentation():
    """Returns page for documentation"""
    return render_template('help.html')
