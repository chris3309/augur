#SPDX-License-Identifier: MIT
"""
Handles global context, I/O, and configuration
"""

import os
from pathlib import Path
import logging
from logging import FileHandler, Formatter
import coloredlogs
import json
from beaker.cache import CacheManager
from beaker.util import parse_cache_config_options
import sqlalchemy as s

from augur.metrics import Metrics
from augur.config import AugurConfig
import augur.logging

ROOT_AUGUR_DIRECTORY = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

logger = logging.getLogger("augur")

class Application():
    """Initalizes all classes from Augur using a config file or environment variables"""

    def __init__(self):
        """
        Reads config, creates DB session, and initializes cache
        """
        self.root_augur_dir = ROOT_AUGUR_DIRECTORY
        self.config = AugurConfig(self.root_augur_dir)

        augur.logging.initialize_logging(ROOT_AUGUR_DIRECTORY, self.config.get_section("Development"), [job["model"] for job in self.config.get_value("Housekeeper", "jobs")])

        self.logger = logger

        self.cache_config = {
            'cache.type': 'file',
            'cache.data_dir': 'runtime/cache/',
            'cache.lock_dir': 'runtime/cache/'
        }

        if not os.path.exists(self.cache_config['cache.data_dir']):
            os.makedirs(self.cache_config['cache.data_dir'])
        if not os.path.exists(self.cache_config['cache.lock_dir']):
            os.makedirs(self.cache_config['cache.lock_dir'])
        cache_parsed = parse_cache_config_options(self.cache_config)
        self.cache = CacheManager(**cache_parsed)

        self.database = self._connect_to_database()
        self.spdx_db = self._connect_to_database(include_spdx=True)

        self.metrics = Metrics(self)

    def _connect_to_database(self, include_spdx=False):
        user = self.config.get_value('Database', 'user')
        host = self.config.get_value('Database', 'host')
        port = self.config.get_value('Database', 'port')
        dbname = self.config.get_value('Database', 'name')

        database_connection_string = 'postgresql://{}:{}@{}:{}/{}'.format(
            user, self.config.get_value('Database', 'password'), host, port, dbname
        )

        csearch_path_options = 'augur_data'
        if include_spdx == True:
            csearch_path_options += ',spdx'

        engine = s.create_engine(database_connection_string, poolclass=s.pool.NullPool,
            connect_args={'options': f'-csearch_path={csearch_path_options}'}, pool_pre_ping=True)

        try:
            test_connection = engine.connect()
            test_connection.close()
            return engine
        except s.exc.OperationalError as e:
            logger.fatal(f"Unable to connect to the database. Terminating...")
            raise(e)

