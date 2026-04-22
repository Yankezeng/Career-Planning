import requests
import json
import sys
import time

BASE_URL = "http://localhost:8000/api"
TOKEN = None

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_response(label, response):
    status = response.status_code
    try:
        data = response.json()
    except:
        data = response.text
    print(f"  [{label}] 状态码: {status}")
    if isinstance(data, dict):
        if data.get("code") == 0:
            print(f"  结果: 成功")
            if data.get("data"):
                if isinstance(data["data"], list):
                    print(f"  数据条数: {len(data['data'])}")
                    for i, item in enumerate(data["data"][:3]):
                        print(f"  [{i+1}] {json.dumps(item, ensure_ascii=False, indent=4)}")
                else:
                    print(f"  数据: {json.dumps(data['data'], ensure_ascii=False, indent=4)}")
        else:
            print(f"  结果: {data.get('message', '未知错误')}")
            print(f"  详情: {json.dumps(data, ensure_ascii=False, indent=4)}")
    else:
        print(f"  响应: {data[:500]}")
    return data

def test_login():
    print_section("步骤1: 登录测试账户 (student01)")
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "student01",
        "password": "student123"
    })
    data = resp.json()
    print(f"  状态码: {resp.status_code}")
    if data.get("code") == 0 and data.get("data", {}).get("token"):
        global TOKEN
        TOKEN = data["data"]["token"]
        print(f"  登录成功! Token: {TOKEN[:30]}...")
        return True
    else:
        print(f"  登录失败: {json.dumps(data, ensure_ascii=False)}")
        return False

def get_headers():
    return {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

def test_recommendations():
    print_section("步骤2: 测试智能目标推荐 API")
    print(f"  GET /students/me/career-goals/recommendations")
    resp = requests.get(f"{BASE_URL}/students/me/career-goals/recommendations", headers=get_headers())
    data = print_response("推荐结果", resp)
    
    if resp.status_code == 200 and data.get("code") == 0:
        recs = data.get("data", [])
        if recs:
            print(f"\n  推荐分析:")
            for i, rec in enumerate(recs[:3]):
                print(f"  [{i+1}] 岗位: {rec.get('job_name')}")
                print(f"      综合推荐分: {rec.get('recommendation_score')}")
                print(f"      匹配度: {rec.get('match_score')} | 能力契合: {rec.get('ability_fit_score')} | 兴趣契合: {rec.get('interest_fit_score')}")
                if rec.get('reason'):
                    print(f"      推荐理由: {rec.get('reason')[:80]}...")
                print()
        else:
            print(f"  暂无推荐数据")
    return resp.status_code == 200

def test_save_goal():
    print_section("步骤3: 测试保存职业目标")
    # 先获取推荐，选第一个作为目标
    resp = requests.get(f"{BASE_URL}/students/me/career-goals/recommendations", headers=get_headers())
    data = resp.json()
    target_job_id = None
    if data.get("code") == 0 and data.get("data"):
        target_job_id = data["data"][0].get("job_id")
        print(f"  选择推荐岗位: {data['data'][0].get('job_name')} (ID: {target_job_id})")
    else:
        print(f"  无推荐数据，使用固定岗位ID测试")
        target_job_id = 1

    print(f"  POST /students/me/career-goals")
    goal_data = {
        "target_job_id": target_job_id,
        "target_company_type": "互联网企业",
        "short_term_goal": "学习Vue3和TypeScript，完成2个个人项目",
        "medium_term_goal": "获取前端开发实习机会，参与实际项目开发",
        "mid_long_term_goal": "成为中级前端开发工程师",
        "long_term_goal": "成长为前端技术负责人或架构师",
        "notes": "希望能在上海找到好的发展机会"
    }
    resp = requests.post(f"{BASE_URL}/students/me/career-goals", json=goal_data, headers=get_headers())
    data = print_response("保存目标", resp)
    return resp.status_code == 200

def test_get_goal():
    print_section("步骤3b: 测试获取职业目标")
    print(f"  GET /students/me/career-goals")
    resp = requests.get(f"{BASE_URL}/students/me/career-goals", headers=get_headers())
    data = print_response("获取目标", resp)
    return resp.status_code == 200

def test_generate_path():
    print_section("步骤4: 测试生成职业路径（关联技能差距）")
    # 先获取目标岗位的job_id
    resp = requests.get(f"{BASE_URL}/students/me/career-goals", headers=get_headers())
    data = resp.json()
    target_job_id = data.get("data", {}).get("target_job_id")
    
    if not target_job_id:
        print(f"  未设置目标岗位，跳过路径生成")
        return False
    
    print(f"  目标岗位ID: {target_job_id}")
    print(f"  POST /students/me/career-path/generate")
    resp = requests.post(
        f"{BASE_URL}/students/me/career-path/generate", 
        json={"target_job_id": target_job_id},
        headers=get_headers()
    )
    data = print_response("生成路径", resp)
    
    if resp.status_code == 200 and data.get("code") == 0:
        path_data = data.get("data", {})
        tasks = path_data.get("tasks", [])
        print(f"\n  路径分析:")
        print(f"  目标岗位: {path_data.get('target_job_name')}")
        print(f"  任务总数: {len(tasks)}")
        
        skill_tasks = [t for t in tasks if t.get("related_skills")]
        print(f"  含技能关联的任务: {len(skill_tasks)}")
        
        for i, task in enumerate(tasks[:5]):
            print(f"\n  任务[{i+1}]: {task.get('title')}")
            print(f"    类别: {task.get('category')} | 优先级: {task.get('priority')}")
            if task.get('related_skills'):
                print(f"    关联技能: {', '.join(task['related_skills'])}")
            if task.get('difficulty_level'):
                print(f"    难度: {task.get('difficulty_level')}")
            if task.get('weekly_tasks'):
                print(f"    每周行动: {' | '.join(task['weekly_tasks'][:2])}")
    return resp.status_code == 200

def test_get_path():
    print_section("步骤4b: 测试获取已保存的路径")
    print(f"  GET /students/me/career-path")
    resp = requests.get(f"{BASE_URL}/students/me/career-path", headers=get_headers())
    data = print_response("获取路径", resp)
    return resp.status_code == 200

def test_path_progress():
    print_section("步骤5: 测试路径进度查询")
    print(f"  POST /students/me/career-path/progress")
    resp = requests.post(f"{BASE_URL}/students/me/career-path/progress", headers=get_headers())
    data = print_response("进度查询", resp)
    
    if resp.status_code == 200 and data.get("code") == 0:
        prog = data.get("data", {})
        print(f"\n  进度概况:")
        print(f"  总任务数: {prog.get('total')}")
        print(f"  已完成: {prog.get('completed')}")
        print(f"  完成率: {prog.get('completion_rate')}%")
        print(f"  按类别: {prog.get('tasks_by_category')}")
    return resp.status_code == 200

def test_complete_task():
    print_section("步骤5b: 测试完成任务标记")
    # 先获取路径找到第一个任务ID
    resp = requests.get(f"{BASE_URL}/students/me/career-path", headers=get_headers())
    data = resp.json()
    tasks = data.get("data", {}).get("tasks", [])
    
    if not tasks:
        print(f"  无任务数据，跳过")
        return False
    
    task_id = tasks[0].get("id")
    print(f"  完成任务ID: {task_id} - {tasks[0].get('title')}")
    print(f"  POST /students/me/career-path/tasks/{task_id}/complete")
    resp = requests.post(f"{BASE_URL}/students/me/career-path/tasks/{task_id}/complete", headers=get_headers())
    data = print_response("完成任务", resp)
    
    if resp.status_code == 200 and data.get("code") == 0:
        prog = data.get("data", {})
        print(f"\n  更新后进度:")
        print(f"  总任务数: {prog.get('total')}")
        print(f"  已完成: {prog.get('completed')}")
        print(f"  完成率: {prog.get('completion_rate')}%")
    return resp.status_code == 200

def test_re_evaluate():
    print_section("步骤6: 测试路径重新评估")
    print(f"  POST /students/me/career-path/re-evaluate")
    resp = requests.post(f"{BASE_URL}/students/me/career-path/re-evaluate", headers=get_headers())
    data = print_response("重新评估", resp)
    
    if resp.status_code == 200 and data.get("code") == 0:
        result = data.get("data", {})
        print(f"\n  评估结果:")
        print(f"  {result.get('message')}")
        print(f"  原任务数: {result.get('old_task_count')}")
        print(f"  新任务数: {result.get('new_task_count')}")
    return resp.status_code == 200

def test_matches():
    print_section("辅助测试: 确保岗位匹配数据存在")
    resp = requests.post(f"{BASE_URL}/students/me/matches/generate", headers=get_headers())
    data = resp.json()
    print(f"  生成匹配: 状态码 {resp.status_code}")
    if data.get("code") == 0:
        matches = data.get("data", [])
        print(f"  匹配岗位数: {len(matches)}")
        if matches:
            print(f"  第一个匹配: {matches[0].get('job_name')} - {matches[0].get('total_score')}分")
    return resp.status_code == 200

def test_profile():
    print_section("辅助测试: 确保学生画像存在")
    resp = requests.get(f"{BASE_URL}/students/me/profile", headers=get_headers())
    data = resp.json()
    print(f"  获取画像: 状态码 {resp.status_code}")
    if data.get("code") == 0 and data.get("data"):
        profile = data["data"]
        print(f"  画像成熟度: {profile.get('maturity_level')}")
        print(f"  能力标签: {profile.get('ability_tags')}")
        print(f"  总分: {profile.get('total_score')}")
    else:
        print(f"  无画像数据，尝试生成...")
        resp2 = requests.post(f"{BASE_URL}/students/me/profile/generate", headers=get_headers())
        data2 = resp2.json()
        print(f"  生成画像: 状态码 {resp2.status_code}")
    return True

def main():
    print("\n" + "="*60)
    print("  职业规划新功能测试")
    print("  测试账户: student01")
    print("="*60)
    
    results = {}
    
    if not test_login():
        print("\n❌ 登录失败，终止测试")
        sys.exit(1)
    
    time.sleep(0.5)
    test_profile()
    time.sleep(0.5)
    test_matches()
    time.sleep(0.5)
    
    results["推荐API"] = test_recommendations()
    time.sleep(0.5)
    results["保存目标"] = test_save_goal()
    time.sleep(0.5)
    results["获取目标"] = test_get_goal()
    time.sleep(0.5)
    results["生成路径"] = test_generate_path()
    time.sleep(0.5)
    results["获取路径"] = test_get_path()
    time.sleep(0.5)
    results["进度查询"] = test_path_progress()
    time.sleep(0.5)
    results["完成任务"] = test_complete_task()
    time.sleep(0.5)
    results["重新评估"] = test_re_evaluate()
    
    print_section("测试总结")
    all_pass = True
    for name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
        if not passed:
            all_pass = False
    
    print(f"\n  {'='*40}")
    if all_pass:
        print(f"  全部测试通过 ✅")
    else:
        print(f"  部分测试失败 ❌")
    print(f"  {'='*40}")

if __name__ == "__main__":
    main()
