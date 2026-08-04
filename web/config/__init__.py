import pymysql

# Django's MySQL backend expects the mysqlclient driver. PyMySQL is a
# pure-Python alternative with the same DB-API interface, so this line
# makes Django use it as a drop-in replacement.
pymysql.install_as_MySQLdb()
