# Use PyMySQL as fallback when mysqlclient isn't available (e.g., Railway)
try:
    import MySQLdb  # mysqlclient
except ImportError:
    import pymysql
    pymysql.install_as_MySQLdb()
