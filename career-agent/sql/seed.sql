USE career_agent;

-- 本文件提供 MySQL 手动导入版基础演示账号与企业端数据。
-- 若希望获得完整的岗位、画像、匹配、成长、报告与投递演示链路，
-- 推荐优先启动后端自动播种，或执行 backend/scripts/seed_demo.py。

INSERT INTO roles (id, name, code, description, deleted) VALUES
  (1, '管理员', 'admin', '系统管理员', 0),
  (2, '企业', 'enterprise', '企业招聘方用户', 0),
  (3, '学生', 'student', '学生用户', 0)
ON DUPLICATE KEY UPDATE
  name = VALUES(name),
  description = VALUES(description),
  deleted = VALUES(deleted);

INSERT INTO departments (id, name, description, deleted) VALUES
  (1, '计算机学院', '信息类专业', 0),
  (2, '经济管理学院', '管理与营销类专业', 0)
ON DUPLICATE KEY UPDATE
  description = VALUES(description),
  deleted = VALUES(deleted);

INSERT INTO classes (id, name, grade, department_id, deleted) VALUES
  (1, '软件工程 2201 班', '2022', 1, 0),
  (2, '市场营销 2201 班', '2022', 2, 0)
ON DUPLICATE KEY UPDATE
  grade = VALUES(grade),
  department_id = VALUES(department_id),
  deleted = VALUES(deleted);

INSERT INTO users (id, username, password_hash, real_name, email, is_active, role_id, department_id, class_id, deleted) VALUES
  (1, 'admin', '$pbkdf2-sha256$29000$lNIaQwiB8N6b0/ofAyAkhA$NHg3X0QyL0itkB8LeDL/Nv2X5eMaWUbUFoV824Eyxs4', '系统管理员', 'admin@example.com', 1, 1, 1, NULL, 0),
  (2, 'enterprise01', '$pbkdf2-sha256$29000$llJKCcFYS2kNwZjzPmfM2Q$bR.bziAwxOWgRU.U6O01Wt99c30Kk9caFXUJ1fSIK1I', '星联科技', 'enterprise01@example.com', 1, 2, NULL, NULL, 0),
  (4, 'student01', '$pbkdf2-sha256$29000$hPB.r9Xa2/v//x9jDKGUEg$32e5sFMveNLi3SouLSiB2XdKMkyOXWfHLwqDdYL1bQU', '张晨', 'student01@example.com', 1, 3, 1, 1, 0)
ON DUPLICATE KEY UPDATE
  password_hash = VALUES(password_hash),
  real_name = VALUES(real_name),
  email = VALUES(email),
  is_active = VALUES(is_active),
  role_id = VALUES(role_id),
  department_id = VALUES(department_id),
  class_id = VALUES(class_id),
  deleted = VALUES(deleted);

INSERT INTO enterprise_profiles (id, user_id, company_name, company_code, industry, address, company_type, company_size, description, source_doc_ids, deleted) VALUES
  (1, 2, '星联科技有限公司', 'ENT-001', '互联网', '上海市浦东新区张江高科技园区', '成长型企业', '100-499人', '聚焦企业数字化产品与校园招聘合作，长期招聘前端、Java、测试与产品方向候选人。', JSON_ARRAY(), 0)
ON DUPLICATE KEY UPDATE
  user_id = VALUES(user_id),
  company_code = VALUES(company_code),
  industry = VALUES(industry),
  address = VALUES(address),
  company_type = VALUES(company_type),
  company_size = VALUES(company_size),
  description = VALUES(description),
  source_doc_ids = VALUES(source_doc_ids),
  deleted = VALUES(deleted);

INSERT INTO system_configs (`key`, `value`, config_type, description, deleted) VALUES
  ('job_tags_catalog', '["Java","Python","SQL","Vue 3","产品","运营","设计","测试"]', 'json', '岗位标签目录', 0),
  ('model_provider', 'mock', 'text', '默认模型提供方', 0),
  ('match_top_n', '5', 'text', '默认推荐岗位数量', 0)
ON DUPLICATE KEY UPDATE
  `value` = VALUES(`value`),
  config_type = VALUES(config_type),
  description = VALUES(description),
  deleted = VALUES(deleted);
