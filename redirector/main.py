# -*- encoding: utf-8 -*-

import argparse
import dataset
import logging
import os.path
import re
from operator import attrgetter
from collections import namedtuple
from xml.etree import ElementTree

class MagentoAccessor:
    """

    simple direct access to magento data and database

    """

    LOCAL_XML = "app/etc/local.xml"
    MEDIA_PRODUCT = "media/catalog/product"
    log = logging.getLogger("MagentoAccessor")

    STORE = 'core_store'
    SITE = 'core_website'
    GROUP = 'core_store_group'
    CONFIG_DATA = 'core_config_data'

    def __init__(self, magento_path):
        self.magento_path = magento_path

    def read(self):
        tree = ElementTree.parse(os.path.join(self.magento_path, self.LOCAL_XML))
        prefix = tree.find(".//db/table_prefix").text
        self.prefix = prefix if prefix else ""

        self.db_url = 'mysql+mysqlconnector://{username}:{password}@{hostname}/{database}'.format(
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

    def sites(self):
        return self.get(self.SITE).all()

    def stores(self):
        store = self.get(self.STORE)
        return store.find(store.table.columns.is_active == 1,
                          store.table.columns.code != 'admin')

    def is_default_store(self, store):
        data = self.get(self.GROUP).find_one(group_id=store['group_id'])
        return data['default_store_id'] == store['store_id']

    def config(self, store, path):
        result = self.get(self.CONFIG_DATA).find_one(scope_id=store['store_id'],
                                                     scope='stores',
                                                     path=path)
        if not result is None:
            return result
        result = self.get(self.CONFIG_DATA).find_one(scope_id=store['website_id'],
                                                     scope='websites',
                                                     path=path)
        if not result is None:
            return result
        return self.get(self.CONFIG_DATA).find_one(scope_id=0,
                                                   scope='default',
                                                   path=path)


StoreData = namedtuple('StoreDate', ['language', 'url', 'is_default', 'code'])

class RedirectorGenerator:
    """

    language redirector for nginx from magento

    """

    # case insensitive matching:
    rewrite_cond = '''  if ($first_language ~* '{language}') {{
     rewrite /.* {url} break;
  }}
'''
    language_head = '''# baseurl: {url}
location = / {{
  if ($http_cookie ~* "cookielaw") {{
    break;
  }}
  if ($http_user_agent ~* 'http|bot|crawl|spider|^$') {{
    break;
  }}
  if ($args != "") {{
    break;
  }}
  if ($http_referer ~* "{basename}") {{
    break;
  }}
  # accept-language: en,en-US;q=0.8,ja;q=0.6
  set $first_language $http_accept_language;
  if ($first_language ~* '^(.+?),') {{
    set $first_language $1;
  }}
'''
    language_tail = '''
  index index.html index.php;
  try_files $uri $uri/ @handler;
}
'''

    def __init__(self):
        parser = argparse.ArgumentParser(description='redirector')
        parser.add_argument('-v', '--verbose', action='store_true', default=False)
        parser.add_argument('-l', '--language', action='append',
                            help='two letter language followed by = and then by store code',
                            type=RedirectorGenerator.key_value, dest='language')
        parser.add_argument('-d', '--directory', required=True,
                            type=RedirectorGenerator.writeable_dir,
                            help='target directory for configuration files')
        parser.add_argument('-b', '--basename', required=True,
                            help='choose a common base name')
        parser.add_argument('-s', '--skip-site', action='append', default=[],
                            help='Skip a website by magento code')
        parser.add_argument('magento_path', metavar='MAGENTOPATH',
                            help='base path of magento')
        args = parser.parse_args()
        self.magento_path = args.magento_path
        self.languages = dict(args.language if args.language else [])
        self.target_directory = args.directory
        self.basename = args.basename
        self.sites_to_skip = args.skip_site
        logging.basicConfig(level=(logging.DEBUG if args.verbose else logging.INFO))

    @staticmethod
    def writeable_dir(dir):
        """
        writeable directory

        """

        if not os.path.exists(dir):
            raise ValueError('directory {0} must exists'.format(dir))
        if not os.path.isdir(dir):
            raise ValueError('path {} must be a directory'.format(dir))
        if not os.access(dir, os.W_OK):
            raise ValueError('directory {} must be writeable'.format(dir))
        return dir

    @staticmethod
    def key_value(item):
        """

        key = value

        """

        k, v = item.split('=')
        return (k, v)

    @staticmethod
    def to_language_code(lang):
        return lang.replace('_', '-').lower()

    def to_nginx(self, baseurl, values, languages):
        """
        single rule generator

        """
        from pprint import pprint
        # il corrispondete per url StoreData
        site_data = self.optimize([data for data in values if data.url == baseurl])[0]
        name = site_data.code
        with open(os.path.join(self.target_directory, name + '.conf'), 'w') as f:
            f.write(self.language_head.format(url=baseurl, basename=self.basename))
            for data in languages:
                # evitati gli stessi indirizzi ...
                # ... e anche la lingua corrispondente alla lingua-paese.
                if data.url != baseurl and \
                    not site_data.language.startswith(data.language):
                    f.write(self.rewrite_cond.format(language=self.to_language_code(data.language),
                                                     url=data.url))
            f.write(self.language_tail)

    @staticmethod
    def optimize(values):
        """

        simplify StoreDatas filtering duplicate language match (like it-IT and it)

        """
        return sorted((value for value in values
                      if not any(value != other and value.url == other.url and
                                 re.match(other.language, value.language, re.IGNORECASE)
                                 for other in values)),
                      key=attrgetter('language'), reverse=True)

    def generate(self):
        """
        snippets generator

        """

        mage = MagentoAccessor(self.magento_path)
        mapping = []
        by_url = {}
        for store in mage.stores():
            code = store['code']
            # skip website by magento code:
            if code in self.sites_to_skip:
                continue
            language = mage.config(store, 'general/locale/code')['value']
            url = mage.config(store, 'web/unsecure/base_url')['value']
            is_default = mage.is_default_store(store)
            data = StoreData(language=language, url=url, is_default=is_default,
                             code=code)
            mapping.append(data)
            try:
                by_url[url].append(code)
            except KeyError:
                by_url[url] = [code]

        by_lang = {}
        values = []
        for store in mapping:
            url = store.url
            if len(by_url[store.url]) > 1 and not store.is_default:
                # standard magento store redirect
                url += '?___store={code}'.format(code=store.code)
            languages = [store.language]
            if '_' in store.language:
                languages.append(store.language[:store.language.find('_')])
            for language in languages:
                # new storedata with modified language and url
                data = StoreData(language=language, url=url, code=store.code,
                                 is_default=store.is_default)
                values.append(data)
                fixed = self.languages.get(language)
                if not fixed is None:
                    if fixed == data.code:
                        by_lang[language] = data
                    else:
                        pass # skipped
                else:
                    if language in by_lang:
                        codes = [item.code for item in mapping if item.language.startswith(language)]
                        raise Exception('multiple language found use -l {lang}= with one of {codes}'.format(lang=language,
                                                                                                            codes=codes))
                    by_lang[language] = data
        # the order is need in order to match language correctly in nginx
        lang_values = self.optimize(by_lang.values())
        for url in by_url.keys():
            self.to_nginx(url, values, lang_values)

def cli():
    RedirectorGenerator().generate()
