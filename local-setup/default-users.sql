INSERT INTO auth_user (password, last_login, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined)
VALUES
  ('pbkdf2_sha256$1200000$RpUpBM2CFuOESWbOkw6flR$QxCNrWgA99AulfZiELTfs0Awu4e9Hpt9RW15AvKHNds=', NULL, false, 'alice', 'Alice', 'Fernando', 'alice@example.com', false, true, NOW()),
  ('pbkdf2_sha256$1200000$RpUpBM2CFuOESWbOkw6flR$QxCNrWgA99AulfZiELTfs0Awu4e9Hpt9RW15AvKHNds=', NULL, false, 'bob', 'Bob', 'Perera', 'bob@example.com', false, true, NOW()),
  ('pbkdf2_sha256$1200000$RpUpBM2CFuOESWbOkw6flR$QxCNrWgA99AulfZiELTfs0Awu4e9Hpt9RW15AvKHNds=', NULL, false, 'carol', 'Carol', 'Silva', 'carol@example.com', false, true, NOW());
