#assethook - Import asset tags and names into your Jamf PRO Server!

## This is a flask application that listens for webhooks. It also contains a database so you can upload your asset tags and device names

#Quickstart 

```easy_install pip
pip install virtualenv
virtualenv assethook
cd assethook
source bin/activate
git clone https://github.com/bradschm/assethook
python setup.py install
gunicorn wsgi:app```
