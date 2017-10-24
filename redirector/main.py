# -*- encoding: utf-8 -*-

import logging
import argparse
import os.path
from xml.etree import ElementTree
import dataset


class MagentoAccessor:
    """

    accessor to magento data

    """

    LOCAL_XML = "app/etc/local.xml"
    MEDIA_PRODUCT = "media/catalog/product"
    log = logging.getLogger("MagentoAccessor")

    def __init__(self, magento_path):
        self.magento_path = magento_path

    def read(self):
        tree = ElementTree.parse(os.path.join(self.magento_path, self.LOCAL_XML))
        prefix = tree.find(".//db/table_prefix").text
        self.prefix = prefix if prefix else ""

        self.db_url = 'mysql://{username}:{password}@{hostname}/{database}'.format(
            username=tree.find(".//connection/username").text,
            password=tree.find(".//connection/password").text,
            database=tree.find(".//connection/dbname").text,
            hostname = tree.find(".//connection/host").text)

    @property
    def db(self):
        self.read()
        return dataset.connect(self.db_url)

    def get(self, tablename):
        return self.db[self.prefix + tablename]

class MageApp:

    STORE = 'core_store'
    CONFIG_DATA = 'core_config_data'

    def __init__(self):
        parser = argparse.ArgumentParser(description='redirector')
        parser.add_argument('-v', '--verbose', action='store_true', default=False)
        parser.add_argument('magento_path', metavar='MAGENTOPATH',
                            help='base path of magento')
        args = parser.parse_args()
        self.magento_path = args.magento_path
        logging.basicConfig(level=(logging.DEBUG if args.verbose else logging.INFO))

    def run(self):
        mage = MagentoAccessor(self.magento_path)
        for store in mage.get(self.STORE):
            print(store)
            data = mage.get(self.CONFIG_DATA).find_one(scope_id=store['store_id'],
                                                       scope='stores')
            print(data)



def cli():
    MageApp().run()
