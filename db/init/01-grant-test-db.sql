-- Django's test runner creates a throw-away database named test_<MYSQL_DATABASE>
-- to run the test suite against. The default user created by the mysql image
-- only has privileges on MYSQL_DATABASE, so this grants it privileges on the
-- matching test_ database too.
GRANT ALL PRIVILEGES ON `test_%`.* TO 'resolve_ai_user'@'%';
FLUSH PRIVILEGES;
