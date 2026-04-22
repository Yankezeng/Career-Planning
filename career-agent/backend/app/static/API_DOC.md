# API 文档说明

## 在线文档

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## 认证接口

- `POST /api/auth/login`
- `POST /api/auth/register`
- `GET /api/auth/me`

## 岗位模块

- `GET /api/jobs`
- `POST /api/jobs`
- `GET /api/jobs/{id}`
- `PUT /api/jobs/{id}`
- `DELETE /api/jobs/{id}`
- `POST /api/jobs/{id}/generate-profile`
- `GET /api/jobs/{id}/relations`
- `GET /api/jobs/relations/transfer/{source_job_id}/{target_job_id}`

## 学生信息模块

- `GET /api/students/me`
- `PUT /api/students/me`
- `GET|POST|PUT|DELETE /api/students/me/projects`
- `GET|POST|PUT|DELETE /api/students/me/skills`
- `GET|POST|PUT|DELETE /api/students/me/certificates`
- `GET|POST|PUT|DELETE /api/students/me/internships`
- `GET|POST|PUT|DELETE /api/students/me/competitions`
- `GET|POST|PUT|DELETE /api/students/me/campus-experiences`
- `GET /api/students/me/attachments`
- `POST /api/students/me/attachments`
- `DELETE /api/students/me/attachments/{id}`

## AI 简历与画像模块

- `POST /api/students/me/resume/parse/{attachment_id}`
- `POST /api/students/me/resume/ingest/{attachment_id}`
- `POST /api/students/me/resume/optimize/{attachment_id}`
- `GET /api/students/me/resume/preview/{attachment_id}`
- `GET /api/students/me/resume/export/word/{attachment_id}`
- `POST /api/students/me/profile/generate`
- `GET /api/students/me/profile`

## 人岗匹配模块

- `POST /api/students/me/matches/generate`
- `GET /api/students/me/matches`
- `GET /api/students/me/matches/{jobId}`

## 职业规划模块

- `POST /api/students/me/career-goals`
- `GET /api/students/me/career-goals`
- `POST /api/students/me/career-path/generate`
- `GET /api/students/me/career-path`

## 报告模块

- `POST /api/students/me/report/generate`
- `GET /api/students/me/report/latest`
- `GET /api/students/reports/{id}/preview`
- `GET /api/students/reports/{id}/export/pdf`

## 成长跟踪模块

- `GET /api/students/me/growth-records`
- `POST /api/students/me/growth-records`
- `GET /api/students/me/reviews`
- `GET /api/students/me/re-optimization/latest`
- `POST /api/students/me/re-optimization`

## 学生简历投递模块

- `GET /api/students/me/resume-delivery/targets`
- `GET /api/students/me/resume-deliveries`
- `POST /api/students/me/resume-deliveries`

说明：
- 投递目标来自 Milvus / Milvus Lite 岗位知识库
- 返回结果按匹配度从高到低排序
- 即使匹配度为 `0%`，也会保留在列表中展示

## 企业端接口

- `GET /api/enterprise/students`
- `GET /api/enterprise/students/{student_id}/profile`
- `GET /api/enterprise/students/{student_id}/report`
- `GET /api/enterprise/students/{student_id}/matches`
- `GET /api/enterprise/students/{student_id}/matches/{job_id}`
- `GET /api/enterprise/students/{student_id}/career-path`
- `GET /api/enterprise/students/{student_id}/growth-records`
- `GET /api/enterprise/students/{student_id}/optimization/latest`
- `POST /api/enterprise/students/{student_id}/review`
- `GET /api/enterprise/deliveries`
- `GET /api/enterprise/dashboard`
- `GET /api/enterprise/deliveries/{delivery_id}`

说明：
- 系统默认预置 `enterprise01` 企业测试账号
- 学生向知识库中的新企业投递简历时，系统也会自动创建新的企业账号
- 企业端可查看投递列表、学生画像摘要、简历附件、岗位来源与 HRM 仪表盘数据

## 管理端接口

- `GET /api/admin/users`
- `POST /api/admin/users`
- `GET /api/admin/stats/dashboard`
- `GET /api/admin/stats/control-center`
- `GET /api/admin/configs`
- `PUT /api/admin/configs`
- `GET /api/admin/departments`
- `GET /api/admin/classes`

说明：
- 管理端提供 CRM / 中控仪表盘数据接口，可查看全部账号、企业库、数据库状态和系统运行统计

## 默认测试账号

- 管理员：`admin / admin123`
- 学生：`student01 / student123`
- 企业：`enterprise01 / enterprise123`

## 当前前端入口说明

- 访问前端根地址时会先进入统一登录/注册页：`/login`
- 学生端首页为 AI 对话入口，已内嵌附件上传、简历识别和写入档案入口
- 学生端 `/dashboard` 已调整为“学生中控台”，集中展示画像、匹配、成长路径、报告状态与快捷入口
- 学生端“学生档案中心”已整合基础信息、技能清单和学生能力画像快照
- AI 简历优化能力仅保留在 Agent 技能中，对话里可直接生成最新可编辑 Word 版
- 学生端单独保留“简历预览中心”，用于查看原始简历、AI 优化稿摘要并下载文件
- 企业端首页为 HRM 工作台，用于查看招聘总览；“候选人库”页面单独用于筛选候选人、查看详情和简历预览
- 管理端首页为 CRM / 系统中控仪表盘，可查看账号、企业库、MySQL 与 Milvus 状态
