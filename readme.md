easy_install pip
pip install virtualenv
virtualenv assethook
cd assethook
source bin/activate
git clone https://github.com/bradschm/assethook
python setup.py install
gunicorn wsgi:app
