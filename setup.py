from setuptools import setup, find_packages

__author__ = 'Marco Andreini'
__version__ = '0.1.0'
__contact__ = 'marco.andreini@gmail.com'
__url__ = 'TODO'
__license__ = 'GPLv3'


setup(
    name="language-redirector",
    version=__version__,
    author=__author__,
    author_email=__contact__,
    url=__url__,
    license=__license__,
    packages=find_packages(),
    entry_points='''
        [console_scripts]
        language-redirector=redirector.main:cli
    ''',
    include_package_data=True,
    description="Magento language redirector for NGINX.",
    long_description=open("README.txt").read(),
    install_requires=[
        "dataset"
    ]
)
