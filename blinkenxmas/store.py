import sys
import json
import sqlite3
from collections.abc import MutableMapping


class StoragePositions(MutableMapping):
    def __init__(self, connection):
        self._conn = connection

    def _create_tables(self):
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE positions (
                    led  INTEGER NOT NULL,
                    x    NUMBER NOT NULL,
                    y    NUMBER NOT NULL,
                    z    NUMBER NOT NULL,

                    CONSTRAINT presets_pk PRIMARY KEY (led),
                    CONSTRAINT coords_ck CHECK (
                        x BETWEEN 0 AND 1 AND
                        y BETWEEN 0 AND 1 AND
                        z BETWEEN 0 AND 1
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

    def __contains__(self, led):
        sql = "SELECT 1 FROM positions WHERE led = ?"
        for row in self._conn.execute(sql, (led,)):
            return True
        return False

    def __getitem__(self, led):
        sql = "SELECT x, y, z FROM positions WHERE led = ?"
        for row in self._conn.execute(sql, (led,)):
            return tuple(row)
        raise KeyError(led)

    def __setitem__(self, led, position):
        # TODO Assert that the structure is correct (voluptuous? Or just
        # decompose it into tables?)
        data = json.dumps(data)
        sql = (
            """
            INSERT INTO positions (led, x, y, z) VALUES (?, ?, ?, ?)
            ON CONFLICT (led) DO UPDATE SET x = ?, y = ?, z = ?
            """)
        x, y, z = position
        with self._conn:
            self._conn.execute(sql, (led, x, y, z, x, y, z))

    def __delitem__(self, led):
        sql = "DELETE FROM presets WHERE led = ?"
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
    schema_version = 2

    def __init__(self, db):
        self._conn = sqlite3.connect(db)
        self._conn.row_factory = sqlite3.Row
        self._presets = StoragePresets(self._conn)
        self._positions = StoragePositions(self._conn)
        self._create_tables()

    @property
    def presets(self):
        return self._presets

    @property
    def positions(self):
        return self._positions

    @staticmethod
    def log_message(msg):
        print(msg, file=sys.stderr)
        sys.stderr.flush()

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
