# assethook - Import asset tags and names into your Jamf PRO Server!

## This is my first web application - Feedback is much appreciated! More documentation and features to come! 

This is a flask application that listens for webhooks. It also contains a database so you can upload your asset tags and device names. When a device Enrolls or otherwise triggers a webhook, it can reach out to this application to see if there are any asset tags and names associated in the database with the serial number provided by the webook. 

# Quickstart - run in Terminal

```bash
git clone https://github.com/bradschm/assethook
easy_install pip or sudo apt-get install pip 
pip install virtualenv
virtualenv assethook
cd assethook
source bin/activate
python setup.py install
```

Secured with TLS:
```bash
gunicorn -w 4 wsgi:app --keyfile your.key --certfile your.crt
```

Not secured with TLS:
```bash
gunicorn -w 4 wsgi:app
```

Visit https://server:8000/ in a web browser and configure the settings, notice you can turn off the device naming by setting set_name to False. 

The username is admin and the password is default 
This is temporary for this release, I want to change this to use a more secure method of authentication. For now, you can change this password in assethook/assethook.py

You'll need to upload a csv file to get data into the local database. See the Upload option for the sample csv file.

Visit Help, so you can setup the API account and webhooks in your Jamf Pro Server. 

Finally, you'll probably want to setup a launch daemon or init service so this runs all the time.






