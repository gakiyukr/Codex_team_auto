#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Codex App Activation Helper (全自动激活及协议模拟脚本)
=====================================================
本项目将以下两种运行模式整合为一体：
1. 协议模拟模式 (默认/推荐): 模拟 Codex Desktop 启动时完整的 API 遥测/指标上报链路，无感完成激活。
2. 本地拉起模式: 备份当前登录态，将目标 Token 写入 ~/.codex/auth.json，静默拉起本地 Codex.exe 运行 15 秒并强杀，之后恢复原登录态。

使用示例：
  # 模拟激活单个 JSON 凭证文件（使用代理）
  python codex_activation_helper.py --file .\output\codex_auth\f80huzngrijv1fe406r1.json --proxy http://127.0.0.1:7890

  # 模拟激活某个目录下所有的 JSON 凭证
  python codex_activation_helper.py --dir .\output\codex_auth --proxy http://127.0.0.1:7890

  # 使用本地客户端模式拉起激活单个邮箱
  python codex_activation_helper.py --file .\output\codex_auth\f80huzngrijv1fe406r1.json --method local-app
"""

import os
import sys
import json
import time
import uuid
import base64
import argparse
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

sys.stdout.reconfigure(encoding="utf-8")

try:
    import requests
except ImportError:
    print("[!] 缺少 requests 依赖，请运行: pip install requests")
    sys.exit(1)

# ── 协议常量 ──────────────────────────────────────────────────────────
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
TOKEN_ENDPOINT = "https://auth.openai.com/oauth/token"
CHATGPT_BASE = "https://chatgpt.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"

# ── 工具函数 ──────────────────────────────────────────────────────────
def log(msg: str, symbol: str = "*") -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] [{symbol}] {msg}", flush=True)

def jwt_decode(token: str) -> Dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8", errors="ignore"))
    except Exception:
        return {}

def extract_account_id(access_token: str, id_token: str = "") -> str:
    for tok in (access_token, id_token):
        if not tok:
            continue
        jwt = jwt_decode(tok)
        auth_info = jwt.get("https://api.openai.com/auth", {})
        account_id = auth_info.get("chatgpt_account_id") or auth_info.get("account_id")
        if account_id:
            return str(account_id)
        if jwt.get("email"):
            # 有时 email 字段同级会有 account_id
            account_id = jwt.get("account_id")
            if account_id:
                return str(account_id)
    return ""

def is_auth_json_file(path: Path) -> bool:
    if "metadata" in path.name or "system_bak" in path.name:
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    tokens = data.get("tokens", {})
    return isinstance(tokens, dict) and bool(tokens.get("access_token") or tokens.get("refresh_token"))

def refresh_access_token(refresh_tok: str, proxy: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """使用 refresh_token 刷新 access_token"""
    sess = requests.Session()
    sess.trust_env = False
    if proxy:
        sess.proxies.update({"http": proxy, "https": proxy})
        
    try:
        resp = sess.post(
            TOKEN_ENDPOINT,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            data={
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "refresh_token": refresh_tok,
            },
            timeout=30,
            verify=False
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            log(f"刷新 Token 失败: HTTP {resp.status_code} {resp.text[:200]}", "!")
    except Exception as e:
        log(f"刷新 Token 发生网络错误: {e}", "!")
    return None

# ── 模式 1: 纯协议模拟激活 ─────────────────────────────────────────────
def run_protocol_activation(auth_data: Dict[str, Any], proxy: Optional[str] = None) -> bool:
    tokens = auth_data.get("tokens", {})
    access_token = tokens.get("access_token", "")
    id_token = tokens.get("id_token", "")
    refresh_tok = tokens.get("refresh_token", "")
    
    # 自动解析 email 信息
    jwt_p = jwt_decode(access_token)
    profile = jwt_p.get("https://api.openai.com/profile", {})
    email = profile.get("email") or jwt_p.get("email") or "Unknown"
    
    log(f"启动协议激活流程: {email}")
    
    sess = requests.Session()
    sess.trust_env = False
    if proxy:
        sess.proxies.update({"http": proxy, "https": proxy})
        
    # Step 0: 自动刷新 Token
    if refresh_tok:
        log("检查并刷新 Access Token 中...")
        refreshed = refresh_access_token(refresh_tok, proxy)
        if refreshed and refreshed.get("access_token"):
            access_token = refreshed["access_token"]
            tokens["access_token"] = access_token
            if refreshed.get("refresh_token"):
                tokens["refresh_token"] = refreshed["refresh_token"]
                refresh_tok = refreshed["refresh_token"]
            if refreshed.get("id_token"):
                tokens["id_token"] = refreshed["id_token"]
                id_token = refreshed["id_token"]
            log("Access Token 刷新成功 ✓")
            
    account_id = extract_account_id(access_token, id_token)
    if not access_token or not account_id:
        log("缺少 access_token 或无法解析 account_id，激活中止。", "!")
        return False
    tokens["account_id"] = account_id
        
    log(f"解析到 Account ID: {account_id}")
    
    # 构建模拟头部
    headers = {
        "authorization": f"Bearer {access_token}",
        "chatgpt-account-id": account_id,
        "content-type": "application/json",
        "oai-language": "en",
        "originator": "Codex Desktop",
        "user-agent": UA,
        "accept": "*/*",
        "accept-encoding": "identity",
    }
    
    app_session_id = str(uuid.uuid4())
    stable_id = str(uuid.uuid4())
    
    # 模拟客户端请求接口序列
    endpoints = [
        ("POST", "/backend-api/wham/statsig/bootstrap", {
            "json": {
                "app_session_id": app_session_id,
                "app_version": "26.609.41114",
                "build_flavor": "prod",
                "locale": "zh-CN",
                "stable_id": stable_id,
                "system_name": "Windows",
                "system_version": "10.0.22631",
                "window_type": "electron"
            }
        }, "Statsig 引导上报"),
        ("GET", "/backend-api/wham/accounts/check", {}, "工作区检查"),
        ("GET", "/backend-api/wham/tasks/list", {
            "params": {"limit": 20, "task_filter": "current"}
        }, "当前任务列表列表"),
        ("GET", "/backend-api/wham/usage", {}, "使用率查询 (核心积分激活接口)"),
        ("GET", "/backend-api/wham/sites/access", {}, "项目站点访问权限"),
        ("POST", "/backend-api/wham/apps", {
            "json": {
                "id": 1,
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "arguments": {"limit": 20},
                    "name": "sites_list_projects"
                }
            }
        }, "项目列表读取"),
        ("GET", "/backend-api/accounts/check/v4-2023-04-27", {}, "账号风控/状态检查 v4"),
        ("GET", f"/backend-api/accounts/{account_id}/settings", {}, "用户设置拉取"),
        ("GET", f"/backend-api/accounts/{account_id}/codex_invite_promo_status", {}, "受邀活动红利状态"),
        ("GET", "/backend-api/me", {}, "个人信息拉取"),
        ("GET", f"/backend-api/accounts/{account_id}/remaining_balance", {}, "余额查询", False)
    ]
    
    success_count = 0
    required_success_count = 0
    required_total = 0
    for idx, endpoint in enumerate(endpoints, 1):
        method, path, kwargs, label, *flags = endpoint
        required = flags[0] if flags else True
        if required:
            required_total += 1
        url = CHATGPT_BASE + path
        try:
            resp = sess.request(method, url, headers=headers, timeout=20, verify=False, **kwargs)
            status = resp.status_code
            if status == 200:
                success_count += 1
                if required:
                    required_success_count += 1
                optional_note = "" if required else "（可选）"
                log(f"[{idx}/{len(endpoints)}] {label}{optional_note} 成功 -> HTTP {status}")
            else:
                optional_note = "" if required else "（可选，不影响激活判定）"
                symbol = "!" if required else "*"
                log(f"[{idx}/{len(endpoints)}] {label}{optional_note} 异常 -> HTTP {status}，响应内容: {resp.text[:100]}", symbol)
        except Exception as e:
            optional_note = "" if required else "（可选，不影响激活判定）"
            symbol = "!" if required else "*"
            log(f"[{idx}/{len(endpoints)}] {label}{optional_note} 失败 -> 异常: {e}", symbol)
            
    is_fully_success = required_success_count == required_total
    if is_fully_success:
        log(f"账号 {email} 关键协议请求模拟成功完成 ({required_success_count}/{required_total})，积分应该已增加 ✓", "✓")
    else:
        log(f"账号 {email} 部分关键接口模拟失败，共成功 {required_success_count}/{required_total}", "!")
    return is_fully_success

# ── 模式 2: 本地客户端静默拉起激活 ─────────────────────────────────────
def run_local_app_activation(auth_data: Dict[str, Any]) -> bool:
    codex_exe = r"C:\Users\16546\AppData\Local\OpenAI\Codex\bin\codex.exe"
    if not os.path.exists(codex_exe):
        # 尝试备选路径
        codex_exe = Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin" / "codex.exe"
        codex_exe = str(codex_exe)
        if not os.path.exists(codex_exe):
            log(f"未找到本地 Codex 安装路径，无法使用 local-app 模式!", "!")
            return False

    tokens = auth_data.get("tokens", {})
    access_token = tokens.get("access_token", "")
    id_token = tokens.get("id_token", "")
    account_id = extract_account_id(access_token, id_token)
    
    jwt_p = jwt_decode(access_token)
    email = jwt_p.get("email") or "Unknown"
    
    log(f"启动本地客户端静默激活流程: {email}")
    
    codex_dir = Path.home() / ".codex"
    auth_json_path = codex_dir / "auth.json"
    backup_auth_path = codex_dir / "auth.json.system_bak"
    lock_file = codex_dir / "activation.lock"
    
    # 跨进程文件锁定机制防止并发写冲突
    log("获取本地客户端激活文件锁...")
    lock_fh = None
    try:
        import msvcrt
        codex_dir.mkdir(parents=True, exist_ok=True)
        lock_fh = open(lock_file, "w")
        msvcrt.flock(lock_fh.fileno(), msvcrt.LK_LOCK)
    except Exception as e:
        log(f"无法应用 Windows 文件锁 (仅作警告): {e}", "!")

    try:
        # 1. 备份原有的登录凭据
        if auth_json_path.exists():
            log(f"备份当前 auth.json 到 {backup_auth_path}...")
            shutil.copy2(auth_json_path, backup_auth_path)
            
        # 2. 写入子账号的临时登录凭据
        auth_payload = {
            "auth_mode": "chatgpt",
            "OPENAI_API_KEY": None,
            "tokens": {
                "id_token": id_token,
                "access_token": access_token,
                "refresh_token": tokens.get("refresh_token", ""),
                "account_id": account_id
            },
            "last_refresh": auth_data.get("last_refresh") or time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        log(f"写入子账号凭据到 {auth_json_path}...")
        codex_dir.mkdir(parents=True, exist_ok=True)
        auth_json_path.write_text(json.dumps(auth_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        
        # 3. 后台静默启动 Codex.exe
        log(f"后台静默拉起 {codex_exe}...")
        proc = subprocess.Popen([codex_exe], creationflags=0x00000008)  # DETACHED_PROCESS 无窗口
        log(f"已拉起进程 (PID: {proc.pid})。等待 15 秒以完成遥测指标上报...")
        time.sleep(15)
        
        # 4. 强杀进程
        log("结束 Codex.exe 进程...")
        subprocess.run(["taskkill", "/F", "/IM", "codex.exe"], capture_output=True)
        log("Codex.exe 进程已结束。")
        
    except Exception as e:
        log(f"本地拉起模式发生异常: {e}", "!")
        return False
    finally:
        # 5. 还原原有的登录凭据
        if backup_auth_path.exists():
            log("恢复原有的 auth.json 登录态...")
            if auth_json_path.exists():
                auth_json_path.unlink()
            shutil.move(str(backup_auth_path), str(auth_json_path))
            log("登录态恢复成功 ✓")
            
        # 释放锁
        if lock_fh:
            try:
                import msvcrt
                msvcrt.flock(lock_fh.fileno(), msvcrt.LK_UNLCK)
                lock_fh.close()
            except:
                pass
            try:
                if lock_file.exists():
                    lock_file.unlink()
            except:
                pass

    log(f"账号 {email} 本地激活流程完成 ✓", "✓")
    return True

# ── 主流程控制 ────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description="Codex 客户端启动与激活模拟工具")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="指定要激活的单个 Codex 凭证 JSON 文件路径")
    group.add_argument("--dir", help="指定包含多个 Codex 凭证 JSON 文件的目录")
    
    parser.add_argument(
        "--method",
        choices=["protocol", "local-app"],
        default="protocol",
        help="激活模式。protocol: 纯 API 模拟(推荐，支持代理)；local-app: 拉起本地客户端 (默认: protocol)"
    )
    parser.add_argument("--proxy", help="用于协议模拟的代理地址 (例如: http://127.0.0.1:7890)")
    parser.add_argument("--save-back", action="store_true", help="若刷新了 Access Token，是否写回原 JSON 文件")
    
    args = parser.parse_args()
    
    if args.proxy:
        # 禁用 InsecureRequestWarning 警告
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        except:
            pass

    files_to_process = []
    if args.file:
        p = Path(args.file)
        if not p.exists():
            print(f"[!] 指定文件不存在: {args.file}")
            return 1
        files_to_process.append(p)
    elif args.dir:
        d = Path(args.dir)
        if not d.exists() or not d.is_dir():
            print(f"[!] 指定目录不存在或不是目录: {args.dir}")
            return 1
        all_json_files = list(d.glob("*.json"))
        files_to_process.extend([f for f in all_json_files if is_auth_json_file(f)])
        skipped = len(all_json_files) - len(files_to_process)
        if skipped:
            log(f"已跳过 {skipped} 个非账号 JSON 文件")
        
    if not files_to_process:
        print("[!] 没有找到需要激活的 JSON 凭证文件。")
        return 1
        
    print("=" * 60)
    print(f"开始执行激活任务，待处理文件数: {len(files_to_process)} 个，模式: {args.method}")
    print("=" * 60)
    
    success_count = 0
    for idx, fpath in enumerate(files_to_process, 1):
        print(f"\n[{idx}/{len(files_to_process)}] 正在读取: {fpath.name}")
        try:
            content = fpath.read_text(encoding="utf-8")
            auth_data = json.loads(content)
        except Exception as e:
            log(f"读取/解析 JSON 文件失败: {e}", "!")
            continue
            
        if "tokens" not in auth_data:
            log("JSON 格式不正确，缺少 tokens 节点，跳过。", "!")
            continue
            
        old_tokens_blob = json.dumps(auth_data.get("tokens", {}), sort_keys=True, ensure_ascii=False)
        
        ok = False
        if args.method == "protocol":
            ok = run_protocol_activation(auth_data, args.proxy)
        else:
            ok = run_local_app_activation(auth_data)

        if args.save_back and args.method == "protocol":
            new_tokens_blob = json.dumps(auth_data.get("tokens", {}), sort_keys=True, ensure_ascii=False)
            if old_tokens_blob != new_tokens_blob:
                try:
                    fpath.write_text(json.dumps(auth_data, indent=2, ensure_ascii=False), encoding="utf-8")
                    log("已成功将更新后的凭据回写到原 JSON 文件")
                except Exception as e:
                    log(f"回写 JSON 文件失败: {e}", "!")
                    ok = False

        if ok:
            success_count += 1
                        
        time.sleep(1)
        
    print("\n" + "=" * 60)
    print(f"激活任务结束！总成功数: {success_count}/{len(files_to_process)}")
    print("=" * 60)
    return 0 if success_count > 0 else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[!] 用户取消。")
        sys.exit(130)
