from setuptools import setup

setup(
    name='JSS Asset Hook',
    packages=['assethook'],
    include_package_data=True,
    # install_requires=[
    #     'flask','requests','flask_excel','gunicorn'
    # ],
    install_requires=[
        'requests','flask_excel','gunicorn'
    ],
)
