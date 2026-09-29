"""
Manajer Basis Data Multi-Engine Transportasi Nataru.
Mendukung:
1. MySQL XAMPP (Localhost:3306) via PyMySQL
2. MySQL CLI (mysql.exe) fallback
3. SQLite lokal terindeks (nataru_analytics.db)
"""

import os
import io
import sqlite3
import subprocess
import logging
from typing import Dict, Tuple, Any, Optional
import pandas as pd
import numpy as np

from ..config.settings import MYSQL_CONFIG, SQLITE_DB_PATH, BASE_DIR, find_mysql_cli

logger = logging.getLogger("NataruAnalytics")

try:
    import pymysql
    import pymysql.cursors
    import pymysql.constants.CLIENT
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False

class NataruDBManager:
    """
    Manajer database otomatis yang menghubungkan script ke:
    1. MySQL XAMPP (Localhost:3306, Database: database_nataru) via PyMySQL
    2. Fallback ke MySQL CLI (mysql.exe) jika dibutuhkan
    3. Fallback ke SQLite lokal jika MySQL sedang tidak aktif
    """

    def __init__(self, mysql_config: Dict[str, Any] = MYSQL_CONFIG, sqlite_path: str = SQLITE_DB_PATH, force_sqlite: bool = False):
        self.mysql_config = mysql_config
        self.sqlite_path = sqlite_path
        self.engine_type = "SQLITE"
        self.mysql_cli_path = find_mysql_cli()
        self.use_cli = False
        self.force_sqlite = force_sqlite
        if force_sqlite:
            self.engine_type = "SQLITE"
            logger.info(f"Mode dipaksa: Menggunakan local SQLite database: {self.sqlite_path}")
        else:
            self._detect_engine()

    def _detect_engine(self):
        """Mendeteksi koneksi database terbaik yang tersedia."""
        if PYMYSQL_AVAILABLE:
            try:
                # Cek koneksi server MySQL
                conn = pymysql.connect(
                    host=self.mysql_config["host"],
                    port=self.mysql_config["port"],
                    user=self.mysql_config["user"],
                    password=self.mysql_config["password"],
                    charset=self.mysql_config["charset"],
                    connect_timeout=3
                )
                with conn.cursor() as cur:
                    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{self.mysql_config['database']}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
                conn.select_db(self.mysql_config["database"])
                conn.close()
                self.engine_type = "MYSQL"
                logger.info(f"Koneksi berhasil ke MySQL XAMPP (Port {self.mysql_config['port']}, DB: {self.mysql_config['database']}) via PyMySQL.")
                return
            except Exception as e:
                logger.warning(f"Koneksi PyMySQL gagal: {e}. Menguji ketersediaan CLI...")

        if self.mysql_cli_path and os.path.exists(self.mysql_cli_path):
            try:
                cmd = [
                    self.mysql_cli_path,
                    f"-h{self.mysql_config['host']}",
                    f"-P{self.mysql_config['port']}",
                    f"-u{self.mysql_config['user']}",
                    "-e", f"CREATE DATABASE IF NOT EXISTS `{self.mysql_config['database']}`; STATUS;"
                ]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
                if res.returncode == 0:
                    self.engine_type = "MYSQL"
                    self.use_cli = True
                    logger.info(f"Koneksi berhasil ke MySQL XAMPP via CLI ({self.mysql_cli_path}).")
                    return
            except Exception as e:
                logger.warning(f"Koneksi MySQL CLI gagal: {e}")

        # Fallback ke SQLite lokal
        self.engine_type = "SQLITE"
        logger.info(f"Menggunakan local SQLite database: {self.sqlite_path}")

    def query(self, sql: str, params: Optional[Tuple] = None) -> pd.DataFrame:
        """Mengeksekusi kueri SELECT dan mengembalikan DataFrame pandas."""
        if self.engine_type == "MYSQL" and not self.use_cli and PYMYSQL_AVAILABLE:
            conn = None
            try:
                conn = pymysql.connect(
                    host=self.mysql_config["host"],
                    port=self.mysql_config["port"],
                    user=self.mysql_config["user"],
                    password=self.mysql_config["password"],
                    database=self.mysql_config["database"],
                    charset=self.mysql_config["charset"],
                    cursorclass=pymysql.cursors.DictCursor
                )
                with conn.cursor() as cur:
                    cur.execute(sql, params or ())
                    rows = cur.fetchall()
                    if not rows:
                        return pd.DataFrame()
                    return pd.DataFrame(rows)
            except Exception as e:
                logger.warning(f"Gagal query ke MySQL ({e}), fallback membaca dari SQLite lokal...")
                return self._query_sqlite(sql, params)
            finally:
                if conn:
                    conn.close()

        elif self.engine_type == "MYSQL" and self.use_cli:
            try:
                clean_sql = sql.replace('"', '\\"')
                cmd = [
                    self.mysql_cli_path,
                    f"-h{self.mysql_config['host']}",
                    f"-P{self.mysql_config['port']}",
                    f"-u{self.mysql_config['user']}",
                    self.mysql_config["database"],
                    "-e", clean_sql,
                    "--batch", "--raw"
                ]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
                if res.returncode == 0 and res.stdout.strip():
                    return pd.read_csv(io.StringIO(res.stdout), sep='\t')
                return pd.DataFrame()
            except Exception as e:
                logger.warning(f"Gagal query CLI MySQL: {e}. Fallback ke SQLite...")
                return self._query_sqlite(sql, params)

        return self._query_sqlite(sql, params)

    def _query_sqlite(self, sql: str, params: Optional[Tuple] = None) -> pd.DataFrame:
        conn = sqlite3.connect(self.sqlite_path)
        try:
            return pd.read_sql_query(sql, conn, params=params)
        finally:
            conn.close()

    def execute(self, sql: str, params: Optional[Tuple] = None):
        """Mengeksekusi perintah DDL/DML seperti INSERT, UPDATE, CREATE TABLE."""
        if self.engine_type == "MYSQL" and not self.use_cli and PYMYSQL_AVAILABLE:
            conn = None
            try:
                conn = pymysql.connect(
                    host=self.mysql_config["host"],
                    port=self.mysql_config["port"],
                    user=self.mysql_config["user"],
                    password=self.mysql_config["password"],
                    database=self.mysql_config["database"],
                    charset=self.mysql_config["charset"]
                )
                with conn.cursor() as cur:
                    cur.execute(sql, params or ())
                conn.commit()
            except Exception as e:
                logger.error(f"Error eksekusi MySQL: {e}")
                self._execute_sqlite(sql, params)
            finally:
                if conn:
                    conn.close()
        elif self.engine_type == "MYSQL" and self.use_cli:
            try:
                cmd = [
                    self.mysql_cli_path,
                    f"-h{self.mysql_config['host']}",
                    f"-P{self.mysql_config['port']}",
                    f"-u{self.mysql_config['user']}",
                    self.mysql_config["database"],
                    "-e", sql
                ]
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            except Exception as e:
                logger.error(f"Error eksekusi MySQL CLI: {e}")
                self._execute_sqlite(sql, params)
        else:
            self._execute_sqlite(sql, params)

    def _execute_sqlite(self, sql: str, params: Optional[Tuple] = None):
        conn = sqlite3.connect(self.sqlite_path)
        try:
            with conn:
                conn.execute(sql, params or ())
        finally:
            conn.close()

    def execute_script(self, script: str):
        """Mengeksekusi multi-statement SQL script (DDL, Views, Triggers)."""
        # Eksekusi di SQLite selalu
        try:
            conn = sqlite3.connect(self.sqlite_path)
            conn.executescript(script)
            conn.close()
        except Exception as e:
            logger.debug(f"SQLite script execute info: {e}")

        # Eksekusi di MySQL jika aktif
        if self.engine_type == "MYSQL":
            if self.use_cli and self.mysql_cli_path:
                try:
                    cmd = [
                        self.mysql_cli_path,
                        f"-h{self.mysql_config['host']}",
                        f"-P{self.mysql_config['port']}",
                        f"-u{self.mysql_config['user']}",
                        self.mysql_config["database"]
                    ]
                    subprocess.run(cmd, input=script, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                except Exception as e:
                    logger.debug(f"MySQL CLI executescript: {e}")
            elif PYMYSQL_AVAILABLE:
                try:
                    conn = pymysql.connect(
                        host=self.mysql_config["host"],
                        port=self.mysql_config["port"],
                        user=self.mysql_config["user"],
                        password=self.mysql_config["password"],
                        database=self.mysql_config["database"],
                        charset=self.mysql_config["charset"],
                        client_flag=pymysql.constants.CLIENT.MULTI_STATEMENTS
                    )
                    with conn.cursor() as cur:
                        cur.execute(script)
                    conn.commit()
                    conn.close()
                except Exception as e:
                    logger.debug(f"PyMySQL executescript: {e}")

    def save_dataframe(self, df: pd.DataFrame, table_name: str):
        """Menyimpan DataFrame ke tabel database SQL (baik SQLite maupun MySQL)."""
        if df.empty:
            return

        # 1. Simpan ke SQLite
        try:
            conn = sqlite3.connect(self.sqlite_path)
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            conn.close()
            logger.info(f"Tabel `{table_name}` ({len(df):,} baris) berhasil disimpan ke SQLite.")
        except Exception as e:
            logger.error(f"Gagal simpan `{table_name}` ke SQLite: {e}")

        # 2. Simpan ke MySQL jika aktif
        if self.engine_type == "MYSQL":
            self._save_to_mysql(df, table_name)

    def _save_to_mysql(self, df: pd.DataFrame, table_name: str):
        """Menyimpan DataFrame ke MySQL dengan pembuatan skema kolom otomatis."""
        if not PYMYSQL_AVAILABLE and not self.use_cli:
            return

        cols = []
        for col in df.columns:
            dtype = df[col].dtype
            if "int" in str(dtype):
                col_type = "BIGINT"
            elif "float" in str(dtype):
                col_type = "DOUBLE"
            elif "datetime" in str(dtype):
                col_type = "DATETIME"
            else:
                max_len = df[col].astype(str).str.len().max() if not df[col].empty else 255
                if max_len > 255:
                    col_type = "TEXT"
                else:
                    col_type = f"VARCHAR({max(int(max_len * 1.5), 64)})"
            cols.append(f"`{col}` {col_type}")

        try:
            conn = pymysql.connect(
                host=self.mysql_config["host"],
                port=self.mysql_config["port"],
                user=self.mysql_config["user"],
                password=self.mysql_config["password"],
                database=self.mysql_config["database"],
                charset=self.mysql_config["charset"]
            )
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS `{table_name}`;")
                create_sql = f"CREATE TABLE `{table_name}` ({', '.join(cols)});"
                cur.execute(create_sql)

                cols_placeholder = ", ".join([f"`{c}`" for c in df.columns])
                vals_placeholder = ", ".join(["%s"] * len(df.columns))
                insert_sql = f"INSERT INTO `{table_name}` ({cols_placeholder}) VALUES ({vals_placeholder})"

                chunk_size = 1000
                records = df.replace({np.nan: None}).to_numpy().tolist()
                for i in range(0, len(records), chunk_size):
                    chunk = records[i:i + chunk_size]
                    cur.executemany(insert_sql, chunk)

                conn.commit()
            conn.close()
            logger.info(f"Tabel `{table_name}` ({len(df):,} baris) berhasil disimpan ke MySQL.")
        except Exception as e:
            logger.warning(f"Gagal simpan `{table_name}` ke MySQL via PyMySQL: {e}. Menguji fallback CLI...")
            if self.mysql_cli_path:
                try:
                    temp_csv = os.path.join(BASE_DIR, f"_temp_{table_name}.csv")
                    df.to_csv(temp_csv, index=False)
                    load_sql = f"""
                    DROP TABLE IF EXISTS `{table_name}`;
                    CREATE TABLE `{table_name}` ({', '.join(cols)});
                    """
                    self.execute_script(load_sql)
                    if os.path.exists(temp_csv):
                        os.remove(temp_csv)
                except Exception as ex:
                    logger.warning(f"Gagal fallback CLI MySQL: {ex}")
