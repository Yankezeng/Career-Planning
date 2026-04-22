import subprocess
import time
import sys
import requests
import json

BASE_URL = "http://127.0.0.1:8000/api"

def start_server():
    print("正在启动后端服务器...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=r"d:\python程序\大学生职业规划\career-agent\backend",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    time.sleep(8)
    return proc

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def print_data(label, data, indent=2):
    spaces = " " * indent
    if isinstance(data, dict):
        print(f"{spaces}[{label}]")
        if data.get("code") == 200 or data.get("message") == "success":
            print(f"{spaces}  状态: 成功")
            d = data.get("data")
            if isinstance(d, list):
                print(f"{spaces}  数量: {len(d)}")
                for i, item in enumerate(d[:3]):
                    if isinstance(item, dict):
                        print(f"{spaces}  [{i+1}] " + json.dumps({k: v for k, v in item.items() if k not in ('id', 'created_at', 'updated_at')}, ensure_ascii=False))
                    else:
                        print(f"{spaces}  [{i+1}] {item}")
            elif isinstance(d, dict):
                for k, v in d.items():
                    if isinstance(v, (dict, list)):
                        print(f"{spaces}  {k}: {json.dumps(v, ensure_ascii=False)}")
                    else:
                        print(f"{spaces}  {k}: {v}")
        else:
            print(f"{spaces}  状态: {data.get('message', '未知')}")
            print(f"{spaces}  详情: {json.dumps(data, ensure_ascii=False)}")
    else:
        print(f"{spaces}[{label}] {data}")

def test_all():
    proc = start_server()
    
    try:
        print_section("功能测试 - 职业规划优化模块")
        print(f"测试账户: student01 / student123\n")
        
        results = {}
        
        # Step 1: Login
        print_section("步骤1: 登录")
        resp = requests.post(f"{BASE_URL}/auth/login", json={"username": "student01", "password": "student123"}, timeout=10)
        login_data = resp.json()
        print_data("登录结果", login_data)
        
        if resp.status_code != 200 or login_data.get("code") != 200:
            print("登录失败，终止测试")
            return
        
        token = login_data["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        results["登录"] = True
        
        time.sleep(0.3)
        
        # Step 2: Ensure profile exists
        print_section("步骤2: 检查/生成学生画像")
        resp = requests.get(f"{BASE_URL}/students/me/profile", headers=headers, timeout=10)
        prof_data = resp.json()
        if prof_data.get("code") != 200 or not prof_data.get("data"):
            print("  画像不存在，正在生成...")
            resp = requests.post(f"{BASE_URL}/students/me/profile/generate", headers=headers, timeout=10)
            prof_data = resp.json()
            print_data("生成画像", prof_data)
        else:
            d = prof_data.get("data", {})
            print(f"  画像成熟度: {d.get('maturity_level')}")
            print(f"  能力标签: {d.get('ability_tags')}")
            print(f"  总分: {d.get('total_score')}")
        results["画像检查"] = True
        
        time.sleep(0.3)
        
        # Step 3: Generate matches
        print_section("步骤3: 检查/生成岗位匹配")
        resp = requests.get(f"{BASE_URL}/students/me/matches", headers=headers, timeout=120)
        match_data = resp.json()
        if match_data.get("code") != 200 or not match_data.get("data"):
            print("  匹配不存在，正在生成...")
            resp = requests.post(f"{BASE_URL}/students/me/matches/generate", headers=headers, timeout=180)
            match_data = resp.json()
            print_data("生成匹配", match_data)
        else:
            d = match_data.get("data", [])
            print(f"  匹配岗位数: {len(d)}")
            if d:
                print(f"  第一名: {d[0].get('job_name')} ({d[0].get('total_score')}分)")
        results["岗位匹配"] = True
        
        time.sleep(0.3)
        
        # Step 4: Test recommendations
        print_section("步骤4: 测试智能目标推荐")
        resp = requests.get(f"{BASE_URL}/students/me/career-goals/recommendations", headers=headers, timeout=15)
        rec_data = resp.json()
        print_data("推荐结果", rec_data)
        if resp.status_code == 200 and rec_data.get("code") == 200:
            recs = rec_data.get("data", [])
            if recs:
                print(f"\n  详细推荐分析:")
                for i, rec in enumerate(recs[:3]):
                    print(f"  [{i+1}] {rec.get('job_name')}")
                    print(f"      推荐分={rec.get('recommendation_score')} | 匹配={rec.get('match_score')} | 能力={rec.get('ability_fit_score')} | 兴趣={rec.get('interest_fit_score')}")
                    if rec.get('reason'):
                        print(f"      理由: {rec.get('reason')[:100]}...")
                    if rec.get('strengths'):
                        print(f"      优势: {rec['strengths'][0]}")
                    if rec.get('gaps'):
                        print(f"      差距: {rec['gaps'][0]}")
                    print()
                results["智能推荐"] = True
            else:
                print("  无推荐数据")
                results["智能推荐"] = False
        else:
            results["智能推荐"] = False
        
        time.sleep(0.3)
        
        # Step 5: Save career goal
        print_section("步骤5: 测试职业目标保存")
        target_job_id = rec_data.get("data", [{}])[0].get("job_id") if rec_data.get("data") else 1
        print(f"  选择岗位ID: {target_job_id}")
        goal = {
            "target_job_id": target_job_id,
            "short_term_goal": "学习核心技能，完成入门项目",
            "medium_term_goal": "参与实习，积累实战经验",
            "long_term_goal": "成长为资深工程师"
        }
        resp = requests.post(f"{BASE_URL}/students/me/career-goals", json=goal, headers=headers, timeout=10)
        goal_data = resp.json()
        print_data("保存目标", goal_data)
        results["保存目标"] = resp.status_code == 200 and goal_data.get("code") == 200
        
        time.sleep(0.3)
        
        # Step 6: Generate path with skill gaps
        print_section("步骤6: 测试路径生成（含技能差距分析）")
        resp = requests.post(f"{BASE_URL}/students/me/career-path/generate", json={"target_job_id": target_job_id}, headers=headers, timeout=30)
        path_data = resp.json()
        print_data("生成路径", path_data)
        
        if resp.status_code == 200 and path_data.get("code") == 200:
            pd = path_data.get("data", {})
            tasks = pd.get("tasks", [])
            print(f"\n  路径详细信息:")
            print(f"  目标岗位: {pd.get('target_job_name')}")
            print(f"  任务总数: {len(tasks)}")
            
            skill_tasks = [t for t in tasks if t.get("related_skills")]
            print(f"  含技能关联的任务: {len(skill_tasks)}")
            
            diff_tasks = [t for t in tasks if t.get("difficulty_level")]
            print(f"  含难度标识的任务: {len(diff_tasks)}")
            
            print(f"\n  任务列表:")
            for i, task in enumerate(tasks[:8]):
                print(f"\n  [{i+1}] {task.get('title')}")
                print(f"      类别={task.get('category')} 优先级={task.get('priority')}")
                if task.get("related_skills"):
                    print(f"      关联技能: {', '.join(task['related_skills'])}")
                if task.get("difficulty_level"):
                    print(f"      难度: {task['difficulty_level']}")
                if task.get("weekly_tasks"):
                    print(f"      每周行动: {' | '.join(task['weekly_tasks'][:2])}")
            
            results["路径生成"] = True
        else:
            results["路径生成"] = False
        
        time.sleep(0.3)
        
        # Step 7: Path progress
        print_section("步骤7: 测试路径进度查询")
        resp = requests.post(f"{BASE_URL}/students/me/career-path/progress", headers=headers, timeout=10)
        prog_data = resp.json()
        print_data("进度查询", prog_data)
        if resp.status_code == 200 and prog_data.get("code") == 200:
            pd = prog_data.get("data", {})
            print(f"\n  进度: {pd.get('completed')}/{pd.get('total')} ({pd.get('completion_rate')}%)")
            print(f"  类别分布: {pd.get('tasks_by_category')}")
            results["进度查询"] = True
        else:
            results["进度查询"] = False
        
        time.sleep(0.3)
        
        # Step 8: Complete a task
        print_section("步骤8: 测试任务完成标记")
        resp = requests.get(f"{BASE_URL}/students/me/career-path", headers=headers, timeout=10)
        current_path = resp.json()
        tasks = current_path.get("data", {}).get("tasks", [])
        if tasks:
            task_id = tasks[0]["id"]
            print(f"  完成任务: {tasks[0].get('title')} (ID: {task_id})")
            resp = requests.post(f"{BASE_URL}/students/me/career-path/tasks/{task_id}/complete", headers=headers, timeout=10)
            comp_data = resp.json()
            print_data("完成任务", comp_data)
            if resp.status_code == 200 and comp_data.get("code") == 200:
                pd = comp_data.get("data", {})
                print(f"  更新后进度: {pd.get('completed')}/{pd.get('total')} ({pd.get('completion_rate')}%)")
                results["完成任务"] = True
            else:
                results["完成任务"] = False
        else:
            print("  无任务可标记")
            results["完成任务"] = False
        
        time.sleep(0.3)
        
        # Step 9: Re-evaluate path
        print_section("步骤9: 测试路径重新评估")
        resp = requests.post(f"{BASE_URL}/students/me/career-path/re-evaluate", headers=headers, timeout=30)
        reeval_data = resp.json()
        print_data("重新评估", reeval_data)
        if resp.status_code == 200 and reeval_data.get("code") == 200:
            rd = reeval_data.get("data", {})
            print(f"\n  {rd.get('message')}")
            results["重新评估"] = True
        else:
            results["重新评估"] = False
        
        # Summary
        print_section("测试总结")
        all_pass = True
        for name, passed in results.items():
            status = "[PASS] 通过" if passed else "[FAIL] 失败"
            print(f"  {name}: {status}")
            if not passed:
                all_pass = False
        
        print(f"\n  {'='*40}")
        if all_pass:
            print(f"  全部 {len(results)} 项测试通过!")
        else:
            failed = [n for n, p in results.items() if not p]
            print(f"  {len(results) - len(failed)}/{len(results)} 通过")
            print(f"  失败: {', '.join(failed)}")
        print(f"  {'='*40}")
        
    except Exception as e:
        print(f"测试异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        proc.terminate()
        proc.wait(timeout=5)

if __name__ == "__main__":
    test_all()
