import json
import math as m
import sqlite3
import logging
from collections import namedtuple
from collections.abc import MutableMapping


class Position(namedtuple('Position', ('x', 'y', 'z', 'a', 'r'))):
    @classmethod
    def from_polar(cls, y, a, r):
        x = r * m.sin(m.radians(a))
        z = r * m.cos(m.radians(a))
        return Position(x, y, z, a, r)

    @classmethod
    def from_cartesian(cls, x, y, z):
        a = m.degrees(m.atan2(z, x) + m.pi)
        r = m.hypot(x, z)
        return Position(x, y, z, a, r)

    @property
    def a_r(self):
        return m.radians(self.a)


class StoragePositions(MutableMapping):
    def __init__(self, connection):
        self._conn = connection

    def _create_tables(self):
        with self._conn:
            self._conn.execute(
                "DROP TABLE IF EXISTS positions")
            self._conn.execute(
                """
                CREATE TABLE positions (
                    led  INTEGER NOT NULL,
                    y    NUMBER NOT NULL,
                    a    NUMBER NOT NULL,
                    r    NUMBER NOT NULL,

                    CONSTRAINT presets_pk PRIMARY KEY (led),
                    CONSTRAINT coords_ck CHECK (
                        y BETWEEN 0 AND 1 AND
                        a BETWEEN 0 AND 360 AND
                        r BETWEEN 0 AND 1
                    )
                )
                """)

    def __bool__(self):
        sql = "SELECT 1 FROM positions"
        for row in self._conn.execute(sql):
            return True
        return False

    def __len__(self):
        sql = "SELECT COUNT(*) FROM positions"
        for row in self._conn.execute(sql):
            return row[0]
        return 0

    def __iter__(self):
        sql = "SELECT led FROM positions ORDER BY led"
        for row in self._conn.execute(sql):
            yield row['led']

    def items(self):
        sql = "SELECT led, y, a, r FROM positions ORDER BY led"
        for row in self._conn.execute(sql):
            yield row['led'], Position.from_polar(row['y'], row['a'], row['r'])

    def __contains__(self, led):
        sql = "SELECT 1 FROM positions WHERE led = ?"
        for row in self._conn.execute(sql, (led,)):
            return True
        return False

    def __getitem__(self, led):
        sql = "SELECT y, a, r FROM positions WHERE led = ?"
        for row in self._conn.execute(sql, (led,)):
            return Position.from_polar(row['y'], row['a'], row['r'])
        raise KeyError(led)

    def __setitem__(self, led, position):
        if not isinstance(position, Position):
            position = Position.from_cartesian(*position)
        sql = (
            """
            INSERT INTO positions (led, y, a, r) VALUES (?, ?, ?, ?)
            ON CONFLICT (led) DO UPDATE SET y = ?, a = ?, r = ?
            """)
        with self._conn:
            self._conn.execute(sql, (
                led, position.y, position.a, position.r,
                position.y, position.a, position.r))

    def __delitem__(self, led):
        sql = "DELETE FROM positions WHERE led = ?"
        with self._conn:
            self._conn.execute(sql, (led,))


class StoragePresets(MutableMapping):
    def __init__(self, connection):
        self._conn = connection

    def _create_tables(self):
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE presets (
                    name VARCHAR(200) NOT NULL,
                    data TEXT NOT NULL,

                    CONSTRAINT presets_pk PRIMARY KEY (name),
                    CONSTRAINT presets_name_ck CHECK (name <> ''),
                    CONSTRAINT presets_data_ck CHECK (data <> '')
                )
                """)

    def __bool__(self):
        sql = "SELECT 1 FROM presets"
        for row in self._conn.execute(sql):
            return True
        return False

    def __len__(self):
        sql = "SELECT COUNT(*) FROM presets"
        for row in self._conn.execute(sql):
            return row[0]
        return 0

    def __iter__(self):
        sql = "SELECT name FROM presets ORDER BY name"
        for row in self._conn.execute(sql):
            yield row['name']

    def __contains__(self, preset):
        sql = "SELECT 1 FROM presets WHERE name = ?"
        for row in self._conn.execute(sql, (preset,)):
            return True
        return False

    def __getitem__(self, preset):
        sql = "SELECT data FROM presets WHERE name = ?"
        for row in self._conn.execute(sql, (preset,)):
            return json.loads(row['data'])
        raise KeyError(preset)

    def __setitem__(self, preset, data):
        # TODO Assert that the structure is correct (voluptuous? Or just
        # decompose it into tables?)
        data = json.dumps(data)
        sql = (
            """
            INSERT INTO presets (name, data) VALUES (?, ?)
            ON CONFLICT (name) DO UPDATE SET data = ?
            """)
        with self._conn:
            self._conn.execute(sql, (preset, data, data))

    def __delitem__(self, preset):
        sql = "DELETE FROM presets WHERE name = ?"
        with self._conn:
            self._conn.execute(sql, (preset,))


class Storage:
    schema_version = 3
    logger = logging.getLogger('storage')

    def __init__(self, db):
        if sqlite3.threadsafety < 1:
            raise RuntimeError(
                'sqlite3 must be compiled with at least basic multi-thread '
                'capabilities')
        self._conn = sqlite3.connect(db)
        self._conn.row_factory = sqlite3.Row
        self._presets = StoragePresets(self._conn)
        self._positions = StoragePositions(self._conn)
        self._create_tables()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if exc[0] is not None:
            self._conn.rollback()
        else:
            self._conn.commit()

    @property
    def presets(self):
        return self._presets

    @property
    def positions(self):
        return self._positions

    @classmethod
    def log_message(cls, msg):
        cls.logger.warning(msg)

    def _create_tables(self):
        try:
            with self._conn:
                for row in self._conn.execute("SELECT version FROM config"):
                    if row['version'] == Storage.schema_version:
                        return
                    elif row['version'] > Storage.schema_version:
                        raise RuntimeError(
                            f"Incompatible schema version {row['version']}; "
                            f"expected {self.schema_version}")
        except sqlite3.OperationalError:
            # Creation case
            Storage.log_message(
                f"Creating schema at version {Storage.schema_version}")
            with self._conn:
                self._conn.execute(
                    """
                    CREATE TABLE config (
                        version INT NOT NULL,

                        CONSTRAINT config_pk PRIMARY KEY (version),
                        CONSTRAINT config_ck CHECK (version >= 1)
                    )
                    """)
                self._conn.execute(
                    "INSERT INTO config(version) VALUES (?)",
                    (Storage.schema_version,))
                self._presets._create_tables()
                self._positions._create_tables()
            return
        else:
            # Upgrade case
            Storage.log_message(
                f"Upgrading storage from version {row['version']} to "
                f"{Storage.schema_version}")
            with self._conn:
                self._conn.execute(
                    "UPDATE config SET version = ?",
                    (Storage.schema_version,))
                self._positions._create_tables()
