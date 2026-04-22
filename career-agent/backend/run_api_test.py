import subprocess
import time
import sys
import os
import requests
import json

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "test_results.txt")

def log(msg):
    print(msg)
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

BASE_URL = "http://127.0.0.1:8000/api"

def start_server():
    log("正在启动后端服务器...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=os.path.dirname(__file__),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    time.sleep(10)
    return proc

def section(title):
    log(f"\n{'='*60}")
    log(f"  {title}")
    log(f"{'='*60}")

def test_all():
    # Clear output file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("")

    proc = start_server()
    
    try:
        section("功能测试 - 职业规划优化模块")
        log("测试账户: student01 / student123\n")
        
        results = {}
        
        # Step 1: Login
        section("步骤1: 登录")
        try:
            resp = requests.post(f"{BASE_URL}/auth/login", json={"username": "student01", "password": "student123"}, timeout=10)
            login_data = resp.json()
            log(f"  状态码: {resp.status_code}")
            log(f"  返回: {json.dumps(login_data, ensure_ascii=False)[:200]}...")
            
            if resp.status_code == 200 and login_data.get("code") == 200:
                token = login_data["data"]["access_token"]
                headers = {"Authorization": f"Bearer {token}"}
                results["登录"] = "PASS"
                log("  登录成功!")
            else:
                log("  登录失败")
                results["登录"] = "FAIL"
                return
        except Exception as e:
            log(f"  登录异常: {e}")
            results["登录"] = "FAIL"
            return
        
        time.sleep(0.5)
        
        # Step 2: Profile
        section("步骤2: 检查学生画像")
        try:
            resp = requests.get(f"{BASE_URL}/students/me/profile", headers=headers, timeout=10)
            prof = resp.json()
            if prof.get("code") == 200 and prof.get("data"):
                d = prof["data"]
                log(f"  成熟度: {d.get('maturity_level')}")
                log(f"  能力标签: {d.get('ability_tags')}")
                results["画像检查"] = "PASS"
            else:
                results["画像检查"] = "FAIL"
        except Exception as e:
            log(f"  异常: {e}")
            results["画像检查"] = "FAIL"
        
        time.sleep(0.5)
        
        # Step 3: Matches
        section("步骤3: 检查岗位匹配")
        try:
            resp = requests.get(f"{BASE_URL}/students/me/matches", headers=headers, timeout=60)
            match = resp.json()
            if match.get("code") == 200 and match.get("data"):
                d = match["data"]
                log(f"  匹配岗位数: {len(d)}")
                if d:
                    log(f"  第一名: {d[0].get('job_name')} ({d[0].get('total_score')}分)")
                results["岗位匹配"] = "PASS"
            else:
                results["岗位匹配"] = "FAIL"
        except Exception as e:
            log(f"  异常: {e}")
            results["岗位匹配"] = "FAIL"
        
        time.sleep(0.5)
        
        # Step 4: Recommendations
        section("步骤4: 智能目标推荐")
        try:
            resp = requests.get(f"{BASE_URL}/students/me/career-goals/recommendations", headers=headers, timeout=30)
            rec = resp.json()
            if resp.status_code == 200 and rec.get("code") == 200:
                recs = rec.get("data", [])
                log(f"  推荐岗位数: {len(recs)}")
                for i, r in enumerate(recs[:3]):
                    log(f"  [{i+1}] {r.get('job_name')} - 推荐分:{r.get('recommendation_score')} | 匹配:{r.get('match_score')} | 能力:{r.get('ability_fit_score')} | 兴趣:{r.get('interest_fit_score')}")
                    if r.get('strengths'):
                        log(f"      优势: {r['strengths'][0]}")
                    if r.get('gaps'):
                        log(f"      差距: {r['gaps'][0]}")
                    if r.get('reason'):
                        log(f"      理由: {r['reason'][:80]}...")
                results["智能推荐"] = "PASS" if recs else "FAIL"
            else:
                log(f"  推荐失败: {json.dumps(rec, ensure_ascii=False)[:200]}")
                results["智能推荐"] = "FAIL"
        except Exception as e:
            log(f"  异常: {e}")
            results["智能推荐"] = "FAIL"
        
        time.sleep(0.5)
        
        # Step 5: Save goal
        section("步骤5: 保存职业目标")
        try:
            target_job_id = rec.get("data", [{}])[0].get("job_id", 1) if rec.get("data") else 1
            goal = {
                "target_job_id": target_job_id,
                "short_term_goal": "学习核心技能",
                "medium_term_goal": "参与实习",
                "long_term_goal": "成长为资深工程师"
            }
            resp = requests.post(f"{BASE_URL}/students/me/career-goals", json=goal, headers=headers, timeout=10)
            gd = resp.json()
            if resp.status_code == 200 and gd.get("code") == 200:
                log(f"  目标已保存: 岗位ID={target_job_id}")
                results["保存目标"] = "PASS"
            else:
                log(f"  保存失败: {json.dumps(gd, ensure_ascii=False)[:200]}")
                results["保存目标"] = "FAIL"
        except Exception as e:
            log(f"  异常: {e}")
            results["保存目标"] = "FAIL"
        
        time.sleep(0.5)
        
        # Step 6: Generate path
        section("步骤6: 生成职业路径（技能差距分析）")
        try:
            resp = requests.post(f"{BASE_URL}/students/me/career-path/generate", json={"target_job_id": target_job_id}, headers=headers, timeout=60)
            pd = resp.json()
            if resp.status_code == 200 and pd.get("code") == 200:
                d = pd.get("data", {})
                tasks = d.get("tasks", [])
                log(f"  目标岗位: {d.get('target_job_name')}")
                log(f"  任务总数: {len(tasks)}")
                
                skill_tasks = [t for t in tasks if t.get("related_skills")]
                log(f"  含技能关联的任务: {len(skill_tasks)}")
                
                diff_tasks = [t for t in tasks if t.get("difficulty_level")]
                log(f"  含难度标识的任务: {len(diff_tasks)}")
                
                log(f"\n  任务详情:")
                for i, t in enumerate(tasks[:6]):
                    log(f"  [{i+1}] {t.get('title')}")
                    log(f"      类别={t.get('category')} 优先级={t.get('priority')}")
                    if t.get("related_skills"):
                        log(f"      关联技能: {', '.join(t['related_skills'][:3])}")
                    if t.get("difficulty_level"):
                        log(f"      难度: {t['difficulty_level']}")
                    if t.get("weekly_tasks"):
                        log(f"      每周行动: {' | '.join(t['weekly_tasks'][:2])}")
                
                results["路径生成"] = "PASS"
            else:
                log(f"  生成失败: {json.dumps(pd, ensure_ascii=False)[:300]}")
                results["路径生成"] = "FAIL"
        except Exception as e:
            log(f"  异常: {e}")
            results["路径生成"] = "FAIL"
        
        time.sleep(0.5)
        
        # Step 7: Progress
        section("步骤7: 路径进度查询")
        try:
            resp = requests.post(f"{BASE_URL}/students/me/career-path/progress", headers=headers, timeout=10)
            pg = resp.json()
            if resp.status_code == 200 and pg.get("code") == 200:
                d = pg.get("data", {})
                log(f"  进度: {d.get('completed')}/{d.get('total')} ({d.get('completion_rate')}%)")
                log(f"  类别分布: {d.get('tasks_by_category')}")
                results["进度查询"] = "PASS"
            else:
                results["进度查询"] = "FAIL"
        except Exception as e:
            log(f"  异常: {e}")
            results["进度查询"] = "FAIL"
        
        time.sleep(0.5)
        
        # Step 8: Complete task
        section("步骤8: 标记任务完成")
        try:
            resp = requests.get(f"{BASE_URL}/students/me/career-path", headers=headers, timeout=10)
            cp = resp.json()
            if cp.get("data") and cp["data"].get("tasks"):
                task_id = cp["data"]["tasks"][0]["id"]
                task_title = cp["data"]["tasks"][0].get("title")
                log(f"  完成任务: {task_title} (ID: {task_id})")
                resp = requests.post(f"{BASE_URL}/students/me/career-path/tasks/{task_id}/complete", headers=headers, timeout=10)
                cd = resp.json()
                if resp.status_code == 200 and cd.get("code") == 200:
                    d = cd.get("data", {})
                    log(f"  更新后: {d.get('completed')}/{d.get('total')} ({d.get('completion_rate')}%)")
                    results["完成任务"] = "PASS"
                else:
                    results["完成任务"] = "FAIL"
            else:
                log("  无任务")
                results["完成任务"] = "FAIL"
        except Exception as e:
            log(f"  异常: {e}")
            results["完成任务"] = "FAIL"
        
        time.sleep(0.5)
        
        # Step 9: Re-evaluate
        section("步骤9: 路径重新评估")
        try:
            resp = requests.post(f"{BASE_URL}/students/me/career-path/re-evaluate", headers=headers, timeout=60)
            re = resp.json()
            if resp.status_code == 200 and re.get("code") == 200:
                d = re.get("data", {})
                log(f"  {d.get('message')}")
                results["重新评估"] = "PASS"
            else:
                log(f"  重新评估失败: {json.dumps(re, ensure_ascii=False)[:200]}")
                results["重新评估"] = "FAIL"
        except Exception as e:
            log(f"  异常: {e}")
            results["重新评估"] = "FAIL"
        
        # Summary
        section("测试总结")
        all_pass = True
        for name, status in results.items():
            icon = "PASS" if status == "PASS" else "FAIL"
            log(f"  {name}: [{icon}]")
            if status != "PASS":
                all_pass = False
        
        total = len(results)
        passed = sum(1 for s in results.values() if s == "PASS")
        log(f"\n  {'='*40}")
        if all_pass:
            log(f"  全部 {total} 项测试通过!")
        else:
            log(f"  {passed}/{total} 通过")
            log(f"  失败: {', '.join(n for n, s in results.items() if s != 'PASS')}")
        log(f"  {'='*40}")
        
    except Exception as e:
        log(f"\n测试异常: {e}")
        import traceback
        log(traceback.format_exc())
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except:
            proc.kill()

if __name__ == "__main__":
    test_all()
