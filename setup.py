from setuptools import setup

setup(
    name='anpr-mssql-server',
    version='2.0.0',
    py_modules=[],
    install_requires=[
        'click',
        'docker',
        'toml'
    ],
    entry_points='''
        [console_scripts]
        server=server:anpr
    ''',
)
