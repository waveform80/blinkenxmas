import json
import sqlite3
from collections.abc import MutableMapping


class Storage(MutableMapping):
    schema_version = 1

    def __init__(self, db):
        self._conn = sqlite3.connect(db)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        try:
            with self._conn:
                for row in self._conn.execute("SELECT version FROM config"):
                    if row['version'] == self.schema_version:
                        return
                    else:
                        raise RuntimeError(
                            f'Incompatible schema version {row.version}; '
                            f'expected {self.schema_version}')
        except sqlite3.OperationalError:
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
                    """
                    INSERT INTO config(version) VALUES (?)
                    """, (self.schema_version,))
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
